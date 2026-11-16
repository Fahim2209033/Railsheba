-- =====================================================================
--  RAIL SEBA - database schema (basic SQL only: tables, keys, defaults)
--  1) Create an empty database called railseba   2) run this file
--  3) run sample_data.sql
--  All the rules (search, fares, seat clash check, refunds) are written
--  in the Python code, so this file is only the table design.
-- =====================================================================

DROP TABLE IF EXISTS refunds, payments, tickets, bookings, trips, seats, coaches,
    fare_rates, fare_settings, cancellation_rules, seat_classes,
    train_stops, trains, stations, users CASCADE;

-- 1. People who use the website -----------------------------------------
CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    full_name     VARCHAR(100) NOT NULL,
    email         VARCHAR(120) UNIQUE,
    mobile        VARCHAR(15)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nid           VARCHAR(17)  UNIQUE,
    role          VARCHAR(10)  NOT NULL DEFAULT 'PASSENGER',   -- PASSENGER or ADMIN
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Stations ----------------------------------------------------------------
CREATE TABLE stations (
    station_id   SERIAL PRIMARY KEY,
    station_code VARCHAR(10) NOT NULL UNIQUE,
    station_name VARCHAR(80) NOT NULL,
    district     VARCHAR(50)
);

-- 3. Trains (every direction is its own train: 725 Khulna-Dhaka, 726 Dhaka-Khulna)
CREATE TABLE trains (
    train_id     SERIAL PRIMARY KEY,
    train_number VARCHAR(10) NOT NULL UNIQUE,
    train_name   VARCHAR(80) NOT NULL,
    train_type   VARCHAR(15) NOT NULL,       -- INTERCITY, MAIL_EXPRESS, COMMUTER, LOCAL
    off_day      INT,                        -- 0 = Sunday ... 6 = Saturday, empty = runs daily
    is_active    BOOLEAN NOT NULL DEFAULT TRUE
);

-- 4. The route of a train, stop by stop ---------------------------------------
CREATE TABLE train_stops (
    train_id       INT NOT NULL REFERENCES trains(train_id),
    stop_order     INT NOT NULL,             -- 1 = first station, 2 = next, ...
    station_id     INT NOT NULL REFERENCES stations(station_id),
    arrival_time   TIME,                     -- empty at the first stop
    departure_time TIME,                     -- empty at the last stop
    day_offset     INT NOT NULL DEFAULT 0,   -- 1 = this stop is after midnight
    distance_km    NUMERIC(6,1) NOT NULL,    -- km from the first station
    PRIMARY KEY (train_id, stop_order)
);

-- 5. Seat classes and prices ----------------------------------------------------
CREATE TABLE seat_classes (
    class_id   SERIAL PRIMARY KEY,
    class_code VARCHAR(12) NOT NULL UNIQUE,   -- S_CHAIR, SNIGDHA, AC_S ...
    class_name VARCHAR(40) NOT NULL,
    has_vat    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE fare_rates (
    rate_id     SERIAL PRIMARY KEY,
    train_type  VARCHAR(15) NOT NULL,
    class_id    INT NOT NULL REFERENCES seat_classes(class_id),
    rate_per_km NUMERIC(6,2) NOT NULL,        -- taka per km
    min_fare    NUMERIC(8,2) NOT NULL DEFAULT 0,
    UNIQUE (train_type, class_id)
);

CREATE TABLE fare_settings (                  -- only one row
    setting_id         INT PRIMARY KEY DEFAULT 1,
    vat_percent        NUMERIC(4,2) NOT NULL,
    service_charge     NUMERIC(6,2) NOT NULL, -- per ticket
    child_discount_pct NUMERIC(4,2) NOT NULL,
    hold_minutes       INT NOT NULL           -- how long seats are held while paying
);

-- 6. Coaches and seats ---------------------------------------------------------------
CREATE TABLE coaches (
    coach_id   SERIAL PRIMARY KEY,
    train_id   INT NOT NULL REFERENCES trains(train_id),
    coach_code VARCHAR(5) NOT NULL,           -- KA, KHA, GA ...
    class_id   INT NOT NULL REFERENCES seat_classes(class_id),
    UNIQUE (train_id, coach_code)
);

CREATE TABLE seats (
    seat_id     SERIAL PRIMARY KEY,
    coach_id    INT NOT NULL REFERENCES coaches(coach_id),
    seat_number INT NOT NULL,
    UNIQUE (coach_id, seat_number)
);

-- 7. A trip = one train on one date ------------------------------------------------
CREATE TABLE trips (
    trip_id      SERIAL PRIMARY KEY,
    train_id     INT NOT NULL REFERENCES trains(train_id),
    journey_date DATE NOT NULL,
    status       VARCHAR(10) NOT NULL DEFAULT 'SCHEDULED',   -- SCHEDULED, CANCELLED, COMPLETED
    UNIQUE (train_id, journey_date)
);

-- 8. A booking = one checkout (1 to 4 tickets, one payment) --------------------
CREATE TABLE bookings (
    booking_id      SERIAL PRIMARY KEY,
    pnr             VARCHAR(12) NOT NULL UNIQUE,
    user_id         INT NOT NULL REFERENCES users(user_id),
    trip_id         INT NOT NULL REFERENCES trips(trip_id),
    from_station_id INT NOT NULL REFERENCES stations(station_id),
    to_station_id   INT NOT NULL REFERENCES stations(station_id),
    status          VARCHAR(10) NOT NULL DEFAULT 'PENDING',  -- PENDING, CONFIRMED, CANCELLED, EXPIRED
    subtotal        NUMERIC(10,2) NOT NULL,
    vat_amount      NUMERIC(10,2) NOT NULL DEFAULT 0,
    service_charge  NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_amount    NUMERIC(10,2) NOT NULL,
    expires_at      TIMESTAMP NOT NULL,                      -- seats are held until this time
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at    TIMESTAMP
);

-- 9. A ticket = one seat for one passenger on one part of the route ---------------
CREATE TABLE tickets (
    ticket_id       SERIAL PRIMARY KEY,
    ticket_no       VARCHAR(16) NOT NULL UNIQUE,
    booking_id      INT NOT NULL REFERENCES bookings(booking_id),
    trip_id         INT NOT NULL REFERENCES trips(trip_id),
    seat_id         INT NOT NULL REFERENCES seats(seat_id),
    from_stop_order INT NOT NULL,
    to_stop_order   INT NOT NULL,
    passenger_name  VARCHAR(100) NOT NULL,
    passenger_type  VARCHAR(10) NOT NULL DEFAULT 'ADULT',    -- ADULT or CHILD
    fare_amount     NUMERIC(10,2) NOT NULL,
    status          VARCHAR(10) NOT NULL DEFAULT 'HELD'      -- HELD, ISSUED, CANCELLED, EXPIRED
);

-- 10. Payments -------------------------------------------------------------------------
CREATE TABLE payments (
    payment_id     SERIAL PRIMARY KEY,
    booking_id     INT NOT NULL REFERENCES bookings(booking_id),
    method         VARCHAR(10) NOT NULL,                     -- BKASH, NAGAD, ROCKET, UPAY, CARD, NEXUSPAY
    gateway_txn_id VARCHAR(60) UNIQUE,
    amount         NUMERIC(10,2) NOT NULL,
    status         VARCHAR(10) NOT NULL DEFAULT 'INITIATED', -- INITIATED, SUCCESS, FAILED, REFUNDED
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    paid_at        TIMESTAMP
);

-- 11. Cancellation rules and refunds ---------------------------------------------------
CREATE TABLE cancellation_rules (
    rule_id           SERIAL PRIMARY KEY,
    min_hours_before  INT NOT NULL,           -- applies from this many hours before departure ...
    max_hours_before  INT,                    -- ... up to this many (empty = no limit)
    deduction_percent NUMERIC(5,2) NOT NULL
);

CREATE TABLE refunds (
    refund_id        SERIAL PRIMARY KEY,
    ticket_id        INT NOT NULL UNIQUE REFERENCES tickets(ticket_id),
    payment_id       INT NOT NULL REFERENCES payments(payment_id),
    deduction_amount NUMERIC(10,2) NOT NULL,
    refund_amount    NUMERIC(10,2) NOT NULL,
    status           VARCHAR(10) NOT NULL DEFAULT 'REQUESTED',  -- REQUESTED, APPROVED, PROCESSED, REJECTED
    requested_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at     TIMESTAMP
);

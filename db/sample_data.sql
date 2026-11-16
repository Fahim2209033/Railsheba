
-- =====================================================================
-- RAIL SEBA - sample_data.sql
-- PostgreSQL
-- Run AFTER schema.sql on an EMPTY database.
--
-- Sample password: password123
-- Admin:     01700000000
-- Passenger: 01700000001
--
-- 12 trains, 26 stations, 5 seat classes.
-- 4 coaches per train, 40 seats per coach.
-- Schedules and distances are illustrative development data.
-- =====================================================================


-- 1. SEAT CLASSES

INSERT INTO seat_classes (class_code, class_name, has_vat) VALUES
 ('SHOVAN',    'Shovan',       FALSE),
 ('SHOVAN_CH', 'Shovan Chair', FALSE),
 ('SNIGDHA',   'Snigdha',      TRUE),
 ('S_CHAIR',   'S. Chair',     FALSE),
 ('AC_B',      'AC Berth',     TRUE);


-- 2. FARE SETTINGS

INSERT INTO fare_settings
(vat_percent, service_charge, child_discount_pct, hold_minutes)
VALUES (15, 20, 50, 10);


-- 3. FARE RATES

INSERT INTO fare_rates
(train_type, class_id, rate_per_km, min_fare)
SELECT
    'INTERCITY',
    sc.class_id,
    r.rate_per_km,
    r.min_fare
FROM (
    VALUES
        ('SHOVAN_CH', 1.20, 30.00),
        ('SNIGDHA',   3.75, 50.00),
        ('S_CHAIR',   2.25, 50.00),
        ('AC_B',      4.50, 50.00)
) AS r(class_code, rate_per_km, min_fare)
JOIN seat_classes sc
    ON sc.class_code = r.class_code;


-- 4. CANCELLATION RULES

INSERT INTO cancellation_rules
(min_hours_before, max_hours_before, deduction_percent)
VALUES
 (48, NULL, 10),
 (12, 48,   25),
 (6,  12,   50),
 (0,  6,    100);


-- 5. STATIONS

INSERT INTO stations (station_code, station_name, district) VALUES
 ('DHK', 'Dhaka ', 'Dhaka'),
 ('BBA', 'Biman Bandar', 'Dhaka'),
 ('BBZ', 'Bhairab Bazar', 'Kishoreganj'),
 ('BBR', 'Brahmanbaria', 'Brahmanbaria'),
 ('AKH', 'Akhaura', 'Brahmanbaria'),
 ('CML', 'Cumilla', 'Cumilla'),
 ('FNI', 'Feni', 'Feni'),
 ('CTG', 'Chattogram', 'Chattogram'),
 ('SRM', 'Srimangal', 'Moulvibazar'),
 ('SYL', 'Sylhet', 'Sylhet'),
 ('TNG', 'Tangail', 'Tangail'),
 ('ISD', 'Ishwardi', 'Pabna'),
 ('STH', 'Santahar', 'Bogra'),
 ('PBT', 'Parbatipur', 'Dinajpur'),
 ('DNJ', 'Dinajpur', 'Dinajpur'),
 ('SRJ', 'Sirajganj', 'Sirajganj'),
 ('RAJ', 'Rajshahi', 'Rajshahi'),
 ('BOG', 'Bogura', 'Bogura'),
 ('BHG', 'Bhanga', 'Faridpur'),
 ('JSR', 'Jashore', 'Jashore'),
 ('NPA', 'Noapara', 'Khulna'),
 ('KHL', 'Khulna', 'Khulna'),
 ('SNG', 'Singia Junction', 'Jashore'),
 ('NRL', 'Narail', 'Narail'),
 ('LHG', 'Lohagora', 'Narail'),
 ('KSH', 'Kashiani Junction', 'Gopalganj');


-- 6. TRAINS

INSERT INTO trains (train_number, train_name, train_type) VALUES
 ('701', 'Subarna Express',       'INTERCITY'),
 ('702', 'Subarna Express',       'INTERCITY'),
 ('703', 'Mahanagar Godhuli',     'INTERCITY'),
 ('704', 'Mahanagar Provati',     'INTERCITY'),
 ('705', 'Ekota Express',         'INTERCITY'),
 ('706', 'Ekota Express',         'INTERCITY'),
 ('709', 'Parabat Express',       'INTERCITY'),
 ('710', 'Parabat Express',       'INTERCITY'),
 ('725', 'Sundarban Express',     'INTERCITY'),
 ('726', 'Sundarban Express',     'INTERCITY'),
 ('825', 'Jahanabad Express',     'INTERCITY'),
 ('826', 'Jahanabad Express',     'INTERCITY');


-- 7. TRAIN ROUTES

INSERT INTO train_stops
(train_id, stop_order, station_id, arrival_time,
 departure_time, day_offset, distance_km)

SELECT
    t.train_id,
    r.stop_order,
    s.station_id,
    r.arrival_time,
    r.departure_time,
    r.day_offset,
    r.distance_km
FROM (
    VALUES

    -- 701: Chattogram -> Dhaka

    ('701',1,'CTG',NULL::TIME,'07:00'::TIME,0,0.0),
    ('701',2,'FNI','08:20'::TIME,'08:22'::TIME,0,102.0),
    ('701',3,'CML','09:15'::TIME,'09:17'::TIME,0,162.0),
    ('701',4,'AKH','09:50'::TIME,'09:52'::TIME,0,195.0),
    ('701',5,'BBZ','10:25'::TIME,'10:27'::TIME,0,227.0),
    ('701',6,'BBA','11:45'::TIME,'11:47'::TIME,0,300.0),
    ('701',7,'DHK','12:30'::TIME,NULL::TIME,0,320.0),


    -- 702: Dhaka -> Chattogram

    ('702',1,'DHK',NULL::TIME,'15:00'::TIME,0,0.0),
    ('702',2,'BBA','15:25'::TIME,'15:27'::TIME,0,20.0),
    ('702',3,'BBZ','16:45'::TIME,'16:47'::TIME,0,93.0),
    ('702',4,'AKH','17:20'::TIME,'17:22'::TIME,0,125.0),
    ('702',5,'CML','17:55'::TIME,'17:57'::TIME,0,158.0),
    ('702',6,'FNI','18:55'::TIME,'18:57'::TIME,0,218.0),
    ('702',7,'CTG','20:30'::TIME,NULL::TIME,0,320.0),


    -- 703: Mahanagar Godhuli
    -- Chattogram -> Dhaka

    ('703',1,'CTG',NULL::TIME,'15:00'::TIME,0,0.0),
    ('703',2,'FNI','16:20'::TIME,'16:22'::TIME,0,102.0),
    ('703',3,'CML','17:15'::TIME,'17:17'::TIME,0,162.0),
    ('703',4,'AKH','17:50'::TIME,'17:52'::TIME,0,195.0),
    ('703',5,'BBZ','18:25'::TIME,'18:27'::TIME,0,227.0),
    ('703',6,'BBA','19:50'::TIME,'19:52'::TIME,0,300.0),
    ('703',7,'DHK','20:45'::TIME,NULL::TIME,0,320.0),


    -- 704: Mahanagar Provati
    -- Dhaka -> Chattogram

    ('704',1,'DHK',NULL::TIME,'07:45'::TIME,0,0.0),
    ('704',2,'BBA','08:10'::TIME,'08:12'::TIME,0,20.0),
    ('704',3,'BBZ','09:30'::TIME,'09:32'::TIME,0,93.0),
    ('704',4,'AKH','10:05'::TIME,'10:07'::TIME,0,125.0),
    ('704',5,'CML','10:40'::TIME,'10:42'::TIME,0,158.0),
    ('704',6,'FNI','11:40'::TIME,'11:42'::TIME,0,218.0),
    ('704',7,'CTG','14:00'::TIME,NULL::TIME,0,320.0),


    -- 705: Ekota Express
    -- Dhaka -> Dinajpur

    ('705',1,'DHK',NULL::TIME,'10:00'::TIME,0,0.0),
    ('705',2,'TNG','11:35'::TIME,'11:37'::TIME,0,95.0),
    ('705',3,'ISD','13:30'::TIME,'13:32'::TIME,0,190.0),
    ('705',4,'STH','15:30'::TIME,'15:35'::TIME,0,250.0),
    ('705',5,'PBT','17:30'::TIME,'17:35'::TIME,0,330.0),
    ('705',6,'DNJ','19:45'::TIME,NULL::TIME,0,370.0),


    -- 706: Ekota Express
    -- Dinajpur -> Dhaka

    ('706',1,'DNJ',NULL::TIME,'21:20'::TIME,0,0.0),
    ('706',2,'PBT','23:20'::TIME,'23:25'::TIME,0,40.0),
    ('706',3,'STH','01:20'::TIME,'01:25'::TIME,1,120.0),
    ('706',4,'ISD','03:20'::TIME,'03:22'::TIME,1,180.0),
    ('706',5,'TNG','05:30'::TIME,'05:32'::TIME,1,275.0),
    ('706',6,'DHK','07:10'::TIME,NULL::TIME,1,370.0),


    -- 709: Parabat Express
    -- Dhaka -> Sylhet

    ('709',1,'DHK',NULL::TIME,'06:35'::TIME,0,0.0),
    ('709',2,'BBA','07:00'::TIME,'07:02'::TIME,0,20.0),
    ('709',3,'BBZ','08:20'::TIME,'08:22'::TIME,0,93.0),
    ('709',4,'AKH','09:00'::TIME,'09:02'::TIME,0,130.0),
    ('709',5,'SRM','11:00'::TIME,'11:02'::TIME,0,210.0),
    ('709',6,'SYL','13:40'::TIME,NULL::TIME,0,300.0),


    -- 710: Parabat Express
    -- Sylhet -> Dhaka

    ('710',1,'SYL',NULL::TIME,'15:00'::TIME,0,0.0),
    ('710',2,'SRM','16:30'::TIME,'16:32'::TIME,0,90.0),
    ('710',3,'AKH','18:30'::TIME,'18:32'::TIME,0,170.0),
    ('710',4,'BBZ','19:00'::TIME,'19:02'::TIME,0,207.0),
    ('710',5,'BBA','21:45'::TIME,'21:47'::TIME,0,280.0),
    ('710',6,'DHK','22:25'::TIME,NULL::TIME,0,300.0),


    -- 725: Sundarban Express
    -- Khulna -> Dhaka

    ('725',1,'KHL',NULL::TIME,'20:30'::TIME,0,0.0),
    ('725',2,'NPA','21:00'::TIME,'21:02'::TIME,0,25.0),
    ('725',3,'JSR','22:00'::TIME,'22:05'::TIME,0,90.0),
    ('725',4,'BHG','00:30'::TIME,'00:32'::TIME,1,200.0),
    ('725',5,'DHK','05:40'::TIME,NULL::TIME,1,400.0),


    -- 726: Sundarban Express
    -- Dhaka -> Khulna

    ('726',1,'DHK',NULL::TIME,'06:20'::TIME,0,0.0),
    ('726',2,'BHG','08:30'::TIME,'08:32'::TIME,0,100.0),
    ('726',3,'JSR','12:30'::TIME,'12:35'::TIME,0,300.0),
    ('726',4,'NPA','14:00'::TIME,'14:02'::TIME,0,365.0),
    ('726',5,'KHL','15:40'::TIME,NULL::TIME,0,400.0),


    -- 825: Jahanabad Express
    -- Khulna -> Dhaka

    ('825',1,'KHL',NULL::TIME,'06:00'::TIME,0,0.0),
    ('825',2,'NPA','06:33'::TIME,'06:36'::TIME,0,25.0),
    ('825',3,'SNG','06:51'::TIME,'06:53'::TIME,0,45.0),
    ('825',4,'NRL','07:13'::TIME,'07:16'::TIME,0,65.0),
    ('825',5,'LHG','07:29'::TIME,'07:31'::TIME,0,80.0),
    ('825',6,'KSH','07:41'::TIME,'07:44'::TIME,0,100.0),
    ('825',7,'BHG','08:13'::TIME,'08:16'::TIME,0,140.0),
    ('825',8,'DHK','09:45'::TIME,NULL::TIME,0,210.0),


    -- 826: Jahanabad Express
    -- Dhaka -> Khulna

    ('826',1,'DHK',NULL::TIME,'20:00'::TIME,0,0.0),
    ('826',2,'BHG','21:03'::TIME,'21:06'::TIME,0,70.0),
    ('826',3,'KSH','21:34'::TIME,'21:37'::TIME,0,110.0),
    ('826',4,'LHG','21:48'::TIME,'21:50'::TIME,0,130.0),
    ('826',5,'NRL','22:03'::TIME,'22:06'::TIME,0,145.0),
    ('826',6,'SNG','22:34'::TIME,'22:40'::TIME,0,165.0),
    ('826',7,'NPA','22:54'::TIME,'22:56'::TIME,0,185.0),
    ('826',8,'KHL','23:45'::TIME,NULL::TIME,0,210.0)

) AS r(train_number, stop_order, station_code,
       arrival_time, departure_time, day_offset, distance_km)

JOIN trains t
    ON t.train_number = r.train_number

JOIN stations s
    ON s.station_code = r.station_code

ORDER BY t.train_id, r.stop_order;


-- 8. COACHES

INSERT INTO coaches (train_id, coach_code, class_id)
SELECT
    t.train_id,
    c.coach_code,
    sc.class_id
FROM trains t
CROSS JOIN (
    VALUES
       ('KA',  'S_CHAIR'),
       ('KHA', 'S_CHAIR'),
       ('GA',  'SNIGDHA'),
       ('GHA', 'AC_B')
) AS c(coach_code, class_code)
JOIN seat_classes sc
    ON sc.class_code = c.class_code
ORDER BY t.train_id, c.coach_code;


-- 9. SEATS
-- Every coach has 40 seats.
-- Total: 12 trains x 4 coaches x 40 seats = 1,920 seats.

INSERT INTO seats (coach_id, seat_number)
SELECT
    c.coach_id,
    n.seat_number
FROM coaches c
CROSS JOIN generate_series(1, 40) AS n(seat_number)
ORDER BY c.coach_id, n.seat_number;


-- 10. TRIPS

INSERT INTO trips (train_id, journey_date)
SELECT
    t.train_id,
    CURRENT_DATE + d.day_number
FROM trains t
CROSS JOIN generate_series(0, 9) AS d(day_number)
ORDER BY d.day_number, t.train_id;


-- 11. USERS

INSERT INTO users
(full_name, email, mobile, password_hash, nid, role)
VALUES
(
 'Admin',
 'admin@railseba.test',
 '01700000000',
 'scrypt:32768:8:1$jss7x9qOKN9V95T9$1573347e628bcb50b975ded86946824588b57de406f1fcce90f71183c8c571619d667f23ec3908bbeb1f97e3297769bb704427fc258ccf89b6386ed0644fdf61',
 NULL,
 'ADMIN'
),
(
 'Mahmudul Hassan',
 'mahmudul@example.com',
 '01700000001',
 'scrypt:32768:8:1$jss7x9qOKN9V95T9$1573347e628bcb50b975ded86946824588b57de406f1fcce90f71183c8c571619d667f23ec3908bbeb1f97e3297769bb704427fc258ccf89b6386ed0644fdf61',
 NULL,
 'PASSENGER'
),
(
 'Sayanta Das',
 'sayanta@example.com',
 '01700000002',
 'scrypt:32768:8:1$jss7x9qOKN9V95T9$1573347e628bcb50b975ded86946824588b57de406f1fcce90f71183c8c571619d667f23ec3908bbeb1f97e3297769bb704427fc258ccf89b6386ed0644fdf61',
 NULL,
 'PASSENGER'
),
(
 'HM Fahim',
 'fahim@example.com',
 '01700000003',
 'scrypt:32768:8:1$jss7x9qOKN9V95T9$1573347e628bcb50b975ded86946824588b57de406f1fcce90f71183c8c571619d667f23ec3908bbeb1f97e3297769bb704427fc258ccf89b6386ed0644fdf61',
 NULL,
 'PASSENGER'
);


-- 12. ROW COUNT VERIFICATION

SELECT 'seat_classes' AS table_name, COUNT(*) AS total
FROM seat_classes

UNION ALL
SELECT 'fare_settings', COUNT(*) FROM fare_settings

UNION ALL
SELECT 'fare_rates', COUNT(*) FROM fare_rates

UNION ALL
SELECT 'cancellation_rules', COUNT(*) FROM cancellation_rules

UNION ALL
SELECT 'stations', COUNT(*) FROM stations

UNION ALL
SELECT 'trains', COUNT(*) FROM trains

UNION ALL
SELECT 'train_stops', COUNT(*) FROM train_stops

UNION ALL
SELECT 'coaches', COUNT(*) FROM coaches

UNION ALL
SELECT 'seats', COUNT(*) FROM seats

UNION ALL
SELECT 'trips', COUNT(*) FROM trips

UNION ALL
SELECT 'users', COUNT(*) FROM users;

"""Rail Seba - Flask app.
The database only stores data (plain tables). The rules - train search, fares,
seat clash check, hold timeout and refunds - are written here in Python."""
import os, re, secrets, string
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps

import psycopg2, psycopg2.extras, segno
from flask import (Flask, g, render_template, request, redirect, url_for,
                   session, flash, abort)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-me")
DSN = os.environ.get("DATABASE_URL", "dbname=railseba user=postgres password=fahim host=localhost port=5432")


# ---------------------------------------------------------------- database
def db():
    if "db" not in g:
        g.db = psycopg2.connect(DSN, options="-c timezone=Asia/Dhaka",
                                cursor_factory=psycopg2.extras.RealDictCursor)
    return g.db

@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()

def q(sql, args=(), one=False):
    """Run a SELECT and return the rows (or just the first row)."""
    with db().cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows

def ex(sql, args=()):
    """Run an INSERT / UPDATE (call db().commit() afterwards)."""
    with db().cursor() as cur:
        cur.execute(sql, args)

def login_required(f):
    @wraps(f)
    def wrapper(*a, **k):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.full_path))
        return f(*a, **k)
    return wrapper


# ---------------------------------------------------------------- rules in Python
def money(x):
    """Round to whole taka (0.5 goes up)."""
    return Decimal(x).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

def base_fare(km, rate, min_fare, child=False, child_pct=50):
    fare = max(Decimal(min_fare), Decimal(km) * Decimal(rate))
    if child:
        fare = fare * (100 - Decimal(child_pct)) / 100
    return money(fare)

def settings():
    return q("SELECT * FROM fare_settings", one=True)

def expire_holds():
    """Free the seats of bookings that were not paid in time."""
    ex("""UPDATE tickets SET status = 'EXPIRED'
          WHERE status = 'HELD' AND booking_id IN
                (SELECT booking_id FROM bookings WHERE status = 'PENDING' AND expires_at < CURRENT_TIMESTAMP)""")
    ex("UPDATE bookings SET status = 'EXPIRED' WHERE status = 'PENDING' AND expires_at < CURRENT_TIMESTAMP")
    db().commit()


# ---------------------------------------------------------------- login / register
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        mobile, nid = f["mobile"].strip(), f.get("nid", "").strip() or None
        if not re.fullmatch(r"01[3-9]\d{8}", mobile):
            flash("Enter a valid mobile number like 01712345678.")
        elif nid and not re.fullmatch(r"\d{10}|\d{13}|\d{17}", nid):
            flash("NID must have 10, 13 or 17 digits.")
        elif q("SELECT 1 FROM users WHERE mobile = %s", (mobile,)):
            flash("This mobile number is already registered.")
        else:
            try:
                ex("INSERT INTO users (full_name, email, mobile, password_hash, nid) VALUES (%s,%s,%s,%s,%s)",
                   (f["full_name"].strip(), f.get("email", "").strip() or None, mobile,
                    generate_password_hash(f["password"]), nid))
                db().commit()
                flash("Account created. Please log in.")
                return redirect(url_for("login"))
            except psycopg2.errors.UniqueViolation:
                db().rollback()
                flash("This email or NID is already registered.")
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = q("SELECT * FROM users WHERE mobile = %s", (request.form["mobile"].strip(),), one=True)
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session.update(user_id=u["user_id"], name=u["full_name"], role=u["role"])
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") else url_for("index"))
        flash("Wrong mobile number or password.")
    return render_template("auth.html", mode="login")

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------- home + search
@app.get("/")
def index():
    today = q("SELECT CURRENT_DATE AS d", one=True)["d"]      # the database clock (Asia/Dhaka)
    return render_template("index.html",
        stations=q("SELECT station_name FROM stations ORDER BY station_name"),
        classes=q("""SELECT DISTINCT sc.class_id, sc.class_code FROM seat_classes sc
                     JOIN coaches c ON c.class_id = sc.class_id ORDER BY sc.class_id"""),
        today=today, last_day=today + timedelta(days=9))

SEARCH_SQL = """
SELECT t.trip_id, tr.train_id, tr.train_number, tr.train_name, tr.train_type,
       fs.stop_order AS from_order, ts.stop_order AS to_order,
       fs.departure_time, fs.day_offset AS dep_day, ts.arrival_time, ts.day_offset AS arr_day,
       ts.distance_km - fs.distance_km AS km,
       sf.station_name AS from_station, st.station_name AS to_station
FROM train_stops fs
JOIN stations sf    ON sf.station_id = fs.station_id
JOIN train_stops ts ON ts.train_id = fs.train_id AND ts.stop_order > fs.stop_order
JOIN stations st    ON st.station_id = ts.station_id
JOIN trains tr      ON tr.train_id = fs.train_id
JOIN trips t        ON t.train_id = tr.train_id
WHERE sf.station_name ILIKE %(from)s || '%%'
  AND st.station_name ILIKE %(to)s || '%%'
  AND tr.is_active AND t.status = 'SCHEDULED'
  AND t.journey_date = %(date)s::date - fs.day_offset
ORDER BY fs.departure_time"""

# every class of a train: price rule + how many seats are still free on this part of the trip
CLASSES_SQL = """
SELECT sc.class_id, sc.class_code, sc.has_vat, fr.rate_per_km, fr.min_fare,
       (SELECT COUNT(*) FROM seats s JOIN coaches c ON c.coach_id = s.coach_id
         WHERE c.train_id = %(train)s AND c.class_id = sc.class_id)
     - (SELECT COUNT(*) FROM tickets k JOIN seats s ON s.seat_id = k.seat_id
          JOIN coaches c ON c.coach_id = s.coach_id
         WHERE k.trip_id = %(trip)s AND c.class_id = sc.class_id AND k.status IN ('HELD', 'ISSUED')
           AND k.from_stop_order < %(to)s AND %(from)s < k.to_stop_order) AS free
FROM seat_classes sc
JOIN fare_rates fr ON fr.class_id = sc.class_id AND fr.train_type = %(type)s
WHERE sc.class_id IN (SELECT class_id FROM coaches WHERE train_id = %(train)s)
ORDER BY sc.class_id"""

def minutes(t, day):
    return day * 1440 + t.hour * 60 + t.minute

@app.get("/search")
def search():
    a = request.args
    try:
        d, cls = date.fromisoformat(a["date"]), int(a.get("class_id") or 0)
    except (KeyError, ValueError):
        return redirect(url_for("index"))
    expire_holds()
    cfg = settings()
    now = q("SELECT now()::timestamp AS n", one=True)["n"]
    found = []
    for r in q(SEARCH_SQL, {"from": a.get("from", "").strip(), "to": a.get("to", "").strip(), "date": d}):
        dep = datetime.combine(d, r["departure_time"])
        if dep < now:
            continue                                    # train already left
        length = minutes(r["arrival_time"], r["arr_day"]) - minutes(r["departure_time"], r["dep_day"])
        r.update(dep=dep, arr=dep + timedelta(minutes=length), duration=f"{length // 60:02d}h {length % 60:02d}m")
        r["classes"] = []
        for c in q(CLASSES_SQL, {"train": r["train_id"], "trip": r["trip_id"], "from": r["from_order"],
                                 "to": r["to_order"], "type": r["train_type"]}):
            fare = base_fare(r["km"], c["rate_per_km"], c["min_fare"])
            c["price"] = money(fare * (1 + cfg["vat_percent"] / 100)) if c["has_vat"] else fare
            r["classes"].append(c)
        if cls and not any(c["class_id"] == cls for c in r["classes"]):
            continue                                    # train has no seats of the chosen class
        r["trying"] = q("SELECT COUNT(*) AS n FROM bookings WHERE trip_id = %s AND status = 'PENDING'",
                        (r["trip_id"],), one=True)["n"]
        found.append(r)
    return render_template("results.html", trains=found, d=d, cls=cls,
                           from_name=a.get("from", ""), to_name=a.get("to", ""))


# ---------------------------------------------------------------- seat selection
@app.get("/trip/<int:trip_id>")
@login_required
def trip(trip_id):
    p = {"trip": trip_id, "fo": request.args.get("from_order", type=int),
         "to": request.args.get("to_order", type=int), "cls": request.args.get("class_id", type=int)}
    expire_holds()
    info = q("""SELECT t.trip_id, t.journey_date, tr.train_number, tr.train_name,
                       sc.class_code, sc.has_vat, fr.rate_per_km, fr.min_fare,
                       sf.station_name AS from_station, st.station_name AS to_station,
                       ts.distance_km - fs.distance_km AS km, fs.departure_time
                FROM trips t
                JOIN trains tr ON tr.train_id = t.train_id
                JOIN seat_classes sc ON sc.class_id = %(cls)s
                JOIN fare_rates fr ON fr.class_id = sc.class_id AND fr.train_type = tr.train_type
                JOIN train_stops fs ON fs.train_id = tr.train_id AND fs.stop_order = %(fo)s
                JOIN stations sf ON sf.station_id = fs.station_id
                JOIN train_stops ts ON ts.train_id = tr.train_id AND ts.stop_order = %(to)s
                JOIN stations st ON st.station_id = ts.station_id
                WHERE t.trip_id = %(trip)s""", p, one=True) or abort(404)
    seats = q("""SELECT s.seat_id, c.coach_code, s.seat_number,
                        s.seat_id IN (SELECT seat_id FROM tickets
                                      WHERE trip_id = %(trip)s AND status IN ('HELD', 'ISSUED')
                                        AND from_stop_order < %(to)s AND %(fo)s < to_stop_order) AS booked
                 FROM trips t
                 JOIN coaches c ON c.train_id = t.train_id AND c.class_id = %(cls)s
                 JOIN seats s ON s.coach_id = c.coach_id
                 WHERE t.trip_id = %(trip)s ORDER BY c.coach_code, s.seat_number""", p)
    cfg = settings()
    fare = base_fare(info["km"], info["rate_per_km"], info["min_fare"])
    price = money(fare * (1 + cfg["vat_percent"] / 100)) if info["has_vat"] else fare
    return render_template("seats.html", i=info, seats=seats, price=price,
                           fo=p["fo"], to=p["to"], cls=p["cls"], child_pct=cfg["child_discount_pct"])

@app.post("/book")
@login_required
def book():
    f = request.form
    trip_id, fo, to, cls = (int(f[k]) for k in ("trip_id", "from_order", "to_order", "class_id"))
    back = url_for("trip", trip_id=trip_id, from_order=fo, to_order=to, class_id=cls)
    seat_ids = sorted({int(s) for s in f.getlist("seat_id")})
    pax = [(s, f.get(f"name_{s}", "").strip(), f.get(f"ptype_{s}", "ADULT")) for s in seat_ids]
    if not 1 <= len(pax) <= 4 or any(not n or p not in ("ADULT", "CHILD") for _, n, p in pax):
        flash("Choose 1 to 4 seats and enter a name for every passenger.")
        return redirect(back)

    expire_holds()
    conn = db(); cur = conn.cursor()
    # Lock this trip: if two people book at the same moment, the second one waits here.
    cur.execute("""SELECT t.train_id, tr.train_type FROM trips t JOIN trains tr ON tr.train_id = t.train_id
                   WHERE t.trip_id = %s AND t.status = 'SCHEDULED' FOR UPDATE OF t""", (trip_id,))
    trip_row = cur.fetchone() or abort(404)
    cur.execute("""SELECT fs.station_id AS from_id, ts.station_id AS to_id, ts.distance_km - fs.distance_km AS km
                   FROM train_stops fs, train_stops ts
                   WHERE fs.train_id = %s AND fs.stop_order = %s AND ts.train_id = %s AND ts.stop_order = %s""",
                (trip_row["train_id"], fo, trip_row["train_id"], to))
    seg = cur.fetchone()
    cur.execute("""SELECT sc.has_vat, fr.rate_per_km, fr.min_fare FROM seat_classes sc
                   JOIN fare_rates fr ON fr.class_id = sc.class_id AND fr.train_type = %s
                   WHERE sc.class_id = %s""", (trip_row["train_type"], cls))
    rate = cur.fetchone()
    cur.execute("""SELECT COUNT(*) AS n FROM seats s JOIN coaches c ON c.coach_id = s.coach_id
                   WHERE c.train_id = %s AND c.class_id = %s AND s.seat_id IN %s""",
                (trip_row["train_id"], cls, tuple(seat_ids)))
    if not seg or not rate or fo >= to or cur.fetchone()["n"] != len(seat_ids):
        abort(400)

    # seat clash check: is any chosen seat already sold for an overlapping part of the trip?
    cur.execute("""SELECT COUNT(*) AS n FROM tickets
                   WHERE trip_id = %s AND seat_id IN %s AND status IN ('HELD', 'ISSUED')
                     AND from_stop_order < %s AND %s < to_stop_order""", (trip_id, tuple(seat_ids), to, fo))
    if cur.fetchone()["n"]:
        conn.rollback()
        flash("Sorry, one of those seats was just taken. Please choose again.")
        return redirect(back)

    cur.execute("SELECT * FROM fare_settings")
    cfg = cur.fetchone()
    fares = [base_fare(seg["km"], rate["rate_per_km"], rate["min_fare"], p == "CHILD", cfg["child_discount_pct"])
             for _, _, p in pax]
    subtotal = sum(fares, Decimal(0))
    vat = (subtotal * cfg["vat_percent"] / 100).quantize(Decimal("0.01")) if rate["has_vat"] else Decimal("0.00")
    service = cfg["service_charge"] * len(pax)
    pnr = "RS" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))

    cur.execute("""INSERT INTO bookings (pnr, user_id, trip_id, from_station_id, to_station_id, subtotal,
                                         vat_amount, service_charge, total_amount, expires_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, CURRENT_TIMESTAMP + (%s * INTERVAL '1 minute'))
                   RETURNING booking_id""",
                (pnr, session["user_id"], trip_id, seg["from_id"], seg["to_id"], subtotal, vat, service,
                 subtotal + vat + service, cfg["hold_minutes"]))
    booking_id = cur.fetchone()["booking_id"]
    for n, ((seat_id, name, ptype), fare) in enumerate(zip(pax, fares), 1):
        cur.execute("""INSERT INTO tickets (ticket_no, booking_id, trip_id, seat_id, from_stop_order,
                                            to_stop_order, passenger_name, passenger_type, fare_amount)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (f"{pnr}-{n}", booking_id, trip_id, seat_id, fo, to, name, ptype, fare))
    conn.commit()
    return redirect(url_for("pay", booking_id=booking_id))


# ---------------------------------------------------------------- payment (demo)
@app.route("/pay/<int:booking_id>", methods=["GET", "POST"])
@login_required
def pay(booking_id):
    expire_holds()
    b = q("""SELECT b.*, EXTRACT(EPOCH FROM (b.expires_at - CURRENT_TIMESTAMP::timestamp)) AS seconds_left,
                    tr.train_number, tr.train_name, t.journey_date,
                    sf.station_name AS from_station, st.station_name AS to_station
             FROM bookings b JOIN trips t ON t.trip_id = b.trip_id JOIN trains tr ON tr.train_id = t.train_id
             JOIN stations sf ON sf.station_id = b.from_station_id JOIN stations st ON st.station_id = b.to_station_id
             WHERE b.booking_id = %s AND b.user_id = %s""", (booking_id, session["user_id"]), one=True) or abort(404)
    if b["status"] != "PENDING":
        flash("This booking is not waiting for payment (it may have expired).")
        return redirect(url_for("tickets"))
    if request.method == "POST":
        method = request.form.get("method")
        if method not in ("BKASH", "NAGAD", "ROCKET", "UPAY", "CARD", "NEXUSPAY"):
            abort(400)
        # DEMO: a real site would call the bKash / SSLCommerz payment gateway here
        ex("""INSERT INTO payments (booking_id, method, gateway_txn_id, amount, status, paid_at)
              VALUES (%s,%s,%s,%s,'SUCCESS',CURRENT_TIMESTAMP)""",
           (booking_id, method, "DEMO" + secrets.token_hex(6).upper(), b["total_amount"]))
        ex("UPDATE bookings SET status = 'CONFIRMED', confirmed_at = CURRENT_TIMESTAMP WHERE booking_id = %s", (booking_id,))
        ex("UPDATE tickets SET status = 'ISSUED' WHERE booking_id = %s AND status = 'HELD'", (booking_id,))
        db().commit()
        flash("Payment successful. Your tickets are issued!")
        return redirect(url_for("tickets"))
    tix = q("""SELECT k.*, c.coach_code, s.seat_number FROM tickets k JOIN seats s ON s.seat_id = k.seat_id
               JOIN coaches c ON c.coach_id = s.coach_id WHERE k.booking_id = %s ORDER BY k.ticket_id""", (booking_id,))
    return render_template("pay.html", b=b, tix=tix, left=int(b["seconds_left"]))


# ---------------------------------------------------------------- my tickets, print page, cancel
TICKET_SQL = """
SELECT k.ticket_id, k.ticket_no, k.status, k.passenger_name, k.passenger_type, k.fare_amount,
       b.pnr, tr.train_number, tr.train_name, t.journey_date, c.coach_code, s.seat_number, sc.class_code,
       sf.station_name AS from_station, st.station_name AS to_station, fs.departure_time, ts.arrival_time,
       (t.journey_date + fs.day_offset + fs.departure_time) > CURRENT_TIMESTAMP::timestamp AS upcoming
FROM tickets k
JOIN bookings b ON b.booking_id = k.booking_id
JOIN trips t ON t.trip_id = k.trip_id
JOIN trains tr ON tr.train_id = t.train_id
JOIN seats s ON s.seat_id = k.seat_id
JOIN coaches c ON c.coach_id = s.coach_id
JOIN seat_classes sc ON sc.class_id = c.class_id
JOIN train_stops fs ON fs.train_id = t.train_id AND fs.stop_order = k.from_stop_order
JOIN train_stops ts ON ts.train_id = t.train_id AND ts.stop_order = k.to_stop_order
JOIN stations sf ON sf.station_id = fs.station_id
JOIN stations st ON st.station_id = ts.station_id
WHERE b.user_id = %s """

@app.get("/tickets")
@login_required
def tickets():
    rows = q(TICKET_SQL + "AND k.status IN ('ISSUED', 'CANCELLED') ORDER BY t.journey_date DESC, k.ticket_id",
             (session["user_id"],))
    return render_template("tickets.html", rows=rows)

@app.get("/ticket/<int:ticket_id>")
@login_required
def ticket_page(ticket_id):
    k = q(TICKET_SQL + "AND k.ticket_id = %s", (session["user_id"], ticket_id), one=True) or abort(404)
    text = f"RAILSEBA|{k['ticket_no']}|{k['pnr']}|{k['train_number']}|{k['journey_date']}|{k['coach_code']}-{k['seat_number']}"
    return render_template("ticket.html", k=k, qr=segno.make(text).svg_inline(scale=4, border=1))

@app.post("/cancel/<int:ticket_id>")
@login_required
def cancel(ticket_id):
    k = q("""SELECT k.ticket_id, k.booking_id, k.fare_amount,
                    EXTRACT(EPOCH FROM ((t.journey_date + fs.day_offset + fs.departure_time)
                                        - CURRENT_TIMESTAMP::timestamp)) / 3600 AS hours_left
             FROM tickets k JOIN bookings b ON b.booking_id = k.booking_id
             JOIN trips t ON t.trip_id = k.trip_id
             JOIN train_stops fs ON fs.train_id = t.train_id AND fs.stop_order = k.from_stop_order
             WHERE k.ticket_id = %s AND b.user_id = %s AND k.status = 'ISSUED'""",
          (ticket_id, session["user_id"]), one=True) or abort(404)
    if k["hours_left"] <= 0:
        flash("This train has already left, so the ticket cannot be cancelled.")
        return redirect(url_for("tickets"))
    pct = Decimal(100)                                  # no rule matches = no refund
    for r in q("SELECT * FROM cancellation_rules ORDER BY min_hours_before DESC"):
        if k["hours_left"] >= r["min_hours_before"] and (r["max_hours_before"] is None or k["hours_left"] < r["max_hours_before"]):
            pct = r["deduction_percent"]
            break
    deduction = (k["fare_amount"] * pct / 100).quantize(Decimal("0.01"))
    payment = q("SELECT payment_id FROM payments WHERE booking_id = %s AND status = 'SUCCESS'",
                (k["booking_id"],), one=True) or abort(404)
    ex("""INSERT INTO refunds (ticket_id, payment_id, deduction_amount, refund_amount)
          VALUES (%s,%s,%s,%s)""", (ticket_id, payment["payment_id"], deduction, k["fare_amount"] - deduction))
    ex("UPDATE tickets SET status = 'CANCELLED' WHERE ticket_id = %s", (ticket_id,))
    if not q("SELECT 1 FROM tickets WHERE booking_id = %s AND status = 'ISSUED'", (k["booking_id"],)):
        ex("UPDATE bookings SET status = 'CANCELLED' WHERE booking_id = %s", (k["booking_id"],))
        ex("UPDATE payments SET status = 'REFUNDED' WHERE payment_id = %s", (payment["payment_id"],))
    db().commit()
    flash(f"Ticket cancelled. Refund: {k['fare_amount'] - deduction} BDT ({pct}% deducted).")
    return redirect(url_for("tickets"))


# ---------------------------------------------------------------- information pages
@app.get("/trains")
def trains_page():
    rows = q("""SELECT tr.train_id, tr.train_number, tr.train_name, tr.train_type,
                  (SELECT s.station_name FROM train_stops p JOIN stations s ON s.station_id = p.station_id
                    WHERE p.train_id = tr.train_id ORDER BY p.stop_order LIMIT 1) AS origin,
                  (SELECT s.station_name FROM train_stops p JOIN stations s ON s.station_id = p.station_id
                    WHERE p.train_id = tr.train_id ORDER BY p.stop_order DESC LIMIT 1) AS destination,
                  (SELECT departure_time FROM train_stops WHERE train_id = tr.train_id AND stop_order = 1) AS departs
                FROM trains tr WHERE tr.is_active ORDER BY tr.train_number""")
    return render_template("trains.html", rows=rows)

@app.get("/train/<int:train_id>")
def train_info(train_id):
    t = q("SELECT * FROM trains WHERE train_id = %s", (train_id,), one=True) or abort(404)
    stops = q("""SELECT p.*, s.station_name FROM train_stops p JOIN stations s ON s.station_id = p.station_id
                 WHERE p.train_id = %s ORDER BY p.stop_order""", (train_id,))
    classes = q("""SELECT sc.class_code, COUNT(s.seat_id) AS seats FROM coaches c
                   JOIN seat_classes sc ON sc.class_id = c.class_id JOIN seats s ON s.coach_id = c.coach_id
                   WHERE c.train_id = %s GROUP BY sc.class_id, sc.class_code ORDER BY sc.class_id""", (train_id,))
    return render_template("train_info.html", t=t, stops=stops, classes=classes)

@app.get("/contact")
def contact():
    return render_template("contact.html")


from admin import init_admin
init_admin(app, q, db, login_required)

if __name__ == "__main__":
    app.run(debug=True)

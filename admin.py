"""Admin panel (role = ADMIN). Registered from app.py via init_admin()."""
from functools import wraps
import psycopg2
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort


def init_admin(app, q, db, login_required):
    bp = Blueprint("admin", __name__, url_prefix="/admin")

    def admin_required(f):
        @wraps(f)
        @login_required
        def wrapper(*a, **k):
            if session.get("role") != "ADMIN":
                abort(403)
            return f(*a, **k)
        return wrapper

    def run(sql, args, ok, back):
        """Execute one write, commit, flash result, redirect."""
        try:
            with db().cursor() as cur:
                cur.execute(sql, args)
                n = cur.rowcount
            db().commit()
            flash(ok.format(n=n))
        except psycopg2.Error as e:
            db().rollback()
            flash("Error: " + (e.diag.message_primary or "invalid input"))
        return redirect(back)

    def lookups():
        return (q("SELECT station_id, station_name FROM stations ORDER BY station_name"),
                q("SELECT class_id, class_name FROM seat_classes ORDER BY class_id"))

    # ---------- dashboard ----------
    @bp.get("/")
    @admin_required
    def dashboard():
        stats = q("""SELECT (SELECT count(*) FROM users WHERE role='PASSENGER') AS users,
                            (SELECT count(*) FROM trains WHERE is_active) AS trains,
                            (SELECT count(*) FROM bookings WHERE status='CONFIRMED') AS bookings,
                            (SELECT coalesce(sum(amount),0) FROM payments WHERE status='SUCCESS') AS revenue,
                            (SELECT count(*) FROM refunds WHERE status='REQUESTED') AS pending_refunds""", one=True)
        recent = q("""SELECT b.pnr, b.status, b.total_amount, b.created_at, u.full_name, tr.train_name, t.journey_date
                      FROM bookings b JOIN users u ON u.user_id=b.user_id JOIN trips t ON t.trip_id=b.trip_id
                      JOIN trains tr ON tr.train_id=t.train_id ORDER BY b.created_at DESC LIMIT 10""")
        return render_template("admin/dashboard.html", s=stats, recent=recent)

    # ---------- trains, stops, coaches ----------
    @bp.route("/trains", methods=["GET", "POST"])
    @admin_required
    def trains():
        if request.method == "POST":
            f = request.form
            return run("""INSERT INTO trains (train_number, train_name, train_type, off_day)
                          VALUES (%s,%s,%s,%s)""",
                       (f["train_number"].strip(), f["train_name"].strip(), f["train_type"], f.get("off_day") or None),
                       "Train added.", url_for("admin.trains"))
        rows = q("""SELECT t.*, (SELECT count(*) FROM train_stops WHERE train_id=t.train_id) AS stops,
                           (SELECT count(*) FROM coaches WHERE train_id=t.train_id) AS coaches
                    FROM trains t ORDER BY t.train_number""")
        return render_template("admin/trains.html", rows=rows)

    @bp.get("/train/<int:tid>")
    @admin_required
    def train(tid):
        t = q("SELECT * FROM trains WHERE train_id=%s", (tid,), one=True) or abort(404)
        stops = q("""SELECT ts.*, s.station_name FROM train_stops ts JOIN stations s ON s.station_id=ts.station_id
                     WHERE ts.train_id=%s ORDER BY ts.stop_order""", (tid,))
        coaches = q("""SELECT c.coach_code, sc.class_name,
                              (SELECT count(*) FROM seats WHERE coach_id=c.coach_id) AS seats
                       FROM coaches c JOIN seat_classes sc ON sc.class_id=c.class_id
                       WHERE c.train_id=%s ORDER BY c.coach_id""", (tid,))
        stations, classes = lookups()
        return render_template("admin/train.html", t=t, stops=stops, coaches=coaches,
                               stations=stations, classes=classes, next_order=len(stops) + 1)

    @bp.post("/train/<int:tid>/stop")
    @admin_required
    def add_stop(tid):
        f = request.form
        return run("""INSERT INTO train_stops (train_id, stop_order, station_id, arrival_time, departure_time,
                                               day_offset, distance_km) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                   (tid, f["stop_order"], f["station_id"], f.get("arrival_time") or None,
                    f.get("departure_time") or None, f.get("day_offset") or 0, f["distance_km"]),
                   "Stop added.", url_for("admin.train", tid=tid))

    @bp.post("/train/<int:tid>/coach")
    @admin_required
    def add_coach(tid):
        f = request.form
        try:
            n = int(f["seat_count"])
            assert 1 <= n <= 120
            with db().cursor() as cur:
                cur.execute("INSERT INTO coaches (train_id, coach_code, class_id) VALUES (%s,%s,%s) RETURNING coach_id",
                            (tid, f["coach_code"].strip().upper(), f["class_id"]))
                cid = cur.fetchone()["coach_id"]
                cur.execute("INSERT INTO seats (coach_id, seat_number) SELECT %s, g FROM generate_series(1,%s) g", (cid, n))
            db().commit()
            flash(f"Coach added with {n} seats.")
        except (psycopg2.Error, AssertionError, ValueError) as e:
            db().rollback()
            flash("Error: could not add coach (duplicate code or invalid seat count).")
        return redirect(url_for("admin.train", tid=tid))

    @bp.post("/train/<int:tid>/toggle")
    @admin_required
    def toggle_train(tid):
        return run("UPDATE trains SET is_active = NOT is_active WHERE train_id=%s", (tid,),
                   "Train status changed.", url_for("admin.trains"))

    # ---------- trips ----------
    @bp.route("/trips", methods=["GET", "POST"])
    @admin_required
    def trips():
        if request.method == "POST":
            f = request.form
            tid = f.get("train_id") or None
            return run("""INSERT INTO trips (train_id, journey_date)
                          SELECT t.train_id, d::date FROM trains t,
                                 generate_series(%s::date, %s::date + (%s::int - 1), interval '1 day') d
                          WHERE t.is_active AND (%s::int IS NULL OR t.train_id = %s::int)
                            AND (t.off_day IS NULL OR extract(dow FROM d) <> t.off_day)
                          ON CONFLICT (train_id, journey_date) DO NOTHING""",
                       (f["start"], f["start"], f["days"], tid, tid),
                       "{n} new trips created.", url_for("admin.trips"))
        rows = q("""SELECT t.trip_id, t.journey_date, t.status, tr.train_number, tr.train_name,
                           (SELECT count(*) FROM tickets k WHERE k.trip_id=t.trip_id AND k.status IN ('HELD','ISSUED')) AS sold
                    FROM trips t JOIN trains tr ON tr.train_id=t.train_id
                    WHERE t.journey_date >= current_date ORDER BY t.journey_date, tr.train_number LIMIT 200""")
        return render_template("admin/trips.html", rows=rows,
                               trains=q("SELECT train_id, train_number, train_name FROM trains ORDER BY train_number"))

    @bp.post("/trips/<int:trip_id>/cancel")
    @admin_required
    def cancel_trip(trip_id):
        return run("""UPDATE trips SET status='CANCELLED' WHERE trip_id=%s AND status='SCHEDULED'
                      AND NOT EXISTS (SELECT 1 FROM tickets WHERE trip_id=%s AND status IN ('HELD','ISSUED'))""",
                   (trip_id, trip_id), "Trips cancelled: {n} (trips with live tickets are skipped).", url_for("admin.trips"))

    # ---------- fares & settings ----------
    @bp.get("/fares")
    @admin_required
    def fares():
        rates = q("""SELECT fr.train_type, fr.class_id, sc.class_name, fr.rate_per_km, fr.min_fare
                     FROM fare_rates fr JOIN seat_classes sc ON sc.class_id=fr.class_id ORDER BY fr.train_type, fr.class_id""")
        return render_template("admin/fares.html", rates=rates, classes=lookups()[1],
                               cfg=q("SELECT * FROM fare_settings", one=True))

    @bp.post("/fares/rate")
    @admin_required
    def save_rate():
        f = request.form
        return run("""INSERT INTO fare_rates (train_type, class_id, rate_per_km, min_fare) VALUES (%s,%s,%s,%s)
                      ON CONFLICT (train_type, class_id) DO UPDATE
                      SET rate_per_km=EXCLUDED.rate_per_km, min_fare=EXCLUDED.min_fare""",
                   (f["train_type"], f["class_id"], f["rate_per_km"], f["min_fare"]),
                   "Fare rate saved.", url_for("admin.fares"))

    @bp.post("/fares/settings")
    @admin_required
    def save_settings():
        f = request.form
        return run("""UPDATE fare_settings SET vat_percent=%s, service_charge=%s,
                      child_discount_pct=%s, hold_minutes=%s""",
                   (f["vat_percent"], f["service_charge"], f["child_discount_pct"], f["hold_minutes"]),
                   "Settings saved.", url_for("admin.fares"))

    # ---------- refunds ----------
    @bp.get("/refunds")
    @admin_required
    def refunds():
        rows = q("""SELECT r.*, k.ticket_no, k.passenger_name, u.full_name, u.mobile, p.method
                    FROM refunds r JOIN tickets k ON k.ticket_id=r.ticket_id
                    JOIN bookings b ON b.booking_id=k.booking_id JOIN users u ON u.user_id=b.user_id
                    JOIN payments p ON p.payment_id=r.payment_id ORDER BY r.status, r.requested_at DESC""")
        return render_template("admin/refunds.html", rows=rows)

    @bp.post("/refunds/<int:rid>/process")
    @admin_required
    def process_refund(rid):
        return run("UPDATE refunds SET status='PROCESSED', processed_at=now() WHERE refund_id=%s AND status='REQUESTED'",
                   (rid,), "Refund marked as processed.", url_for("admin.refunds"))

    # ---------- stations ----------
    @bp.route("/stations", methods=["GET", "POST"])
    @admin_required
    def stations():
        if request.method == "POST":
            f = request.form
            return run("INSERT INTO stations (station_code, station_name, district) VALUES (%s,%s,%s)",
                       (f["station_code"].strip().upper(), f["station_name"].strip(), f.get("district")),
                       "Station added.", url_for("admin.stations"))
        return render_template("admin/stations.html", rows=q("SELECT * FROM stations ORDER BY station_name"))

    app.register_blueprint(bp)

# Rail Seba - Bangladesh Railway e-ticket (semester project)
Python (Flask) + HTML/CSS frontend, PostgreSQL database.

Flow: search trains -> choose class -> pick seats -> pay (demo) -> e-ticket with QR -> cancel / refund.
Admin: stations, trains, routes, coaches, trips, fares, refunds.

## Run
1. In pgAdmin create an empty database called **railseba**.
2. Query Tool: run `db/schema.sql`, then `db/sample_data.sql`.
3. In the VS Code terminal (inside this folder):

       python -m venv venv
       venv\Scripts\activate               (Mac/Linux: source venv/bin/activate)
       pip install -r requirements.txt
       $env:DATABASE_URL="dbname=railseba user=postgres password=YOUR_PASSWORD host=localhost"
       python app.py                       (open http://127.0.0.1:5000)

## Logins (password `password123`)
Admin `01700000000` (Admin link in the menu) - passenger `01700000001`.

## Folder
- `app.py`   all pages and rules (search, fares, seat clash check, hold timeout, refunds)
- `admin.py` admin pages
- `db/schema.sql` tables only, `db/sample_data.sql` plain INSERT statements
- `templates/`, `static/style.css` the pages and the look

## Not included
Real payment gateway (payment is a demo), CSRF protection, email/SMS.

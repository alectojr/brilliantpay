# BrilliantPay

**Financial data management web app for Brilliant Driving School**

A clean, modern Flask application for recording student payment details (bank & mobile money) together with receipt photos.

## Features

- **Catchy name**: BrilliantPay – the finance hub that keeps Brilliant Driving School on the road to success.
- **Role-based access**
  - **Super user**: can add payments and modify/delete any record.
  - **Staff user**: can add bank and mobile money payments, including additional payments for an existing student.
- **Login & Signup** pages with modern classic UI matching the school logo colours (navy, red, yellow accents).
- **Profile dashboard** with an option to change your password.
- **Existing payments register** with search and XLSX export for staff and super users.
- **Idle-session timeout** signs users out after one minute without activity.
- The login background has previous/next arrows to browse four photographic images in `static/img/`.
- **Forgot Password**: generates a temporary **fruit-based** password (e.g. `Mango42`, `Pineapple17`).
- **Dashboard** with left sidebar navigation:
  1. Add payment details – Bank payments
  2. Add payment details – Mobile payments
  3. Existing payments – search, add to a student, and paginate records
- Stores: Student name, Form of payment, Amount, Reference, Receipt photo, Notes, Date, Uploader.

## Quick Start

```bash
# Activate the virtual environment (created earlier)
source /tmp/brilliantpay_venv/bin/activate

# Go to the project
cd /home/workdir/artifacts/brilliantpay

# Run
python app.py
```

Open http://127.0.0.1:5000 in your browser.

### Provisioning the First Super User
No default super-user credentials are created automatically. Before the first start, set these environment variables for the system administrator:

```text
BRILLIANTPAY_ADMIN_USERNAME=admin
BRILLIANTPAY_ADMIN_EMAIL=admin@example.com
BRILLIANTPAY_ADMIN_PASSWORD=<strong-unique-password>
```

The account is created once when `python app.py` initializes the database. Do not put these values in source control.

## Creating a Staff Account
Use the **Sign Up** page – new accounts are created with the `staff` role.

## Colour Palette (from school logo)
- Red: `#C41E3A`
- Deep Navy: `#0B2545`
- Road Yellow: `#F5C518`
- Clean light backgrounds

## Tech Stack
- Python 3 + Flask
- Flask-SQLAlchemy (SQLite)
- Flask-Login
- Bootstrap 5 + Bootstrap Icons
- Pillow (image handling)

## Project Structure
```
brilliantpay/
├── app.py
├── brilliantpay.db          # created on first run
├── README.md
├── static/
│   ├── css/style.css
│   ├── img/logo.png
│   └── uploads/             # receipt images
└── templates/
    ├── base.html
    ├── login.html
    ├── signup.html
    ├── forgot_password.html
    ├── dashboard.html
    ├── add_bank.html
    ├── add_mobile.html
    ├── modify_payments.html
    └── edit_payment.html
```

## Production Deployment

1. Install dependencies with `python -m pip install -r requirements.txt`.
2. Set a permanent `BRILLIANTPAY_SECRET_KEY` and use a strong random value.
3. Set `BRILLIANTPAY_ENV=production`; this enables secure session cookies and refuses to start without a secret key.
4. Set `BRILLIANTPAY_DATABASE_URL` to PostgreSQL or another production database. SQLite is suitable for local use only.
5. Run database initialization once with the administrator provisioning variables above, then remove the admin password variable.
6. Serve the app behind HTTPS with Waitress, for example: `waitress-serve --listen=127.0.0.1:8080 wsgi:app` (or use a WSGI entry point appropriate to your host).
7. Schedule `backup.ps1` to back up the database and receipt directory automatically.

Receipt uploads are limited to 8 MB and verified as images. The app also records payment create, update, and delete actions in the audit log.

---
Built for Brilliant Driving School 🚗💨

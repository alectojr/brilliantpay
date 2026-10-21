# BrilliantPay

**Financial data management web app for Brilliant Driving School**

A clean, modern Flask application for recording student payment details (bank & mobile money) together with receipt photos.

## Features

- **Catchy name**: BrilliantPay – the finance hub that keeps Brilliant Driving School on the road to success.
- **Role-based access**
  - **Super user and staff**: can add payments and edit payment details, except the amount received and payment date.
  - **Super user**: can delete payment records.
- **Course fees**: Basic (TZS 300,000), Public Service Vehicles (PSV) (TZS 250,000), and Heavy Vehicles (HGV) (TZS 350,000). Record the actual amount received separately.
- **Login & Signup** pages with modern classic UI matching the school logo colours (navy, red, yellow accents).
- **Profile dashboard** with an option to change your password.
- **Existing payments register** with search and XLSX export for staff and super users.
- **Payment invoices**: recording a bank or mobile payment opens a printable invoice with a signed, RGB-styled QR code for verification. The first two invoices for a payment can be generated from Existing Payments without additional authorization; further invoices require an active super-user password.
- **Bank receipt review**: bank payments start pending verification; staff and super users can verify or reject after checking an official bank record, with the reviewer and notes recorded. Reused references for the same bank are flagged. This workflow does not establish authenticity from an image alone.
- **Idle-session timeout** signs users out after four minutes without activity.
- Login, signup, and forgot-password backgrounds have previous/next arrows to browse four photographic images in `static/img/`.
- **Forgot Password**: generates a temporary **fruit-based** password (e.g. `Mango42`, `Pineapple17`).
- **Dashboard** with left sidebar navigation:
  1. Add payment details – Bank payments
  2. Add payment details – Mobile payments
  3. Existing payments – search, add to a student, and paginate records
- The dashboard provides WhatsApp and email contact actions for Brilliant Driving School.
- Stores: Student name, Course, Form of payment, Amount received, Reference, Receipt photo, Notes, Date, Uploader.

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
- Flask-SQLAlchemy (SQLite locally; PostgreSQL on Render)
- Flask-Login
- Bootstrap 5 + Bootstrap Icons
- Pillow (image handling)
- qrcode (signed invoice verification QR codes)

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

## Render Deployment

The root `render.yaml` defines a paid Singapore web service, a managed PostgreSQL database, a persistent disk for receipt uploads, and a database-backed `/healthz` check. The Render service starts through `wsgi:app`, which initializes the schema.

1. Before publishing, rotate any credentials that were previously committed. Use a new, unique first-admin password; Render generates a new `BRILLIANTPAY_SECRET_KEY`.
2. Publish the `render-deploy` branch and create a Blueprint in Render from that branch. Review the resources and charges before deploying. Do not deploy the existing `main` branch.
3. During Blueprint creation, enter the first-admin username, email, and a strong unique password when prompted. Render creates a fresh database; local payments and receipt images are not migrated.
4. After the first successful deployment and admin login, remove `BRILLIANTPAY_ADMIN_PASSWORD` from the web service's Render environment settings. The administrator account remains in PostgreSQL.
5. Confirm the service health check passes, then verify sign-in, payment creation, receipt upload, invoice generation, and bank review.
6. Back up the PostgreSQL database and `/var/data/uploads` separately. Persistent disks are not backups.

The deployment branch is intended to be a clean snapshot without the tracked local database or earlier commit history. The existing branch and local database remain preserved. This does not erase old commits from the GitHub repository; rotate exposed credentials and keep repository access restricted. If historical payment data must be removed from GitHub entirely, that requires a separate coordinated history purge.

For local production-style startup, set `BRILLIANTPAY_SECRET_KEY` in the process environment before running `start_brilliantpay.bat`. Never place real credentials in source control.

Receipt uploads are limited to 8 MB and verified as images. The app also records payment create, update, and delete actions in the audit log.

---
Built for Brilliant Driving School 🚗💨

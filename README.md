# BrilliantPay

**Financial data management web app for Brilliant Driving School**

A clean, modern Flask application for recording student payment details (bank & mobile money) together with receipt photos.

## Features

- **Catchy name**: BrilliantPay – the finance hub that keeps Brilliant Driving School on the road to success.
- **Role-based access**
  - **Super user** (`admin`): unlimited privileges – can add payments *and* modify/delete any record.
  - **Staff user**: can add bank (CRDB / NMB) and mobile money payments.
- **Login & Signup** pages with modern classic UI matching the school logo colours (navy, red, yellow accents).
- **Forgot Password**: generates a temporary **fruit-based** password (e.g. `Mango42`, `Pineapple17`).
- **Dashboard** with left sidebar navigation:
  1. Add payment details – Bank (CRDB & NMB)
  2. Add payment details – Mobile payments
  3. Modify Payment details (super user only)
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

### Default Super User
- **Username**: `admin`
- **Password**: `BrilliantAdmin1`

Change this password after first login in a real deployment!

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

## Next Steps (as we expand)
- Amount reports / filters by date or student
- Export to Excel / PDF
- Change-password page after temp login
- Email delivery of temporary passwords
- More payment fields (course type, instalment number, etc.)

---
Built for Brilliant Driving School 🚗💨

# BrilliantPay

**Financial data management web app for Brilliant Driving School**

A clean, modern Flask application for recording student payment details (bank & mobile money) together with receipt photos.

## Features

- **Catchy name**: BrilliantPay – the finance hub that keeps Brilliant Driving School on the road to success.
- **Role-based access**
  - **Super user**: can add, view, edit, export, and delete payments, but cannot verify or reject bank records.
  - **Staff**: can upload payments and view the dashboard, existing register, and receipt files; they cannot edit, export, delete, or review payments.
  - **Bank reviewer**: can view existing payments and receipts and verify/reject bank records, but cannot add, edit, delete, export, or access invoice-printing pages.
  - **Payment entry**: can access the dashboard and add bank/mobile payments only; cannot browse existing records, view receipts, or review bank payments.
- **Course fees**: Basic (TZS 300,000), Public Service Vehicles (PSV) (TZS 250,000), and Heavy Vehicles (HGV) (TZS 350,000). Record the actual amount received separately.
- **Login & Signup** pages with modern classic UI matching the school logo colours (navy, red, yellow accents).
- **Profile dashboard** for password updates, choosing from 25 illustrated avatars, and optionally adding contact email and phone details.
- **First-login avatar selection**: every user chooses a team avatar before using the app; usernames are unchanged.
- **Team messages**: users can choose a teammate from the message-board dropdown, start private conversations, and track unread messages from the notification bell.
- **Live unread-message alerts** refresh automatically and play a brief sound for new incoming messages.
- Super users can reset all active users to unique temporary fruit-based passwords at once or reset an individual account. Each affected user must set a strong new password the next time they sign in; the one-time passwords are displayed only to the super user for secure sharing.
- The dashboard welcomes each signed-in user with a Nairobi-time greeting. Reviewers are notified when bank payments with receipts are awaiting verification. Successful logins display a short branded loading bar.
- **Existing payments register** with search and XLSX export for super users; staff and bank reviewers have read-only access.
- **Payment invoices**: recording a bank or mobile payment opens a printable invoice with a signed, RGB-styled QR code for verification. The first two invoices for a payment can be generated from Existing Payments without additional authorization; further invoices require an active super-user password.
- **Bank receipt review**: bank payments start pending verification; only bank reviewers can verify or reject after checking an official bank record, with the reviewer and notes recorded. Reused references for the same bank are flagged. This workflow does not establish authenticity from an image alone.
- **Idle-session timeout** signs users out after four minutes without activity.
- Login, signup, and forgot-password backgrounds have previous/next arrows to browse four photographic images in `static/img/`.
- **Password resets**: the public Forgot Password page explains how to use a temporary password. Super users can reset all active accounts at once or reset individual accounts from the Profile Dashboard. One-time passwords are shown once and affected users must set a strong password after signing in.
- **Role-based dashboard navigation** limits each account to its allowed payment functions.
- The dashboard provides an email contact action for Brilliant Driving School.
- Dashboard dates, password-request timestamps, review timestamps, invoice issue times, and server-generated date defaults use Nairobi East Africa Time (EAT, UTC+3).
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

## Windows Desktop Installer

The desktop client opens the existing BrilliantPay server in a standalone Windows application window. It does not run a second app or keep a separate database; payments, accounts, and messages remain shared on the SSH-hosted server. An HTTPS server address is required for remote connections.

To build on Windows:

1. Install Python and Inno Setup 6.
2. Create or activate a virtual environment, then install project dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Run `build_windows.bat`.
4. The installer is created at `dist\installer\BrilliantPaySetup.exe`. Each build uses a unique `dist\build-*` folder for the app bundle, avoiding Windows file locks from older builds. If Inno Setup is not on `PATH`, use the build output's `ISCC.exe /DBuildRoot="dist\build-..." installer.iss` command to create the installer.

On first launch, enter the HTTPS address of the hosted app. The installer also adds a **Configure BrilliantPay Server** shortcut for changing it later. The address is saved in `%LOCALAPPDATA%\BrilliantPay\desktop.json`. Install Microsoft Edge WebView2 Runtime if the desktop window cannot start.

### Provisioning the First Super User
No default super-user credentials are created automatically. Before the first start, set these environment variables for the system administrator:

```text
BRILLIANTPAY_ADMIN_USERNAME=admin
BRILLIANTPAY_ADMIN_EMAIL=admin@example.com
BRILLIANTPAY_ADMIN_PASSWORD=<strong-unique-password>
```

The account is created once when `python app.py` initializes the database. Do not put these values in source control.

### Provisioning the Restricted Accounts
To create the bank reviewer and payment-entry accounts in an existing database, set all three variables for each role before starting the app:

```text
BRILLIANTPAY_REVIEWER_USERNAME=<reviewer-username>
BRILLIANTPAY_REVIEWER_EMAIL=<reviewer-email>
BRILLIANTPAY_REVIEWER_PASSWORD=<unique-password-at-least-12-characters>
BRILLIANTPAY_ENTRY_USERNAME=<entry-username>
BRILLIANTPAY_ENTRY_EMAIL=<entry-email>
BRILLIANTPAY_ENTRY_PASSWORD=<unique-password-at-least-12-characters>
```

The accounts are created once if that role does not already exist. Remove the password variables after successful startup. The reviewer navigation contains Dashboard, Validate Payments, and Existing Payments. The payment-entry navigation contains Dashboard and Bank/Mobile Payments only.

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
    ├── messages.html
    ├── message_thread.html
    ├── add_bank.html
    ├── add_mobile.html
    ├── modify_payments.html
    └── edit_payment.html
```

## Render Deployment

The root `render.yaml` defines a paid Singapore web service, a managed PostgreSQL database, a persistent disk for receipt uploads, and a database-backed `/healthz` check. The Render service starts through `wsgi:app`, which initializes the schema. For a fresh database, it provisions the administrator, one bank reviewer, and one payment-entry account from their environment variables.

1. Before publishing, rotate any credentials that were previously committed. Use new, unique passwords for both scoped accounts; Render generates a new `BRILLIANTPAY_SECRET_KEY`.
2. Publish the `render-deploy` branch and create a Blueprint in Render from that branch. Review the resources and charges before deploying. Do not deploy the existing `main` branch.
3. During Blueprint creation, enter unique usernames and emails and strong passwords (at least 12 characters) for the administrator, bank reviewer, and payment-entry account when prompted. Render creates a fresh database; local payments and receipt images are not migrated.
4. After the first successful deployment, remove the three account password variables from the web service's Render environment settings. The accounts remain in PostgreSQL.
5. Confirm the service health check passes, then verify sign-in, payment creation, receipt upload, invoice generation, and bank review.
6. Back up the PostgreSQL database and `/var/data/uploads` separately. Persistent disks are not backups.

The deployment branch is intended to be a clean snapshot without the tracked local database or earlier commit history. The existing branch and local database remain preserved. This does not erase old commits from the GitHub repository; rotate exposed credentials and keep repository access restricted. If historical payment data must be removed from GitHub entirely, that requires a separate coordinated history purge.

For local production-style startup, place `BRILLIANTPAY_SECRET_KEY` in the ignored `.env` file before running `start_brilliantpay.bat`. The launcher loads local BrilliantPay environment variables from that file. Never place real credentials in source control.

Receipt uploads are limited to 8 MB and verified as images. The app also records payment create, update, and delete actions in the audit log.

---
Built for Brilliant Driving School 🚗💨

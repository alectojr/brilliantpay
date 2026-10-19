#!/usr/bin/env python3
"""
BrilliantPay - Financial Data Management for Brilliant Driving School
A simple Flask web app for recording student payments with receipt photos.
"""

import os
import random
import secrets
import hmac
import math
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Flask, render_template, redirect, url_for, flash, request,
    send_from_directory, abort, session
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
from sqlalchemy import or_

# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("BRILLIANTPAY_SECRET_KEY")
if not app.config["SECRET_KEY"]:
    if os.environ.get("BRILLIANTPAY_ENV", "development") == "production":
        raise RuntimeError("BRILLIANTPAY_SECRET_KEY must be set in production")
    app.config["SECRET_KEY"] = secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("BRILLIANTPAY_ENV") == "production"
database_url = os.environ.get("BRILLIANTPAY_DATABASE_URL")
if database_url:
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        os.environ.get("BRILLIANTPAY_DATABASE", "brilliantpay.db")
    )
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "static", "uploads"
)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff"}
BANK_PAYMENT_METHODS = (
    "CRDB", "NMB", "NBC", "Stanbic", "Absa", "Standard Chartered",
    "Exim", "KCB", "Equity", "DTB", "NCBA", "Azania", "Amana",
    "Access Bank", "Bank of Baroda", "BOA", "DCB", "Mkombozi",
    "Maendeleo", "TPB", "Uchumi"
)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"

# Fruit list for temporary passwords
FRUITS = [
    "Mango", "Pineapple", "Banana", "Orange", "Apple", "Grape",
    "Watermelon", "Strawberry", "Kiwi", "Peach", "Papaya", "Guava",
    "Passion", "Lychee", "Dragonfruit", "Coconut", "Avocado", "Lemon"
]

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="staff")  # 'super' or 'staff'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    payments = db.relationship("Payment", backref="uploader", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_super(self):
        return self.role == "super"


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(150), nullable=False)
    payment_category = db.Column(db.String(30), nullable=False)  # 'bank' or 'mobile'
    form_of_payment = db.Column(db.String(50), nullable=False)   # CRDB, NMB, M-Pesa, etc.
    amount = db.Column(db.Float, nullable=False)
    reference = db.Column(db.String(100))
    receipt_filename = db.Column(db.String(255))
    notes = db.Column(db.Text)
    payment_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(30), nullable=False)
    payment_id = db.Column(db.Integer)
    details = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_csrf_token():
    def csrf_token():
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return token
    return {"csrf_token": csrf_token}


@app.before_request
def protect_post_requests():
    if request.method == "POST":
        submitted = request.form.get("_csrf_token", "")
        expected = session.get("csrf_token", "")
        if not expected or not submitted or not hmac.compare_digest(submitted, expected):
            abort(400, description="Invalid or missing security token.")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_fruit_password():
    fruit = random.choice(FRUITS)
    number = random.randint(10, 99)
    return f"{fruit}{number}"


def super_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_super():
            flash("You need super-user privileges to access this page.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


def safe_redirect_target(target):
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/"):
        return None
    return target


def save_receipt(file):
    """Save uploaded receipt image, optionally compress a bit, return filename."""
    if not file or file.filename == "":
        return None
    if not allowed_file(file.filename):
        return None
    filename = secure_filename(file.filename)
    if not filename:
        return None
    # Make unique
    name, ext = os.path.splitext(filename)
    unique_name = f"{name}_{secrets.token_hex(6)}{ext}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)

    # Save & lightly optimize with Pillow
    try:
        img = Image.open(file.stream)
        img.verify()
        file.stream.seek(0)
        img = Image.open(file.stream)
        img = img.convert("RGB") if img.mode in ("RGBA", "P") else img
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        img.save(filepath, quality=85, optimize=True)
    except (OSError, ValueError):
        return None
    return unique_name


def record_audit(action, payment_id=None, details=None):
    db.session.add(AuditLog(
        user_id=current_user.id,
        action=action,
        payment_id=payment_id,
        details=details
    ))


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message=error.description), 400


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", code=404, message="The page you requested was not found."), 404


@app.errorhandler(413)
def request_too_large(error):
    return render_template("error.html", code=413, message="The uploaded file is too large. Maximum size is 8 MB."), 413


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template("error.html", code=500, message="Something went wrong. Please try again."), 500


# ---------------------------------------------------------------------------
# Routes – Auth
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=True)
            flash(f"Welcome back, {user.username}!", "success")
            next_page = safe_redirect_target(request.args.get("next"))
            return redirect(next_page or url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("All fields are required.", "warning")
            return render_template("signup.html")
        if password != confirm:
            flash("Passwords do not match.", "warning")
            return render_template("signup.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "warning")
            return render_template("signup.html")
        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "danger")
            return render_template("signup.html")
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return render_template("signup.html")

        # Only allow staff signups; super is created on init
        user = User(username=username, email=email, role="staff")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created successfully! You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    temp_password = None
    if request.method == "POST":
        if os.environ.get("BRILLIANTPAY_ALLOW_DEMO_PASSWORD_RESET") != "1":
            flash("Please contact the system administrator to reset your password.", "info")
            return render_template("forgot_password.html")
        username_or_email = request.form.get("username_or_email", "").strip()
        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email.lower())
        ).first()
        if user:
            temp = generate_fruit_password()
            user.set_password(temp)
            db.session.commit()
            temp_password = temp
            flash(
                "A temporary fruit-based password has been generated. "
                "Please log in and change it soon.",
                "info"
            )
        else:
            flash("No account found with that username or email.", "danger")
    return render_template("forgot_password.html", temp_password=temp_password)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Your current password is incorrect.", "danger")
        elif len(new_password) < 6:
            flash("New password must be at least 6 characters.", "warning")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "warning")
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash("Your password has been changed successfully.", "success")
            return redirect(url_for("profile"))

    return render_template("profile.html")


# ---------------------------------------------------------------------------
# Routes – Dashboard & Payments
# ---------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    total_payments = Payment.query.count()
    total_amount = db.session.query(db.func.sum(Payment.amount)).scalar() or 0
    recent = Payment.query.order_by(Payment.created_at.desc()).limit(8).all()
    return render_template(
        "dashboard.html",
        total_payments=total_payments,
        total_amount=total_amount,
        recent=recent
    )


@app.route("/payments/bank", methods=["GET", "POST"])
@login_required
def add_bank_payment():
    """Add payment details for CRDB and NMB (bank transfers)."""
    if request.method == "POST":
        student_name = request.form.get("student_name", "").strip()
        form_of_payment = request.form.get("form_of_payment", "")
        amount = request.form.get("amount", "0")
        reference = request.form.get("reference", "").strip()
        notes = request.form.get("notes", "").strip()
        payment_date_str = request.form.get("payment_date", "")
        receipt = request.files.get("receipt")

        if not student_name or form_of_payment not in BANK_PAYMENT_METHODS:
            flash("Student name and a valid bank are required.", "warning")
            return render_template("add_bank.html", bank_payment_methods=BANK_PAYMENT_METHODS)

        try:
            amount = float(amount)
            if not math.isfinite(amount) or amount <= 0 or amount > 1000000000:
                raise ValueError
        except ValueError:
            flash("Please enter a valid positive amount.", "warning")
            return render_template("add_bank.html", bank_payment_methods=BANK_PAYMENT_METHODS)

        try:
            payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            payment_date = datetime.utcnow().date()

        filename = save_receipt(receipt) if receipt else None
        if not filename:
            flash("Please upload a valid receipt image (PNG, JPG, JPEG, WEBP, GIF, BMP, or TIFF).", "warning")
            return render_template("add_bank.html", bank_payment_methods=BANK_PAYMENT_METHODS)

        payment = Payment(
            student_name=student_name,
            payment_category="bank",
            form_of_payment=form_of_payment,
            amount=amount,
            reference=reference,
            receipt_filename=filename,
            notes=notes,
            payment_date=payment_date,
            uploaded_by_id=current_user.id
        )
        db.session.add(payment)
        record_audit("created", details=f"Bank payment for {student_name}")
        db.session.commit()
        flash(f"Bank payment for {student_name} recorded successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_bank.html", bank_payment_methods=BANK_PAYMENT_METHODS)


@app.route("/payments/mobile", methods=["GET", "POST"])
@login_required
def add_mobile_payment():
    """Add payment details for mobile money (M-Pesa, Tigo Pesa, Airtel Money, etc.)."""
    if request.method == "POST":
        student_name = request.form.get("student_name", "").strip()
        form_of_payment = request.form.get("form_of_payment", "")
        amount = request.form.get("amount", "0")
        reference = request.form.get("reference", "").strip()
        notes = request.form.get("notes", "").strip()
        payment_date_str = request.form.get("payment_date", "")
        receipt = request.files.get("receipt")

        valid_mobile = ("M-Pesa", "Tigo Pesa", "Airtel Money", "HaloPesa", "Other Mobile")
        if not student_name or form_of_payment not in valid_mobile:
            flash("Student name and valid mobile payment method are required.", "warning")
            return render_template("add_mobile.html")

        try:
            amount = float(amount)
            if not math.isfinite(amount) or amount <= 0 or amount > 1000000000:
                raise ValueError
        except ValueError:
            flash("Please enter a valid positive amount.", "warning")
            return render_template("add_mobile.html")

        try:
            payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            payment_date = datetime.utcnow().date()

        filename = save_receipt(receipt) if receipt else None
        if not filename:
            flash("Please upload a valid receipt image (PNG, JPG, JPEG, WEBP, GIF, BMP, or TIFF).", "warning")
            return render_template("add_mobile.html")

        payment = Payment(
            student_name=student_name,
            payment_category="mobile",
            form_of_payment=form_of_payment,
            amount=amount,
            reference=reference,
            receipt_filename=filename,
            notes=notes,
            payment_date=payment_date,
            uploaded_by_id=current_user.id
        )
        db.session.add(payment)
        record_audit("created", details=f"Mobile payment for {student_name}")
        db.session.commit()
        flash(f"Mobile payment for {student_name} recorded successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_mobile.html")


@app.route("/payments/modify")
@login_required
def modify_payments():
    """List payments for all staff; destructive actions remain super-user-only."""
    search = request.args.get("q", "").strip()
    page = max(request.args.get("page", 1, type=int), 1)
    query = Payment.query
    if search:
        term = f"%{search}%"
        query = query.filter(or_(Payment.student_name.ilike(term), Payment.reference.ilike(term)))
    pagination = query.order_by(Payment.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    selected_student = request.args.get("student_name", "").strip()
    return render_template(
        "modify_payments.html",
        payments=pagination.items,
        pagination=pagination,
        search=search,
        selected_student=selected_student
    )


@app.route("/payments/<int:payment_id>/edit", methods=["GET", "POST"])
@login_required
@super_required
def edit_payment(payment_id):
    payment = db.session.get(Payment, payment_id)
    if not payment:
        abort(404)

    if request.method == "POST":
        payment.student_name = request.form.get("student_name", "").strip()
        payment.form_of_payment = request.form.get("form_of_payment", payment.form_of_payment)
        try:
            payment.amount = float(request.form.get("amount", payment.amount))
        except ValueError:
            flash("Invalid amount.", "warning")
            return render_template("edit_payment.html", payment=payment)
        payment.reference = request.form.get("reference", "").strip()
        payment.notes = request.form.get("notes", "").strip()
        try:
            payment.payment_date = datetime.strptime(
                request.form.get("payment_date"), "%Y-%m-%d"
            ).date()
        except (ValueError, TypeError):
            pass

        # Optional new receipt
        receipt = request.files.get("receipt")
        if receipt and receipt.filename:
            new_fn = save_receipt(receipt)
            if new_fn:
                # Optionally delete old file
                if payment.receipt_filename:
                    old_path = os.path.join(app.config["UPLOAD_FOLDER"], payment.receipt_filename)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except OSError:
                            pass
                payment.receipt_filename = new_fn

        payment.updated_at = datetime.utcnow()
        record_audit("updated", payment.id, f"Updated payment for {payment.student_name}")
        db.session.commit()
        flash("Payment updated successfully.", "success")
        return redirect(url_for("modify_payments"))

    return render_template("edit_payment.html", payment=payment)


@app.route("/payments/<int:payment_id>/delete", methods=["POST"])
@login_required
@super_required
def delete_payment(payment_id):
    payment = db.session.get(Payment, payment_id)
    if not payment:
        abort(404)
    # Delete receipt file if exists
    if payment.receipt_filename:
        path = os.path.join(app.config["UPLOAD_FOLDER"], payment.receipt_filename)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    db.session.delete(payment)
    record_audit("deleted", payment.id, f"Deleted payment for {payment.student_name}")
    db.session.commit()
    flash("Payment deleted.", "info")
    return redirect(url_for("modify_payments"))


@app.route("/uploads/<filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ---------------------------------------------------------------------------
# Init DB & create default super user
# ---------------------------------------------------------------------------
def init_db():
    with app.app_context():
        db.create_all()
        bootstrap_password = os.environ.get("BRILLIANTPAY_ADMIN_PASSWORD")
        if bootstrap_password and not User.query.filter_by(role="super").first():
            super_user = User(
                username=os.environ.get("BRILLIANTPAY_ADMIN_USERNAME", "admin"),
                email=os.environ.get("BRILLIANTPAY_ADMIN_EMAIL", "admin@brilliantdriving.school"),
                role="super"
            )
            super_user.set_password(bootstrap_password)
            db.session.add(super_user)
            db.session.commit()
            print(f">>> Super user created: username={super_user.username}")
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


if __name__ == "__main__":
    init_db()
    app.run(
        host=os.environ.get("BRILLIANTPAY_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("BRILLIANTPAY_DEBUG") == "1"
    )

#!/usr/bin/env python3
"""
BrilliantPay - Financial Data Management for Brilliant Driving School
A simple Flask web app for recording student payments with receipt photos.
"""

import os
import secrets
import hmac
import json
import base64
import math
import re
import time
from io import BytesIO
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Flask, render_template, redirect, url_for, flash, request,
    send_from_directory, abort, session, send_file, jsonify, make_response, g
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import qrcode
from sqlalchemy import inspect, or_, text
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

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
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["IDLE_TIMEOUT_SECONDS"] = 4 * 60
database_url = os.environ.get("BRILLIANTPAY_DATABASE_URL")
if database_url:
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        os.environ.get("BRILLIANTPAY_DATABASE", "brilliantpay.db")
    )
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.abspath(os.environ.get(
    "BRILLIANTPAY_UPLOAD_FOLDER",
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "static", "uploads")
))
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff"}
NAIROBI_TZ = timezone(timedelta(hours=3), name="EAT")


def utcnow_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def nairobi_now():
    return datetime.now(NAIROBI_TZ)


def nairobi_greeting(value=None):
    hour = (value or nairobi_now()).hour
    if hour < 5 or hour >= 21:
        return "Good night"
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def format_eat(value, format_string="%d %b %Y %H:%M"):
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(NAIROBI_TZ).strftime(format_string)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"


@app.get("/healthz")
def healthz():
    db.session.execute(text("SELECT 1"))
    return jsonify(status="ok")


BANK_PAYMENT_METHODS = (
    "CRDB", "NMB", "NBC", "Stanbic", "Absa", "Standard Chartered",
    "Exim", "KCB", "Equity", "DTB", "NCBA", "Azania", "Amana",
    "Access Bank", "Bank of Baroda", "BOA", "DCB", "Mkombozi",
    "Maendeleo", "TPB", "Uchumi"
)
COURSE_FEES = {
    "Basic": 300000,
    "Public Service Vehicles (PSV)": 250000,
    "Heavy Vehicles (HGV)": 350000,
}

# Fruit list for temporary passwords
FRUITS = [
    "Mango", "Pineapple", "Banana", "Orange", "Apple", "Grape",
    "Watermelon", "Strawberry", "Kiwi", "Peach", "Papaya", "Guava",
    "Passion", "Lychee", "Dragonfruit", "Coconut", "Avocado", "Lemon"
]
AVATAR_NAMES = (
    "Amani", "Zuri", "Baraka", "Neema", "Imani", "Jabari", "Nia",
    "Kito", "Asha", "Taji", "Sanaa", "Amara", "Enzi", "Kendi",
    "Lulu", "Pendo", "Tumaini", "Azizi", "Juma", "Malaika",
    "Khamisi", "Zawadi", "Ayo", "Faraja", "Rehema",
)
AVATAR_IDS_IN_ORDER = (
    "amani", "zuri", "baraka", "neema", "imani", "jabari",
    *(f"avatar-{index:02d}" for index in range(7, 26)),
)
AVATAR_SKIN_TONES = ("#6f3f2a", "#8d5739", "#b87953", "#d99b72", "#f0c4a0")
AVATAR_HAIR_COLORS = ("#211916", "#3b241b", "#6a3d2c", "#1a1b29", "#7b4a2d")
AVATAR_BACKGROUNDS = ("#f3d9d4", "#dbe9f5", "#e7e4f8", "#d9eee6", "#f7e9c9")
AVATAR_SHIRT_COLORS = ("#c41e3a", "#0b2545", "#267f76", "#7655a5", "#d28a2e")
AVATARS = tuple(
    {
        "id": AVATAR_IDS_IN_ORDER[index],
        "name": name,
        "skin": AVATAR_SKIN_TONES[index % len(AVATAR_SKIN_TONES)],
        "hair": AVATAR_HAIR_COLORS[(index // 5) % len(AVATAR_HAIR_COLORS)],
        "background": AVATAR_BACKGROUNDS[(index * 2 // 5) % len(AVATAR_BACKGROUNDS)],
        "shirt": AVATAR_SHIRT_COLORS[(index // 5 + index % 5) % len(AVATAR_SHIRT_COLORS)],
        "style": index % 5,
    }
    for index, name in enumerate(AVATAR_NAMES)
)
AVATAR_IDS = {avatar["id"] for avatar in AVATARS}

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="staff")  # 'super' or 'staff'
    avatar_id = db.Column(db.String(40))
    phone_number = db.Column(db.String(40))
    contact_email = db.Column(db.String(120))
    password_change_required = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    is_active = db.Column(db.Boolean, default=True)

    payments = db.relationship(
        "Payment",
        back_populates="uploader",
        foreign_keys="Payment.uploaded_by_id",
        lazy=True
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_super(self):
        return self.role == "super"

    def is_bank_reviewer(self):
        return self.role == "bank_reviewer"

    def is_payment_entry(self):
        return self.role == "payment_entry"

    def can_add_payments(self):
        return self.role in {"super", "staff", "payment_entry"}

    def can_view_payments(self):
        return self.role in {"super", "staff", "bank_reviewer"}


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(150), nullable=False)
    course = db.Column(db.String(100))
    payment_category = db.Column(db.String(30), nullable=False)  # 'bank' or 'mobile'
    form_of_payment = db.Column(db.String(50), nullable=False)   # CRDB, NMB, M-Pesa, etc.
    amount = db.Column(db.Float, nullable=False)
    reference = db.Column(db.String(100))
    receipt_filename = db.Column(db.String(255))
    notes = db.Column(db.Text)
    payment_date = db.Column(db.Date, nullable=False, default=lambda: nairobi_now().date())
    bank_review_status = db.Column(db.String(20))
    bank_reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    bank_reviewed_at = db.Column(db.DateTime)
    bank_review_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    existing_invoice_count = db.Column(db.Integer, nullable=False, default=0)
    uploader = db.relationship(
        "User",
        back_populates="payments",
        foreign_keys=[uploaded_by_id]
    )
    bank_reviewer = db.relationship("User", foreign_keys=[bank_reviewer_id])


class InvoiceIssue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payment.id"), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    snapshot = db.Column(db.Text, nullable=False)
    signature = db.Column(db.String(64), nullable=False)
    source = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow_naive, nullable=False)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(30), nullable=False)
    payment_id = db.Column(db.Integer)
    details = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=utcnow_naive, nullable=False)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    body = db.Column(db.String(2000), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow_naive, nullable=False, index=True)
    read_at = db.Column(db.DateTime)
    sender = db.relationship("User", foreign_keys=[sender_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])


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

    def avatar_image_url(avatar_id):
        return url_for(
            "avatar_image",
            avatar_id=avatar_id if avatar_id in AVATAR_IDS else "amani"
        )

    unread_message_count = (
        Message.query.filter_by(
            recipient_id=current_user.id,
            read_at=None
        ).count()
        if current_user.is_authenticated
        else 0
    )
    return {
        "csrf_token": csrf_token,
        "avatar_image_url": avatar_image_url,
        "unread_message_count": unread_message_count,
        "unread_notifications": (
            Message.query.filter_by(
                recipient_id=current_user.id,
                read_at=None
            ).order_by(Message.created_at.desc(), Message.id.desc()).limit(5).all()
            if current_user.is_authenticated
            else []
        ),
        "course_fees": COURSE_FEES,
        "bank_payment_methods": BANK_PAYMENT_METHODS,
        "format_eat": format_eat,
        "nairobi_today": nairobi_now().date().isoformat(),
        "show_login_loader": g.pop("show_login_loader", False),
    }


@app.get("/avatars/<avatar_id>.svg")
def avatar_image(avatar_id):
    avatar = next((item for item in AVATARS if item["id"] == avatar_id), None)
    if not avatar:
        abort(404)

    hairstyle = (
        f'<path d="M22 45c0-23 13-34 28-34s28 11 28 34c-8-9-17-13-28-13S30 36 22 45z" fill="{avatar["hair"]}"/>',
        f'<path d="M19 48c0-25 12-37 31-37s31 12 31 37v20H69V47c-6-8-12-11-19-11s-14 3-19 11v21H19z" fill="{avatar["hair"]}"/>',
        f'<path d="M19 43c0-21 12-32 31-32s31 11 31 32H68c-4-7-10-10-18-10s-14 3-18 10z" fill="{avatar["hair"]}"/><circle cx="23" cy="27" r="10" fill="{avatar["hair"]}"/><circle cx="39" cy="15" r="9" fill="{avatar["hair"]}"/><circle cx="56" cy="14" r="10" fill="{avatar["hair"]}"/><circle cx="73" cy="26" r="10" fill="{avatar["hair"]}"/>',
        f'<path d="M19 44c0-23 12-34 31-34s31 11 31 34c-8-8-18-12-31-12S27 36 19 44z" fill="{avatar["hair"]}"/><circle cx="24" cy="17" r="9" fill="{avatar["hair"]}"/><circle cx="76" cy="17" r="9" fill="{avatar["hair"]}"/>',
        f'<path d="M19 47c0-25 12-37 31-37s31 12 31 37l-9-7-7 6-7-6-8 7-8-7-8 7-7-6z" fill="{avatar["hair"]}"/>',
    )[avatar["style"]]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" role="img">
<circle cx="50" cy="50" r="50" fill="{avatar["background"]}"/>
<path d="M10 100c2-20 16-31 40-31s38 11 40 31" fill="{avatar["shirt"]}"/>
<path d="M40 64h20v15H40z" fill="{avatar["skin"]}"/>
<ellipse cx="50" cy="47" rx="25" ry="29" fill="{avatar["skin"]}"/>
<path d="M25 42c0-22 10-32 25-32s25 10 25 32c-7-8-15-12-25-12S32 34 25 42z" fill="{avatar["hair"]}"/>
{hairstyle}
<path d="M37 48h4m18 0h4" stroke="#38251f" stroke-width="3" stroke-linecap="round"/>
<path d="M45 61q5 4 10 0" fill="none" stroke="#7f3e39" stroke-width="2" stroke-linecap="round"/>
</svg>'''
    response = make_response(svg)
    response.mimetype = "image/svg+xml"
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.before_request
def enforce_idle_timeout():
    g.show_login_loader = session.pop("show_login_loader", False)
    if not current_user.is_authenticated:
        return

    now = time.time()
    last_activity = session.get("last_activity")
    if not isinstance(last_activity, (int, float)) or now - last_activity >= app.config["IDLE_TIMEOUT_SECONDS"]:
        logout_user()
        session.pop("last_activity", None)
        flash("You were logged out after four minutes of inactivity.", "warning")
        return redirect(url_for("login"))

    session["last_activity"] = now


@app.before_request
def require_avatar_selection():
    if (
        current_user.is_authenticated
        and current_user.avatar_id not in AVATAR_IDS
        and request.endpoint not in {"static", "choose_avatar", "logout", "session_activity"}
    ):
        return redirect(url_for("choose_avatar"))


@app.before_request
def require_password_change():
    if (
        current_user.is_authenticated
        and current_user.password_change_required
        and request.endpoint not in {
            "static", "change_password", "logout", "session_activity"
        }
    ):
        next_page = request.full_path if request.query_string else request.path
        return redirect(url_for("change_password", next=next_page))


@app.before_request
def protect_post_requests():
    if request.method == "POST":
        submitted = request.form.get("_csrf_token", "") or request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf_token", "")
        if not expected or not submitted or not hmac.compare_digest(submitted, expected):
            abort(400, description="Invalid or missing security token.")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_fruit_password():
    fruits = (secrets.choice(FRUITS) for _ in range(5))
    suffix = secrets.randbelow(10000)
    return f"{'-'.join(fruits)}-{suffix:04d}"


def super_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_super():
            flash("You need super-user privileges to access this page.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def safe_redirect_target(target):
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/"):
        return None
    return target


def password_policy_error(password):
    character_types = (
        any(character.islower() for character in password),
        any(character.isupper() for character in password),
        any(character.isdigit() for character in password),
        any(not character.isalnum() for character in password),
    )
    if len(password) < 12:
        return "Password must be at least 12 characters."
    if sum(character_types) < 3:
        return "Password must include at least three of: lowercase, uppercase, number, and symbol."
    return None


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


def has_duplicate_bank_reference(method, reference, exclude_payment_id=None):
    normalized_reference = reference.strip().lower()
    if not normalized_reference:
        return False
    query = Payment.query.filter(
        Payment.payment_category == "bank",
        Payment.form_of_payment == method,
        db.func.lower(db.func.trim(Payment.reference)) == normalized_reference
    )
    if exclude_payment_id is not None:
        query = query.filter(Payment.id != exclude_payment_id)
    return query.first() is not None


def invoice_snapshot(payment):
    return {
        "payment_id": payment.id,
        "student_name": payment.student_name,
        "course": payment.course or "",
        "category": payment.payment_category,
        "method": payment.form_of_payment,
        "amount": f"{payment.amount:.2f}",
        "reference": payment.reference or "",
        "payment_date": payment.payment_date.isoformat(),
        "notes": payment.notes or "",
    }


def invoice_signature(snapshot_json):
    return hmac.new(
        app.config["SECRET_KEY"].encode("utf-8"),
        snapshot_json.encode("utf-8"),
        "sha256"
    ).hexdigest()


def create_invoice_issue(payment, source):
    snapshot_json = json.dumps(
        invoice_snapshot(payment), sort_keys=True, separators=(",", ":")
    )
    issue = InvoiceIssue(
        payment_id=payment.id,
        token=secrets.token_urlsafe(32),
        snapshot=snapshot_json,
        signature=invoice_signature(snapshot_json),
        source=source
    )
    db.session.add(issue)
    return issue


def render_invoice(issue):
    snapshot_json = issue.snapshot
    signature_valid = hmac.compare_digest(
        issue.signature, invoice_signature(snapshot_json)
    )

    verification_url = url_for("verify_invoice", token=issue.token, _external=True)
    qr = qrcode.QRCode(box_size=6, border=4)
    qr.add_data(verification_url)
    qr.make(fit=True)
    qr_image = qr.make_image(
        fill_color=(11, 37, 69), back_color=(255, 255, 255)
    ).convert("RGB")
    output = BytesIO()
    qr_image.save(output, format="PNG")
    qr_data_uri = "data:image/png;base64," + base64.b64encode(
        output.getvalue()
    ).decode("ascii")
    return render_template(
        "invoice.html",
        snapshot=json.loads(snapshot_json),
        issue=issue,
        qr_data_uri=qr_data_uri,
        verification_url=verification_url,
        signature_valid=signature_valid
    )


def invoice_issue_is_valid(issue):
    return hmac.compare_digest(
        issue.signature, invoice_signature(issue.snapshot)
    )


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
            session["last_activity"] = time.time()
            flash(f"Welcome back, {user.username}!", "success")
            if user.password_change_required:
                session["show_login_loader"] = False
                return redirect(url_for("change_password", next=request.args.get("next", "")))
            session["show_login_loader"] = True
            next_page = safe_redirect_target(request.args.get("next"))
            if user.avatar_id not in AVATAR_IDS:
                return redirect(url_for("choose_avatar", next=next_page))
            return redirect(next_page or url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/choose-avatar", methods=["GET", "POST"])
@login_required
def choose_avatar():
    if current_user.avatar_id in AVATAR_IDS:
        return redirect(url_for("dashboard"))

    next_page = safe_redirect_target(request.args.get("next"))
    if request.method == "POST":
        avatar_id = request.form.get("avatar_id", "")
        if avatar_id not in AVATAR_IDS:
            flash("Choose one of the available avatars to continue.", "warning")
        else:
            current_user.avatar_id = avatar_id
            db.session.commit()
            flash("Your avatar has been saved.", "success")
            return redirect(next_page or url_for("dashboard"))

    return render_template(
        "avatar_setup.html",
        avatars=AVATARS,
        next_page=next_page
    )


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


@app.get("/forgot-password")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("forgot_password.html")


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if not current_user.password_change_required:
        return redirect(url_for("profile"))

    next_page = safe_redirect_target(request.args.get("next"))
    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        policy_error = password_policy_error(new_password)

        if policy_error:
            flash(policy_error, "warning")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "warning")
        elif current_user.check_password(new_password):
            flash("Choose a password different from your temporary password.", "warning")
        else:
            current_user.set_password(new_password)
            current_user.password_change_required = False
            db.session.commit()
            flash("Your password has been changed successfully.", "success")
            if current_user.avatar_id not in AVATAR_IDS:
                return redirect(url_for("choose_avatar", next=next_page))
            return redirect(next_page or url_for("dashboard"))

    return render_template("change_password.html", next_page=next_page)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("last_activity", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/session/activity", methods=["POST"])
@login_required
def session_activity():
    return "", 204


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        policy_error = password_policy_error(new_password)

        if not current_user.check_password(current_password):
            flash("Your current password is incorrect.", "danger")
        elif policy_error:
            flash(policy_error, "warning")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "warning")
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash("Your password has been changed successfully.", "success")
            return redirect(url_for("profile"))

    users = User.query.order_by(User.username).all() if current_user.is_super() else []
    return render_template("profile.html", users=users, avatars=AVATARS)


@app.post("/profile/contact")
@login_required
def update_profile_contact():
    contact_email = request.form.get("contact_email", "").strip().lower()
    phone_number = request.form.get("phone_number", "").strip()
    avatar_id = request.form.get("avatar_id", "")

    if contact_email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contact_email):
        flash("Enter a valid contact email address or leave it blank.", "warning")
        return redirect(url_for("profile"))
    if len(phone_number) > 40:
        flash("Phone numbers must be 40 characters or fewer.", "warning")
        return redirect(url_for("profile"))
    if avatar_id not in AVATAR_IDS:
        flash("Choose one of the available avatars.", "warning")
        return redirect(url_for("profile"))

    current_user.contact_email = contact_email or None
    current_user.phone_number = phone_number or None
    current_user.avatar_id = avatar_id
    db.session.commit()
    flash("Your profile details have been saved.", "success")
    return redirect(url_for("profile"))


@app.post("/users/reset-passwords")
@login_required
@roles_required("super")
def reset_all_user_passwords():
    active_users = User.query.filter_by(is_active=True).order_by(User.username).all()
    generated_passwords = []
    for user in active_users:
        temporary_password = generate_fruit_password()
        user.set_password(temporary_password)
        user.password_change_required = True
        generated_passwords.append({
            "username": user.username,
            "password": temporary_password
        })
    db.session.commit()

    response = make_response(render_template(
        "profile.html",
        users=User.query.order_by(User.username).all(),
        avatars=AVATARS,
        bulk_reset_passwords=generated_passwords
    ))
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/users/<int:user_id>/reset-password")
@login_required
@roles_required("super")
def reset_user_password(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    temporary_password = generate_fruit_password()
    user.set_password(temporary_password)
    user.password_change_required = True
    db.session.commit()
    flash(f"Generated a temporary password for {user.username}.", "success")
    response = make_response(render_template(
        "profile.html",
        users=User.query.order_by(User.username).all(),
        avatars=AVATARS,
        reset_user=user,
        reset_password=temporary_password
    ))
    response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------
# Routes – Dashboard & Payments
# ---------------------------------------------------------------------------
@app.route("/messages")
@login_required
def messages():
    selected_user_id = request.args.get("user_id", type=int)
    if selected_user_id is not None:
        contact = db.session.get(User, selected_user_id)
        if not contact or not contact.is_active or contact.id == current_user.id:
            abort(404)
        return redirect(url_for("message_thread", user_id=contact.id))

    contacts = User.query.filter(
        User.id != current_user.id,
        User.is_active.is_(True)
    ).order_by(User.username.asc()).all()
    unread_by_sender = dict(
        db.session.query(Message.sender_id, db.func.count(Message.id))
        .filter_by(recipient_id=current_user.id, read_at=None)
        .group_by(Message.sender_id)
        .all()
    )
    return render_template(
        "messages.html",
        contacts=contacts,
        unread_by_sender=unread_by_sender
    )


@app.get("/notifications/unread")
@login_required
def unread_notifications():
    unread_messages = Message.query.filter_by(
        recipient_id=current_user.id,
        read_at=None
    ).order_by(Message.created_at.desc(), Message.id.desc()).limit(5).all()
    return jsonify(
        count=Message.query.filter_by(
            recipient_id=current_user.id,
            read_at=None
        ).count(),
        items=[
            {
                "id": message.id,
                "sender": message.sender.username,
                "preview": message.body[:120],
                "url": url_for("message_thread", user_id=message.sender_id),
            }
            for message in unread_messages
        ]
    )


@app.route("/messages/<int:user_id>", methods=["GET", "POST"])
@login_required
def message_thread(user_id):
    contact = db.session.get(User, user_id)
    if not contact or not contact.is_active or contact.id == current_user.id:
        abort(404)

    thread_messages = Message.query.filter(or_(
        db.and_(
            Message.sender_id == current_user.id,
            Message.recipient_id == contact.id
        ),
        db.and_(
            Message.sender_id == contact.id,
            Message.recipient_id == current_user.id
        )
    )).order_by(Message.created_at.asc(), Message.id.asc()).all()

    unread_messages = [
        message for message in thread_messages
        if message.recipient_id == current_user.id and message.read_at is None
    ]
    if unread_messages:
        read_at = utcnow_naive()
        for message in unread_messages:
            message.read_at = read_at

    draft_message = ""
    if request.method == "POST":
        draft_message = request.form.get("body", "").strip()
        if not draft_message:
            flash("Enter a message before sending.", "warning")
        elif len(draft_message) > 2000:
            flash("Messages must be 2,000 characters or fewer.", "warning")
        else:
            db.session.add(Message(
                sender_id=current_user.id,
                recipient_id=contact.id,
                body=draft_message
            ))
            db.session.commit()
            return redirect(url_for("message_thread", user_id=contact.id))

    if unread_messages:
        db.session.commit()
    return render_template(
        "message_thread.html",
        contact=contact,
        thread_messages=thread_messages,
        draft_message=draft_message
    )


@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.can_view_payments():
        total_payments = Payment.query.count()
        total_amount = db.session.query(db.func.sum(Payment.amount)).scalar() or 0
    else:
        total_payments = 0
        total_amount = 0
    recent = (
        [] if current_user.role in {"payment_entry", "bank_reviewer"}
        else Payment.query.order_by(Payment.created_at.desc()).limit(8).all()
    )
    pending_bank_reviews = (
        Payment.query.filter_by(
            payment_category="bank",
            bank_review_status="pending"
        ).filter(
            Payment.receipt_filename.isnot(None),
            Payment.receipt_filename != ""
        ).count()
        if current_user.is_bank_reviewer()
        else 0
    )
    current_time = nairobi_now()
    greeting = nairobi_greeting(current_time)
    return render_template(
        "dashboard.html",
        total_payments=total_payments,
        total_amount=total_amount,
        recent=recent,
        pending_bank_reviews=pending_bank_reviews,
        greeting=greeting,
        nairobi_time=current_time
    )


@app.route("/payments/bank", methods=["GET", "POST"])
@login_required
@roles_required("super", "staff", "payment_entry")
def add_bank_payment():
    """Add payment details for CRDB and NMB (bank transfers)."""
    if request.method == "POST":
        student_name = request.form.get("student_name", "").strip()
        course = request.form.get("course", "")
        form_of_payment = request.form.get("form_of_payment", "")
        amount = request.form.get("amount", "0")
        reference = request.form.get("reference", "").strip()
        notes = request.form.get("notes", "").strip()
        payment_date_str = request.form.get("payment_date", "")
        receipt = request.files.get("receipt")

        if not student_name or course not in COURSE_FEES or form_of_payment not in BANK_PAYMENT_METHODS:
            flash("Student name, course, and a valid bank are required.", "warning")
            return render_template(
                "add_bank.html",
                bank_payment_methods=BANK_PAYMENT_METHODS,
                course_fees=COURSE_FEES
            )

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
            payment_date = nairobi_now().date()

        filename = save_receipt(receipt) if receipt else None
        if not filename:
            flash("Please upload a valid receipt image (PNG, JPG, JPEG, WEBP, GIF, BMP, or TIFF).", "warning")
            return render_template(
                "add_bank.html",
                bank_payment_methods=BANK_PAYMENT_METHODS,
                course_fees=COURSE_FEES
            )

        duplicate_reference = has_duplicate_bank_reference(form_of_payment, reference)
        payment = Payment(
            student_name=student_name,
            course=course,
            payment_category="bank",
            form_of_payment=form_of_payment,
            amount=amount,
            reference=reference,
            receipt_filename=filename,
            notes=notes,
            payment_date=payment_date,
            uploaded_by_id=current_user.id,
            bank_review_status="pending"
        )
        db.session.add(payment)
        db.session.flush()
        issue = create_invoice_issue(payment, "recorded")
        record_audit("created", payment.id, f"Bank payment for {student_name}")
        record_audit("invoice", payment.id, "Initial invoice generated")
        if duplicate_reference:
            record_audit(
                "duplicate_reference",
                payment.id,
                f"Duplicate {form_of_payment} bank reference flagged"
            )
        db.session.commit()
        if duplicate_reference:
            flash(
                f"Payment for {student_name} was recorded and flagged: this {form_of_payment} "
                "reference already appears on another bank payment. Verify it against the official bank record.",
                "warning"
            )
        else:
            flash(
                f"Bank payment for {student_name} recorded and marked pending official verification.",
                "success"
            )
        if current_user.role in {"staff", "payment_entry"}:
            return redirect(url_for("dashboard"))
        return redirect(url_for("view_invoice", token=issue.token))

    return render_template("add_bank.html", bank_payment_methods=BANK_PAYMENT_METHODS)


@app.route("/payments/mobile", methods=["GET", "POST"])
@login_required
@roles_required("super", "staff", "payment_entry")
def add_mobile_payment():
    """Add payment details for mobile money (M-Pesa, Tigo Pesa, Airtel Money, etc.)."""
    if request.method == "POST":
        student_name = request.form.get("student_name", "").strip()
        course = request.form.get("course", "")
        form_of_payment = request.form.get("form_of_payment", "")
        amount = request.form.get("amount", "0")
        reference = request.form.get("reference", "").strip()
        notes = request.form.get("notes", "").strip()
        payment_date_str = request.form.get("payment_date", "")
        receipt = request.files.get("receipt")

        valid_mobile = ("M-Pesa", "Tigo Pesa", "Airtel Money", "HaloPesa", "Other Mobile")
        if not student_name or course not in COURSE_FEES or form_of_payment not in valid_mobile:
            flash("Student name, course, and a valid mobile payment method are required.", "warning")
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
            payment_date = nairobi_now().date()

        filename = save_receipt(receipt) if receipt else None
        if not filename:
            flash("Please upload a valid receipt image (PNG, JPG, JPEG, WEBP, GIF, BMP, or TIFF).", "warning")
            return render_template("add_mobile.html")

        payment = Payment(
            student_name=student_name,
            course=course,
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
        db.session.flush()
        issue = create_invoice_issue(payment, "recorded")
        record_audit("created", payment.id, f"Mobile payment for {student_name}")
        record_audit("invoice", payment.id, "Initial invoice generated")
        db.session.commit()
        flash(f"Mobile payment for {student_name} recorded successfully!", "success")
        if current_user.role in {"staff", "payment_entry"}:
            return redirect(url_for("dashboard"))
        return redirect(url_for("view_invoice", token=issue.token))

    return render_template("add_mobile.html")


@app.route("/payments/modify")
@login_required
@roles_required("super", "staff", "bank_reviewer")
def modify_payments():
    """List payments for all staff; destructive actions remain super-user-only."""
    search = request.args.get("q", "").strip()
    page = max(request.args.get("page", 1, type=int), 1)
    query = payments_query(search)
    pagination = query.order_by(Payment.payment_date.desc(), Payment.id.desc()).paginate(
        page=page, per_page=25, error_out=False
    )
    payment_ids = [payment.id for payment in pagination.items]
    duplicate_reference_keys = set()
    bank_methods = {
        payment.form_of_payment
        for payment in pagination.items
        if payment.payment_category == "bank" and payment.reference
    }
    bank_references = {
        payment.reference.strip().lower()
        for payment in pagination.items
        if payment.payment_category == "bank" and payment.reference and payment.reference.strip()
    }
    if bank_methods and bank_references:
        duplicate_reference_keys = set(
            db.session.query(
                Payment.form_of_payment,
                db.func.lower(db.func.trim(Payment.reference))
            )
            .filter(
                Payment.payment_category == "bank",
                Payment.form_of_payment.in_(bank_methods),
                db.func.lower(db.func.trim(Payment.reference)).in_(bank_references)
            )
            .group_by(
                Payment.form_of_payment,
                db.func.lower(db.func.trim(Payment.reference))
            )
            .having(db.func.count(Payment.id) > 1)
            .all()
        )
    duplicate_payment_ids = {
        payment.id
        for payment in pagination.items
        if payment.payment_category == "bank"
        and payment.reference
        and (payment.form_of_payment, payment.reference.strip().lower()) in duplicate_reference_keys
    }
    latest_invoice_by_payment = {}
    if payment_ids:
        latest_invoice_ids = (
            db.session.query(
                InvoiceIssue.payment_id,
                db.func.max(InvoiceIssue.id).label("latest_id")
            )
            .filter(InvoiceIssue.payment_id.in_(payment_ids))
            .group_by(InvoiceIssue.payment_id)
            .subquery()
        )
        latest_invoice_by_payment = {
            issue.payment_id: issue
            for issue in InvoiceIssue.query.join(
                latest_invoice_ids,
                InvoiceIssue.id == latest_invoice_ids.c.latest_id
            ).all()
        }
    selected_student = request.args.get("student_name", "").strip()
    return render_template(
        "modify_payments.html",
        payments=pagination.items,
        duplicate_payment_ids=duplicate_payment_ids,
        latest_invoice_by_payment=latest_invoice_by_payment,
        pagination=pagination,
        search=search,
        selected_student=selected_student
    )


@app.route("/payments/validate")
@login_required
@roles_required("bank_reviewer")
def validate_bank_payments():
    search = request.args.get("q", "").strip()
    page = max(request.args.get("page", 1, type=int), 1)
    pagination = payments_query(search).filter_by(
        payment_category="bank"
    ).order_by(
        Payment.payment_date.desc(), Payment.id.desc()
    ).paginate(page=page, per_page=25, error_out=False)

    duplicate_reference_keys = set(
        db.session.query(
            Payment.form_of_payment,
            db.func.lower(db.func.trim(Payment.reference))
        )
        .filter(
            Payment.payment_category == "bank",
            Payment.reference.isnot(None),
            db.func.trim(Payment.reference) != ""
        )
        .group_by(
            Payment.form_of_payment,
            db.func.lower(db.func.trim(Payment.reference))
        )
        .having(db.func.count(Payment.id) > 1)
        .all()
    )
    duplicate_payment_ids = {
        payment.id
        for payment in pagination.items
        if payment.reference
        and (payment.form_of_payment, payment.reference.strip().lower()) in duplicate_reference_keys
    }
    return render_template(
        "validate_payments.html",
        payments=pagination.items,
        duplicate_payment_ids=duplicate_payment_ids,
        pagination=pagination,
        search=search
    )


@app.route("/payments/<int:payment_id>/bank-review", methods=["POST"])
@login_required
@roles_required("bank_reviewer")
def review_bank_payment(payment_id):
    payment = db.session.get(Payment, payment_id)
    if not payment:
        abort(404)
    if payment.payment_category != "bank":
        abort(400, description="Only bank payments can be reviewed with this action.")

    decision = request.form.get("decision", "")
    review_notes = request.form.get("review_notes", "").strip()
    if decision not in {"verified", "rejected"}:
        abort(400, description="Select a valid bank receipt review decision.")
    return_page = request.form.get("return_page", type=int)
    return_search = request.form.get("return_q", "").strip()

    def review_redirect():
        if current_user.is_bank_reviewer():
            return redirect(url_for(
                "validate_bank_payments",
                page=max(return_page or 1, 1),
                q=return_search
            ))
        return redirect(url_for("modify_payments"))

    if request.form.get("official_record_checked") != "on":
        flash("Confirm that you checked the official bank record before reviewing this receipt.", "warning")
        return review_redirect()
    if not review_notes:
        flash("Add a short note describing the official bank-record check.", "warning")
        return review_redirect()
    if len(review_notes) > 500:
        flash("The bank-record check note must be 500 characters or fewer.", "warning")
        return review_redirect()

    payment.bank_review_status = decision
    payment.bank_reviewer_id = current_user.id
    payment.bank_reviewed_at = utcnow_naive()
    payment.bank_review_notes = review_notes
    record_audit(
        f"bank_{decision}",
        payment.id,
        f"{decision.title()} after official bank-record check: {review_notes[:350]}"
    )
    db.session.commit()
    flash(
        f"Bank payment #{payment.id} marked {decision}.",
        "success" if decision == "verified" else "warning"
    )
    return review_redirect()


@app.route("/payments/<int:payment_id>/invoice/existing", methods=["POST"])
@login_required
@roles_required("super")
def generate_existing_invoice(payment_id):
    payment = db.session.get(Payment, payment_id)
    if not payment:
        abort(404)

    requires_admin_password = payment.existing_invoice_count >= 2
    if not requires_admin_password:
        updated = Payment.query.filter(
            Payment.id == payment_id,
            Payment.existing_invoice_count < 2
        ).update(
            {Payment.existing_invoice_count: Payment.existing_invoice_count + 1},
            synchronize_session=False
        )
        requires_admin_password = not updated
        if updated:
            db.session.expire(payment, ["existing_invoice_count"])

    if requires_admin_password:
        admin_password = request.form.get("admin_password", "")
        active_super_users = User.query.filter_by(
            role="super", is_active=True
        ).all()
        if not any(user.check_password(admin_password) for user in active_super_users):
            db.session.rollback()
            flash("Enter a valid super-user password to generate additional invoices.", "danger")
            return redirect(url_for("modify_payments"))

        updated = Payment.query.filter_by(id=payment_id).update(
            {Payment.existing_invoice_count: Payment.existing_invoice_count + 1},
            synchronize_session=False
        )
        if not updated:
            db.session.rollback()
            abort(404)
        db.session.expire(payment, ["existing_invoice_count"])

    issue = create_invoice_issue(payment, "existing")
    audit_details = "Existing Payments invoice generated"
    if requires_admin_password:
        audit_details += " with super-user password authorization"
    record_audit("invoice", payment.id, audit_details)
    db.session.commit()
    return redirect(url_for("view_invoice", token=issue.token))


@app.route("/invoices/<token>")
@login_required
@roles_required("super")
def view_invoice(token):
    issue = InvoiceIssue.query.filter_by(token=token).first_or_404()
    return render_invoice(issue)


@app.route("/invoices/verify/<token>")
def verify_invoice(token):
    issue = InvoiceIssue.query.filter_by(token=token).first_or_404()
    valid = invoice_issue_is_valid(issue)
    snapshot = json.loads(issue.snapshot) if valid else None
    return render_template(
        "invoice_verify.html",
        valid=valid,
        snapshot=snapshot
    )


def payments_query(search=""):
    query = Payment.query
    if search:
        term = f"%{search}%"
        query = query.filter(or_(
            Payment.student_name.ilike(term),
            Payment.course.ilike(term),
            Payment.reference.ilike(term),
            Payment.form_of_payment.ilike(term),
            Payment.notes.ilike(term)
        ))
    return query


@app.route("/payments/export.xlsx")
@login_required
@roles_required("super")
def export_payments():
    search = request.args.get("q", "").strip()
    payments = payments_query(search).order_by(
        Payment.payment_date.desc(), Payment.id.desc()
    ).all()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Payments"
    headers = [
        "Payment ID", "Payer / Student", "Course", "Payment Category", "Method",
        "Amount (TZS)", "Payment Date", "Reference", "Notes",
        "Receipt File", "Uploaded By"
    ]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0B2545")

    for payment in payments:
        sheet.append([
            payment.id,
            payment.student_name,
            payment.course or "",
            payment.payment_category.title(),
            payment.form_of_payment,
            payment.amount,
            payment.payment_date,
            payment.reference or "",
            payment.notes or "",
            payment.receipt_filename or "",
            payment.uploader.username,
        ])
        sheet.cell(row=sheet.max_row, column=6).number_format = '#,##0.00'
        sheet.cell(row=sheet.max_row, column=7).number_format = "dd mmm yyyy"

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column, width in {
        "A": 13, "B": 28, "C": 32, "D": 20, "E": 24, "F": 16,
        "G": 18, "H": 24, "I": 40, "J": 32, "K": 22
    }.items():
        sheet.column_dimensions[column].width = width

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    filename = f"brilliantpay-payments-{nairobi_now():%Y%m%d-%H%M%S}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/payments/<int:payment_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("super")
def edit_payment(payment_id):
    payment = db.session.get(Payment, payment_id)
    if not payment:
        abort(404)

    if request.method == "POST":
        student_name = request.form.get("student_name", "").strip()
        course = request.form.get("course", "")
        form_of_payment = request.form.get("form_of_payment", "")
        valid_methods = BANK_PAYMENT_METHODS if payment.payment_category == "bank" else (
            "M-Pesa", "Tigo Pesa", "Airtel Money", "HaloPesa", "Other Mobile"
        )
        if not student_name or (course and course not in COURSE_FEES):
            flash("Please provide a student name and a valid course.", "warning")
            return render_template(
                "edit_payment.html",
                payment=payment,
                bank_payment_methods=BANK_PAYMENT_METHODS
            )
        if form_of_payment not in valid_methods:
            flash("Please select a valid payment method.", "warning")
            return render_template(
                "edit_payment.html",
                payment=payment,
                bank_payment_methods=BANK_PAYMENT_METHODS
            )
        payment.student_name = student_name
        payment.course = course or None
        payment.form_of_payment = form_of_payment
        payment.reference = request.form.get("reference", "").strip()
        payment.notes = request.form.get("notes", "").strip()
        if payment.payment_category == "bank":
            payment.bank_review_status = "pending"
            payment.bank_reviewer_id = None
            payment.bank_reviewed_at = None
            payment.bank_review_notes = None
            record_audit(
                "bank_review_reset",
                payment.id,
                "Bank payment details edited; official verification returned to pending"
            )

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

        payment.updated_at = utcnow_naive()
        record_audit("updated", payment.id, f"Updated payment for {payment.student_name}")
        db.session.commit()
        flash("Payment updated successfully.", "success")
        return redirect(url_for("modify_payments"))

    return render_template(
        "edit_payment.html",
        payment=payment,
        bank_payment_methods=BANK_PAYMENT_METHODS
    )


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
    InvoiceIssue.query.filter_by(payment_id=payment.id).delete(synchronize_session=False)
    db.session.delete(payment)
    record_audit("deleted", payment.id, f"Deleted payment for {payment.student_name}")
    db.session.commit()
    flash("Payment deleted.", "info")
    return redirect(url_for("modify_payments"))


@app.route("/uploads/<filename>")
@login_required
@roles_required("super", "staff", "bank_reviewer")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/payments/<int:payment_id>/receipt")
@login_required
@roles_required("super", "staff", "bank_reviewer")
def view_receipt(payment_id):
    payment = db.session.get(Payment, payment_id)
    if not payment or not payment.receipt_filename:
        abort(404)
    return render_template(
        "receipt_viewer.html",
        payment=payment,
        receipt_url=url_for("uploaded_file", filename=payment.receipt_filename)
    )


# ---------------------------------------------------------------------------
# Init DB & create default super user
# ---------------------------------------------------------------------------
def init_db():
    with app.app_context():
        db.create_all()
        with db.engine.begin() as connection:
            user_columns = {
                column["name"] for column in inspect(connection).get_columns("user")
            }
            if "avatar_id" not in user_columns:
                connection.execute(text(
                    "ALTER TABLE user ADD COLUMN avatar_id VARCHAR(40)"
                ))
            if "password_change_required" not in user_columns:
                connection.execute(text(
                    "ALTER TABLE user ADD COLUMN "
                    "password_change_required BOOLEAN NOT NULL DEFAULT FALSE"
                ))
            for column_name, column_type in (
                ("phone_number", "VARCHAR(40)"),
                ("contact_email", "VARCHAR(120)"),
            ):
                if column_name not in user_columns:
                    connection.execute(text(
                        f"ALTER TABLE user ADD COLUMN {column_name} {column_type}"
                    ))
            payment_columns = {
                column["name"] for column in inspect(connection).get_columns("payment")
            }
            if "existing_invoice_count" not in payment_columns:
                connection.execute(text(
                    "ALTER TABLE payment ADD COLUMN "
                    "existing_invoice_count INTEGER NOT NULL DEFAULT 0"
                ))
            if "course" not in payment_columns:
                connection.execute(text(
                    "ALTER TABLE payment ADD COLUMN course VARCHAR(100)"
                ))
                payment_columns.add("course")
            payment_migrations = {
                "bank_review_status": "VARCHAR(20)",
                "bank_reviewer_id": "INTEGER REFERENCES user(id)",
                "bank_reviewed_at": "DATETIME",
                "bank_review_notes": "TEXT",
            }
            for column_name, column_type in payment_migrations.items():
                if column_name not in payment_columns:
                    connection.execute(text(
                        f"ALTER TABLE payment ADD COLUMN {column_name} {column_type}"
                    ))
            connection.execute(text(
                "UPDATE payment SET bank_review_status = 'pending' "
                "WHERE payment_category = 'bank' AND bank_review_status IS NULL"
            ))
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

        for prefix, role in (
            ("BRILLIANTPAY_REVIEWER", "bank_reviewer"),
            ("BRILLIANTPAY_ENTRY", "payment_entry"),
        ):
            username = os.environ.get(f"{prefix}_USERNAME", "").strip()
            email = os.environ.get(f"{prefix}_EMAIL", "").strip().lower()
            password = os.environ.get(f"{prefix}_PASSWORD", "")
            if not any((username, email, password)):
                continue
            if User.query.filter_by(role=role).first():
                continue
            if not username or not email or not password:
                raise RuntimeError(
                    f"Set {prefix}_USERNAME, {prefix}_EMAIL, and {prefix}_PASSWORD together."
                )
            if len(password) < 12:
                raise RuntimeError(f"{prefix}_PASSWORD must be at least 12 characters.")
            if User.query.filter(
                or_(User.username == username, User.email == email)
            ).first():
                raise RuntimeError(
                    f"Cannot create the {role} account: username or email is already in use."
                )
            scoped_user = User(username=username, email=email, role=role)
            scoped_user.set_password(password)
            db.session.add(scoped_user)
            db.session.commit()
            print(f">>> {role} account created: username={username}")
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


if __name__ == "__main__":
    init_db()
    app.run(
        host=os.environ.get("BRILLIANTPAY_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("BRILLIANTPAY_DEBUG") == "1"
    )

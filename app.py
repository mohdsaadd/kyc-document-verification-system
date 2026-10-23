import os
import secrets
from datetime import datetime, date, timedelta, timezone
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_FOLDER", BASE_DIR / "uploads")).resolve()
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-this-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'kyc.db'}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="reviewer")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class KycCase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(120), nullable=False)
    customer_email = db.Column(db.String(160), nullable=False)
    document_type = db.Column(db.String(60), nullable=False)
    reference_number = db.Column(db.String(40), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pending")
    notes = db.Column(db.Text, default="")
    document_filename = db.Column(db.String(255))
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    due_date = db.Column(db.Date, default=lambda: date.today() + timedelta(days=3), nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("kyc_case.id"), nullable=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(80), nullable=False)
    details = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    case = db.relationship("KycCase")
    actor = db.relationship("User")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def log_action(action, details="", case_id=None):
    db.session.add(AuditLog(
        case_id=case_id,
        actor_id=current_user.id,
        action=action,
        details=details[:500],
    ))


@app.cli.command("init-db")
def init_db():
    """Create tables and seed demo users if they do not exist."""
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", role="admin")
        admin.set_password(os.getenv("DEMO_ADMIN_PASSWORD", "Admin123!"))
        reviewer = User(username="reviewer", role="reviewer")
        reviewer.set_password(os.getenv("DEMO_REVIEWER_PASSWORD", "Review123!"))
        db.session.add_all([admin, reviewer])
        db.session.commit()
        print("Created demo users: admin / Admin123! and reviewer / Review123!")
        print("Change these passwords before using the app beyond a local demo.")
    else:
        print("Database already initialized.")


@app.route("/")
@login_required
def dashboard():
    total = KycCase.query.count()
    pending = KycCase.query.filter_by(status="Pending").count()
    approved = KycCase.query.filter_by(status="Approved").count()
    rejected = KycCase.query.filter_by(status="Rejected").count()
    overdue = KycCase.query.filter(KycCase.status == "Pending", KycCase.due_date < date.today()).count()
    recent = KycCase.query.order_by(KycCase.created_at.desc()).limit(8).all()
    return render_template("dashboard.html", total=total, pending=pending, approved=approved,
                           rejected=rejected, overdue=overdue, cases=recent)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            log_action("login", f"User {user.username} logged in")
            db.session.commit()
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    log_action("logout", f"User {current_user.username} logged out")
    db.session.commit()
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/cases")
@login_required
def cases():
    status = request.args.get("status", "")
    query = KycCase.query
    if status in {"Pending", "Approved", "Rejected"}:
        query = query.filter_by(status=status)
    search = request.args.get("q", "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(db.or_(KycCase.customer_name.ilike(like),
                                    KycCase.reference_number.ilike(like),
                                    KycCase.customer_email.ilike(like)))
    all_cases = query.order_by(KycCase.created_at.desc()).all()
    return render_template("cases.html", cases=all_cases, status=status, q=search)


@app.route("/cases/new", methods=["GET", "POST"])
@role_required("admin", "reviewer")
def new_case():
    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        customer_email = request.form.get("customer_email", "").strip()
        document_type = request.form.get("document_type", "").strip()
        notes = request.form.get("notes", "").strip()
        due_date_raw = request.form.get("due_date", "").strip()
        upload = request.files.get("document")

        if not customer_name or not customer_email or not document_type:
            flash("Name, email, and document type are required.", "error")
            return render_template("case_form.html", case=None)
        if len(customer_name) > 120 or len(customer_email) > 160:
            flash("One or more fields are too long.", "error")
            return render_template("case_form.html", case=None)

        due_date = date.today() + timedelta(days=3)
        if due_date_raw:
            try:
                due_date = date.fromisoformat(due_date_raw)
            except ValueError:
                flash("Enter a valid due date.", "error")
                return render_template("case_form.html", case=None)

        stored_name = None
        if upload and upload.filename:
            if not allowed_file(upload.filename):
                flash("Allowed document formats: PDF, PNG, JPG, JPEG.", "error")
                return render_template("case_form.html", case=None)
            safe_name = secure_filename(upload.filename)
            stored_name = f"{secrets.token_hex(12)}_{safe_name}"
            upload.save(UPLOAD_DIR / stored_name)

        case = KycCase(
            customer_name=customer_name,
            customer_email=customer_email,
            document_type=document_type,
            reference_number=f"KYC-{secrets.token_hex(4).upper()}",
            notes=notes,
            document_filename=stored_name,
            created_by_id=current_user.id,
            due_date=due_date,
        )
        db.session.add(case)
        db.session.flush()
        log_action("case_created", f"Created KYC case {case.reference_number}", case.id)
        db.session.commit()
        flash(f"Case {case.reference_number} created.", "success")
        return redirect(url_for("case_detail", case_id=case.id))
    return render_template("case_form.html", case=None)


@app.route("/cases/<int:case_id>")
@login_required
def case_detail(case_id):
    case = db.get_or_404(KycCase, case_id)
    logs = AuditLog.query.filter_by(case_id=case.id).order_by(AuditLog.created_at.desc()).all()
    return render_template("case_detail.html", case=case, logs=logs, today=date.today())


@app.route("/cases/<int:case_id>/review", methods=["POST"])
@role_required("admin", "reviewer")
def review_case(case_id):
    case = db.get_or_404(KycCase, case_id)
    if case.status != "Pending":
        flash("Only pending cases can be reviewed.", "error")
        return redirect(url_for("case_detail", case_id=case.id))
    status = request.form.get("status")
    notes = request.form.get("notes", "").strip()
    if status not in {"Approved", "Rejected"}:
        abort(400)
    case.status = status
    case.notes = notes or case.notes
    case.reviewed_by_id = current_user.id
    log_action("case_reviewed", f"Changed status to {status}", case.id)
    db.session.commit()
    flash(f"Case marked {status.lower()}.", "success")
    return redirect(url_for("case_detail", case_id=case.id))


@app.route("/cases/<int:case_id>/document")
@login_required
def download_document(case_id):
    case = db.get_or_404(KycCase, case_id)
    if not case.document_filename:
        abort(404)
    # Authenticated users only; production systems should add stricter per-case permissions.
    return send_from_directory(UPLOAD_DIR, case.document_filename, as_attachment=True)


@app.route("/audit")
@role_required("admin")
def audit():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("audit.html", logs=logs)


@app.route("/reminders")
@role_required("admin", "reviewer")
def reminders():
    today = date.today()
    pending = KycCase.query.filter_by(status="Pending").order_by(KycCase.due_date.asc()).all()
    return render_template("reminders.html", cases=pending, today=today)


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have permission to view this page."), 403


@app.errorhandler(413)
def too_large(_error):
    return render_template("error.html", code=413, message="File is too large. Maximum upload size is 5 MB."), 413


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")

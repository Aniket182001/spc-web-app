import functools

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import User


auth_bp = Blueprint("auth", __name__)


def admin_required(f):
    """Decorator that restricts a view to admin users only (role == 'admin').
    Returns HTTP 403 Forbidden for non-admins.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def _safe_next_url(next_url):
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return url_for("spc.dashboard")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("spc.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        try:
            user = User.query.filter_by(username=username).first()
        except SQLAlchemyError:
            flash("Database connection error. Please try again later or contact support.", "error")
            return render_template("login.html")

        if user and user.check_password(password):
            if user.is_deleted:
                flash("Your account has been deactivated. Contact administrator.", "error")
                return redirect(url_for("auth.login"))
            if not user.is_active:
                flash("Your account has been deactivated. Contact administrator.", "error")
                return redirect(url_for("auth.login"))
            login_user(user)
            return redirect(_safe_next_url(request.args.get("next")))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@auth_bp.before_app_request
def require_password_change():
    """Force users with must_change_password to change their password before accessing the app."""
    if current_user.is_authenticated and current_user.must_change_password:
        # Allow requests to static files and auth routes to go through
        allowed_endpoints = ("auth.change_password", "auth.logout", "static")
        if request.endpoint and request.endpoint not in allowed_endpoints:
            return redirect(url_for("auth.change_password"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))

    # We don't block them from accessing this page even if must_change_password is False,
    # but the prompt focuses on "First-login password change" so it's mainly for that.

    if request.method == "POST":
        current_pwd = request.form.get("current_password", "")
        new_pwd = request.form.get("new_password", "")
        confirm_pwd = request.form.get("confirm_password", "")

        if not current_pwd or not new_pwd:
            flash("All fields are required.", "error")
            return render_template("change_password.html")

        if not current_user.check_password(current_pwd):
            flash("Current password is incorrect.", "error")
            return render_template("change_password.html")

        if new_pwd != confirm_pwd:
            flash("New password and confirm password do not match.", "error")
            return render_template("change_password.html")

        current_user.set_password(new_pwd)
        current_user.must_change_password = False
        try:
            db.session.commit()
            flash("Password changed successfully.", "success")
            return redirect(url_for("spc.dashboard"))
        except SQLAlchemyError:
            db.session.rollback()
            flash("Database error. Please try again.", "error")

    return render_template("change_password.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("spc.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        try:
            if User.query.filter_by(username=username).first():
                flash("Username is already registered.", "error")
                return render_template("register.html")

            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash("Database connection error. Please try again later or contact support.", "error")
            return render_template("register.html")

        login_user(user)
        return redirect(url_for("spc.dashboard"))

    return render_template("register.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("auth.login"))

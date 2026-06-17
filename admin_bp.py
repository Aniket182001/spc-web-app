from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from auth import admin_required
from extensions import db
from models import User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users")
@admin_required
def users():
    """Admin-only page listing all registered users."""
    all_users = User.query.order_by(User.username).all()
    return render_template("admin/users.html", users=all_users)


@admin_bp.route("/user/<int:user_id>/toggle-status", methods=["POST"])
@admin_required
def toggle_status(user_id):
    """Toggle a user's is_active status.

    Safety rules:
    - Admins cannot act on themselves.
    - Admins cannot act on other admins.
    """
    target = User.query.get_or_404(user_id)

    # Safety: block self-deactivation
    if target.id == current_user.id:
        flash("You cannot change your own account status.", "error")
        return redirect(url_for("admin.users"))

    # Safety: block acting on other admins
    if target.role == "admin":
        flash("Admin accounts cannot be deactivated.", "error")
        return redirect(url_for("admin.users"))

    # Toggle
    target.is_active = not target.is_active
    try:
        db.session.commit()
        if target.is_active:
            flash(f"User '{target.username}' activated successfully.", "success")
        else:
            flash(f"User '{target.username}' deactivated successfully.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Database error. Please try again.", "error")

    return redirect(url_for("admin.users"))


@admin_bp.route("/users/create", methods=["GET", "POST"])
@admin_required
def create_user():
    """Admin-only form to create a new user account."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        # ── Validation ────────────────────────────────────
        if not username:
            flash("Username cannot be empty.", "error")
            return render_template("admin/create_user.html", username=username)

        if not password:
            flash("Password cannot be empty.", "error")
            return render_template("admin/create_user.html", username=username)

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("admin/create_user.html", username=username)

        if User.query.filter_by(username=username).first():
            flash(f"Username '{username}' is already taken.", "error")
            return render_template("admin/create_user.html", username=username)

        # ── Create user ───────────────────────────────────
        new_user = User(username=username)
        new_user.set_password(password)
        # role and is_active default to "user" / True via model defaults
        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f"User '{username}' created successfully.", "success")
            return redirect(url_for("admin.users"))
        except SQLAlchemyError:
            db.session.rollback()
            flash("Database error. Please try again.", "error")
            return render_template("admin/create_user.html", username=username)

    return render_template("admin/create_user.html", username="")

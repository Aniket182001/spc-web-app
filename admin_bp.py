from flask import Blueprint, flash, redirect, render_template, url_for
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

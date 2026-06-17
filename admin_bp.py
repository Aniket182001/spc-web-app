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
    show_archived = request.args.get("show_archived", "false").lower() == "true"
    
    query = User.query
    if not show_archived:
        query = query.filter_by(is_deleted=False)
        
    all_users = query.order_by(User.username).all()
    return render_template("admin/users.html", users=all_users, show_archived=show_archived)


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
        new_user.must_change_password = True
        new_user.plan_name = "Free"
        new_user.monthly_chart_limit = 20
        new_user.charts_used_this_month = 0
        new_user.subscription_active = True
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


@admin_bp.route("/user/<int:user_id>/reset-password", methods=["GET", "POST"])
@admin_required
def reset_password(user_id):
    """Admin-only form to reset a user's password."""
    target = User.query.get_or_404(user_id)

    # Safety: block acting on admins
    if target.role == "admin":
        flash("Admin account passwords cannot be reset here.", "error")
        return redirect(url_for("admin.users"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        # ── Validation ────────────────────────────────────
        if not password:
            flash("Password cannot be empty.", "error")
            return render_template("admin/reset_password.html", user=target)

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("admin/reset_password.html", user=target)

        # ── Reset password ────────────────────────────────
        target.set_password(password)
        try:
            db.session.commit()
            flash("Password reset successfully.", "success")
            return redirect(url_for("admin.users"))
        except SQLAlchemyError:
            db.session.rollback()
            flash("Database error. Please try again.", "error")
            return render_template("admin/reset_password.html", user=target)

    return render_template("admin/reset_password.html", user=target)


@admin_bp.route("/user/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    """Soft delete a user."""
    target = User.query.get_or_404(user_id)

    if target.id == current_user.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin.users"))

    if target.role == "admin":
        flash("Admin accounts cannot be deleted.", "error")
        return redirect(url_for("admin.users"))

    target.is_deleted = True
    target.is_active = False
    try:
        db.session.commit()
        flash("User archived successfully.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Database error. Please try again.", "error")

    return redirect(url_for("admin.users"))


@admin_bp.route("/user/<int:user_id>/restore", methods=["POST"])
@admin_required
def restore_user(user_id):
    """Restore a soft-deleted user."""
    target = User.query.get_or_404(user_id)

    target.is_deleted = False
    target.is_active = True
    try:
        db.session.commit()
        flash("User restored successfully.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Database error. Please try again.", "error")

    return redirect(url_for("admin.users", show_archived="true"))

from flask import Blueprint, render_template

from auth import admin_required
from models import User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users")
@admin_required
def users():
    """Admin-only page listing all registered users."""
    all_users = User.query.order_by(User.username).all()
    return render_template("admin/users.html", users=all_users)

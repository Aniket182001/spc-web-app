import os
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError
# Load environment variables from .env file if it exists
load_dotenv()


from flask import Flask, render_template, request, url_for
from auth import auth_bp
from chart_info import CHART_INFO, chart_info_bp
from extensions import db, login_manager
from models import User
from spc_charts import spc_bp
from capability import capability_bp
import webbrowser
from threading import Timer
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect


def open_browser():
    webbrowser.open_new("http://localhost:5000")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

flask_env = os.environ.get("FLASK_ENV", "development")
if flask_env == "production" and not os.environ.get("DATABASE_URL"):
    raise RuntimeError(
        "DATABASE_URL missing in production environment. Refusing to fall back to SQLite."
    )

sqlite_path = os.path.join(app.instance_path, "spc_app.db")
default_sqlite_path = f"sqlite:///{sqlite_path}"

db_url = os.environ.get(
    "DATABASE_URL",
    default_sqlite_path,
)
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

os.makedirs(app.instance_path, exist_ok=True)
os.makedirs("static", exist_ok=True)

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access SPC Insights."

# Initialize Flask-Migrate
migrate = Migrate(app, db, render_as_batch=True)
csrf = CSRFProtect(app)

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except (ValueError, SQLAlchemyError):
        return None


# Register modules
app.register_blueprint(auth_bp)
app.register_blueprint(spc_bp)
app.register_blueprint(capability_bp)
app.register_blueprint(chart_info_bp)


# ─── Admin CLI commands ────────────────────────────────
import click

@app.cli.command("make-admin")
@click.argument("username")
def make_admin(username):
    """Promote a user to admin role by USERNAME.

    Example:
        flask make-admin johndoe
    """
    user = User.query.filter_by(username=username).first()
    if user is None:
        click.echo(f"[ERROR] No user found with username '{username}'.")
        raise SystemExit(1)

    if user.role == "admin":
        click.echo(f"[INFO] '{username}' is already an admin. No changes made.")
        return

    user.role = "admin"
    try:
        db.session.commit()
        click.echo(f"[OK] '{username}' has been promoted to admin.")
    except SQLAlchemyError as exc:
        db.session.rollback()
        click.echo(f"[ERROR] Database error: {exc}")
        raise SystemExit(1)


# ─── Public homepage ───────────────────────────────────
@app.route("/")
def home():
    return render_template("home.html")


@app.context_processor
def inject_chart_information():
    summaries = {
        chart["dropdown_value"]: {
            "description": chart["short_description"],
            "url": url_for(
                "chart_info.chart_info_detail",
                chart_type=chart_slug.replace("_", "-"),
            ),
        }
        for chart_slug, chart in CHART_INFO.items()
    }
    selected_chart = request.form.get("chart", "xbar_r")

    if selected_chart not in summaries:
        selected_chart = "xbar_r"

    return {
        "chart_summaries": summaries,
        "selected_chart": selected_chart,
        "selected_chart_summary": summaries[selected_chart],
    }

if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        Timer(1, open_browser).start()

    debug_mode = os.environ.get("FLASK_ENV", "development") == "development"
    app.run(debug=debug_mode)

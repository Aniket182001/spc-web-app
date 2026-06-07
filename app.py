import os
from flask import Flask, request, url_for
from auth import auth_bp
from chart_info import CHART_INFO, chart_info_bp
from extensions import db, login_manager
from models import User
from spc_charts import spc_bp
from capability import capability_bp
import webbrowser
from threading import Timer


def open_browser():
    webbrowser.open_new("http://localhost:5000")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(app.instance_path, 'spc_app.db')}",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(app.instance_path, exist_ok=True)
os.makedirs("static", exist_ok=True)

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access SPC Insight Pro."


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


with app.app_context():
    db.create_all()


# Register modules
app.register_blueprint(auth_bp)
app.register_blueprint(spc_bp)
app.register_blueprint(capability_bp)
app.register_blueprint(chart_info_bp)


@app.context_processor
def inject_chart_information():
    summaries = {
        chart["dropdown_value"]: {
            "description": chart["short_description"],
            "url": url_for(
                "chart_info.chart_info_detail",
                chart_type=chart_slug,
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

    app.run(debug=True)

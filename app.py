import os
from flask import Flask
from auth import auth_bp
from extensions import db, login_manager
from models import User
from spc_charts import spc_bp
from capability import capability_bp

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

if __name__ == '__main__':

    print("🚀 Starting SPC Server...")
    print("👉 Open http://127.0.0.1:5000 in browser")

    app.run(debug=True)

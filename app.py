from flask import Flask
from spc_charts import spc_bp
from capability import capability_bp

app = Flask(__name__)

# Register modules
app.register_blueprint(spc_bp)
app.register_blueprint(capability_bp)

if __name__ == '__main__':

    print("🚀 Starting SPC Server...")
    print("👉 Open http://127.0.0.1:5000 in browser")

    app.run(debug=True)
from flask import Flask, render_template, session, redirect, url_for
from flask_cors import CORS
import os
from dotenv import load_dotenv
from config import config
import database as db
from api.routes import api, get_week_range

load_dotenv()

def create_app(config_name = "default"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    app.secret_key = os.environ.get('SECRET_KEY', os.urandom(32))

    CORS(app)

    app.register_blueprint(api)

    with app.app_context():
        db.init_db()

    #path route of the application
    @app.route("/")
    def index():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return render_template("login.html")
    
    @app.route("/dashboard")
    def dashboard():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return render_template("dashboard.html")

    @app.route("/health")
    def health():
        return {"status": "Healthy"}, 200
    
    return app

if __name__ == "__main__":
    config_name = os.getenv("FLASK_ENV", "development")
    app = create_app(config_name)
    week_start, week_end = get_week_range()

    if config_name == "development":
        week_start, week_end = get_week_range()

        print("\n" + "="*50)
        print("💳 BUDGET TRACKER 💳")
        print("="*50)
        print(f"http://localhost:5000")
        print(f"Week: {week_start} to {week_end}")
        print("="*50 + "\n")

    port = int(os.environ.get("PORT", 5000))
    app.run(host = "0.0.0.0", port = 5000, debug = (config_name == "development"))

app = create_app(ps.getenv("FLASK_ENV", "production"))


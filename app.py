from flask import Flask, render_template, session, redirect, url_for, jsonify
from flask_cors import CORS
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from config import config
import database as db
from api.routes import api, get_week_range
from extensions import limiter



def create_app(config_name = "default"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    secret_key = os.environ.get('SECRET_KEY')
    if config_name == "production":
        missing = [
            name for name, val in (
                ("SECRET_KEY", secret_key),
                ("CORS_ORIGINS", os.environ.get("CORS_ORIGINS")),
                ("DATABASE_URL", os.environ.get("DATABASE_URL")),
            )
            if not val
        ]
        if missing:
            raise RuntimeError(
                "Missing required environment variables in production: "
                + ", ".join(missing)
            )
        app.secret_key = secret_key
    else:
        app.secret_key = secret_key or os.urandom(32)

    cors_origins = os.environ.get("CORS_ORIGINS", "")
    if cors_origins:
        origins = [o.strip() for o in cors_origins.split(",") if o.strip()]
        CORS(app, origins=origins, supports_credentials=True)
    elif config_name != "production":
        CORS(app, supports_credentials=True)

    limiter.init_app(app)

    @app.errorhandler(429)
    def rate_limit_exceeded(_e):
        return jsonify({
            "error": "Too many attempts. Please wait a few minutes and try again.",
        }), 429

    app.register_blueprint(api)

    with app.app_context():
        db.init_db()

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
        return jsonify({"status": "Healthy"}), 200

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

app = create_app(os.getenv("FLASK_ENV", "production"))


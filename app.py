from flask import Flask, render_template
from flask_cors import CORS
import os
from config import config
import database as db
from api.routes import api, get_week_range

def create_app(config_name = "default"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    CORS(app)

    app.register_blueprint(api)

    with app.app_context():
        db.init_db()
    #path route of the application
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/health")
    def health():
        return {"status": "Healthy"}, 200
    
    return app

if __name__ == "__main__":
    config_name = os.getenv("FLASK_ENV", "development")
    app = create_app(config_name)
    week_start, week_end = get_week_range()

    print("\n" + "="*50)
    print("💳 BUDGET TRACKER 💳")
    print("="*50)
    print(f"http://localhost:5000")
    print(f"Week: {week_start} to {week_end}")
    print("="*50 + "\n")

    app.run(host = "0.0.0.0", port = 5000, debug = True)



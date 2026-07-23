from flask import Flask, render_template, session, redirect, url_for, jsonify
from flask_cors import CORS
import click
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from config import config
import database as db
from api.routes import api, validate_password
from extensions import limiter


def register_admin_commands(app):
    @app.cli.group("admin")
    def admin_commands():
        """Manage administrator access from a trusted operator shell."""

    @admin_commands.command("create")
    @click.argument("username")
    @click.argument("email")
    def create_admin(username, email):
        username = username.strip()
        email = email.strip().lower()
        if len(username) < 5 or len(username) > db.MAX_USERNAME_LEN:
            raise click.ClickException(
                f"Username must be between 5 and {db.MAX_USERNAME_LEN} characters."
            )
        if "@" not in email or len(email) > db.MAX_EMAIL_LEN:
            raise click.ClickException("Enter a valid email address.")

        password = click.prompt(
            "Password",
            hide_input=True,
            confirmation_prompt=True,
            type=str,
        )
        if len(password) > 128:
            raise click.ClickException("Password is too long.")
        is_valid, message = validate_password(password)
        if not is_valid:
            raise click.ClickException(message)

        result = db.create_admin_user(username, email, password)
        if result["status"] == "duplicate":
            raise click.ClickException("That username or email is already registered.")
        click.echo("Administrator account created and email marked verified.")

    @admin_commands.command("grant")
    @click.argument("username")
    def grant_admin(username):
        result = db.set_admin_role(username, True)
        messages = {
            "updated": "Administrator access granted.",
            "unchanged": "The account is already an administrator.",
            "not_found": "Account not found.",
        }
        click.echo(messages.get(result, "Administrator update failed."))
        if result == "not_found":
            raise click.ClickException(messages[result])

    @admin_commands.command("revoke")
    @click.argument("username")
    def revoke_admin(username):
        result = db.set_admin_role(username, False)
        messages = {
            "updated": "Administrator access revoked.",
            "unchanged": "The account is already a normal user.",
            "not_found": "Account not found.",
            "last_admin": "Cannot revoke the last active administrator.",
        }
        click.echo(messages.get(result, "Administrator update failed."))
        if result in ("not_found", "last_admin"):
            raise click.ClickException(messages[result])



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
    register_admin_commands(app)

    @app.errorhandler(429)
    def rate_limit_exceeded(_e):
        return jsonify({
            "error": "Too many attempts. Please wait a few minutes and try again.",
        }), 429

    @app.errorhandler(413)
    def request_too_large(_e):
        return jsonify({"error": "The uploaded file is too large."}), 413

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


def env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


if __name__ == "__main__":
    config_name = os.getenv("FLASK_ENV", "development")
    is_dev = config_name == "development"
    app = create_app(config_name)
    port = int(os.environ.get("PORT", 5000))
    use_reload = env_bool("FLASK_RELOAD", is_dev)

    app.run(
        host="0.0.0.0",
        port=port,
        debug=is_dev,
        use_reloader=use_reload and is_dev,
        reloader_type="stat" if os.name == "nt" else "auto",
        threaded=True,
    )

app = create_app(os.getenv("FLASK_ENV", "production"))

import os
import secrets
from functools import wraps

from flask import jsonify, request, session


def allowed_origins():
    raw = os.environ.get("CORS_ORIGINS", "")
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def verify_request_origin():
    if os.environ.get("FLASK_ENV", "development") != "production":
        return True

    origins = allowed_origins()
    if not origins:
        return False

    origin = (request.headers.get("Origin") or "").rstrip("/")
    if origin and origin in origins:
        return True

    referer = request.headers.get("Referer") or ""
    return any(referer.startswith(f"{allowed}/") or referer == allowed for allowed in origins)


def issue_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def rotate_csrf_token():
    token = secrets.token_urlsafe(32)
    session["csrf_token"] = token
    return token


def csrf_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return f(*args, **kwargs)

        if not verify_request_origin():
            return jsonify({"error": "Invalid request origin"}), 403

        sent = request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf_token")
        if not expected or not sent or not secrets.compare_digest(sent, expected):
            return jsonify({"error": "Invalid or missing CSRF token"}), 403

        return f(*args, **kwargs)

    return decorated


def origin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return f(*args, **kwargs)
        if not verify_request_origin():
            return jsonify({"error": "Invalid request origin"}), 403
        return f(*args, **kwargs)

    return decorated

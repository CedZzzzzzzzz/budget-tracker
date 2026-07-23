import logging
from functools import wraps

import psycopg2
from flask import jsonify

logger = logging.getLogger(__name__)

try:
    from google.genai import errors as google_genai_errors
    GEMINI_ERRORS = (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        google_genai_errors.APIError,
    )
except ImportError:
    GEMINI_ERRORS = (ValueError, TypeError, KeyError, AttributeError, OSError)


def internal_error():
    return jsonify({"error": "An internal error occurred"}), 500


def handle_api_errors(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning("%s invalid request: %s", view.__name__, exc)
            return jsonify({"error": "Invalid request data"}), 400
        except psycopg2.Error as exc:
            logger.exception("%s database error: %s", view.__name__, exc)
            return internal_error()
        except Exception as exc:
            logger.exception("%s failed: %s", view.__name__, exc)
            return internal_error()

    return wrapped

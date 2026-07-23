import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or "dev-secret-key-changing-in-production"
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_REFRESH_EACH_REQUEST = True
    ADMIN_DASHBOARD_ENABLED = os.environ.get("ADMIN_DASHBOARD_ENABLED", "true").strip().lower() in (
        "1", "true", "yes", "on"
    )
    RECEIPT_OCR_ENABLED = os.environ.get("RECEIPT_OCR_ENABLED", "false").strip().lower() in (
        "1", "true", "yes", "on"
    )
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", str(10 * 1024 * 1024)))
    MAX_FORM_MEMORY_SIZE = int(os.environ.get("MAX_FORM_MEMORY_SIZE", str(9 * 1024 * 1024)))
    MAX_FORM_PARTS = int(os.environ.get("MAX_FORM_PARTS", "8"))
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SECRET_KEY = os.environ.get('SECRET_KEY')

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class TestingConfig(Config):
    TESTING = True
    DEBUG = True

config = {
    "development" : DevelopmentConfig,
    "production" : ProductionConfig,
    "testing" : TestingConfig,
    "default" : DevelopmentConfig,
}

import os
from urllib.parse import urlsplit

from flask import Flask
from .extensions import db, login_manager


def _configure_database(app):
    # Vercel's Supabase integration injects POSTGRES_URL / DATABASE_URL. Its pooler
    # connection string can carry query params psycopg2 doesn't recognize as a DSN,
    # so rebuild a clean URL and pass sslmode via connect_args instead.
    database_url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
    if database_url:
        parts = urlsplit(database_url)
        clean_url = (
            f"postgresql+psycopg2://{parts.username}:{parts.password}"
            f"@{parts.hostname}:{parts.port or 5432}{parts.path}"
        )
        app.config["SQLALCHEMY_DATABASE_URI"] = clean_url
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"sslmode": "require"}}
        return

    instance_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "instance")
    os.makedirs(instance_dir, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(instance_dir, "payroll.db")


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    _configure_database(app)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20MB

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .auth import auth_bp
    from .upload import upload_bp
    from .dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(dashboard_bp)

    with app.app_context():
        db.create_all()
        from .seed import seed_defaults
        seed_defaults()

    return app

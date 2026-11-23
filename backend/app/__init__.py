import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify


def create_app(test_config=None):
    load_dotenv()
    project_root = Path(__file__).resolve().parents[2]

    # Só a pasta frontend/ é pública (em /frontend/...). backend/ e .env nunca são servidos.
    app = Flask(__name__, static_folder=str(project_root / "frontend"), static_url_path="/frontend")
    app.config.from_mapping(
        PROJECT_ROOT=str(project_root),
        SECRET_KEY=os.getenv("SECRET_KEY", "development-only-change-me"),
        DATABASE_URL=os.getenv("DATABASE_URL", ""),  # PostgreSQL (web). Vazio = SQLite local.
        DATABASE_PATH=os.getenv("DATABASE_PATH", os.path.join(app.instance_path, "ajna.db")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
        # Endereço público do site, usado nos links enviados por e-mail.
        BASE_URL=os.getenv("BASE_URL", "http://127.0.0.1:5000").rstrip("/"),
        # E-mail (SMTP). Vazio = e-mails salvos em backend/instance/outbox/ em vez de enviados.
        SMTP_HOST=os.getenv("SMTP_HOST", ""),
        SMTP_PORT=os.getenv("SMTP_PORT", "587"),
        SMTP_USER=os.getenv("SMTP_USER", ""),
        SMTP_PASSWORD=os.getenv("SMTP_PASSWORD", ""),
        MAIL_FROM=os.getenv("MAIL_FROM", ""),
    )
    if test_config:
        app.config.update(test_config)

    if os.getenv("FLASK_ENV") == "production" and app.config["SECRET_KEY"] == "development-only-change-me":
        raise RuntimeError("SECRET_KEY deve ser configurada em produção.")

    from .database import close_db, init_db
    from .routes.account import account_bp
    from .routes.acupoints import acupoints_bp
    from .routes.auth import auth_bp
    from .routes.crm import crm_bp
    from .routes.patient import patient_bp
    from .routes.public import public_bp
    from .routes.records import records_bp
    from .routes.theory import theory_bp
    from .routes.finance import finance_bp

    if app.config.get("INIT_DB", True):
        init_db(app)
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(account_bp, url_prefix="/api/account")
    app.register_blueprint(patient_bp, url_prefix="/api/patient")
    app.register_blueprint(crm_bp, url_prefix="/api/admin")
    app.register_blueprint(records_bp, url_prefix="/api/admin")
    app.register_blueprint(acupoints_bp, url_prefix="/api/admin")
    app.register_blueprint(theory_bp, url_prefix="/api/admin")
    app.register_blueprint(finance_bp, url_prefix="/api/admin")
    app.teardown_appcontext(close_db)

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    return app

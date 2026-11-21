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
        DATABASE_PATH=os.getenv("DATABASE_PATH", os.path.join(app.instance_path, "ajna.db")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
    )
    if test_config:
        app.config.update(test_config)

    if os.getenv("FLASK_ENV") == "production" and app.config["SECRET_KEY"] == "development-only-change-me":
        raise RuntimeError("SECRET_KEY deve ser configurada em produção.")

    from .database import close_db, init_db
    from .routes.auth import auth_bp
    from .routes.crm import crm_bp
    from .routes.patient import patient_bp
    from .routes.public import public_bp

    init_db(app)
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(patient_bp, url_prefix="/api/patient")
    app.register_blueprint(crm_bp, url_prefix="/api/admin")
    app.teardown_appcontext(close_db)

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    return app

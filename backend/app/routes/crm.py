import re
import sqlite3
from datetime import date

from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

from ..database import get_db
from ..security import csrf_required, login_required, roles_required

crm_bp = Blueprint("crm", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@crm_bp.get("/dashboard")
@login_required
@roles_required("admin")
def dashboard():
    db = get_db()
    patients = db.execute("SELECT COUNT(*) FROM users WHERE role = 'patient' AND active = 1").fetchone()[0]
    today = db.execute(
        "SELECT COUNT(*) FROM appointments WHERE date = ? AND status != 'cancelled'", (date.today().isoformat(),)
    ).fetchone()[0]
    return jsonify(patients=patients, appointments_today=today)


@crm_bp.get("/patients")
@login_required
@roles_required("admin")
def patients():
    rows = get_db().execute(
        "SELECT id, name, email, phone, active, created_at FROM users WHERE role = 'patient' ORDER BY name"
    ).fetchall()
    return jsonify(items=[dict(r) for r in rows])


@crm_bp.post("/patients")
@login_required
@roles_required("admin")
@csrf_required
def create_patient():
    """O administrador cria o acesso do cliente (nome, e-mail e senha inicial)."""
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    phone = str(payload.get("phone", "")).strip() or None
    password = str(payload.get("password", ""))
    if not name or not EMAIL_RE.match(email):
        return jsonify(error="Informe nome e um e-mail válido."), 400
    if len(password) < 8:
        return jsonify(error="A senha inicial precisa ter pelo menos 8 caracteres."), 400
    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (name, email, phone, password_hash, role) VALUES (?, ?, ?, ?, 'patient')",
            (name, email, phone, generate_password_hash(password)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(error="Já existe um acesso com este e-mail."), 409
    return jsonify(ok=True), 201


@crm_bp.patch("/patients/<int:user_id>")
@login_required
@roles_required("admin")
@csrf_required
def update_patient(user_id):
    """Ativa/desativa o acesso ou redefine a senha do cliente."""
    payload = request.get_json(silent=True) or {}
    new_password = str(payload.get("password") or "")
    if new_password and len(new_password) < 8:
        return jsonify(error="A senha precisa ter pelo menos 8 caracteres."), 400
    db = get_db()
    if "active" in payload:
        db.execute("UPDATE users SET active = ? WHERE id = ? AND role = 'patient'",
                   (1 if payload["active"] else 0, user_id))
    if new_password:
        db.execute("UPDATE users SET password_hash = ? WHERE id = ? AND role = 'patient'",
                   (generate_password_hash(new_password), user_id))
    db.commit()
    return jsonify(ok=True)

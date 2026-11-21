from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from ..database import get_db
from ..security import login_required, new_csrf_token

auth_bp = Blueprint("auth", __name__)

# Usado quando o e-mail não existe, para o tempo de resposta não revelar quais contas existem.
_DUMMY_HASH = generate_password_hash("conta-inexistente")


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not email or not password:
        return jsonify(error="Informe e-mail e senha."), 400

    user = get_db().execute(
        "SELECT id, name, role, password_hash FROM users WHERE email = ? AND active = 1", (email,)
    ).fetchone()
    password_ok = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password)
    if not user or not password_ok:
        return jsonify(error="E-mail ou senha incorretos."), 401

    session.clear()
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    return jsonify(role=user["role"], name=user["name"], csrf_token=new_csrf_token())


@auth_bp.get("/me")
@login_required
def me():
    user = get_db().execute(
        "SELECT name, email, role FROM users WHERE id = ? AND active = 1", (session["user_id"],)
    ).fetchone()
    if not user:
        session.clear()
        return jsonify(error="Autenticação necessária."), 401
    return jsonify(**dict(user), csrf_token=session.get("csrf_token"))


@auth_bp.post("/logout")
def logout():
    session.clear()
    return "", 204

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash

from ..database import get_db
from ..security import new_csrf_token

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not email or not password:
        return jsonify(error="Informe e-mail e senha."), 400

    user = get_db().users.find_one({"email": email, "active": True})
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify(error="Credenciais inválidas."), 401

    session.clear()
    session["user_id"] = str(user["_id"])
    session["role"] = user["role"]
    return jsonify(role=user["role"], csrf_token=new_csrf_token())


@auth_bp.post("/logout")
def logout():
    session.clear()
    return "", 204


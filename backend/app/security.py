from functools import wraps
from secrets import compare_digest, token_urlsafe

from flask import jsonify, request, session


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(error="Autenticação necessária."), 401
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("role") not in roles:
                return jsonify(error="Acesso não autorizado."), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator


def csrf_required(view):
    """Exige o cabeçalho X-CSRF-Token em requisições que alteram dados."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = session.get("csrf_token", "")
        sent = request.headers.get("X-CSRF-Token", "")
        if not expected or not compare_digest(expected, sent):
            return jsonify(error="Sessão expirada. Entre novamente."), 403
        return view(*args, **kwargs)
    return wrapped


def new_csrf_token():
    token = token_urlsafe(32)
    session["csrf_token"] = token
    return token

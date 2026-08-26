from functools import wraps
from secrets import token_urlsafe

from flask import abort, jsonify, session


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
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def new_csrf_token():
    token = token_urlsafe(32)
    session["csrf_token"] = token
    return token


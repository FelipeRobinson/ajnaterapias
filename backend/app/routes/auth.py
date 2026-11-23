import hashlib
from datetime import datetime, timedelta
from html import escape
from secrets import token_urlsafe

from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from ..database import get_db, primary_admin
from ..mailer import send_email
from ..security import csrf_required, login_required, new_csrf_token

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
        "SELECT name, email, role, avatar FROM users WHERE id = ? AND active = 1", (session["user_id"],)
    ).fetchone()
    if not user:
        session.clear()
        return jsonify(error="Autenticação necessária."), 401
    return jsonify(**dict(user), csrf_token=session.get("csrf_token"))


MAX_AVATAR = 300_000  # a tela reduz a foto para 320px antes de enviar; isto é só um teto


@auth_bp.put("/me/avatar")
@login_required
@csrf_required
def set_avatar():
    """Foto de perfil opcional (admin ou cliente). Enviar image=null remove a foto."""
    image = (request.get_json(silent=True) or {}).get("image")
    if image is not None:
        image = str(image)
        if not image.startswith(("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")):
            return jsonify(error="Envie uma imagem JPG, PNG ou WEBP."), 400
        if len(image) > MAX_AVATAR:
            return jsonify(error="A foto é grande demais."), 400
    db = get_db()
    db.execute("UPDATE users SET avatar = ? WHERE id = ?", (image, session["user_id"]))
    db.commit()
    return jsonify(ok=True, avatar=image)


@auth_bp.post("/logout")
def logout():
    session.clear()
    return "", 204


# ------------------------------------------------------------------ esqueci a senha
RESET_MINUTES = 30
RESET_COOLDOWN_SECONDS = 120  # evita encher a caixa de alguém com pedidos repetidos
MIN_PASSWORD = {"admin": 12, "patient": 8}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


@auth_bp.post("/forgot")
def forgot_password():
    """Envia um link de redefinição ao e-mail informado (cliente ou administrador).

    A resposta é SEMPRE a mesma, exista ou não a conta, para não revelar quem tem cadastro.
    """
    email = str((request.get_json(silent=True) or {}).get("email", "")).strip().lower()
    answer = jsonify(ok=True, message="Se este e-mail estiver cadastrado, enviaremos um link para criar uma nova senha.")
    if not email:
        return jsonify(error="Informe seu e-mail."), 400
    db = get_db()
    user = db.execute("SELECT id, name, email FROM users WHERE email = ? AND active = 1", (email,)).fetchone()
    if not user:
        return answer
    recent = (datetime.now() - timedelta(seconds=RESET_COOLDOWN_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
    if db.execute("SELECT 1 FROM password_resets WHERE user_id = ? AND created_at > ?", (user["id"], recent)).fetchone():
        return answer

    db.execute("UPDATE password_resets SET used = 1 WHERE user_id = ? AND used = 0", (user["id"],))
    token = token_urlsafe(32)
    expires = (datetime.now() + timedelta(minutes=RESET_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute("INSERT INTO password_resets (user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
               (user["id"], _token_hash(token), expires, _now()))
    db.commit()

    link = f'{current_app.config["BASE_URL"]}/frontend/crm/redefinir.html?token={token}'
    send_email(
        user["email"],
        "Criar nova senha — Ajna Terapias",
        f"Olá, {user['name']}!\n\nRecebemos um pedido para criar uma nova senha de acesso à Ajna Terapias.\n"
        f"Abra o link abaixo (válido por {RESET_MINUTES} minutos):\n{link}\n\n"
        "Se não foi você, ignore este e-mail: sua senha continua a mesma.",
        _reset_html(user["name"], link),
    )
    return answer


@auth_bp.post("/reset")
def reset_password():
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("token", ""))
    password = str(payload.get("password", ""))
    db = get_db()
    row = db.execute(
        """SELECT r.id, r.user_id, r.expires_at, r.used, u.role, u.name, u.email
           FROM password_resets r JOIN users u ON u.id = r.user_id WHERE r.token_hash = ? AND u.active = 1""",
        (_token_hash(token),),
    ).fetchone() if token else None
    if not row or row["used"]:
        return jsonify(error="Link inválido ou já utilizado. Peça um novo em “Esqueci minha senha”."), 400
    if row["expires_at"] < _now():
        return jsonify(error="Link expirado. Peça um novo em “Esqueci minha senha”."), 400
    minimum = MIN_PASSWORD.get(row["role"], 8)
    if len(password) < minimum:
        return jsonify(error=f"A nova senha precisa ter pelo menos {minimum} caracteres.", min_length=minimum), 400

    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(password), row["user_id"]))
    db.execute("UPDATE password_resets SET used = 1 WHERE user_id = ?", (row["user_id"],))
    db.commit()

    # Aviso de segurança à própria pessoa e, se for administrador, também à administradora principal.
    notice = ("A senha de acesso à Ajna Terapias foi redefinida pelo link de “Esqueci minha senha”.\n"
              "Se não foi você, entre em contato com a clínica imediatamente.")
    recipients = {row["email"]}
    if row["role"] == "admin":
        principal = primary_admin(db)
        if principal:
            recipients.add(principal["email"])
    for to in recipients:
        try:
            send_email(to, f"Senha redefinida — {row['name']} — Ajna Terapias", notice)
        except Exception:
            current_app.logger.exception("Falha ao enviar aviso de senha redefinida para %s", to)
    return jsonify(ok=True)


@auth_bp.get("/reset-info")
def reset_info():
    """A página de nova senha usa isto para mostrar o tamanho mínimo e validar o link antes de digitar."""
    token = request.args.get("token", "")
    row = get_db().execute(
        """SELECT r.expires_at, r.used, u.role FROM password_resets r JOIN users u ON u.id = r.user_id
           WHERE r.token_hash = ? AND u.active = 1""", (_token_hash(token),),
    ).fetchone() if token else None
    if not row or row["used"] or row["expires_at"] < _now():
        return jsonify(valid=False), 200
    return jsonify(valid=True, min_length=MIN_PASSWORD.get(row["role"], 8))


def _reset_html(name, link):
    return f"""
<div style="font-family:Segoe UI,Arial,sans-serif;max-width:520px;margin:auto;color:#24152e">
  <div style="background:linear-gradient(135deg,#24063a,#7800b4);color:#fff;padding:24px;border-radius:16px 16px 0 0">
    <h2 style="margin:0">🪷 Ajna Terapias</h2>
    <p style="margin:6px 0 0;opacity:.85">Criar nova senha</p>
  </div>
  <div style="border:1px solid #ebe2ef;border-top:0;padding:24px;border-radius:0 0 16px 16px">
    <p>Olá, <b>{escape(name)}</b>!</p>
    <p>Recebemos um pedido para criar uma nova senha de acesso.</p>
    <p style="text-align:center;margin:28px 0">
      <a href="{escape(link)}" style="background:#7800b4;color:#fff;padding:14px 26px;border-radius:12px;text-decoration:none;font-weight:700">
        Criar nova senha</a>
    </p>
    <p style="color:#6c5b73;font-size:13px">O link vale por {RESET_MINUTES} minutos. Se não foi você, ignore este e-mail: sua senha continua a mesma.</p>
  </div>
</div>"""

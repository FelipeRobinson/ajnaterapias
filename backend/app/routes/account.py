"""Alteração dos dados de login do administrador, confirmada por e-mail.

Fluxo:
  1. No painel ("Minha conta"), o admin informa o que quer mudar + a SENHA ATUAL.
  2. O sistema envia um link de confirmação para o E-MAIL ATUAL da conta (válido por 30 min).
  3. Só ao clicar no link a alteração é aplicada. Depois, um aviso é enviado ao(s) e-mail(s).
"""
import hashlib
import json
import re
from datetime import datetime, timedelta
from html import escape
from secrets import token_urlsafe

from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from ..database import get_db
from ..mailer import mask_email, send_email
from ..security import csrf_required, login_required, roles_required

account_bp = Blueprint("account", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TOKEN_MINUTES = 30
MIN_ADMIN_PASSWORD = 12
FIELD_LABELS = {"name": "Nome", "email": "E-mail de login", "phone": "Telefone", "password": "Senha"}


def _admin(view):
    return login_required(roles_required("admin")(view))


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@account_bp.get("")
@_admin
def my_account():
    user = get_db().execute("SELECT name, email, phone FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    return jsonify(dict(user))


@account_bp.post("/change-request")
@_admin
@csrf_required
def change_request():
    payload = request.get_json(silent=True) or {}
    db = get_db()
    user = db.execute("SELECT id, name, email, phone, password_hash FROM users WHERE id = ?",
                      (session["user_id"],)).fetchone()
    if not check_password_hash(user["password_hash"], str(payload.get("current_password", ""))):
        return jsonify(error="Senha atual incorreta."), 400

    changes = {}
    name = str(payload.get("name", "")).strip()
    if name and name != user["name"]:
        changes["name"] = name
    email = str(payload.get("email", "")).strip().lower()
    if email and email != user["email"]:
        if not EMAIL_RE.match(email):
            return jsonify(error="Informe um e-mail válido."), 400
        if db.execute("SELECT 1 FROM users WHERE email = ? AND id != ?", (email, user["id"])).fetchone():
            return jsonify(error="Esse e-mail já está em uso por outra conta."), 409
        changes["email"] = email
    if "phone" in payload:
        phone = str(payload.get("phone") or "").strip() or None
        if phone != user["phone"]:
            changes["phone"] = phone
    new_password = str(payload.get("new_password", ""))
    if new_password:
        if len(new_password) < MIN_ADMIN_PASSWORD:
            return jsonify(error=f"A nova senha precisa ter pelo menos {MIN_ADMIN_PASSWORD} caracteres."), 400
        changes["password_hash"] = generate_password_hash(new_password)  # nunca guardamos a senha em texto
    if not changes:
        return jsonify(error="Nenhuma alteração informada."), 400

    # Um pedido novo invalida os anteriores ainda não usados.
    db.execute("UPDATE account_changes SET used = 1 WHERE user_id = ? AND used = 0", (user["id"],))
    token = token_urlsafe(32)
    expires = (datetime.now() + timedelta(minutes=TOKEN_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute("INSERT INTO account_changes (user_id, token_hash, payload, expires_at) VALUES (?, ?, ?, ?)",
               (user["id"], _hash(token), json.dumps(changes), expires))
    db.commit()

    link = f'{current_app.config["BASE_URL"]}/api/account/confirm?token={token}'
    items = [FIELD_LABELS["password" if k == "password_hash" else k] for k in changes]
    lines = "\n".join(f"  • {i}" for i in items)
    send_email(
        user["email"],
        "Confirme a alteração dos seus dados de acesso — Ajna Terapias",
        f"Olá, {user['name']}!\n\nFoi pedida uma alteração nos dados de acesso do painel da Ajna Terapias:\n{lines}\n\n"
        f"Para confirmar, abra o link abaixo (válido por {TOKEN_MINUTES} minutos):\n{link}\n\n"
        "Se não foi você, ignore este e-mail: nada será alterado. Recomendamos trocar sua senha.",
        _email_html(user["name"], items, link),
    )
    return jsonify(ok=True, sent_to=mask_email(user["email"]), minutes=TOKEN_MINUTES)


@account_bp.get("/confirm")
def confirm():
    token = request.args.get("token", "")
    db = get_db()
    row = db.execute("SELECT * FROM account_changes WHERE token_hash = ?", (_hash(token),)).fetchone() if token else None
    if not row or row["used"]:
        return _page("Link inválido ou já utilizado", "Peça a alteração novamente pelo painel."), 400
    if row["expires_at"] < _now():
        return _page("Link expirado", f"O link vale por {TOKEN_MINUTES} minutos. Peça a alteração novamente pelo painel."), 400

    changes = json.loads(row["payload"])
    user = db.execute("SELECT id, name, email FROM users WHERE id = ?", (row["user_id"],)).fetchone()
    if "email" in changes and db.execute("SELECT 1 FROM users WHERE email = ? AND id != ?",
                                         (changes["email"], user["id"])).fetchone():
        return _page("E-mail indisponível", "Esse e-mail passou a ser usado por outra conta. Peça a alteração novamente."), 409

    columns = ", ".join(f"{k} = ?" for k in changes)  # chaves vêm só do nosso próprio código
    db.execute(f"UPDATE users SET {columns} WHERE id = ?", (*changes.values(), user["id"]))
    db.execute("UPDATE account_changes SET used = 1 WHERE id = ?", (row["id"],))
    db.commit()

    # Aviso de segurança para o e-mail antigo (e o novo, se mudou).
    items = [FIELD_LABELS["password" if k == "password_hash" else k] for k in changes]
    notice = ("Os dados de acesso do painel da Ajna Terapias foram alterados: " + ", ".join(items) +
              ".\nSe não foi você, entre em contato com o responsável técnico imediatamente.")
    recipients = {user["email"], changes.get("email", user["email"])}
    for to in recipients:
        try:
            send_email(to, "Seus dados de acesso foram alterados — Ajna Terapias", notice)
        except Exception:  # o aviso não deve desfazer a alteração já confirmada
            current_app.logger.exception("Falha ao enviar aviso de alteração para %s", to)

    session.clear()  # obriga a entrar de novo com os dados novos
    return _page("Alteração confirmada! ✅", "Seus dados de acesso foram atualizados. Entre novamente no painel.", ok=True)


def _email_html(name, items, link):
    li = "".join(f"<li>{escape(i)}</li>" for i in items)
    return f"""
<div style="font-family:Segoe UI,Arial,sans-serif;max-width:520px;margin:auto;color:#24152e">
  <div style="background:linear-gradient(135deg,#24063a,#7800b4);color:#fff;padding:24px;border-radius:16px 16px 0 0">
    <h2 style="margin:0">🪷 Ajna Terapias</h2>
    <p style="margin:6px 0 0;opacity:.85">Confirmação de alteração de acesso</p>
  </div>
  <div style="border:1px solid #ebe2ef;border-top:0;padding:24px;border-radius:0 0 16px 16px">
    <p>Olá, <b>{escape(name)}</b>!</p>
    <p>Foi pedida uma alteração nos dados de acesso do painel:</p>
    <ul>{li}</ul>
    <p style="text-align:center;margin:28px 0">
      <a href="{escape(link)}" style="background:#7800b4;color:#fff;padding:14px 26px;border-radius:12px;text-decoration:none;font-weight:700">
        Confirmar alteração</a>
    </p>
    <p style="color:#6c5b73;font-size:13px">O link vale por {TOKEN_MINUTES} minutos. Se não foi você, ignore este e-mail: nada será alterado.</p>
  </div>
</div>"""


def _page(title, text, ok=False):
    color = "#15803d" if ok else "#b4233f"
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)} | Ajna Terapias</title></head>
<body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#16001f;font-family:system-ui,sans-serif">
<main style="background:#fff;max-width:420px;margin:20px;padding:32px;border-radius:20px;text-align:center">
<h1 style="color:{color};font-size:1.4rem">{escape(title)}</h1><p style="color:#6c5b73">{escape(text)}</p>
<a href="/login" style="display:inline-block;margin-top:12px;background:#7800b4;color:#fff;padding:12px 22px;border-radius:12px;text-decoration:none;font-weight:700">Ir para o login</a>
</main></body></html>"""

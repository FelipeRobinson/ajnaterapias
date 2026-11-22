"""Envio de e-mails.

Com SMTP configurado no .env (ex.: Gmail com "senha de app"), o e-mail é enviado de verdade.
Sem SMTP, o e-mail é salvo como arquivo em backend/instance/outbox/ — útil para testar localmente.
"""
import os
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage

from flask import current_app


def send_email(to, subject, text, html=None):
    cfg = current_app.config
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.get("MAIL_FROM") or cfg.get("SMTP_USER") or "Ajna Terapias <nao-responda@ajna.local>"
    msg["To"] = to
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    if not cfg.get("SMTP_HOST"):
        if cfg.get("TESTING"):
            current_app.config.setdefault("OUTBOX", []).append(msg)
            return None
        outbox = os.path.join(current_app.instance_path, "outbox")
        os.makedirs(outbox, exist_ok=True)
        path = os.path.join(outbox, f"{datetime.now():%Y%m%d-%H%M%S-%f}.eml")
        with open(path, "wb") as f:
            f.write(bytes(msg))
        current_app.logger.warning("SMTP não configurado: e-mail para %s salvo em %s", to, path)
        current_app.config.setdefault("OUTBOX", []).append(msg)  # usado nos testes
        return path

    port = int(cfg.get("SMTP_PORT") or 587)
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(cfg["SMTP_HOST"], port, context=context, timeout=20) as smtp:
            smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(cfg["SMTP_HOST"], port, timeout=20) as smtp:
            smtp.starttls(context=context)
            smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            smtp.send_message(msg)
    return None


def mask_email(email):
    """ellenrobinsoner@gmail.com -> el***********er@gmail.com"""
    user, _, domain = email.partition("@")
    if len(user) <= 4:
        return f"{user[0]}***@{domain}"
    return f"{user[:2]}{'*' * (len(user) - 4)}{user[-2:]}@{domain}"

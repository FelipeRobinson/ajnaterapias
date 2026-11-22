"""Esqueci minha senha (cliente e administrador) e administradora principal."""
import re

from werkzeug.security import generate_password_hash

from app.database import get_db, set_setting
from tests.test_admin import admin_client, new_patient


def setup(tmp_path):
    c, h = admin_client(tmp_path)
    app = c.application
    app.config.update(SMTP_HOST="", OUTBOX=[], BASE_URL="http://teste")
    return app, c, h


def token_from_last_email(app):
    body = app.config["OUTBOX"][-1].get_body(("plain",)).get_content()
    return re.search(r"token=(\S+)", body).group(1)


def test_patient_forgot_and_reset(tmp_path):
    app, c, h = setup(tmp_path)
    new_patient(c, h)
    anon = app.test_client()

    r = anon.post("/api/auth/forgot", json={"email": "ana@x.com"})
    assert r.status_code == 200
    assert app.config["OUTBOX"][-1]["To"] == "ana@x.com"
    token = token_from_last_email(app)
    assert anon.get(f"/api/auth/reset-info?token={token}").get_json() == {"valid": True, "min_length": 8}

    assert anon.post("/api/auth/reset", json={"token": token, "password": "123"}).status_code == 400
    assert anon.post("/api/auth/reset", json={"token": token, "password": "nova-senha-ana"}).status_code == 200
    assert anon.post("/api/auth/login", json={"email": "ana@x.com", "password": "nova-senha-ana"}).status_code == 200
    # link de uso único
    assert anon.post("/api/auth/reset", json={"token": token, "password": "outra-senha-ana"}).status_code == 400
    assert anon.get(f"/api/auth/reset-info?token={token}").get_json() == {"valid": False}


def test_unknown_email_gets_same_answer_and_no_email(tmp_path):
    app, c, h = setup(tmp_path)
    anon = app.test_client()
    known = anon.post("/api/auth/forgot", json={"email": "adm@x.com"}).get_json()
    unknown = anon.post("/api/auth/forgot", json={"email": "ninguem@x.com"}).get_json()
    assert known == unknown
    assert [m["To"] for m in app.config["OUTBOX"]] == ["adm@x.com"]


def test_cooldown_between_requests(tmp_path):
    app, c, h = setup(tmp_path)
    anon = app.test_client()
    anon.post("/api/auth/forgot", json={"email": "adm@x.com"})
    anon.post("/api/auth/forgot", json={"email": "adm@x.com"})
    assert len(app.config["OUTBOX"]) == 1


def test_admin_reset_needs_12_chars_and_notifies_primary(tmp_path):
    app, c, h = setup(tmp_path)
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO users (name, email, password_hash, role) VALUES ('Ellen', 'ellen@x.com', ?, 'admin')",
                   (generate_password_hash("senha-da-ellen-1"),))
        set_setting(db, "primary_admin_id", db.execute("SELECT id FROM users WHERE email='ellen@x.com'").fetchone()["id"])
        db.commit()
    anon = app.test_client()
    anon.post("/api/auth/forgot", json={"email": "adm@x.com"})
    token = token_from_last_email(app)
    assert anon.get(f"/api/auth/reset-info?token={token}").get_json()["min_length"] == 12
    assert anon.post("/api/auth/reset", json={"token": token, "password": "curta-123"}).status_code == 400
    assert anon.post("/api/auth/reset", json={"token": token, "password": "senha-admin-nova"}).status_code == 200
    notices = {m["To"] for m in app.config["OUTBOX"] if "redefinida" in m["Subject"]}
    assert notices == {"adm@x.com", "ellen@x.com"}


def test_admin_change_is_confirmed_by_primary_admin(tmp_path):
    app, c, h = setup(tmp_path)
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO users (name, email, password_hash, role) VALUES ('Ellen', 'ellen@x.com', ?, 'admin')",
                   (generate_password_hash("senha-da-ellen-1"),))
        set_setting(db, "primary_admin_id", db.execute("SELECT id FROM users WHERE email='ellen@x.com'").fetchone()["id"])
        db.commit()
    r = c.post("/api/account/change-request", headers=h, json={"current_password": "senha-admin-123", "name": "Outro nome"})
    assert r.status_code == 200
    msg = app.config["OUTBOX"][-1]
    assert msg["To"] == "ellen@x.com"  # a confirmação vai para a principal, não para quem pediu
    assert "adm@x.com" in msg.get_body(("plain",)).get_content()

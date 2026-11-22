"""Alteração do login do administrador com confirmação por e-mail."""
import re

from tests.test_admin import admin_client


def setup(tmp_path):
    c, h = admin_client(tmp_path)
    app = c.application
    app.config.update(SMTP_HOST="", OUTBOX=[], BASE_URL="http://teste")
    return app, c, h


def last_link(app):
    body = app.config["OUTBOX"][-1].get_body(("plain",)).get_content()
    return re.search(r"http://teste(/api/account/confirm\?token=\S+)", body).group(1)


def test_change_requires_email_confirmation(tmp_path):
    app, c, h = setup(tmp_path)
    r = c.post("/api/account/change-request", headers=h, json={
        "current_password": "senha-admin-123", "email": "novo@x.com",
        "phone": "(19) 90000-0000", "new_password": "senha-nova-segura"})
    assert r.status_code == 200 and r.get_json()["sent_to"].endswith("@x.com")

    # o e-mail vai para o endereço ATUAL, e nada mudou ainda
    msg = app.config["OUTBOX"][-1]
    assert msg["To"] == "adm@x.com"
    assert c.application.test_client().post("/api/auth/login", json={"email": "novo@x.com", "password": "senha-nova-segura"}).status_code == 401

    link = last_link(app)
    page = c.get(link)
    assert page.status_code == 200 and "confirmada" in page.get_data(as_text=True)

    fresh = app.test_client()
    assert fresh.post("/api/auth/login", json={"email": "adm@x.com", "password": "senha-admin-123"}).status_code == 401
    assert fresh.post("/api/auth/login", json={"email": "novo@x.com", "password": "senha-nova-segura"}).status_code == 200
    assert fresh.get("/api/account").get_json()["phone"] == "(19) 90000-0000"

    # avisos de alteração enviados ao e-mail antigo e ao novo
    notices = {m["To"] for m in app.config["OUTBOX"] if "foram alterados" in m["Subject"]}
    assert notices == {"adm@x.com", "novo@x.com"}

    # o link não funciona duas vezes
    assert c.get(link).status_code == 400


def test_wrong_current_password_and_weak_password(tmp_path):
    app, c, h = setup(tmp_path)
    assert c.post("/api/account/change-request", headers=h,
                  json={"current_password": "errada", "name": "X"}).status_code == 400
    assert c.post("/api/account/change-request", headers=h,
                  json={"current_password": "senha-admin-123", "new_password": "curta"}).status_code == 400
    assert app.config["OUTBOX"] == []


def test_new_request_invalidates_old_link_and_expired_link(tmp_path):
    app, c, h = setup(tmp_path)
    body = {"current_password": "senha-admin-123", "name": "Nome 1"}
    c.post("/api/account/change-request", headers=h, json=body)
    first = last_link(app)
    c.post("/api/account/change-request", headers=h, json={**body, "name": "Nome 2"})
    second = last_link(app)
    assert c.get(first).status_code == 400

    from app.database import get_db
    with app.app_context():
        db = get_db()
        db.execute("UPDATE account_changes SET expires_at = '2000-01-01 00:00:00' WHERE used = 0")
        db.commit()
    assert "expirado" in c.get(second).get_data(as_text=True)


def test_only_admin_and_csrf(tmp_path):
    app, c, h = setup(tmp_path)
    assert c.post("/api/account/change-request", json={"current_password": "senha-admin-123", "name": "X"}).status_code == 403
    assert app.test_client().get("/api/account").status_code == 401

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db


def make_app(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE_PATH": str(tmp_path / "t.db"), "DATABASE_URL": ""})
    from app.database import init_db
    init_db(app)
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
                   ("Adm", "adm@x.com", generate_password_hash("senha-admin-123")))
        db.commit()
    return app


def test_admin_creates_patient_who_can_log_in(tmp_path):
    app = make_app(tmp_path)
    admin = app.test_client()
    r = admin.post("/api/auth/login", json={"email": "adm@x.com", "password": "senha-admin-123"})
    assert r.status_code == 200 and r.get_json()["role"] == "admin"
    token = r.get_json()["csrf_token"]

    # Sem CSRF é recusado
    assert admin.post("/api/admin/patients", json={"name": "A", "email": "a@x.com", "password": "12345678"}).status_code == 403
    r = admin.post("/api/admin/patients", json={"name": "Ana", "email": "ana@x.com", "password": "12345678"},
                   headers={"X-CSRF-Token": token})
    assert r.status_code == 201

    client = app.test_client()
    r = client.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"})
    assert r.status_code == 200 and r.get_json()["role"] == "patient"
    assert client.get("/api/admin/patients").status_code == 403
    assert client.get("/api/patient/me/appointments").status_code == 200


def test_wrong_password(tmp_path):
    app = make_app(tmp_path)
    r = app.test_client().post("/api/auth/login", json={"email": "adm@x.com", "password": "errada"})
    assert r.status_code == 401


def test_duplicate_email_is_rejected(tmp_path):
    app = make_app(tmp_path)
    admin = app.test_client()
    token = admin.post("/api/auth/login", json={"email": "adm@x.com", "password": "senha-admin-123"}).get_json()["csrf_token"]
    body = {"name": "Ana", "email": "ana@x.com", "password": "12345678"}
    assert admin.post("/api/admin/patients", json=body, headers={"X-CSRF-Token": token}).status_code == 201
    assert admin.post("/api/admin/patients", json=body, headers={"X-CSRF-Token": token}).status_code == 409
    assert admin.get("/api/admin/dashboard").get_json()["patients"] == 1

"""Testes do painel do administrador: clientes (CRUD) e agenda."""
from datetime import date

from tests.test_auth import make_app


def admin_client(tmp_path):
    app = make_app(tmp_path)
    app.config["CLOSED_WEEKDAYS"] = ()  # os testes agendam "hoje", que pode cair numa segunda ou sexta
    c = app.test_client()
    token = c.post("/api/auth/login", json={"email": "adm@x.com", "password": "senha-admin-123"}).get_json()["csrf_token"]
    h = {"X-CSRF-Token": token}
    return c, h


def new_patient(c, h, email="ana@x.com"):
    assert c.post("/api/admin/patients", json={"name": "Ana", "email": email, "password": "12345678"}, headers=h).status_code == 201
    return next(p["id"] for p in c.get("/api/admin/patients").get_json()["items"] if p["email"] == email)


def test_edit_and_delete_patient(tmp_path):
    c, h = admin_client(tmp_path)
    pid = new_patient(c, h)
    other = new_patient(c, h, "bia@x.com")

    r = c.patch(f"/api/admin/patients/{pid}", json={"name": "Ana Souza", "phone": "1199"}, headers=h)
    assert r.status_code == 200
    p = next(x for x in c.get("/api/admin/patients").get_json()["items"] if x["id"] == pid)
    assert p["name"] == "Ana Souza" and p["phone"] == "1199"

    # e-mail repetido é recusado
    assert c.patch(f"/api/admin/patients/{pid}", json={"email": "bia@x.com"}, headers=h).status_code == 409

    assert c.delete(f"/api/admin/patients/{other}", headers=h).status_code == 204
    assert len(c.get("/api/admin/patients").get_json()["items"]) == 1


def test_agenda_flow(tmp_path):
    c, h = admin_client(tmp_path)
    pid = new_patient(c, h)
    today = date.today().isoformat()
    body = {"patient_user_id": pid, "date": today, "start": "09:00", "end": "10:00"}

    assert c.post("/api/admin/appointments", json=body, headers=h).status_code == 201
    # horário sobreposto é recusado
    assert c.post("/api/admin/appointments", json={**body, "start": "09:30", "end": "10:30"}, headers=h).status_code == 409
    # término antes do início é recusado
    assert c.post("/api/admin/appointments", json={**body, "start": "11:00", "end": "10:00"}, headers=h).status_code == 400

    items = c.get(f"/api/admin/appointments?from={today}&to={today}").get_json()["items"]
    assert len(items) == 1 and items[0]["patient_name"] == "Ana"
    aid = items[0]["id"]

    dash = c.get("/api/admin/dashboard").get_json()
    assert dash["appointments_today"] == 1 and dash["today"][0]["start"] == "09:00"

    assert c.patch(f"/api/admin/appointments/{aid}", json={"start": "14:00", "end": "15:00"}, headers=h).status_code == 200
    assert c.patch(f"/api/admin/appointments/{aid}", json={"status": "done"}, headers=h).status_code == 200

    # cliente com histórico não pode ser excluído
    assert c.delete(f"/api/admin/patients/{pid}", headers=h).status_code == 409

    # o próprio cliente vê a sessão
    cli = c.application.test_client()
    cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"})
    mine = cli.get("/api/patient/me/appointments").get_json()["items"]
    assert [{k: v for k, v in m.items() if k != "id"} for m in mine] == [{"date": today, "start": "14:00", "end": "15:00", "status": "done"}]

    assert c.delete(f"/api/admin/appointments/{aid}", headers=h).status_code == 204
    assert c.delete(f"/api/admin/patients/{pid}", headers=h).status_code == 204


def test_patient_cannot_use_admin_routes(tmp_path):
    c, h = admin_client(tmp_path)
    new_patient(c, h)
    cli = c.application.test_client()
    cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"})
    assert cli.get("/api/admin/appointments").status_code == 403
    assert cli.get("/api/admin/dashboard").status_code == 403

"""Prontuário (ficha fixa) e protocolo (a cada sessão): só o administrador acessa."""
from datetime import date

from tests.test_admin import admin_client, new_patient


def setup(tmp_path):
    c, h = admin_client(tmp_path)
    pid = new_patient(c, h)
    today = date.today().isoformat()
    assert c.post("/api/admin/appointments", headers=h,
                  json={"patient_user_id": pid, "date": today, "start": "09:00", "end": "10:00"}).status_code == 201
    aid = c.get(f"/api/admin/appointments?from={today}&to={today}").get_json()["items"][0]["id"]
    return c, h, pid, aid


def test_record_is_created_once_and_edited(tmp_path):
    c, h, pid, aid = setup(tmp_path)
    assert c.get(f"/api/admin/patients/{pid}/file").get_json()["record"] is None

    body = {"main_complaint": "Dor lombar", "pain_scale": "7", "conditions": ["Insônia", "inventado"],
            "gender": "Masculino", "consent": True, "campo_desconhecido": "x" * 10}
    assert c.put(f"/api/admin/patients/{pid}/record", json=body, headers=h).status_code == 200
    rec = c.get(f"/api/admin/patients/{pid}/file").get_json()["record"]["data"]
    # só campos conhecidos, com valores válidos
    assert rec == {"main_complaint": "Dor lombar", "pain_scale": 7, "conditions": ["Insônia"],
                   "gender": "Masculino", "consent": True}

    assert c.put(f"/api/admin/patients/{pid}/record", json={**body, "main_complaint": "Dor lombar crônica"},
                 headers=h).status_code == 200
    file = c.get(f"/api/admin/patients/{pid}/file").get_json()
    assert file["record"]["data"]["main_complaint"] == "Dor lombar crônica"


def test_protocol_per_session_marks_done(tmp_path):
    c, h, pid, aid = setup(tmp_path)
    r = c.put(f"/api/admin/appointments/{aid}/protocol", headers=h,
              json={"techniques": ["Acupuntura", "Ventosaterapia"], "pain_before": 7, "pain_after": 3,
                    "points": "GB34, BL23"})
    assert r.status_code == 200
    s = c.get(f"/api/admin/patients/{pid}/file").get_json()["sessions"][0]
    assert s["status"] == "done"
    assert s["protocol"]["techniques"] == ["Acupuntura", "Ventosaterapia"]
    assert s["protocol"]["pain_after"] == 3

    # sessão com protocolo não pode ser excluída
    assert c.delete(f"/api/admin/appointments/{aid}", headers=h).status_code == 409
    items = c.get(f"/api/admin/appointments?from={date.today()}&to={date.today()}").get_json()["items"]
    assert items[0]["has_protocol"] == 1


def test_no_protocol_for_requested_or_cancelled(tmp_path):
    c, h, pid, aid = setup(tmp_path)
    c.patch(f"/api/admin/appointments/{aid}", json={"status": "cancelled"}, headers=h)
    assert c.put(f"/api/admin/appointments/{aid}/protocol", headers=h, json={"notes": "x"}).status_code == 400


def test_patient_never_sees_record_or_protocol(tmp_path):
    c, h, pid, aid = setup(tmp_path)
    c.put(f"/api/admin/patients/{pid}/record", json={"main_complaint": "segredo clínico"}, headers=h)
    c.put(f"/api/admin/appointments/{aid}/protocol", json={"notes": "anotação interna"}, headers=h)

    cli = c.application.test_client()
    cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"})
    assert cli.get(f"/api/admin/patients/{pid}/file").status_code == 403
    assert cli.get("/api/admin/forms").status_code == 403
    mine = cli.get("/api/patient/me/appointments").get_json()["items"]
    assert set(mine[0]) == {"id", "date", "start", "end", "status"}  # nada além de data/hora/situação
    for path in ("/api/patient/me/appointments", "/api/patient/me", f"/api/patient/slots?date={date.today()}"):
        text = cli.get(path).get_data(as_text=True)
        assert "segredo" not in text and "interna" not in text

"""Horários marcados como indisponíveis pela administração."""
from datetime import date, timedelta

from tests.test_admin import admin_client, new_patient


def _next_weekday(n=0):
    """Próxima terça (+n dias), sempre no futuro e dentro do período de agendamento."""
    d = date.today() + timedelta(days=1)
    while d.weekday() != 1:
        d += timedelta(days=1)
    return (d + timedelta(days=n)).isoformat()


def test_block_hides_slots_and_prevents_booking(tmp_path):
    c, h = admin_client(tmp_path)
    pid = new_patient(c, h)
    day = _next_weekday()
    r = c.post("/api/admin/blocks", headers=h, json={"date": day, "start": "08:00", "end": "10:00", "reason": "Curso"})
    assert r.status_code == 201 and r.get_json()["created"] == 1

    # a administração não consegue agendar por cima
    r = c.post("/api/admin/appointments", headers=h, json={"patient_user_id": pid, "date": day, "start": "09:00", "end": "10:00"})
    assert r.status_code == 409 and "indisponível" in r.get_json()["error"]
    assert c.post("/api/admin/appointments", headers=h,
                  json={"patient_user_id": pid, "date": day, "start": "10:00", "end": "11:00"}).status_code == 201

    blocks = c.get(f"/api/admin/blocks?from={day}&to={day}").get_json()["items"]
    assert len(blocks) == 1 and blocks[0]["reason"] == "Curso"

    # o cliente não vê o horário bloqueado e não consegue pedi-lo
    cli = c.application.test_client()
    cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"})
    starts = [s["start"] for s in cli.get(f"/api/patient/slots?date={day}").get_json()["slots"]]
    assert "08:00" not in starts and "09:00" not in starts and "10:00" not in starts  # 10h já tem consulta
    busy = cli.get(f"/api/patient/availability?date={day}").get_json()["busy"]
    assert {"start": "08:00", "end": "10:00"} in busy and all(set(b) == {"start", "end"} for b in busy)  # motivo não vaza

    # liberar devolve o horário
    assert c.delete(f"/api/admin/blocks/{blocks[0]['id']}", headers=h).status_code == 204
    starts = [s["start"] for s in cli.get(f"/api/patient/slots?date={day}").get_json()["slots"]]
    assert "08:00" in starts


def test_block_several_days_and_validation(tmp_path):
    c, h = admin_client(tmp_path)
    pid = new_patient(c, h)
    first, last = _next_weekday(), _next_weekday(4)
    c.post("/api/admin/appointments", headers=h, json={"patient_user_id": pid, "date": _next_weekday(2), "start": "09:00", "end": "10:00"})
    r = c.post("/api/admin/blocks", headers=h, json={"date": first, "date_to": last, "start": "00:00", "end": "23:59"})
    assert r.status_code == 201 and r.get_json() == {"ok": True, "created": 5, "appointments_inside": 1}
    assert len(c.get(f"/api/admin/blocks?from={first}&to={last}").get_json()["items"]) == 5

    assert c.post("/api/admin/blocks", headers=h, json={"date": first, "start": "10:00", "end": "09:00"}).status_code == 400
    assert c.post("/api/admin/blocks", headers=h, json={"date": last, "date_to": first, "start": "08:00", "end": "09:00"}).status_code == 400
    assert c.post("/api/admin/blocks", json={"date": first, "start": "08:00", "end": "09:00"}).status_code == 403  # sem CSRF

    cli = c.application.test_client()
    cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"})
    assert cli.get(f"/api/admin/blocks?from={first}&to={last}").status_code == 403

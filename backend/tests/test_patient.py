"""Testes da área do cliente: agendar sessão, cancelar, meus dados."""
from datetime import date, datetime, timedelta

from app.routes import patient as rules
from tests.test_admin import admin_client, new_patient


def next_open_day(min_days=2):
    d = date.today() + timedelta(days=min_days)
    while d.weekday() == 6:  # domingo nunca tem atendimento
        d += timedelta(days=1)
    return d


def setup(tmp_path):
    adm, h = admin_client(tmp_path)
    pid = new_patient(adm, h)
    cli = adm.application.test_client()
    token = cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"}).get_json()["csrf_token"]
    return adm, h, cli, {"X-CSRF-Token": token}, pid


def test_request_confirm_and_cancel(tmp_path):
    adm, h, cli, ch, pid = setup(tmp_path)
    day = next_open_day().isoformat()

    slots = cli.get(f"/api/patient/slots?date={day}").get_json()["slots"]
    assert slots and slots[0]["start"] == "09:00"
    # só 9h–11h e 13h–19h
    assert [s["start"] for s in slots] == ["09:00", "10:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00"]

    # pede o primeiro horário
    assert cli.post("/api/patient/appointments", json={"date": day, "start": slots[0]["start"]}, headers=ch).status_code == 201
    # o mesmo horário some da lista e não pode ser pedido de novo
    assert slots[0] not in cli.get(f"/api/patient/slots?date={day}").get_json()["slots"]
    assert cli.post("/api/patient/appointments", json={"date": day, "start": slots[0]["start"]}, headers=ch).status_code == 409

    mine = cli.get("/api/patient/me/appointments").get_json()["items"]
    assert mine[0]["status"] == "requested"

    # o admin vê o pedido e confirma
    dash = adm.get("/api/admin/dashboard").get_json()
    assert [r["id"] for r in dash["requests"]] == [mine[0]["id"]]
    assert adm.patch(f"/api/admin/appointments/{mine[0]['id']}", json={"status": "scheduled"}, headers=h).status_code == 200
    assert adm.get("/api/admin/dashboard").get_json()["requests"] == []

    # com mais de 24h de antecedência o cliente pode cancelar
    assert cli.post(f"/api/patient/appointments/{mine[0]['id']}/cancel", headers=ch).status_code == 200
    assert cli.get("/api/patient/me/appointments").get_json()["items"][0]["status"] == "cancelled"


def test_cannot_cancel_confirmed_close_to_time(tmp_path):
    adm, h, cli, ch, pid = setup(tmp_path)
    soon = datetime.now() + timedelta(hours=3)
    body = {"patient_user_id": pid, "date": soon.date().isoformat(), "start": soon.strftime("%H:00"),
            "end": (soon + timedelta(hours=1)).strftime("%H:00")}
    if body["end"] <= body["start"]:
        return  # horário cruza a meia-noite; pula
    assert adm.post("/api/admin/appointments", json=body, headers=h).status_code == 201
    aid = cli.get("/api/patient/me/appointments").get_json()["items"][0]["id"]
    assert cli.post(f"/api/patient/appointments/{aid}/cancel", headers=ch).status_code == 400


def test_limits_and_closed_days(tmp_path):
    adm, h, cli, ch, pid = setup(tmp_path)
    adm.application.config["CLOSED_WEEKDAYS"] = (6,)
    closed = date.today() + timedelta(days=1)
    while closed.weekday() != 6:
        closed += timedelta(days=1)
    assert cli.get(f"/api/patient/slots?date={closed}").get_json()["slots"] == []
    assert cli.get(f"/api/patient/slots?date={date.today() - timedelta(days=1)}").get_json()["slots"] == []

    day = next_open_day().isoformat()
    slots = cli.get(f"/api/patient/slots?date={day}").get_json()["slots"]
    for s in slots[: rules.MAX_OPEN]:
        assert cli.post("/api/patient/appointments", json={"date": day, "start": s["start"]}, headers=ch).status_code == 201
    extra = slots[rules.MAX_OPEN]["start"]
    assert cli.post("/api/patient/appointments", json={"date": day, "start": extra}, headers=ch).status_code == 409


def test_profile_and_password(tmp_path):
    adm, h, cli, ch, pid = setup(tmp_path)
    assert cli.patch("/api/patient/me", json={"phone": "11 98888-0000"}, headers=ch).status_code == 200
    assert cli.get("/api/patient/me").get_json()["phone"] == "11 98888-0000"

    assert cli.post("/api/patient/me/password", json={"current": "errada", "new": "nova-senha-1"}, headers=ch).status_code == 400
    assert cli.post("/api/patient/me/password", json={"current": "12345678", "new": "nova-senha-1"}, headers=ch).status_code == 200
    other = adm.application.test_client()
    assert other.post("/api/auth/login", json={"email": "ana@x.com", "password": "nova-senha-1"}).status_code == 200


def test_patient_only_sees_own_appointments(tmp_path):
    adm, h, cli, ch, pid = setup(tmp_path)
    bia = new_patient(adm, h, "bia@x.com")
    day = next_open_day().isoformat()
    assert adm.post("/api/admin/appointments", json={"patient_user_id": bia, "date": day, "start": "08:00", "end": "09:00"},
                    headers=h).status_code == 201
    assert cli.get("/api/patient/me/appointments").get_json()["items"] == []
    bia_appt = adm.get(f"/api/admin/appointments?from={day}&to={day}").get_json()["items"][0]["id"]
    assert cli.post(f"/api/patient/appointments/{bia_appt}/cancel", headers=ch).status_code == 404

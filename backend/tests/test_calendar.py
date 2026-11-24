"""Dias sem atendimento (domingo fixo, os outros editáveis), eventos da clínica e aniversários."""
from datetime import date, timedelta

from app.calendar_rules import events_between, last_saturday
from tests.test_admin import admin_client, new_patient


def _next(weekday):
    d = date.today() + timedelta(days=1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d.isoformat()


def test_last_saturday_of_each_month(tmp_path):
    assert last_saturday(2026, 11) == date(2026, 11, 28)
    assert last_saturday(2026, 2) == date(2026, 2, 28)
    assert last_saturday(2027, 7) == date(2027, 7, 31)  # o próprio último dia é sábado
    c, _h = admin_client(tmp_path)
    with c.application.app_context():
        evs = events_between(date(2026, 11, 1), date(2027, 1, 31))
    assert [e["date"] for e in evs] == ["2026-11-28", "2026-12-26", "2027-01-30"]
    assert all(e["title"] == "Reiki voluntário" for e in evs)


def test_events_visible_to_patients_and_admin(tmp_path):
    c, h = admin_client(tmp_path)
    new_patient(c, h)
    r = c.get("/api/patient/events?from=2026-12-01&to=2026-12-31").get_json()
    assert r["items"][0]["date"] == "2026-12-26"
    cli = c.application.test_client()
    cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"})
    items = cli.get("/api/patient/events").get_json()["items"]
    assert items and all(date.fromisoformat(e["date"]).weekday() == 5 for e in items)
    assert c.application.test_client().get("/api/patient/events").status_code == 401


def test_monday_and_friday_are_closed(tmp_path):
    c, h = admin_client(tmp_path)
    c.application.config["CLOSED_WEEKDAYS"] = (0, 4, 5, 6)
    pid = new_patient(c, h)
    cli = c.application.test_client()
    cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"})
    for wd in (0, 4, 5, 6):
        assert cli.get(f"/api/patient/slots?date={_next(wd)}").get_json()["slots"] == []
    assert cli.get(f"/api/patient/slots?date={_next(1)}").get_json()["slots"]  # terça abre
    info = cli.get("/api/patient/schedule-info").get_json()
    assert 0 not in info["open_weekdays"] and 4 not in info["open_weekdays"] and info["open_weekdays"] == [1, 2, 3]
    assert cli.get("/api/patient/events").get_json()["closed_weekdays"] == [0, 4, 5, 6]

    # a administração só agenda na segunda/sexta como exceção (force)
    body = {"patient_user_id": pid, "date": _next(0), "start": "09:00", "end": "10:00"}
    r = c.post("/api/admin/appointments", headers=h, json=body)
    assert r.status_code == 409 and r.get_json()["closed_day"] is True
    assert c.post("/api/admin/appointments", headers=h, json={**body, "force": True}).status_code == 201
    appt = c.get(f"/api/admin/appointments?from={_next(0)}&to={_next(0)}").get_json()["items"][0]
    assert c.patch(f"/api/admin/appointments/{appt['id']}", headers=h, json={"date": _next(4)}).status_code == 409
    assert c.patch(f"/api/admin/appointments/{appt['id']}", headers=h, json={"date": _next(1)}).status_code == 200


def test_admin_edits_weekdays_but_sunday_is_fixed(tmp_path):
    c, h = admin_client(tmp_path)
    del c.application.config["CLOSED_WEEKDAYS"]  # usa o que está salvo
    assert c.get("/api/admin/calendar-settings").get_json()["closed_weekdays"] == [0, 4, 5, 6]  # padrão
    r = c.put("/api/admin/calendar-settings", headers=h, json={"closed_weekdays": [0, 2]})
    assert r.status_code == 200 and r.get_json()["closed_weekdays"] == [0, 2, 6]  # domingo sempre fechado
    r = c.put("/api/admin/calendar-settings", headers=h, json={"closed_weekdays": []})
    assert r.get_json()["closed_weekdays"] == [6]
    pid = new_patient(c, h)
    cli = c.application.test_client()
    cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"})
    assert cli.get(f"/api/patient/slots?date={_next(6)}").get_json()["slots"] == []
    assert cli.get(f"/api/patient/slots?date={_next(0)}").get_json()["slots"]  # segunda agora abre
    assert cli.get("/api/patient/schedule-info").get_json()["open_weekdays"] == [0, 1, 2, 3, 4, 5]
    assert c.put("/api/admin/calendar-settings", json={"closed_weekdays": []}).status_code == 403  # sem CSRF
    assert cli.put("/api/admin/calendar-settings", json={"closed_weekdays": []}).status_code in (401, 403)


def test_events_crud(tmp_path):
    c, h = admin_client(tmp_path)
    reiki = c.get("/api/admin/events").get_json()["items"]
    assert [e["title"] for e in reiki] == ["Reiki voluntário"]
    assert c.post("/api/admin/events", headers=h, json={"title": "", "date": "2026-12-10"}).status_code == 400
    assert c.post("/api/admin/events", headers=h, json={"title": "Palestra", "date": "2026-12-10",
                                                         "start_time": "19:00", "end_time": "18:00"}).status_code == 400
    assert c.post("/api/admin/events", headers=h, json={"title": "Palestra", "icon": "🎤", "date": "2026-12-10",
                                                         "start_time": "19:00", "end_time": "20:00"}).status_code == 201
    assert c.post("/api/admin/events", headers=h, json={"title": "Meditação", "date": "2026-12-02",
                                                         "recurrence": "weekly", "until": "2026-12-20"}).status_code == 201
    evs = c.get("/api/patient/events?from=2026-12-01&to=2026-12-31").get_json()["items"]
    assert [(e["date"], e["title"]) for e in evs] == [
        ("2026-12-02", "Meditação"), ("2026-12-09", "Meditação"), ("2026-12-10", "Palestra"),
        ("2026-12-16", "Meditação"), ("2026-12-26", "Reiki voluntário")]
    pal = next(e for e in c.get("/api/admin/events").get_json()["items"] if e["title"] == "Palestra")
    assert c.put(f"/api/admin/events/{pal['id']}", headers=h, json={**pal, "title": "Palestra aberta", "recurrence": "yearly"}).status_code == 200
    evs = c.get("/api/patient/events?from=2027-12-01&to=2027-12-31").get_json()["items"]
    assert ("2027-12-10", "Palestra aberta") in [(e["date"], e["title"]) for e in evs]
    assert c.delete(f"/api/admin/events/{pal['id']}", headers=h).status_code == 204
    assert "Palestra aberta" not in [e["title"] for e in c.get("/api/admin/events").get_json()["items"]]
    new_patient(c, h)
    cli = c.application.test_client()
    cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"})
    assert cli.get("/api/admin/events").status_code == 403


def test_birthdays_only_for_admin(tmp_path):
    c, h = admin_client(tmp_path)
    pid = new_patient(c, h)
    assert c.put(f"/api/admin/patients/{pid}/profile", headers=h, json={"profile": {"birth_date": "1990-03-15"}}).status_code == 200
    items = c.get("/api/admin/birthdays?from=2027-03-01&to=2027-03-31").get_json()["items"]
    assert items == [{"date": "2027-03-15", "patient_id": pid, "name": "Ana", "age": 37}]
    assert c.get("/api/admin/birthdays?from=2027-04-01&to=2027-04-30").get_json()["items"] == []
    cli = c.application.test_client()
    cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"})
    assert cli.get("/api/admin/birthdays?from=2027-03-01&to=2027-03-31").status_code == 403

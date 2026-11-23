"""Dias sem atendimento (segunda, sexta, sábado e domingo) e evento mensal "Reiki Para Todos"."""
from datetime import date, timedelta

from app.calendar_rules import events_between, last_saturday
from tests.test_admin import admin_client, new_patient


def _next(weekday):
    d = date.today() + timedelta(days=1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d.isoformat()


def test_last_saturday_of_each_month():
    assert last_saturday(2026, 11) == date(2026, 11, 28)
    assert last_saturday(2026, 2) == date(2026, 2, 28)
    assert last_saturday(2027, 7) == date(2027, 7, 31)  # o próprio último dia é sábado
    evs = events_between(date(2026, 11, 1), date(2027, 1, 31))
    assert [e["date"] for e in evs] == ["2026-11-28", "2026-12-26", "2027-01-30"]
    assert all(e["title"] == "Reiki Para Todos" for e in evs)


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

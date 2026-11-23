"""Financeiro: terapias e preços, pagamentos das sessões, pacotes, despesas e relatório."""
from datetime import date

from tests.test_admin import admin_client, new_patient

TODAY = date.today().isoformat()
YEAR = date.today().year


def _service(c, name):
    return next(s for s in c.get("/api/admin/services").get_json()["items"] if s["name"] == name)


def _appt(c, h, pid, start, **extra):
    body = {"patient_user_id": pid, "date": TODAY, "start": start, "end": f"{int(start[:2]) + 1:02d}:00", **extra}
    assert c.post("/api/admin/appointments", headers=h, json=body).status_code == 201
    items = c.get(f"/api/admin/appointments?from={TODAY}&to={TODAY}").get_json()["items"]
    return next(a for a in items if a["start"] == start)


def test_services_seeded_and_editable(tmp_path):
    c, h = admin_client(tmp_path)
    names = [s["name"] for s in c.get("/api/admin/services").get_json()["items"]]
    assert {"Acupuntura", "Auriculoterapia", "Reiki"} <= set(names)
    acu = _service(c, "Acupuntura")
    assert c.patch(f"/api/admin/services/{acu['id']}", headers=h, json={"price_cents": 15000}).status_code == 200
    assert _service(c, "Acupuntura")["price_cents"] == 15000
    assert c.post("/api/admin/services", headers=h, json={"name": "Acupuntura", "price_cents": 1}).status_code == 409
    assert c.post("/api/admin/services", headers=h, json={"name": "Massagem", "price_cents": -5}).status_code == 400
    assert c.post("/api/admin/services", headers=h, json={"name": "Massagem", "price_cents": 9000}).status_code == 201


def test_session_payment_flow(tmp_path):
    c, h = admin_client(tmp_path)
    pid = new_patient(c, h)
    acu = _service(c, "Acupuntura")
    c.patch(f"/api/admin/services/{acu['id']}", headers=h, json={"price_cents": 15000})
    a = _appt(c, h, pid, "09:00", service_id=acu["id"])
    assert a["price_cents"] == 15000 and a["service_name"] == "Acupuntura"  # preço veio da terapia
    b = _appt(c, h, pid, "11:00", service_id=acu["id"], price_cents=12000)  # valor especial
    assert b["price_cents"] == 12000

    for x in (a, b):
        c.patch(f"/api/admin/appointments/{x['id']}", headers=h, json={"status": "done"})
    rec = c.get("/api/admin/finance/receivable").get_json()
    assert rec["total_cents"] == 27000

    assert c.post("/api/admin/finance/payments", headers=h, json={
        "appointment_id": a["id"], "amount_cents": 15000, "method": "pix", "date": TODAY}).status_code == 201
    assert c.post("/api/admin/finance/payments", headers=h, json={
        "appointment_id": b["id"], "amount_cents": 5000, "method": "dinheiro"}).status_code == 201
    st = {s["id"]: s for s in c.get(f"/api/admin/finance/sessions?from={TODAY}&to={TODAY}").get_json()["items"]}
    assert st[a["id"]]["finance_status"] == "paid" and st[b["id"]]["finance_status"] == "partial"
    assert st[b["id"]]["due_cents"] == 7000
    assert c.get("/api/admin/finance/receivable").get_json()["total_cents"] == 7000

    # validações
    assert c.post("/api/admin/finance/payments", headers=h, json={"appointment_id": a["id"], "amount_cents": 0, "method": "pix"}).status_code == 400
    assert c.post("/api/admin/finance/payments", headers=h, json={"appointment_id": a["id"], "amount_cents": 10, "method": "bitcoin"}).status_code == 400

    pays = c.get(f"/api/admin/finance/payments?from={TODAY}&to={TODAY}").get_json()["items"]
    assert len(pays) == 2 and all(p["patient_name"] == "Ana" for p in pays)
    assert c.delete(f"/api/admin/finance/payments/{pays[0]['id']}", headers=h).status_code == 204


def test_package_is_used_when_session_is_done(tmp_path):
    c, h = admin_client(tmp_path)
    pid = new_patient(c, h)
    acu = _service(c, "Acupuntura")
    r = c.post("/api/admin/finance/packages", headers=h, json={
        "patient_user_id": pid, "service_id": acu["id"], "sessions_total": 2, "price_cents": 50000, "paid_method": "pix"})
    assert r.status_code == 201
    pk = r.get_json()["id"]
    a1, a2, a3 = (_appt(c, h, pid, t, service_id=acu["id"], price_cents=15000) for t in ("08:00", "10:00", "12:00"))
    for a in (a1, a2, a3):
        c.patch(f"/api/admin/appointments/{a['id']}", headers=h, json={"status": "done"})
    st = {s["id"]: s for s in c.get(f"/api/admin/finance/sessions?from={TODAY}&to={TODAY}").get_json()["items"]}
    assert [st[a["id"]]["finance_status"] for a in (a1, a2, a3)] == ["package", "package", "pending"]  # pacote acabou
    pack = c.get("/api/admin/finance/packages").get_json()["items"][0]
    assert pack["sessions_used"] == 2 and pack["paid_cents"] == 50000
    assert c.delete(f"/api/admin/finance/packages/{pk}", headers=h).status_code == 409  # já usado

    # cancelar uma sessão devolve o crédito ao pacote
    c.patch(f"/api/admin/appointments/{a1['id']}", headers=h, json={"status": "cancelled"})
    assert c.get("/api/admin/finance/packages").get_json()["items"][0]["sessions_used"] == 1
    # pacote de outra terapia não é usado
    rei = _service(c, "Reiki")
    c.post("/api/admin/finance/packages", headers=h, json={"patient_user_id": pid, "service_id": rei["id"], "sessions_total": 5})
    a4 = _appt(c, h, pid, "14:00", service_id=acu["id"], price_cents=15000)
    c.patch(f"/api/admin/appointments/{a4['id']}", headers=h, json={"status": "done"})
    st = {s["id"]: s for s in c.get(f"/api/admin/finance/sessions?from={TODAY}&to={TODAY}").get_json()["items"]}
    assert st[a4["id"]]["package_id"] == pk  # voltou a ter saldo no pacote de acupuntura


def test_expenses_and_summary(tmp_path):
    c, h = admin_client(tmp_path)
    pid = new_patient(c, h)
    assert c.post("/api/admin/finance/expenses", headers=h, json={
        "date": f"{YEAR}-01-10", "category": "Aluguel", "amount_cents": 80000, "method": "pix"}).status_code == 201
    assert c.post("/api/admin/finance/expenses", headers=h, json={
        "date": f"{YEAR}-01-15", "category": "Materiais", "amount_cents": 12000}).status_code == 201
    assert c.post("/api/admin/finance/expenses", headers=h, json={"date": "x", "category": "A", "amount_cents": 1}).status_code == 400
    c.post("/api/admin/finance/payments", headers=h, json={"patient_user_id": pid, "amount_cents": 30000, "method": "pix", "date": f"{YEAR}-01-20"})
    s = c.get(f"/api/admin/finance/summary?year={YEAR}").get_json()
    jan = s["months"][0]
    assert (jan["income_cents"], jan["expense_cents"], jan["balance_cents"]) == (30000, 92000, -62000)
    assert s["by_category"] == {"Aluguel": 80000, "Materiais": 12000} and s["by_method"] == {"pix": 30000}
    ex = c.get(f"/api/admin/finance/expenses?from={YEAR}-01-01&to={YEAR}-01-31").get_json()["items"]
    assert c.delete(f"/api/admin/finance/expenses/{ex[0]['id']}", headers=h).status_code == 204


def test_finance_is_admin_only(tmp_path):
    c, h = admin_client(tmp_path)
    new_patient(c, h)
    cli = c.application.test_client()
    cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"})
    for url in ("/api/admin/services", "/api/admin/finance/summary", "/api/admin/finance/packages"):
        assert cli.get(url).status_code == 403


def test_ambulatorio_social(tmp_path):
    c, h = admin_client(tmp_path)
    pid = new_patient(c, h)
    social = next(s for s in c.get("/api/admin/services").get_json()["items"] if s["social"])
    assert social["price_cents"] == 5000 and "Ambulatório Social" in social["name"]

    # marca o paciente como participante do Ambulatório Social
    assert c.patch(f"/api/admin/patients/{pid}", headers=h, json={"social": True}).status_code == 200
    assert next(p for p in c.get("/api/admin/patients").get_json()["items"] if p["id"] == pid)["social"] == 1
    assert c.get(f"/api/admin/patients/{pid}/file").get_json()["patient"]["social"] == 1

    a = _appt(c, h, pid, "09:00", service_id=social["id"])
    assert a["price_cents"] == 5000
    c.patch(f"/api/admin/appointments/{a['id']}", headers=h, json={"status": "done"})
    st = c.get(f"/api/admin/finance/sessions?from={TODAY}&to={TODAY}").get_json()["items"][0]
    assert st["social"] == 1 and st["patient_social"] == 1
    c.post("/api/admin/finance/payments", headers=h, json={"appointment_id": a["id"], "amount_cents": 5000, "method": "pix", "date": TODAY})
    s = c.get(f"/api/admin/finance/summary?year={YEAR}").get_json()["social"]
    assert s == {"sessions": 1, "patients": 1, "income_cents": 5000}

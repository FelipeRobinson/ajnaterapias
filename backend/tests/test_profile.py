"""Dados pessoais do cliente: ele mesmo e a clínica podem ver e editar."""
from tests.test_admin import admin_client, new_patient

GOOD = {"cpf": "529.982.247-25", "cep": "13010111", "street": "Rua das Flores", "number": "10",
        "city": "Campinas", "state": "SP", "birth_date": "1990-05-02", "emergency_name": "Maria"}


def _patient_client(c):
    cli = c.application.test_client()
    tok = cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"}).get_json()["csrf_token"]
    return cli, {"X-CSRF-Token": tok}


def test_patient_fills_and_admin_sees(tmp_path):
    c, h = admin_client(tmp_path)
    pid = new_patient(c, h)
    cli, ch = _patient_client(c)
    me = cli.get("/api/patient/me").get_json()
    assert me["profile"] == {} and me["profile_fields"][1]["title"] == "Endereço"
    assert cli.patch("/api/patient/me", headers=ch, json={"profile": {**GOOD, "lixo": "x"}}).status_code == 200
    prof = cli.get("/api/patient/me").get_json()["profile"]
    assert prof["cep"] == "13010-111" and prof["cpf"] == "529.982.247-25" and "lixo" not in prof
    # a clínica vê na ficha e pode corrigir
    assert c.get(f"/api/admin/patients/{pid}/file").get_json()["patient"]["profile"]["street"] == "Rua das Flores"
    assert c.put(f"/api/admin/patients/{pid}/profile", headers=h, json={"profile": {**GOOD, "number": "20"}}).status_code == 200
    assert cli.get("/api/patient/me").get_json()["profile"]["number"] == "20"
    assert "profile" in c.get("/api/admin/forms").get_json()


def test_profile_validation(tmp_path):
    c, h = admin_client(tmp_path)
    pid = new_patient(c, h)
    cli, ch = _patient_client(c)
    assert cli.patch("/api/patient/me", headers=ch, json={"profile": {"cpf": "111.111.111-11"}}).status_code == 400
    assert cli.patch("/api/patient/me", headers=ch, json={"profile": {"cep": "123"}}).status_code == 400
    assert cli.patch("/api/patient/me", headers=ch, json={"profile": {"state": "XX"}}).status_code == 400
    assert cli.patch("/api/patient/me", headers=ch, json={"phone": "(19) 9"}).status_code == 200  # telefone continua
    assert cli.put(f"/api/admin/patients/{pid}/profile", headers=ch, json={"profile": GOOD}).status_code == 403

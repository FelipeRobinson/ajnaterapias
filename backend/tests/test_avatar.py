"""Foto de perfil opcional para administração e clientes."""
from tests.test_admin import admin_client, new_patient

IMG = "data:image/jpeg;base64," + "A" * 200


def test_admin_and_patient_can_set_and_remove_photo(tmp_path):
    c, h = admin_client(tmp_path)
    assert c.get("/api/auth/me").get_json()["avatar"] is None
    assert c.put("/api/auth/me/avatar", headers=h, json={"image": IMG}).status_code == 200
    assert c.get("/api/auth/me").get_json()["avatar"] == IMG

    pid = new_patient(c, h)
    cli = c.application.test_client()
    tok = cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"}).get_json()["csrf_token"]
    assert cli.put("/api/auth/me/avatar", headers={"X-CSRF-Token": tok}, json={"image": IMG}).status_code == 200
    # a clínica vê a foto do cliente na lista e na ficha
    assert next(p for p in c.get("/api/admin/patients").get_json()["items"] if p["id"] == pid)["avatar"] == IMG
    assert cli.put("/api/auth/me/avatar", headers={"X-CSRF-Token": tok}, json={"image": None}).status_code == 200
    assert cli.get("/api/auth/me").get_json()["avatar"] is None


def test_photo_validation(tmp_path):
    c, h = admin_client(tmp_path)
    assert c.put("/api/auth/me/avatar", headers=h, json={"image": "javascript:alert(1)"}).status_code == 400
    assert c.put("/api/auth/me/avatar", headers=h, json={"image": "data:image/svg+xml;base64,AAAA"}).status_code == 400
    assert c.put("/api/auth/me/avatar", headers=h, json={"image": "data:image/png;base64," + "A" * 400_000}).status_code == 400
    assert c.put("/api/auth/me/avatar", json={"image": IMG}).status_code == 403  # sem CSRF
    assert c.application.test_client().put("/api/auth/me/avatar", json={"image": IMG}).status_code == 401

"""Parte teórica: ficha técnica dos pontos, diagnósticos, sintomas e combinações."""
from app.theory_data import default_categories
from tests.test_admin import admin_client, new_patient


def test_default_categories_are_textbook_classifications():
    c = default_categories()
    assert "Yuan (fonte)" in c["LU9"] and "Shu-Riacho (Terra)" in c["LU9"] and "Hui (influência) – Vasos" in c["LU9"]
    assert "Luo (conexão)" in c["PC6"] and "Abertura – Yin Wei Mai" in c["PC6"]
    assert "He-Mar (Terra)" in c["ST36"] and "He inferior – Estômago" in c["ST36"]
    assert "Shu do dorso – Rim" in c["BL23"] and "Mu frontal – Estômago" in c["REN12"]
    assert "Jing-Poço (Madeira)" in c["LU11"] and "Jing-Poço (Metal)" in c["LI1"]  # yin x yang
    yuan = [k for k, v in c.items() if "Yuan (fonte)" in v]
    assert len(yuan) == 12


def test_everything_loads_seeded_data(tmp_path):
    c, h = admin_client(tmp_path)
    d = c.get("/api/admin/theory").get_json()
    assert len(d["points"]) == 361 + 79
    assert len([i for i in d["items"] if i["kind"] == "syndrome"]) == 36
    assert "Yuan (fonte)" in d["categories"]
    p9 = next(p for p in d["points"] if p["code"] == "LU9")
    assert "Yuan (fonte)" in p9["details"]["categories"]


def test_point_technical_sheet_is_editable(tmp_path):
    c, h = admin_client(tmp_path)
    r = c.patch("/api/admin/theory/points/LI4", headers=h, json={
        "name_pt": "Fundo do Vale", "location": "Dorso da mão",
        "details": {"functions": "Elimina vento", "needling_depth": "0,5–1 cun", "categories": ["Yuan (fonte)", "Ponto mestre da face"],
                    "lixo": "ignorado"}})
    assert r.status_code == 200
    p = next(p for p in c.get("/api/admin/theory").get_json()["points"] if p["code"] == "LI4")
    assert p["name_pt"] == "Fundo do Vale" and p["location"] == "Dorso da mão"
    assert p["details"] == {"functions": "Elimina vento", "needling_depth": "0,5–1 cun",
                            "categories": ["Yuan (fonte)", "Ponto mestre da face"]}
    assert "Ponto mestre da face" in c.get("/api/admin/theory").get_json()["categories"]


def test_syndrome_symptom_and_combination_crud(tmp_path):
    c, h = admin_client(tmp_path)
    r = c.post("/api/admin/theory/syndrome", headers=h, json={
        "name": "Teste de padrão", "group_name": "Rim",
        "data": {"tongue": "Vermelha sem saburra", "pulse": "Fino e rápido"}, "points": ["ki3", "SP6", "INVALIDO"]})
    assert r.status_code == 201
    sid = r.get_json()["id"]
    r = c.post("/api/admin/theory/symptom", headers=h, json={
        "name": "Suores noturnos", "data": {"syndromes": [sid, 99999]}, "points": ["HT6"]})
    sym = r.get_json()["id"]
    r = c.post("/api/admin/theory/combination", headers=h, json={
        "name": "Ansiedade básica", "data": {"indication": "Acalmar a mente"}, "points": ["DU20", "OR-TF4", "PC6"]})
    assert r.status_code == 201
    items = c.get("/api/admin/theory").get_json()["items"]
    syn = next(i for i in items if i["id"] == sid)
    assert syn["points"] == ["KI3", "SP6"] and syn["data"]["pulse"] == "Fino e rápido"
    assert next(i for i in items if i["id"] == sym)["data"]["syndromes"] == [sid]  # id inexistente descartado
    assert next(i for i in items if i["kind"] == "combination")["points"] == ["DU20", "OR-TF4", "PC6"]

    assert c.patch(f"/api/admin/theory/syndrome/{sid}", headers=h, json={"name": "Padrão renomeado", "points": []}).status_code == 200
    # excluir o diagnóstico tira o vínculo do sintoma
    assert c.delete(f"/api/admin/theory/syndrome/{sid}", headers=h).status_code == 204
    items = c.get("/api/admin/theory").get_json()["items"]
    assert next(i for i in items if i["id"] == sym)["data"]["syndromes"] == []
    assert c.post("/api/admin/theory/syndrome", headers=h, json={"name": ""}).status_code == 400
    assert c.post("/api/admin/theory/outra", headers=h, json={"name": "x"}).status_code == 404


def test_patient_cannot_access_theory(tmp_path):
    c, h = admin_client(tmp_path)
    new_patient(c, h)
    cli = c.application.test_client()
    cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"})
    assert cli.get("/api/admin/theory").status_code == 403


def test_tongue_gallery(tmp_path):
    c, h = admin_client(tmp_path)
    d = c.get("/api/admin/theory").get_json()
    tongue = [i for i in d["items"] if i["kind"] == "tongue"]
    assert len(tongue) == 31 and {"Cor do corpo", "Forma", "Saburra"} <= {i["group_name"] for i in tongue}
    sid = next(i for i in d["items"] if i["kind"] == "syndrome")["id"]
    tid = tongue[0]["id"]
    img = "data:image/jpeg;base64," + "A" * 100
    r = c.patch(f"/api/admin/theory/tongue/{tid}", headers=h, json={
        "name": tongue[0]["name"], "group_name": tongue[0]["group_name"],
        "data": {"meaning": "Deficiência de Sangue", "syndromes": [sid], "image": img}})
    assert r.status_code == 200
    t = next(i for i in c.get("/api/admin/theory").get_json()["items"] if i["id"] == tid)
    assert t["data"] == {"meaning": "Deficiência de Sangue", "syndromes": [sid], "image": img}
    # imagem que não é imagem, ou grande demais, é ignorada
    c.patch(f"/api/admin/theory/tongue/{tid}", headers=h, json={"name": "x", "data": {"image": "javascript:alert(1)"}})
    t = next(i for i in c.get("/api/admin/theory").get_json()["items"] if i["id"] == tid)
    assert "image" not in t["data"]

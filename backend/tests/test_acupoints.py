"""Mapa de pontos: 361 pontos da OMS, edição, pontos extras e vínculo com os protocolos."""
from datetime import date

from app.acupoints_data import all_points, default_position
from tests.test_admin import admin_client, new_patient

EXPECTED = {"LU": 11, "LI": 20, "ST": 45, "SP": 21, "HT": 9, "SI": 19, "BL": 67, "KI": 27,
            "PC": 9, "SJ": 23, "GB": 44, "LR": 14, "DU": 28, "REN": 24}


def test_361_points_with_correct_counts_and_names():
    pts = all_points()
    assert len(pts) == 361 == sum(EXPECTED.values())
    for m, n in EXPECTED.items():
        assert [p["number"] for p in pts if p["meridian"] == m] == list(range(1, n + 1))
    by = {p["code"]: p for p in pts}
    assert by["GB20"]["pinyin"] == "Fengchi" and by["GB20"]["intl_code"] == "GB20" and by["GB20"]["meridian"] == "GB"
    assert by["LI4"]["pinyin"] == "Hegu" and by["ST36"]["pinyin"] == "Zusanli"
    assert by["SP6"]["pinyin"] == "Sanyinjiao" and by["DU20"]["pinyin"] == "Baihui"
    assert by["PC6"]["pinyin"] == "Neiguan" and by["LR3"]["pinyin"] == "Taichong"
    assert all(0 <= p["x"] <= 300 and 0 <= p["y"] <= 710 and p["view"] in ("front", "back") for p in pts)


def test_list_edit_and_reset(tmp_path):
    c, h = admin_client(tmp_path)
    data = c.get("/api/admin/acupoints").get_json()
    assert len(data["points"]) == 361 + 79 and len(data["meridians"]) == 16
    ear = [p for p in data["points"] if p["meridian"] == "OR"]
    assert len(ear) == 79 and all(p["view"] == "ear" for p in ear)
    assert next(p for p in ear if p["code"] == "OR-TF4")["pinyin"] == "Shenmen"

    r = c.patch("/api/admin/acupoints/gb20", headers=h,
                json={"location": "Abaixo do occipital", "notes": "Cuidado com a profundidade", "x": 140, "y": 90})
    assert r.status_code == 200 and r.get_json()["location"] == "Abaixo do occipital" and r.get_json()["x"] == 140
    r = c.patch("/api/admin/acupoints/GB20", headers=h, json={"reset_position": True})
    view, x, y = default_position("GB", 20)
    assert (r.get_json()["view"], r.get_json()["x"], r.get_json()["y"]) == (view, x, y)
    assert r.get_json()["location"] == "Abaixo do occipital"  # textos continuam
    assert c.delete("/api/admin/acupoints/GB20", headers=h).status_code == 400  # clássico não se exclui


def test_custom_point(tmp_path):
    c, h = admin_client(tmp_path)
    r = c.post("/api/admin/acupoints", headers=h, json={"code": "ex-hn3", "pinyin": "Yintang", "view": "front"})
    assert r.status_code == 201 and r.get_json()["code"] == "EX-HN3"
    assert c.post("/api/admin/acupoints", headers=h, json={"code": "EX-HN3", "pinyin": "x"}).status_code == 409
    assert len(c.get("/api/admin/acupoints").get_json()["points"]) == 361 + 79 + 1
    assert c.delete("/api/admin/acupoints/EX-HN3", headers=h).status_code == 204


def test_points_in_protocol_and_usage(tmp_path):
    c, h = admin_client(tmp_path)
    pid = new_patient(c, h)
    today = date.today().isoformat()
    c.post("/api/admin/appointments", headers=h, json={"patient_user_id": pid, "date": today, "start": "09:00", "end": "10:00"})
    aid = c.get(f"/api/admin/appointments?from={today}&to={today}").get_json()["items"][0]["id"]

    c.put(f"/api/admin/appointments/{aid}/protocol", headers=h,
          json={"acupoints": ["gb20", "LI4", "LI4", "INVENTADO99"]})
    proto = c.get(f"/api/admin/patients/{pid}/file").get_json()["sessions"][0]["protocol"]
    assert proto["acupoints"] == ["GB20", "LI4"]  # maiúsculo, sem repetir, só pontos que existem

    assert c.get(f"/api/admin/acupoints/usage?patient_id={pid}").get_json() == {"GB20": 1, "LI4": 1}
    pts = {p["code"]: p for p in c.get("/api/admin/acupoints").get_json()["points"]}
    assert pts["GB20"]["used"] == 1 and pts["ST36"]["used"] == 0
    sessions = c.get("/api/admin/acupoints/LI4/sessions").get_json()["items"]
    assert sessions[0]["patient_name"] == "Ana"


def test_patient_cannot_access_map(tmp_path):
    c, h = admin_client(tmp_path)
    new_patient(c, h)
    cli = c.application.test_client()
    cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"})
    assert cli.get("/api/admin/acupoints").status_code == 403


def test_3d_position_save_and_reset(tmp_path):
    c, h = admin_client(tmp_path)
    pos = [-0.26, 0.8, 0.057, 0, 0, 1]
    r = c.patch("/api/admin/acupoints/LI4", headers=h, json={"pos3d": pos})
    assert r.status_code == 200 and r.get_json()["pos3d"] == '{"m": [-0.26, 0.8, 0.057, 0.0, 0.0, 1.0]}'
    r = c.patch("/api/admin/acupoints/LI4", headers=h, json={"pos3d": pos, "model": "f"})
    import json as _j
    assert set(_j.loads(r.get_json()["pos3d"])) == {"m", "f"}  # cada corpo guarda a sua correção
    assert c.patch("/api/admin/acupoints/LI4", headers=h, json={"pos3d": [1, 2]}).status_code == 400
    assert c.patch("/api/admin/acupoints/LI4", headers=h, json={"reset_position": True}).get_json()["pos3d"] is None


def test_auricular_points_in_protocol(tmp_path):
    c, h = admin_client(tmp_path)
    pid = new_patient(c, h)
    today = date.today().isoformat()
    c.post("/api/admin/appointments", headers=h, json={"patient_user_id": pid, "date": today, "start": "09:00", "end": "10:00"})
    aid = c.get(f"/api/admin/appointments?from={today}&to={today}").get_json()["items"][0]["id"]
    c.put(f"/api/admin/appointments/{aid}/protocol", headers=h, json={"acupoints": ["OR-TF4", "or-co10", "GB20"]})
    assert c.get(f"/api/admin/patients/{pid}/file").get_json()["sessions"][0]["protocol"]["acupoints"] == ["OR-TF4", "OR-CO10", "GB20"]
    r = c.patch("/api/admin/acupoints/OR-TF4", headers=h, json={"reset_position": True}).get_json()
    assert (r["view"], r["x"], r["y"]) == ("ear", 166, 120)


def test_old_brazilian_codes_are_migrated_to_chinese(tmp_path):
    """Bancos antigos (VB20, IG4…) passam para as siglas chinesas mantendo edições e combinações."""
    import sqlite3
    from app.database import init_db
    c, h = admin_client(tmp_path)
    app = c.application
    con = sqlite3.connect(app.config["DATABASE_PATH"])
    con.execute("DELETE FROM acupoints WHERE code = 'GB20'")
    con.execute("UPDATE acupoints SET code = 'VB20', meridian = 'VB', location = 'Minha nota' WHERE code = 'GB21'")
    con.execute("""INSERT INTO theory_items (kind, name, data, points, created_at, updated_at)
                   VALUES ('combination', 'Teste', '{}', '["VB20", "IG4", "OR-TF4"]', 'x', 'x')""")
    con.commit()
    con.close()
    init_db(app)
    pts = {p["code"]: p for p in c.get("/api/admin/acupoints").get_json()["points"]}
    assert "VB20" not in pts and pts["GB20"]["location"] == "Minha nota" and pts["GB20"]["meridian"] == "GB"
    combo = next(i for i in c.get("/api/admin/theory").get_json()["items"] if i["name"] == "Teste")
    assert combo["points"] == ["GB20", "LI4", "OR-TF4"]

"""Boas-vindas no primeiro login: vídeo da administração ou do cliente, só uma vez."""
from tests.test_admin import admin_client, new_patient


def _videos(app, tmp_path):
    d = tmp_path / "videos"
    d.mkdir()
    (d / "Ajna_Terapias_como_funciona.mp4").write_bytes(b"ADMIN-VIDEO" * 100)
    (d / "Ajna_Terapias_guia_do_cliente.mp4").write_bytes(b"CLIENT-VIDEO" * 100)
    app.config["ONBOARDING_DIR"] = str(d)


def test_first_login_flag_and_role_videos(tmp_path):
    c, h = admin_client(tmp_path)
    _videos(c.application, tmp_path)
    me = c.get("/api/auth/me").get_json()
    assert me["onboarded"] is False and me["has_video"] is True
    r = c.get("/api/auth/onboarding/video")
    assert r.status_code == 200 and r.data.startswith(b"ADMIN-VIDEO") and r.mimetype == "video/mp4"
    # dá para avançar/voltar no vídeo (pedido parcial)
    assert c.get("/api/auth/onboarding/video", headers={"Range": "bytes=0-9"}).status_code == 206
    assert c.post("/api/auth/onboarding/done", headers=h).status_code == 200
    assert c.get("/api/auth/me").get_json()["onboarded"] is True

    new_patient(c, h)
    cli = c.application.test_client()
    tok = cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"}).get_json()["csrf_token"]
    assert cli.get("/api/auth/me").get_json()["onboarded"] is False
    assert cli.get("/api/auth/onboarding/video").data.startswith(b"CLIENT-VIDEO")  # cliente vê o vídeo dele
    assert cli.post("/api/auth/onboarding/done").status_code == 403  # sem CSRF
    assert cli.post("/api/auth/onboarding/done", headers={"X-CSRF-Token": tok}).status_code == 200
    assert c.application.test_client().get("/api/auth/onboarding/video").status_code == 401


def test_no_video_file(tmp_path):
    c, h = admin_client(tmp_path)
    c.application.config["ONBOARDING_DIR"] = str(tmp_path / "nao-existe")
    assert c.get("/api/auth/me").get_json()["has_video"] is False
    assert c.get("/api/auth/onboarding/video").status_code == 404
    assert c.get("/api/auth/onboarding/outra").status_code == 404

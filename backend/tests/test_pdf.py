"""Botão "Salvar PDF": o servidor devolve um PDF pronto para baixar."""
from tests.test_admin import admin_client, new_patient


def test_pdf_download(tmp_path):
    c, h = admin_client(tmp_path)
    html = '<h1>Relatório</h1><table><tr><td class="k">Nome</td><td>Ana</td></tr></table><img src="http://exemplo.com/x.png">'
    r = c.post("/api/admin/pdf", headers=h, json={"html": html, "filename": "Ficha / Ana: teste"})
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    assert r.data.startswith(b"%PDF")
    assert 'filename=Ficha - Ana- teste.pdf' in r.headers["Content-Disposition"] or "Ficha" in r.headers["Content-Disposition"]
    assert c.post("/api/admin/pdf", headers=h, json={"html": " "}).status_code == 400


def test_pdf_admin_only(tmp_path):
    c, h = admin_client(tmp_path)
    new_patient(c, h)
    assert c.post("/api/admin/pdf", json={"html": "<p>x</p>"}).status_code == 403  # sem CSRF
    cli = c.application.test_client()
    tok = cli.post("/api/auth/login", json={"email": "ana@x.com", "password": "12345678"}).get_json()["csrf_token"]
    assert cli.post("/api/admin/pdf", headers={"X-CSRF-Token": tok}, json={"html": "<p>x</p>"}).status_code == 403

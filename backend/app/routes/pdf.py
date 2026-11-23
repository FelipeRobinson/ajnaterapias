"""Gera o PDF dos relatórios (botão "💾 Salvar PDF"), sem abrir a janela da impressora.

O painel monta o relatório em HTML (o mesmo que aparece na tela) e envia para cá; o servidor
converte com o xhtml2pdf e devolve o arquivo para download. Só a administração usa.
"""
import io
import re

from flask import Blueprint, jsonify, request, send_file

from ..security import csrf_required, login_required, roles_required

pdf_bp = Blueprint("pdf", __name__)
MAX_HTML = 8_000_000  # relatórios grandes com gráficos (imagens em base64)

PDF_CSS = """
@page { size: a4 portrait; margin: 14mm 13mm 16mm 13mm;
        @frame footer { -pdf-frame-content: pdf-footer; bottom: 6mm; margin-left: 13mm; margin-right: 13mm; height: 10mm; } }
body { font-family: Helvetica; font-size: 9.5pt; color: #24152e; line-height: 1.35; }
h1 { font-size: 16pt; color: #7800b4; margin: 0; }
h2 { font-size: 11.5pt; color: #7800b4; margin: 12pt 0 4pt; padding-bottom: 2pt; border-bottom: 0.6pt solid #d9c7e3; }
h3 { font-size: 10pt; margin: 8pt 0 3pt; }
p { margin: 2pt 0; }
table { width: 100%; border-collapse: collapse; margin: 3pt 0 7pt; }
th { background-color: #f3e9f8; color: #5b4866; font-size: 8pt; text-align: left; padding: 3pt 4pt; }
td { padding: 3pt 4pt; border-bottom: 0.4pt solid #ebe2ef; vertical-align: top; }
td.num, th.num { text-align: right; }
td.k { width: 34%; color: #6c5b73; }
.in { color: #15803d; } .out { color: #b4233f; }
.muted { color: #6c5b73; }
.tag { background-color: #f1e6f7; padding: 0 3pt; }
.head td { border: 0; padding: 0; vertical-align: middle; }
.gen { text-align: right; font-size: 7.5pt; color: #6c5b73; }
.totals td { border: 0.6pt solid #ebe2ef; padding: 5pt 6pt; width: 25%; }
.totals .lbl { font-size: 7.5pt; color: #6c5b73; }
.totals .val { font-size: 12pt; font-weight: bold; }
.session { border: 0.6pt solid #ebe2ef; padding: 5pt 7pt; margin: 6pt 0; }
.filters { color: #6c5b73; font-size: 8.5pt; }
.pagebreak { -pdf-keep-with-next: false; }
#pdf-footer { font-size: 7pt; color: #6c5b73; text-align: center; }
"""

_FILENAME_RE = re.compile(r"[^\w\-. ]+", re.UNICODE)


def _only_inline_images(uri, rel):
    """Não deixa o gerador buscar nada fora do documento: só imagens embutidas (data:)."""
    return uri if str(uri).startswith("data:image/") else ""


@pdf_bp.post("/pdf")
@login_required
@roles_required("admin")
@csrf_required
def make_pdf():
    from xhtml2pdf import pisa  # import aqui: só carrega a biblioteca quando alguém gera um PDF

    payload = request.get_json(silent=True) or {}
    body = str(payload.get("html") or "")
    if not body.strip():
        return jsonify(error="Relatório vazio."), 400
    if len(body) > MAX_HTML:
        return jsonify(error="Relatório grande demais para gerar o PDF."), 413
    # nada de scripts nem links externos dentro do PDF
    body = re.sub(r"<script\b.*?</script>", "", body, flags=re.S | re.I)
    footer = str(payload.get("footer") or "Instituto Ajna Terapias Integrativas e Complementares®")[:300]
    name = _FILENAME_RE.sub("-", str(payload.get("filename") or "relatorio")).strip(" -.")[:120] or "relatorio"
    html = (f'<html><head><meta charset="utf-8"><style>{PDF_CSS}</style></head><body>'
            f'<div id="pdf-footer">{footer} · página <pdf:pagenumber/> de <pdf:pagecount/></div>{body}</body></html>')
    out = io.BytesIO()
    result = pisa.CreatePDF(html, dest=out, encoding="utf-8", link_callback=_only_inline_images)
    if result.err:
        return jsonify(error="Não foi possível gerar o PDF."), 500
    out.seek(0)
    return send_file(out, mimetype="application/pdf", as_attachment=True, download_name=f"{name}.pdf")

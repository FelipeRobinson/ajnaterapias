"""Gera backend/db/model.drawio com o modelo atual do banco de dados.

Uso (na raiz do projeto):  .\\.venv\\Scripts\\python.exe backend\\db\\gerar_modelo_drawio.py

Mantém a página "Rascunho original" (o desenho que já existia) e recria a página
"Banco de dados" a partir da lista TABLES abaixo. Ao mudar o banco, atualize TABLES e rode de novo.
"""
import re
from html import escape
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "model.drawio"

# (nome, cor, posição x, posição y, [(coluna, tipo, chave)], descrição)
# chave: "PK", "FK→tabela", "UK" ou ""
TABLES = [
    ("users", "#dae8fc", 40, 40, [
        ("id", "INTEGER", "PK"), ("name", "TEXT", ""), ("email", "TEXT", "UK"), ("phone", "TEXT", ""),
        ("password_hash", "TEXT", ""), ("role", "TEXT  admin | patient", ""), ("active", "INTEGER 0/1", ""),
        ("avatar", "TEXT (foto opcional, data:image)", ""), ("social", "INTEGER 0/1 (Ambulatório Social)", ""),
        ("profile", "TEXT (JSON: CPF, endereço, emergência…)", ""), ("created_at", "TEXT", ""),
    ], "Administradores e clientes (pacientes)"),
    ("appointments", "#d5e8d4", 420, 40, [
        ("id", "INTEGER", "PK"), ("patient_user_id", "INTEGER", "FK→users"), ("date", "TEXT AAAA-MM-DD", ""),
        ("start", "TEXT HH:MM", ""), ("end", "TEXT HH:MM", ""),
        ("status", "TEXT requested|scheduled|done|cancelled", ""), ("created_at", "TEXT", ""),
        ("service_id", "INTEGER", "FK→services"), ("price_cents", "INTEGER (centavos)", ""),
        ("package_id", "INTEGER", "FK→packages"),
    ], "Consultas (pedidas pelo cliente, confirmadas pelo admin); terapia, valor e pacote usado"),
    ("services", "#fce4d6", 40, 1120, [
        ("id", "INTEGER", "PK"), ("name", "TEXT", "UK"), ("price_cents", "INTEGER (centavos)", ""),
        ("active", "INTEGER 0/1", ""), ("social", "INTEGER 0/1 (Ambulatório Social)", ""), ("created_at", "TEXT", ""),
    ], "Financeiro: terapias e preço da sessão (inclui a do Ambulatório Social, R$ 50)"),
    ("packages", "#fce4d6", 420, 1120, [
        ("id", "INTEGER", "PK"), ("patient_user_id", "INTEGER", "FK→users"), ("service_id", "INTEGER", "FK→services"),
        ("sessions_total", "INTEGER", ""), ("price_cents", "INTEGER (centavos)", ""), ("notes", "TEXT", ""),
        ("created_at", "TEXT", ""),
    ], "Financeiro: pacote de N sessões (usadas = consultas com package_id)"),
    ("payments", "#fce4d6", 820, 1120, [
        ("id", "INTEGER", "PK"), ("patient_user_id", "INTEGER", "FK→users"),
        ("appointment_id", "INTEGER", "FK→appointments"), ("package_id", "INTEGER", "FK→packages"),
        ("amount_cents", "INTEGER (centavos)", ""), ("method", "TEXT pix|dinheiro|credito|debito|…", ""),
        ("date", "TEXT AAAA-MM-DD", ""), ("description", "TEXT", ""), ("created_at", "TEXT", ""),
    ], "Financeiro: dinheiro recebido (sessão, pacote ou avulso)"),
    ("expenses", "#fce4d6", 1180, 1120, [
        ("id", "INTEGER", "PK"), ("date", "TEXT AAAA-MM-DD", ""), ("category", "TEXT", ""),
        ("description", "TEXT", ""), ("amount_cents", "INTEGER (centavos)", ""), ("method", "TEXT", ""),
        ("created_at", "TEXT", ""),
    ], "Financeiro: despesas da clínica"),
    ("schedule_blocks", "#d5e8d4", 420, 780, [
        ("id", "INTEGER", "PK"), ("date", "TEXT AAAA-MM-DD", ""), ("start", "TEXT HH:MM", ""),
        ("end", "TEXT HH:MM (dia inteiro = 00:00–23:59)", ""), ("reason", "TEXT", ""), ("created_at", "TEXT", ""),
    ], "Horários indisponíveis marcados pela administração (bloqueiam a agenda e o portal)"),
    ("medical_records", "#f8cecc", 40, 400, [
        ("id", "INTEGER", "PK"), ("patient_user_id", "INTEGER", "FK→users · UK"), ("data", "TEXT (JSON)", ""),
        ("created_at", "TEXT", ""), ("updated_at", "TEXT", ""), ("updated_by", "INTEGER", "FK→users"),
    ], "Prontuário: ficha fixa, 1 por paciente (campos em routes/records.py)"),
    ("session_protocols", "#f8cecc", 420, 400, [
        ("id", "INTEGER", "PK"), ("appointment_id", "INTEGER", "FK→appointments · UK"),
        ("patient_user_id", "INTEGER", "FK→users"), ("data", "TEXT (JSON, inclui acupoints[])", ""),
        ("created_at", "TEXT", ""), ("updated_at", "TEXT", ""), ("updated_by", "INTEGER", "FK→users"),
    ], "Protocolo: 1 por consulta (pontos aplicados ficam em data.acupoints)"),
    ("acupoints", "#e1d5e7", 820, 400, [
        ("code", "TEXT", "PK"), ("meridian", "TEXT", ""), ("number", "INTEGER", ""), ("intl_code", "TEXT", ""),
        ("pinyin", "TEXT", ""), ("name_pt", "TEXT", ""), ("view", "TEXT front|back|ear", ""), ("x", "REAL", ""),
        ("y", "REAL", ""), ("location", "TEXT", ""), ("indications", "TEXT", ""), ("notes", "TEXT", ""),
        ("custom", "INTEGER 0/1", ""), ("updated_at", "TEXT", ""), ("pos3d", "TEXT (JSON {m|f: [x,y,z,nx,ny,nz]})", ""), ("details", "TEXT (JSON: funções, agulhamento, categorias…)", ""),
    ], "Pontos: 361 OMS + 79 auriculares (meridian=OR) + extras; pos3d por corpo (m/f)"),
    ("account_changes", "#fff2cc", 820, 40, [
        ("id", "INTEGER", "PK"), ("user_id", "INTEGER", "FK→users"), ("token_hash", "TEXT", "UK"),
        ("payload", "TEXT (JSON)", ""), ("expires_at", "TEXT", ""), ("used", "INTEGER 0/1", ""),
        ("created_at", "TEXT", ""),
    ], "Alteração de nome/e-mail/telefone do admin, aprovada por e-mail (senha nunca)"),
    ("password_resets", "#fff2cc", 1180, 40, [
        ("id", "INTEGER", "PK"), ("user_id", "INTEGER", "FK→users"), ("token_hash", "TEXT", "UK"),
        ("expires_at", "TEXT", ""), ("used", "INTEGER 0/1", ""), ("created_at", "TEXT", ""),
    ], "Esqueci minha senha (link por e-mail) — único jeito de trocar a senha do admin"),
    ("theory_items", "#e1d5e7", 1180, 560, [
        ("id", "INTEGER", "PK"), ("kind", "TEXT syndrome|symptom|combination|tongue", ""), ("name", "TEXT", ""),
        ("group_name", "TEXT", ""), ("data", "TEXT (JSON)", ""), ("points", "TEXT (JSON códigos)", ""),
        ("created_at", "TEXT", ""), ("updated_at", "TEXT", ""),
    ], "Parte teórica: diagnósticos MTC, sintomas, combinações e língua (foto em data.image)"),
    ("settings", "#f5f5f5", 1180, 400, [
        ("key", "TEXT", "PK"), ("value", "TEXT", ""),
    ], "Configurações (ex.: primary_admin_id = Ellen)"),
]

# (tabela de origem, coluna, tabela de destino, cardinalidade)
RELATIONS = [
    ("appointments", "patient_user_id", "users", "N : 1"),
    ("medical_records", "patient_user_id", "users", "1 : 1"),
    ("session_protocols", "appointment_id", "appointments", "1 : 1"),
    ("session_protocols", "patient_user_id", "users", "N : 1"),
    ("account_changes", "user_id", "users", "N : 1"),
    ("password_resets", "user_id", "users", "N : 1"),
    ("appointments", "service_id", "services", "N : 1"),
    ("appointments", "package_id", "packages", "N : 1"),
    ("packages", "patient_user_id", "users", "N : 1"),
    ("payments", "appointment_id", "appointments", "N : 1"),
    ("payments", "package_id", "packages", "N : 1"),
]

ROW_H, W = 26, 320


def page_tables():
    cells, ids = [], {}
    n = 2
    for name, color, x, y, cols, desc in TABLES:
        tid = f"t_{name}"
        ids[name] = tid
        h = ROW_H * (len(cols) + 1) + 30
        cells.append(
            f'<mxCell id="{tid}" value="&lt;b&gt;{escape(name)}&lt;/b&gt;" style="swimlane;fontStyle=0;childLayout=stackLayout;'
            f'horizontal=1;startSize=30;horizontalStack=0;resizeParent=1;resizeLast=0;collapsible=1;marginBottom=0;'
            f'html=1;fillColor={color};strokeColor=#666666;rounded=1;arcSize=6;fontSize=14;" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{W}" height="{h}" as="geometry"/></mxCell>')
        for i, (col, typ, key) in enumerate(cols):
            label = f"{'🔑 ' if key == 'PK' else '🔗 ' if key.startswith('FK') else '★ ' if key == 'UK' else ''}" \
                    f"&lt;b&gt;{escape(col)}&lt;/b&gt;: {escape(typ)}" + (f" &lt;i&gt;({escape(key)})&lt;/i&gt;" if key else "")
            cells.append(
                f'<mxCell id="{tid}_{col}" value="{label}" style="text;strokeColor=none;fillColor=none;align=left;'
                f'verticalAlign=middle;spacingLeft=6;html=1;fontSize=12;" vertex="1" parent="{tid}">'
                f'<mxGeometry y="{30 + i * ROW_H}" width="{W}" height="{ROW_H}" as="geometry"/></mxCell>')
        cells.append(
            f'<mxCell id="{tid}_desc" value="&lt;i&gt;{escape(desc)}&lt;/i&gt;" style="text;html=1;fontSize=11;'
            f'fontColor=#666666;align=left;spacingLeft=6;whiteSpace=wrap;" vertex="1" parent="{tid}">'
            f'<mxGeometry y="{30 + len(cols) * ROW_H}" width="{W}" height="{ROW_H + 4}" as="geometry"/></mxCell>')
    for k, (src, col, dst, card) in enumerate(RELATIONS):
        cells.append(
            f'<mxCell id="r{k}" value="{escape(card)}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;'
            f'endArrow=ERmandOne;startArrow=ERmany;strokeColor=#7800b4;fontColor=#7800b4;fontSize=11;" edge="1" parent="1" '
            f'source="{ids[src]}_{col}" target="{ids[dst]}_id"><mxGeometry relative="1" as="geometry"/></mxCell>')
    legend = ("&lt;b&gt;Legenda&lt;/b&gt;&lt;br&gt;🔑 chave primária · 🔗 chave estrangeira · ★ valor único&lt;br&gt;"
              "Banco: SQLite (local) → PostgreSQL (host), mesmo esquema.&lt;br&gt;"
              "Gerado por backend/db/gerar_modelo_drawio.py")
    cells.append(f'<mxCell id="legend" value="{legend}" style="text;html=1;align=left;verticalAlign=top;'
                 f'fillColor=#ffffff;strokeColor=#cccccc;rounded=1;spacing=10;fontSize=12;" vertex="1" parent="1">'
                 f'<mxGeometry x="40" y="680" width="320" height="100" as="geometry"/></mxCell>')
    return "".join(cells)


def build():
    old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    drafts = re.findall(r"<diagram\b[^>]*>.*?</diagram>", old, flags=re.S)
    keep = [d for d in drafts if 'name="Banco de dados"' not in d]
    keep = [re.sub(r'name="Page-1"', 'name="Rascunho original"', d, count=1) for d in keep]
    page = ('<diagram id="banco-de-dados" name="Banco de dados"><mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" '
            'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" '
            'pageHeight="1000" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
            + page_tables() + "</root></mxGraphModel></diagram>")
    OUT.write_text('<mxfile host="ajna">' + page + "".join(keep) + "</mxfile>\n", encoding="utf-8")
    print(f"{OUT} atualizado: {len(TABLES)} tabelas, {len(RELATIONS)} relações, {len(keep)} página(s) de rascunho mantida(s).")


if __name__ == "__main__":
    build()

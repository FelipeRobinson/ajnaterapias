"""Parte TEÓRICA do mapa de pontos (somente administração).

- Detalhes técnicos de cada ponto (funções, contraindicações, agulhamento, categorias…), salvos em acupoints.details.
- Diagnósticos da MTC, sintomas e combinações de pontos (cesta), na tabela theory_items (coluna kind).
Inspirado na organização de atlas de acupuntura (ex.: Shen), sem copiar o conteúdo deles.
"""
import json
from datetime import datetime

from flask import Blueprint, jsonify, request

from ..database import get_db
from ..security import csrf_required, login_required, roles_required
from ..theory_data import SYNDROMES, TONGUE, default_categories
from .acupoints import known_codes

theory_bp = Blueprint("theory", __name__)
MAX_TEXT = 6000

# Campos técnicos do ponto (além de localização/indicações/observações/nome, que já são colunas)
POINT_DETAILS = ["functions", "contraindications", "needling_depth", "needling_angle", "technique", "moxa",
                 "combinations_hint", "categories"]
# Campos de cada tipo de item teórico
KINDS = {
    "syndrome": ["cardinal_signs", "causes", "emotional", "diet", "tongue", "pulse", "principle", "tips", "notes"],
    "symptom": ["notes", "syndromes"],
    "combination": ["indication", "notes"],
    "tongue": ["meaning", "notes", "syndromes", "image"],
}
MAX_IMAGE = 900_000  # foto reduzida no navegador (JPEG em base64)


def _admin(view):
    return login_required(roles_required("admin")(view))


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_details(payload):
    out = {}
    for k in POINT_DETAILS:
        v = payload.get(k)
        if k == "categories":
            if isinstance(v, list):
                vals = list(dict.fromkeys(str(x).strip()[:80] for x in v if str(x).strip()))
                if vals:
                    out[k] = vals
        elif v not in (None, ""):
            out[k] = str(v).strip()[:MAX_TEXT]
    return out


def _clean_item(kind, payload, codes, db):
    data = {}
    for k in KINDS[kind]:
        v = (payload.get("data") or {}).get(k)
        if k == "image":
            if isinstance(v, str) and v.startswith("data:image/") and len(v) <= MAX_IMAGE:
                data[k] = v
            continue
        if k == "syndromes":
            ids = [int(x) for x in (v or []) if str(x).isdigit()]
            if ids:
                found = {r["id"] for r in db.execute(
                    f"SELECT id FROM theory_items WHERE kind = 'syndrome' AND id IN ({','.join('?' * len(ids))})", ids).fetchall()}
                data[k] = [i for i in ids if i in found]
        elif v not in (None, ""):
            data[k] = str(v).strip()[:MAX_TEXT]
    points = list(dict.fromkeys(str(c).strip().upper() for c in (payload.get("points") or [])))
    points = [c for c in points if c in codes]
    return data, points


def seed_theory(db):
    """Na primeira vez: categorias padrão nos pontos e os nomes dos diagnósticos da MTC."""
    cats = default_categories()
    for row in db.execute("SELECT code FROM acupoints WHERE details IS NULL").fetchall():
        c = cats.get(row["code"])
        db.execute("UPDATE acupoints SET details = ? WHERE code = ?",
                   (json.dumps({"categories": c} if c else {}, ensure_ascii=False), row["code"]))
    if not db.execute("SELECT 1 FROM theory_items WHERE kind = 'tongue'").fetchone():
        now = _now()
        for group, names in TONGUE.items():
            for name in names:
                db.execute("""INSERT INTO theory_items (kind, name, group_name, data, points, created_at, updated_at)
                              VALUES ('tongue', ?, ?, '{}', '[]', ?, ?)""", (name, group, now, now))
    if not db.execute("SELECT 1 FROM theory_items WHERE kind = 'syndrome'").fetchone():
        now = _now()
        for group, names in SYNDROMES.items():
            for name in names:
                db.execute("""INSERT INTO theory_items (kind, name, group_name, data, points, created_at, updated_at)
                              VALUES ('syndrome', ?, ?, '{}', '[]', ?, ?)""", (name, group, now, now))


@theory_bp.get("/theory")
@_admin
def everything():
    """Tudo da parte teórica de uma vez (pontos com detalhes + diagnósticos + sintomas + combinações)."""
    db = get_db()
    points = []
    for r in db.execute("""SELECT code, meridian, number, intl_code, pinyin, name_pt, view, location, indications,
                                  notes, custom, details, updated_at FROM acupoints ORDER BY custom, meridian, number, code""").fetchall():
        d = dict(r)
        d["details"] = json.loads(r["details"]) if r["details"] else {}
        points.append(d)
    items = []
    for r in db.execute("SELECT * FROM theory_items ORDER BY kind, group_name, name").fetchall():
        d = dict(r)
        d["data"] = json.loads(r["data"] or "{}")
        d["points"] = json.loads(r["points"] or "[]")
        items.append(d)
    cats = sorted({c for p in points for c in p["details"].get("categories", [])})
    return jsonify(points=points, items=items, categories=cats, fields={"point": POINT_DETAILS, **KINDS})


@theory_bp.patch("/theory/points/<code>")
@_admin
@csrf_required
def save_point(code):
    db = get_db()
    point = db.execute("SELECT code FROM acupoints WHERE code = ?", (code.upper(),)).fetchone()
    if not point:
        return jsonify(error="Ponto não encontrado."), 404
    payload = request.get_json(silent=True) or {}
    sets, params = [], []
    for col in ("name_pt", "location", "indications", "notes"):
        if col in payload:
            sets.append(f"{col} = ?"); params.append(str(payload[col] or "").strip()[:MAX_TEXT] or None)
    if "details" in payload:
        sets.append("details = ?"); params.append(json.dumps(clean_details(payload["details"] or {}), ensure_ascii=False))
    if not sets:
        return jsonify(error="Nada para alterar."), 400
    sets.append("updated_at = ?"); params.append(_now())
    db.execute(f"UPDATE acupoints SET {', '.join(sets)} WHERE code = ?", (*params, point["code"]))
    db.commit()
    return jsonify(ok=True)


@theory_bp.post("/theory/<kind>")
@_admin
@csrf_required
def create_item(kind):
    if kind not in KINDS:
        return jsonify(error="Tipo inválido."), 404
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()[:200]
    if not name:
        return jsonify(error="Informe o nome."), 400
    db = get_db()
    data, points = _clean_item(kind, payload, known_codes(db), db)
    now = _now()
    db.execute("""INSERT INTO theory_items (kind, name, group_name, data, points, created_at, updated_at)
                  VALUES (?, ?, ?, ?, ?, ?, ?)""",
               (kind, name, str(payload.get("group_name") or "").strip()[:120] or None,
                json.dumps(data, ensure_ascii=False), json.dumps(points), now, now))
    db.commit()
    new_id = db.execute("SELECT MAX(id) AS id FROM theory_items WHERE kind = ?", (kind,)).fetchone()["id"]
    return jsonify(ok=True, id=new_id), 201


@theory_bp.patch("/theory/<kind>/<int:item_id>")
@_admin
@csrf_required
def update_item(kind, item_id):
    db = get_db()
    if kind not in KINDS or not db.execute("SELECT 1 FROM theory_items WHERE id = ? AND kind = ?", (item_id, kind)).fetchone():
        return jsonify(error="Item não encontrado."), 404
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()[:200]
    if not name:
        return jsonify(error="Informe o nome."), 400
    data, points = _clean_item(kind, payload, known_codes(db), db)
    db.execute("""UPDATE theory_items SET name = ?, group_name = ?, data = ?, points = ?, updated_at = ?
                  WHERE id = ?""",
               (name, str(payload.get("group_name") or "").strip()[:120] or None,
                json.dumps(data, ensure_ascii=False), json.dumps(points), _now(), item_id))
    db.commit()
    return jsonify(ok=True)


@theory_bp.delete("/theory/<kind>/<int:item_id>")
@_admin
@csrf_required
def delete_item(kind, item_id):
    db = get_db()
    db.execute("DELETE FROM theory_items WHERE id = ? AND kind = ?", (item_id, kind))
    if kind == "syndrome":  # tira o vínculo dos sintomas/língua que apontavam para este diagnóstico
        for r in db.execute("SELECT id, data FROM theory_items WHERE kind IN ('symptom', 'tongue')").fetchall():
            d = json.loads(r["data"] or "{}")
            if item_id in d.get("syndromes", []):
                d["syndromes"] = [x for x in d["syndromes"] if x != item_id]
                db.execute("UPDATE theory_items SET data = ? WHERE id = ?", (json.dumps(d, ensure_ascii=False), r["id"]))
    db.commit()
    return "", 204

"""Mapa de pontos de acupuntura (somente administração).

- Lista os 361 pontos (+ extras da clínica) com posição no mapa, textos e observações.
- Permite editar textos, ajustar a posição (arrastando no mapa), criar pontos extras e
  ver em quais sessões cada ponto foi usado (a partir dos protocolos).
"""
import json
import re
from datetime import datetime

from flask import Blueprint, jsonify, request

from ..acupoints_data import default_position, meridians_json, sort_key
from ..database import IntegrityError, get_db
from ..security import csrf_required, login_required, roles_required

acupoints_bp = Blueprint("acupoints", __name__)
CODE_RE = re.compile(r"^[A-Z][A-Z0-9-]{1,14}$")
TEXT_FIELDS = ("name_pt", "location", "indications", "notes")
MAX_TEXT = 4000
EXTRA = {"code": "EX", "intl": "EX", "name": "Pontos extras", "color": "#6c5b73", "element": "—", "bilateral": False}


def _admin(view):
    return login_required(roles_required("admin")(view))


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _clamp_pos(x, y):
    return max(0.0, min(300.0, float(x))), max(0.0, min(710.0, float(y)))


def _usage(db, patient_id=None):
    """{código: [sessões]} a partir dos protocolos preenchidos."""
    sql = """SELECT p.data, a.id AS appointment_id, a.date, a.start, u.id AS patient_id, u.name AS patient_name
             FROM session_protocols p JOIN appointments a ON a.id = p.appointment_id
             JOIN users u ON u.id = a.patient_user_id"""
    params = ()
    if patient_id:
        sql += " WHERE u.id = ?"
        params = (patient_id,)
    used = {}
    for row in db.execute(sql + " ORDER BY a.date DESC", params).fetchall():
        for code in json.loads(row["data"]).get("acupoints", []):
            used.setdefault(code, []).append({k: row[k] for k in ("appointment_id", "date", "start", "patient_id", "patient_name")})
    return used


@acupoints_bp.get("/acupoints")
@_admin
def list_points():
    db = get_db()
    rows = db.execute("SELECT * FROM acupoints ORDER BY custom, meridian, number, code").fetchall()
    counts = {code: len(s) for code, s in _usage(db).items()}
    points = sorted(({**dict(r), "used": counts.get(r["code"], 0)} for r in rows), key=sort_key)
    return jsonify(meridians=meridians_json() + [EXTRA], points=points)


@acupoints_bp.get("/acupoints/usage")
@_admin
def usage_by_patient():
    patient_id = request.args.get("patient_id", type=int)
    return jsonify({code: len(s) for code, s in _usage(get_db(), patient_id).items()})


@acupoints_bp.get("/acupoints/<code>/sessions")
@_admin
def point_sessions(code):
    return jsonify(items=_usage(get_db()).get(code.upper(), []))


@acupoints_bp.patch("/acupoints/<code>")
@_admin
@csrf_required
def update_point(code):
    db = get_db()
    point = db.execute("SELECT * FROM acupoints WHERE code = ?", (code.upper(),)).fetchone()
    if not point:
        return jsonify(error="Ponto não encontrado."), 404
    payload = request.get_json(silent=True) or {}
    sets, params = [], []
    for field in TEXT_FIELDS:
        if field in payload:
            sets.append(f"{field} = ?")
            params.append(str(payload[field] or "").strip()[:MAX_TEXT] or None)
    if "pos3d" in payload:
        p3 = payload["pos3d"]
        if p3 is None:
            sets.append("pos3d = ?"); params.append(None)
        else:
            try:
                vals = [round(float(v), 5) for v in p3]
                assert len(vals) == 6 and all(abs(v) < 5 for v in vals)
            except (TypeError, ValueError, AssertionError):
                return jsonify(error="Posição 3D inválida."), 400
            # guardada por corpo: {"m": [...], "f": [...]} (lista antiga = corpo masculino)
            body = payload.get("model") if payload.get("model") in ("m", "f") else "m"
            saved = json.loads(point["pos3d"]) if point["pos3d"] else {}
            if isinstance(saved, list):
                saved = {"m": saved}
            saved[body] = vals
            sets.append("pos3d = ?"); params.append(json.dumps(saved))
    if payload.get("reset_position"):
        if point["custom"]:
            return jsonify(error="Pontos extras não têm posição padrão."), 400
        view, x, y = default_position(point["meridian"], point["number"])
        sets += ["view = ?", "x = ?", "y = ?", "pos3d = ?"]
        params += [view, x, y, None]
    elif "x" in payload and "y" in payload:
        try:
            x, y = _clamp_pos(payload["x"], payload["y"])
        except (TypeError, ValueError):
            return jsonify(error="Posição inválida."), 400
        sets += ["x = ?", "y = ?"]
        params += [x, y]
        if payload.get("view") in ("front", "back", "ear"):
            sets.append("view = ?")
            params.append(payload["view"])
    if not sets:
        return jsonify(error="Nada para alterar."), 400
    sets.append("updated_at = ?")
    params.append(_now())
    db.execute(f"UPDATE acupoints SET {', '.join(sets)} WHERE code = ?", (*params, point["code"]))
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM acupoints WHERE code = ?", (point["code"],)).fetchone()))


@acupoints_bp.post("/acupoints")
@_admin
@csrf_required
def create_point():
    """Ponto extra da clínica (ex.: Yintang, Taiyang, pontos de auriculoterapia)."""
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip().upper().replace(" ", "-")
    pinyin = str(payload.get("pinyin", "")).strip()
    if not CODE_RE.match(code) or not pinyin:
        return jsonify(error="Informe um código (ex.: EX-HN3) e um nome."), 400
    view = payload.get("view") if payload.get("view") in ("front", "back", "ear") else "front"
    try:
        x, y = _clamp_pos(payload.get("x", 150), payload.get("y", 60))
    except (TypeError, ValueError):
        return jsonify(error="Posição inválida."), 400
    texts = [str(payload.get(f) or "").strip()[:MAX_TEXT] or None for f in TEXT_FIELDS]
    db = get_db()
    try:
        db.execute(
            """INSERT INTO acupoints (code, meridian, number, intl_code, pinyin, name_pt, view, x, y,
                                      location, indications, notes, custom, updated_at)
               VALUES (?, 'EX', NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (code, pinyin, texts[0], view, x, y, texts[1], texts[2], texts[3], _now()),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        return jsonify(error="Já existe um ponto com esse código."), 409
    return jsonify(ok=True, code=code), 201


@acupoints_bp.delete("/acupoints/<code>")
@_admin
@csrf_required
def delete_point(code):
    db = get_db()
    point = db.execute("SELECT custom FROM acupoints WHERE code = ?", (code.upper(),)).fetchone()
    if not point:
        return jsonify(error="Ponto não encontrado."), 404
    if not point["custom"]:
        return jsonify(error="Os pontos padrão (361 clássicos e auriculares) não podem ser excluídos (só editados)."), 400
    if _usage(db).get(code.upper()):
        return jsonify(error="Este ponto já foi usado em protocolos e não pode ser excluído."), 409
    db.execute("DELETE FROM acupoints WHERE code = ?", (code.upper(),))
    db.commit()
    return "", 204


def known_codes(db):
    return {r["code"] for r in db.execute("SELECT code FROM acupoints").fetchall()}

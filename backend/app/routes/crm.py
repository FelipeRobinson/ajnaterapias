"""Rotas do painel do administrador: visão geral, clientes e agenda."""
import re
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

from ..database import IntegrityError, get_db
from ..security import csrf_required, login_required, roles_required

crm_bp = Blueprint("crm", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
# requested = pedida pelo cliente (aguarda confirmação) · scheduled = confirmada
STATUSES = ("requested", "scheduled", "done", "cancelled")


def _admin(view):
    """Atalho: exige login de administrador."""
    return login_required(roles_required("admin")(view))


def _valid_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------- visão geral

@crm_bp.get("/dashboard")
@_admin
def dashboard():
    db = get_db()
    today = date.today()
    week_end = today + timedelta(days=6)
    count = lambda sql, params=(): db.execute(sql, params).fetchone()["n"]
    agenda = db.execute(
        """SELECT a.id, a.patient_user_id, a.start, a."end", a.status, u.name AS patient_name,
                  (SELECT COUNT(*) FROM session_protocols sp WHERE sp.appointment_id = a.id) AS has_protocol
           FROM appointments a JOIN users u ON u.id = a.patient_user_id
           WHERE a.date = ? AND a.status != 'cancelled' ORDER BY a.start""",
        (today.isoformat(),),
    ).fetchall()
    requests = db.execute(
        """SELECT a.id, a.patient_user_id, a.date, a.start, a."end", a.status, u.name AS patient_name
           FROM appointments a JOIN users u ON u.id = a.patient_user_id
           WHERE a.status = 'requested' AND a.date >= ? ORDER BY a.date, a.start""",
        (today.isoformat(),),
    ).fetchall()
    return jsonify(
        requests=[dict(r) for r in requests],
        patients=count("SELECT COUNT(*) AS n FROM users WHERE role = 'patient' AND active = 1"),
        inactive=count("SELECT COUNT(*) AS n FROM users WHERE role = 'patient' AND active = 0"),
        appointments_today=len(agenda),
        appointments_week=count(
            "SELECT COUNT(*) AS n FROM appointments WHERE date BETWEEN ? AND ? AND status != 'cancelled'",
            (today.isoformat(), week_end.isoformat()),
        ),
        today=[dict(r) for r in agenda],
    )


# ---------------------------------------------------------------- clientes

@crm_bp.get("/patients")
@_admin
def patients():
    rows = get_db().execute(
        """SELECT u.id, u.name, u.email, u.phone, u.active, u.created_at,
                  (SELECT COUNT(*) FROM appointments a WHERE a.patient_user_id = u.id) AS appointments
           FROM users u WHERE u.role = 'patient' ORDER BY u.name"""
    ).fetchall()
    return jsonify(items=[dict(r) for r in rows])


@crm_bp.post("/patients")
@_admin
@csrf_required
def create_patient():
    """O administrador cria o acesso do cliente (nome, e-mail e senha inicial)."""
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    phone = str(payload.get("phone", "")).strip() or None
    password = str(payload.get("password", ""))
    if not name or not EMAIL_RE.match(email):
        return jsonify(error="Informe nome e um e-mail válido."), 400
    if len(password) < 8:
        return jsonify(error="A senha inicial precisa ter pelo menos 8 caracteres."), 400
    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (name, email, phone, password_hash, role) VALUES (?, ?, ?, ?, 'patient')",
            (name, email, phone, generate_password_hash(password)),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        return jsonify(error="Já existe um acesso com este e-mail."), 409
    return jsonify(ok=True), 201


@crm_bp.patch("/patients/<int:user_id>")
@_admin
@csrf_required
def update_patient(user_id):
    """Edita nome/e-mail/telefone, ativa/desativa ou redefine a senha do cliente."""
    payload = request.get_json(silent=True) or {}
    db = get_db()
    if not db.execute("SELECT 1 FROM users WHERE id = ? AND role = 'patient'", (user_id,)).fetchone():
        return jsonify(error="Cliente não encontrado."), 404

    sets, params = [], []
    if "name" in payload:
        name = str(payload["name"]).strip()
        if not name:
            return jsonify(error="O nome não pode ficar vazio."), 400
        sets.append("name = ?"); params.append(name)
    if "email" in payload:
        email = str(payload["email"]).strip().lower()
        if not EMAIL_RE.match(email):
            return jsonify(error="Informe um e-mail válido."), 400
        sets.append("email = ?"); params.append(email)
    if "phone" in payload:
        sets.append("phone = ?"); params.append(str(payload["phone"] or "").strip() or None)
    if "active" in payload:
        sets.append("active = ?"); params.append(1 if payload["active"] else 0)
    if payload.get("password"):
        password = str(payload["password"])
        if len(password) < 8:
            return jsonify(error="A senha precisa ter pelo menos 8 caracteres."), 400
        sets.append("password_hash = ?"); params.append(generate_password_hash(password))
    if not sets:
        return jsonify(error="Nada para alterar."), 400

    try:
        db.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ? AND role = 'patient'", (*params, user_id))
        db.commit()
    except IntegrityError:
        db.rollback()
        return jsonify(error="Já existe um acesso com este e-mail."), 409
    return jsonify(ok=True)


@crm_bp.delete("/patients/<int:user_id>")
@_admin
@csrf_required
def delete_patient(user_id):
    """Exclui o cliente. Quem já tem consultas não é apagado (para não perder histórico): desative."""
    db = get_db()
    has_history = db.execute(
        "SELECT COUNT(*) AS n FROM appointments WHERE patient_user_id = ?", (user_id,)
    ).fetchone()["n"]
    if has_history:
        return jsonify(error="Este cliente tem consultas registradas. Desative o acesso em vez de excluir."), 409
    db.execute("DELETE FROM medical_records WHERE patient_user_id = ?", (user_id,))
    db.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ? AND role = 'patient'", (user_id,))
    db.commit()
    return "", 204


# ---------------------------------------------------------------- agenda

def _read_appointment(payload, partial=False):
    """Valida os campos de uma consulta. Retorna (dados, erro)."""
    data = {}
    if not partial or "patient_user_id" in payload:
        try:
            data["patient_user_id"] = int(payload.get("patient_user_id"))
        except (TypeError, ValueError):
            return None, "Escolha o cliente."
    if not partial or "date" in payload:
        if not _valid_date(payload.get("date")):
            return None, "Data inválida."
        data["date"] = payload["date"]
    for field in ("start", "end"):
        if not partial or field in payload:
            if not TIME_RE.match(str(payload.get(field, ""))):
                return None, "Horário inválido. Use HH:MM."
            data[field] = payload[field]
    if "status" in payload:
        if payload["status"] not in STATUSES:
            return None, "Situação inválida."
        data["status"] = payload["status"]
    return data, None


def _conflict(db, day, start, end, ignore_id=None):
    """Existe outra consulta ativa no mesmo dia que se sobrepõe ao horário?"""
    return db.execute(
        """SELECT COUNT(*) AS n FROM appointments
           WHERE date = ? AND status != 'cancelled' AND start < ? AND "end" > ? AND id != ?""",
        (day, end, start, ignore_id or 0),
    ).fetchone()["n"]


@crm_bp.get("/appointments")
@_admin
def appointments():
    start = request.args.get("from") or date.today().isoformat()
    end = request.args.get("to") or (date.fromisoformat(start) + timedelta(days=6)).isoformat()
    if not (_valid_date(start) and _valid_date(end)):
        return jsonify(error="Período inválido."), 400
    rows = get_db().execute(
        """SELECT a.id, a.patient_user_id, a.date, a.start, a."end", a.status, u.name AS patient_name, u.phone,
                  (SELECT COUNT(*) FROM session_protocols sp WHERE sp.appointment_id = a.id) AS has_protocol
           FROM appointments a JOIN users u ON u.id = a.patient_user_id
           WHERE a.date BETWEEN ? AND ? ORDER BY a.date, a.start""",
        (start, end),
    ).fetchall()
    return jsonify(items=[dict(r) for r in rows], **{"from": start, "to": end})


@crm_bp.post("/appointments")
@_admin
@csrf_required
def create_appointment():
    data, error = _read_appointment(request.get_json(silent=True) or {})
    if error:
        return jsonify(error=error), 400
    if data["end"] <= data["start"]:
        return jsonify(error="O horário de término precisa ser depois do início."), 400
    db = get_db()
    if not db.execute("SELECT 1 FROM users WHERE id = ? AND role = 'patient' AND active = 1",
                      (data["patient_user_id"],)).fetchone():
        return jsonify(error="Cliente não encontrado ou desativado."), 400
    if _conflict(db, data["date"], data["start"], data["end"]):
        return jsonify(error="Já existe uma consulta nesse horário."), 409
    db.execute(
        'INSERT INTO appointments (patient_user_id, date, start, "end") VALUES (?, ?, ?, ?)',
        (data["patient_user_id"], data["date"], data["start"], data["end"]),
    )
    db.commit()
    return jsonify(ok=True), 201


@crm_bp.patch("/appointments/<int:appointment_id>")
@_admin
@csrf_required
def update_appointment(appointment_id):
    """Remarca (data/horário) ou muda a situação: agendada, realizada ou cancelada."""
    db = get_db()
    current = db.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    if not current:
        return jsonify(error="Consulta não encontrada."), 404
    data, error = _read_appointment(request.get_json(silent=True) or {}, partial=True)
    if error:
        return jsonify(error=error), 400
    if not data:
        return jsonify(error="Nada para alterar."), 400
    merged = {**dict(current), **data}
    if merged["end"] <= merged["start"]:
        return jsonify(error="O horário de término precisa ser depois do início."), 400
    if merged["status"] != "cancelled" and _conflict(db, merged["date"], merged["start"], merged["end"], appointment_id):
        return jsonify(error="Já existe uma consulta nesse horário."), 409
    columns = ", ".join(f'"{k}" = ?' for k in data)
    db.execute(f"UPDATE appointments SET {columns} WHERE id = ?", (*data.values(), appointment_id))
    db.commit()
    return jsonify(ok=True)


@crm_bp.delete("/appointments/<int:appointment_id>")
@_admin
@csrf_required
def delete_appointment(appointment_id):
    db = get_db()
    if db.execute("SELECT 1 FROM session_protocols WHERE appointment_id = ?", (appointment_id,)).fetchone():
        return jsonify(error="Esta consulta tem protocolo preenchido e não pode ser excluída."), 409
    db.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    db.commit()
    return "", 204

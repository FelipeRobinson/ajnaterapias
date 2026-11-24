"""Rotas do painel do administrador: visão geral, clientes e agenda."""
import json
import re
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

from ..calendar_rules import (RECURRENCES, SUNDAY, WEEKDAY_NAMES, closed_weekdays, is_closed,
                              save_closed_weekdays)
from ..database import IntegrityError, get_db
from .finance import apply_package
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
        """SELECT u.id, u.name, u.email, u.phone, u.active, u.avatar, u.social, u.created_at,
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
    if "social" in payload:  # participa do Ambulatório Social
        sets.append("social = ?"); params.append(1 if payload["social"] else 0)
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
    """Exclui o cliente. Quem já tem sessões não é apagado (para não perder histórico): desative."""
    db = get_db()
    has_history = db.execute(
        "SELECT COUNT(*) AS n FROM appointments WHERE patient_user_id = ?", (user_id,)
    ).fetchone()["n"]
    if has_history:
        return jsonify(error="Este cliente tem sessões registradas. Desative o acesso em vez de excluir."), 409
    db.execute("DELETE FROM medical_records WHERE patient_user_id = ?", (user_id,))
    db.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ? AND role = 'patient'", (user_id,))
    db.commit()
    return "", 204


# ---------------------------------------------------------------- agenda

def _read_appointment(payload, partial=False):
    """Valida os campos de uma sessão. Retorna (dados, erro)."""
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
    # financeiro: terapia e valor da sessão (centavos)
    if "service_id" in payload:
        sid = payload.get("service_id")
        try:
            data["service_id"] = int(sid) if sid not in (None, "") else None
        except (TypeError, ValueError):
            return None, "Terapia inválida."
    if "price_cents" in payload and payload.get("price_cents") not in (None, ""):
        try:
            data["price_cents"] = int(payload["price_cents"])
        except (TypeError, ValueError):
            return None, "Valor inválido."
        if not 0 <= data["price_cents"] <= 100_000_000:
            return None, "Valor inválido."
    return data, None


def _fill_price(db, data):
    """Escolheu a terapia e não digitou valor: usa o preço da terapia."""
    if data.get("service_id") and "price_cents" not in data:
        row = db.execute("SELECT price_cents FROM services WHERE id = ?", (data["service_id"],)).fetchone()
        if not row:
            return "Terapia não encontrada."
        data["price_cents"] = row["price_cents"]
    return None


def _conflict(db, day, start, end, ignore_id=None):
    """Existe outra sessão ativa no mesmo dia que se sobrepõe ao horário?"""
    return db.execute(
        """SELECT COUNT(*) AS n FROM appointments
           WHERE date = ? AND status != 'cancelled' AND start < ? AND "end" > ? AND id != ?""",
        (day, end, start, ignore_id or 0),
    ).fetchone()["n"]


def _blocked(db, day, start, end, ignore_id=None):
    """O horário cai num período marcado como indisponível?"""
    return db.execute(
        """SELECT reason FROM schedule_blocks WHERE date = ? AND start < ? AND "end" > ? AND id != ?""",
        (day, end, start, ignore_id or 0),
    ).fetchone()


@crm_bp.get("/blocks")
@_admin
def blocks():
    start, end = request.args.get("from", ""), request.args.get("to", "")
    if not (_valid_date(start) and _valid_date(end)):
        return jsonify(error="Período inválido."), 400
    rows = get_db().execute(
        'SELECT id, date, start, "end", reason FROM schedule_blocks WHERE date BETWEEN ? AND ? ORDER BY date, start',
        (start, end)).fetchall()
    return jsonify(items=[dict(r) for r in rows])


@crm_bp.post("/blocks")
@_admin
@csrf_required
def create_block():
    """Marca um período como indisponível. Aceita vários dias seguidos (date até date_to)."""
    payload = request.get_json(silent=True) or {}
    first, last = payload.get("date"), payload.get("date_to") or payload.get("date")
    if not (_valid_date(first) and _valid_date(last)) or last < first:
        return jsonify(error="Data inválida."), 400
    days = (date.fromisoformat(last) - date.fromisoformat(first)).days
    if days > 366:
        return jsonify(error="Bloqueie no máximo um ano de cada vez."), 400
    start, end = str(payload.get("start", "")), str(payload.get("end", ""))
    if not (TIME_RE.match(start) and TIME_RE.match(end)) or end <= start:
        return jsonify(error="Horário inválido: o término precisa ser depois do início."), 400
    reason = str(payload.get("reason") or "").strip()[:120] or None
    db = get_db()
    for n in range(days + 1):
        day = (date.fromisoformat(first) + timedelta(days=n)).isoformat()
        db.execute('INSERT INTO schedule_blocks (date, start, "end", reason) VALUES (?, ?, ?, ?)', (day, start, end, reason))
    db.commit()
    # Avisa se ficou alguma sessão dentro do período (a clínica decide se remarca).
    clash = db.execute(
        """SELECT COUNT(*) AS n FROM appointments WHERE date BETWEEN ? AND ? AND status IN ('requested', 'scheduled')
           AND start < ? AND "end" > ?""", (first, last, end, start)).fetchone()["n"]
    return jsonify(ok=True, created=days + 1, appointments_inside=clash), 201


@crm_bp.delete("/blocks/<int:block_id>")
@_admin
@csrf_required
def delete_block(block_id):
    db = get_db()
    db.execute("DELETE FROM schedule_blocks WHERE id = ?", (block_id,))
    db.commit()
    return "", 204


# ---------------------------------------------------------------- dias de atendimento
@crm_bp.get("/calendar-settings")
@_admin
def calendar_settings():
    """Dias da semana sem atendimento. Domingo é fixo; segunda a sábado a administração escolhe."""
    return jsonify(closed_weekdays=list(closed_weekdays()), weekday_names=WEEKDAY_NAMES, fixed=[SUNDAY],
                   recurrences=RECURRENCES)


@crm_bp.put("/calendar-settings")
@_admin
@csrf_required
def save_calendar_settings():
    days = (request.get_json(silent=True) or {}).get("closed_weekdays")
    if not isinstance(days, list):
        return jsonify(error="Informe a lista de dias sem atendimento."), 400
    db = get_db()
    saved = save_closed_weekdays(db, days)
    db.commit()
    return jsonify(ok=True, closed_weekdays=list(saved))


# ---------------------------------------------------------------- eventos da clínica (aparecem para todos)
def _read_event(payload):
    title = str(payload.get("title") or "").strip()[:80]
    if not title:
        return None, "Dê um nome ao evento."
    if not _valid_date(payload.get("date")):
        return None, "Escolha a data do evento."
    rec = payload.get("recurrence") or "once"
    if rec not in RECURRENCES:
        return None, "Repetição inválida."
    until = payload.get("until") or None
    if until and (not _valid_date(until) or until < payload["date"]):
        return None, "A data final da repetição precisa ser depois da data do evento."
    times = []
    for k in ("start_time", "end_time"):
        v = str(payload.get(k) or "").strip()
        if v and not TIME_RE.match(v):
            return None, "Horário inválido."
        times.append(v or None)
    if times[0] and times[1] and times[1] <= times[0]:
        return None, "O horário de término precisa ser depois do início."
    return {"title": title, "icon": (str(payload.get("icon") or "").strip()[:8] or "📅"),
            "description": str(payload.get("description") or "").strip()[:500] or None,
            "date": payload["date"], "recurrence": rec, "until": until if rec != "once" else None,
            "start_time": times[0], "end_time": times[1]}, None


@crm_bp.get("/events")
@_admin
def list_events():
    rows = get_db().execute("SELECT * FROM events ORDER BY date, title").fetchall()
    return jsonify(items=[dict(r) for r in rows], recurrences=RECURRENCES)


@crm_bp.post("/events")
@_admin
@csrf_required
def create_event():
    data, error = _read_event(request.get_json(silent=True) or {})
    if error:
        return jsonify(error=error), 400
    db = get_db()
    db.execute(f"INSERT INTO events ({', '.join(data)}, created_at) VALUES ({', '.join('?' * len(data))}, ?)",
               (*data.values(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    db.commit()
    return jsonify(ok=True), 201


@crm_bp.put("/events/<int:event_id>")
@_admin
@csrf_required
def update_event(event_id):
    db = get_db()
    if not db.execute("SELECT 1 FROM events WHERE id = ?", (event_id,)).fetchone():
        return jsonify(error="Evento não encontrado."), 404
    data, error = _read_event(request.get_json(silent=True) or {})
    if error:
        return jsonify(error=error), 400
    db.execute(f"UPDATE events SET {', '.join(f'{k} = ?' for k in data)} WHERE id = ?", (*data.values(), event_id))
    db.commit()
    return jsonify(ok=True)


@crm_bp.delete("/events/<int:event_id>")
@_admin
@csrf_required
def delete_event(event_id):
    db = get_db()
    db.execute("DELETE FROM events WHERE id = ?", (event_id,))
    db.commit()
    return "", 204


# ---------------------------------------------------------------- aniversários dos clientes (só administração)
@crm_bp.get("/birthdays")
@_admin
def birthdays():
    """Aniversários dos clientes ativos entre duas datas (vem da data de nascimento em "Dados pessoais")."""
    start, end = request.args.get("from", ""), request.args.get("to", "")
    if not (_valid_date(start) and _valid_date(end)) or end < start:
        return jsonify(error="Período inválido."), 400
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if (last - first).days > 800:
        return jsonify(error="Período inválido."), 400
    out = []
    for r in get_db().execute(
            "SELECT id, name, profile FROM users WHERE role = 'patient' AND active = 1 AND profile IS NOT NULL").fetchall():
        try:
            born = date.fromisoformat((json.loads(r["profile"]) or {}).get("birth_date") or "")
        except (ValueError, TypeError, AttributeError):
            continue
        for year in range(first.year, last.year + 1):
            try:
                d = born.replace(year=year)
            except ValueError:  # 29 de fevereiro em ano comum -> 28
                d = date(year, 2, 28)
            if first <= d <= last and year >= born.year:
                out.append({"date": d.isoformat(), "patient_id": r["id"], "name": r["name"], "age": year - born.year})
    return jsonify(items=sorted(out, key=lambda b: (b["date"], b["name"])))


@crm_bp.get("/appointments")
@_admin
def appointments():
    start = request.args.get("from") or date.today().isoformat()
    end = request.args.get("to") or (date.fromisoformat(start) + timedelta(days=6)).isoformat()
    if not (_valid_date(start) and _valid_date(end)):
        return jsonify(error="Período inválido."), 400
    rows = get_db().execute(
        """SELECT a.id, a.patient_user_id, a.date, a.start, a."end", a.status, u.name AS patient_name, u.phone,
                  a.service_id, a.price_cents, a.package_id, s.name AS service_name,
                  (SELECT COUNT(*) FROM session_protocols sp WHERE sp.appointment_id = a.id) AS has_protocol
           FROM appointments a JOIN users u ON u.id = a.patient_user_id LEFT JOIN services s ON s.id = a.service_id
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
        return jsonify(error="Já existe uma sessão nesse horário."), 409
    if _blocked(db, data["date"], data["start"], data["end"]):
        return jsonify(error="Esse horário está marcado como indisponível. Libere-o na agenda antes de agendar."), 409
    if is_closed(date.fromisoformat(data["date"])) and not (request.get_json(silent=True) or {}).get("force"):
        return jsonify(error="Esse é um dia sem atendimento.", closed_day=True), 409
    error = _fill_price(db, data)
    if error:
        return jsonify(error=error), 400
    db.execute(
        'INSERT INTO appointments (patient_user_id, date, start, "end", service_id, price_cents) VALUES (?, ?, ?, ?, ?, ?)',
        (data["patient_user_id"], data["date"], data["start"], data["end"], data.get("service_id"), data.get("price_cents")),
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
        return jsonify(error="Sessão não encontrada."), 404
    data, error = _read_appointment(request.get_json(silent=True) or {}, partial=True)
    if error:
        return jsonify(error=error), 400
    if not data:
        return jsonify(error="Nada para alterar."), 400
    merged = {**dict(current), **data}
    if merged["end"] <= merged["start"]:
        return jsonify(error="O horário de término precisa ser depois do início."), 400
    if merged["status"] != "cancelled" and _conflict(db, merged["date"], merged["start"], merged["end"], appointment_id):
        return jsonify(error="Já existe uma sessão nesse horário."), 409
    moved = any(k in data for k in ("date", "start", "end"))
    if moved and merged["status"] != "cancelled" and _blocked(db, merged["date"], merged["start"], merged["end"]):
        return jsonify(error="Esse horário está marcado como indisponível. Libere-o na agenda antes de remarcar."), 409
    force = (request.get_json(silent=True) or {}).get("force")
    if "date" in data and data["date"] != current["date"] and is_closed(date.fromisoformat(data["date"])) and not force:
        return jsonify(error="Esse é um dia sem atendimento.", closed_day=True), 409
    if data.get("service_id") != current["service_id"] or "price_cents" in data:
        error = _fill_price(db, data)
        if error:
            return jsonify(error=error), 400
    columns = ", ".join(f'"{k}" = ?' for k in data)
    db.execute(f"UPDATE appointments SET {columns} WHERE id = ?", (*data.values(), appointment_id))
    if data.get("status") == "done":
        apply_package(db, appointment_id)  # desconta do pacote do cliente, se houver
    if data.get("status") == "cancelled":
        db.execute("UPDATE appointments SET package_id = NULL WHERE id = ?", (appointment_id,))  # devolve ao pacote
    db.commit()
    return jsonify(ok=True)


@crm_bp.delete("/appointments/<int:appointment_id>")
@_admin
@csrf_required
def delete_appointment(appointment_id):
    db = get_db()
    if db.execute("SELECT 1 FROM session_protocols WHERE appointment_id = ?", (appointment_id,)).fetchone():
        return jsonify(error="Esta sessão tem protocolo preenchido e não pode ser excluída."), 409
    db.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    db.commit()
    return "", 204

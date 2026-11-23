"""Rotas da área do cliente: consultas, pedido de horário e dados pessoais."""
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from ..calendar_rules import closed_weekdays, events_between
from ..database import get_db
from ..security import csrf_required, login_required, roles_required

patient_bp = Blueprint("patient", __name__)

# ------------------------------------------------------------------ regras da clínica
# Ajuste aqui o funcionamento. Dia da semana: 0 = segunda ... 6 = domingo.
OPENING_HOURS = {
    1: ("08:00", "18:00"),
    2: ("08:00", "18:00"),
    3: ("08:00", "18:00"),
}
SLOT_MINUTES = 60          # duração de cada horário
DAYS_AHEAD = 60            # até quantos dias à frente o cliente pode pedir
CANCEL_MIN_HOURS = 24      # antecedência mínima para o cliente cancelar uma consulta confirmada
MAX_OPEN = 3               # máximo de consultas futuras (pedidas + confirmadas) por cliente


def _patient(view):
    return login_required(roles_required("patient")(view))


def _parse_day(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _hm(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _minutes(hm):
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


def _free_slots(db, day):
    """Horários livres de um dia, conforme o funcionamento e as consultas já marcadas."""
    hours = None if day.weekday() in closed_weekdays() else OPENING_HOURS.get(day.weekday())
    if not hours or day < date.today() or day > date.today() + timedelta(days=DAYS_AHEAD):
        return []
    busy = db.execute(
        """SELECT start, "end" FROM appointments WHERE date = ? AND status != 'cancelled'""",
        (day.isoformat(),),
    ).fetchall()
    busy += db.execute('SELECT start, "end" FROM schedule_blocks WHERE date = ?', (day.isoformat(),)).fetchall()
    busy = [(_minutes(b["start"]), _minutes(b["end"])) for b in busy]
    now = datetime.now()
    slots = []
    t, close = _minutes(hours[0]), _minutes(hours[1])
    while t + SLOT_MINUTES <= close:
        end = t + SLOT_MINUTES
        in_past = day == now.date() and t <= now.hour * 60 + now.minute
        if not in_past and not any(s < end and e > t for s, e in busy):
            slots.append({"start": _hm(t), "end": _hm(end)})
        t += SLOT_MINUTES
    return slots


# ------------------------------------------------------------------ consultas

@patient_bp.get("/availability")
@login_required
@roles_required("patient", "admin")
def availability():
    """Retorna apenas livre/ocupado — nunca dados de consultas de outras pessoas."""
    day = request.args.get("date", "")
    if not _parse_day(day):
        return jsonify(error="Data inválida. Use AAAA-MM-DD."), 400
    rows = get_db().execute(
        """SELECT start, "end" FROM appointments WHERE date = ? AND status != 'cancelled' ORDER BY start""", (day,)
    ).fetchall()
    rows += get_db().execute('SELECT start, "end" FROM schedule_blocks WHERE date = ? ORDER BY start', (day,)).fetchall()
    return jsonify(date=day, busy=sorted((dict(r) for r in rows), key=lambda r: r["start"]))


@patient_bp.get("/events")
@login_required
@roles_required("patient", "admin")
def events():
    """Eventos da clínica (ex.: Reiki Para Todos). Sem período, devolve os próximos 6 meses."""
    start = _parse_day(request.args.get("from")) or date.today()
    end = _parse_day(request.args.get("to")) or start + timedelta(days=183)
    if end < start or (end - start).days > 800:
        return jsonify(error="Período inválido."), 400
    return jsonify(items=events_between(start, end), closed_weekdays=list(closed_weekdays()))


@patient_bp.get("/me/appointments")
@_patient
def my_appointments():
    rows = get_db().execute(
        'SELECT id, date, start, "end", status FROM appointments WHERE patient_user_id = ? ORDER BY date, start',
        (session["user_id"],),
    ).fetchall()
    return jsonify(items=[dict(r) for r in rows], cancel_min_hours=CANCEL_MIN_HOURS)


@patient_bp.get("/slots")
@_patient
def slots():
    day = _parse_day(request.args.get("date"))
    if not day:
        return jsonify(error="Data inválida."), 400
    return jsonify(date=day.isoformat(), slots=_free_slots(get_db(), day))


@patient_bp.get("/schedule-info")
@_patient
def schedule_info():
    """Dias de funcionamento e limite de agendamento, para a tela de pedir horário."""
    return jsonify(
        open_weekdays=sorted(w for w in OPENING_HOURS if w not in closed_weekdays()),
        # Horário de fechamento de hoje (ou null se fechado): a tela pula o dia se já passou.
        today_closes=(OPENING_HOURS.get(date.today().weekday()) or (None, None))[1],
        days_ahead=DAYS_AHEAD,
        slot_minutes=SLOT_MINUTES,
        cancel_min_hours=CANCEL_MIN_HOURS,
    )


@patient_bp.post("/appointments")
@_patient
@csrf_required
def request_appointment():
    """O cliente PEDE um horário livre. Fica 'requested' até a clínica confirmar."""
    payload = request.get_json(silent=True) or {}
    day = _parse_day(payload.get("date"))
    start = str(payload.get("start", ""))
    if not day:
        return jsonify(error="Escolha uma data."), 400
    db = get_db()
    slot = next((s for s in _free_slots(db, day) if s["start"] == start), None)
    if not slot:
        return jsonify(error="Esse horário não está mais disponível. Escolha outro."), 409
    open_count = db.execute(
        """SELECT COUNT(*) AS n FROM appointments
           WHERE patient_user_id = ? AND date >= ? AND status IN ('requested', 'scheduled')""",
        (session["user_id"], date.today().isoformat()),
    ).fetchone()["n"]
    if open_count >= MAX_OPEN:
        return jsonify(error=f"Você já tem {MAX_OPEN} consultas em aberto. Fale com a clínica para marcar mais."), 409
    db.execute(
        """INSERT INTO appointments (patient_user_id, date, start, "end", status) VALUES (?, ?, ?, ?, 'requested')""",
        (session["user_id"], day.isoformat(), slot["start"], slot["end"]),
    )
    db.commit()
    return jsonify(ok=True), 201


@patient_bp.post("/appointments/<int:appointment_id>/cancel")
@_patient
@csrf_required
def cancel_appointment(appointment_id):
    db = get_db()
    appt = db.execute(
        "SELECT date, start, status FROM appointments WHERE id = ? AND patient_user_id = ?",
        (appointment_id, session["user_id"]),
    ).fetchone()
    if not appt:
        return jsonify(error="Consulta não encontrada."), 404
    if appt["status"] not in ("requested", "scheduled"):
        return jsonify(error="Esta consulta não pode mais ser cancelada."), 400
    when = datetime.strptime(f'{appt["date"]} {appt["start"]}', "%Y-%m-%d %H:%M")
    if appt["status"] == "scheduled" and when - datetime.now() < timedelta(hours=CANCEL_MIN_HOURS):
        return jsonify(error=f"Cancelamentos com menos de {CANCEL_MIN_HOURS}h de antecedência devem ser feitos com a clínica."), 400
    db.execute("UPDATE appointments SET status = 'cancelled' WHERE id = ?", (appointment_id,))
    db.commit()
    return jsonify(ok=True)


# ------------------------------------------------------------------ meus dados

@patient_bp.get("/me")
@_patient
def profile():
    user = get_db().execute(
        "SELECT name, email, phone, created_at FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()
    return jsonify(dict(user))


@patient_bp.patch("/me")
@_patient
@csrf_required
def update_profile():
    """O cliente pode atualizar o próprio telefone. Nome e e-mail só a clínica altera."""
    payload = request.get_json(silent=True) or {}
    phone = str(payload.get("phone", "")).strip()[:30] or None
    db = get_db()
    db.execute("UPDATE users SET phone = ? WHERE id = ?", (phone, session["user_id"]))
    db.commit()
    return jsonify(ok=True)


@patient_bp.post("/me/password")
@_patient
@csrf_required
def change_password():
    payload = request.get_json(silent=True) or {}
    current = str(payload.get("current", ""))
    new = str(payload.get("new", ""))
    db = get_db()
    user = db.execute("SELECT password_hash FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    if not check_password_hash(user["password_hash"], current):
        return jsonify(error="A senha atual está incorreta."), 400
    if len(new) < 8:
        return jsonify(error="A nova senha precisa ter pelo menos 8 caracteres."), 400
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new), session["user_id"]))
    db.commit()
    return jsonify(ok=True)

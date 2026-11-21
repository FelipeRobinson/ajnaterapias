from datetime import datetime

from flask import Blueprint, jsonify, request, session

from ..database import get_db
from ..security import login_required, roles_required

patient_bp = Blueprint("patient", __name__)


@patient_bp.get("/availability")
@login_required
@roles_required("patient", "admin")
def availability():
    """Retorna apenas livre/ocupado — nunca dados de consultas de outras pessoas."""
    day = request.args.get("date", "")
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return jsonify(error="Data inválida. Use AAAA-MM-DD."), 400
    rows = get_db().execute(
        "SELECT start, end FROM appointments WHERE date = ? AND status != 'cancelled' ORDER BY start", (day,)
    ).fetchall()
    return jsonify(date=day, busy=[dict(r) for r in rows])


@patient_bp.get("/me/appointments")
@login_required
@roles_required("patient")
def my_appointments():
    rows = get_db().execute(
        "SELECT date, start, end, status FROM appointments WHERE patient_user_id = ? ORDER BY date, start",
        (session["user_id"],),
    ).fetchall()
    return jsonify(items=[dict(r) for r in rows])

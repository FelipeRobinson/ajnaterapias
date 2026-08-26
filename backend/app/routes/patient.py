from datetime import datetime

from flask import Blueprint, jsonify, request, session

from ..database import get_db
from ..security import login_required, roles_required

patient_bp = Blueprint("patient", __name__)


@patient_bp.get("/availability")
@login_required
@roles_required("patient")
def availability():
    """Retorna apenas livre/ocupado. Nunca título, anotações ou dados de outra consulta."""
    date = request.args.get("date", "")
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return jsonify(error="Data inválida. Use AAAA-MM-DD."), 400

    appointments = get_db().appointments.find(
        {"date": date}, {"_id": 0, "start": 1, "end": 1, "status": 1}
    )
    busy = [{"start": item["start"], "end": item["end"]} for item in appointments if item.get("status") != "cancelled"]
    return jsonify(date=date, busy=busy)


@patient_bp.get("/me/appointments")
@login_required
@roles_required("patient")
def my_appointments():
    appointments = get_db().appointments.find(
        {"patient_user_id": session["user_id"]},
        {"_id": 0, "date": 1, "start": 1, "end": 1, "status": 1},
    )
    return jsonify(items=list(appointments))


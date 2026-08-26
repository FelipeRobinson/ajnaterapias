from datetime import date

from flask import Blueprint, jsonify

from ..database import get_db
from ..security import login_required, roles_required

crm_bp = Blueprint("crm", __name__)


@crm_bp.get("/dashboard")
@login_required
@roles_required("admin")
def dashboard():
    db = get_db()
    return jsonify(
        patients=db.patients.count_documents({"active": True}),
        appointments_today=db.appointments.count_documents({"date": date.today().isoformat()}),
    )


@crm_bp.get("/patients")
@login_required
@roles_required("admin")
def patients():
    records = get_db().patients.find(
        {}, {"_id": 0, "name": 1, "phone": 1, "email": 1, "updated_at": 1}
    )
    return jsonify(items=list(records))


@crm_bp.get("/patients/<patient_id>/clinical-record")
@login_required
@roles_required("admin")
def clinical_record(patient_id):
    record = get_db().clinical_records.find_one({"patient_id": patient_id}, {"_id": 0})
    return jsonify(record or {})

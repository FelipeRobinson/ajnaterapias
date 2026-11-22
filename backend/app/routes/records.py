"""Prontuário (ficha fixa) e protocolo de atendimento (a cada consulta).

SOMENTE o administrador acessa. O cliente nunca vê estas informações:
na área dele aparecem apenas data, horário e situação das próprias consultas.

Para acrescentar/alterar campos, edite RECORD_FORM ou PROTOCOL_FORM abaixo:
o painel monta os formulários automaticamente a partir daqui.
"""
import json
from datetime import datetime

from flask import Blueprint, jsonify, request, session

from ..database import get_db
from .acupoints import known_codes
from ..security import csrf_required, login_required, roles_required

records_bp = Blueprint("records", __name__)

# Tipos: text, long (texto grande), date, select, multi (várias opções), scale (0 a 10), check (sim/não),
#        points (pontos de acupuntura escolhidos pelo código ou no mapa)
RECORD_FORM = [
    {"title": "Identificação", "icon": "🪪", "fields": [
        {"key": "birth_date", "label": "Data de nascimento", "type": "date"},
        {"key": "gender", "label": "Sexo", "type": "select",
         "options": ["Feminino", "Masculino", "Outro", "Prefere não informar"]},
        {"key": "marital_status", "label": "Estado civil", "type": "select",
         "options": ["Solteiro(a)", "Casado(a)", "União estável", "Divorciado(a)", "Viúvo(a)"]},
        {"key": "profession", "label": "Profissão", "type": "text"},
        {"key": "address", "label": "Endereço", "type": "text"},
        {"key": "emergency_contact", "label": "Contato de emergência", "type": "text"},
        {"key": "referral", "label": "Como conheceu a Ajna", "type": "text"},
    ]},
    {"title": "Queixa principal", "icon": "🎯", "fields": [
        {"key": "main_complaint", "label": "Queixa principal", "type": "long"},
        {"key": "complaint_since", "label": "Desde quando", "type": "text"},
        {"key": "pain_scale", "label": "Intensidade da queixa (0 a 10)", "type": "scale"},
        {"key": "goals", "label": "Objetivos com o tratamento", "type": "long"},
    ]},
    {"title": "Histórico de saúde", "icon": "🩺", "fields": [
        {"key": "conditions", "label": "Condições", "type": "multi", "options": [
            "Hipertensão", "Diabetes", "Problemas cardíacos", "Marcapasso", "Epilepsia", "Gestante",
            "Usa anticoagulante", "Câncer (atual ou prévio)", "Ansiedade", "Depressão", "Insônia",
            "Enxaqueca", "Problemas de coagulação", "Medo de agulhas"]},
        {"key": "medications", "label": "Medicamentos em uso", "type": "long"},
        {"key": "allergies", "label": "Alergias", "type": "text"},
        {"key": "surgeries", "label": "Cirurgias / internações", "type": "long"},
        {"key": "other_treatments", "label": "Outros tratamentos em andamento", "type": "long"},
    ]},
    {"title": "Hábitos de vida", "icon": "🌿", "fields": [
        {"key": "sleep", "label": "Sono", "type": "select", "options": ["Bom", "Regular", "Ruim"]},
        {"key": "sleep_notes", "label": "Observações sobre o sono", "type": "text"},
        {"key": "diet", "label": "Alimentação", "type": "long"},
        {"key": "water", "label": "Ingestão de água", "type": "text"},
        {"key": "physical_activity", "label": "Atividade física", "type": "text"},
        {"key": "alcohol_tobacco", "label": "Álcool / tabaco", "type": "text"},
        {"key": "stress_level", "label": "Nível de estresse (0 a 10)", "type": "scale"},
        {"key": "bowel_urinary", "label": "Funcionamento intestinal / urinário", "type": "text"},
    ]},
    {"title": "Avaliação energética (MTC)", "icon": "☯️", "fields": [
        {"key": "tongue", "label": "Língua", "type": "text"},
        {"key": "pulse", "label": "Pulso", "type": "text"},
        {"key": "emotional", "label": "Aspectos emocionais", "type": "long"},
        {"key": "energetic_diagnosis", "label": "Diagnóstico energético", "type": "long"},
        {"key": "treatment_plan", "label": "Plano de tratamento", "type": "long"},
    ]},
    {"title": "Consentimento e observações", "icon": "✍️", "fields": [
        {"key": "consent", "label": "Termo de consentimento assinado", "type": "check"},
        {"key": "consent_date", "label": "Data da assinatura", "type": "date"},
        {"key": "notes", "label": "Observações gerais", "type": "long"},
    ]},
]

PROTOCOL_FORM = [
    {"title": "Como o paciente chegou", "icon": "🗣️", "fields": [
        {"key": "complaint_today", "label": "Relato do paciente / evolução desde a última sessão", "type": "long"},
        {"key": "pain_before", "label": "Intensidade antes (0 a 10)", "type": "scale"},
    ]},
    {"title": "Atendimento", "icon": "💆", "fields": [
        {"key": "techniques", "label": "Técnicas aplicadas", "type": "multi", "options": [
            "Acupuntura", "Eletroacupuntura", "Auriculoterapia", "Ventosaterapia", "Moxabustão",
            "Reiki", "Shiatsu", "Reflexologia", "Massagem"]},
        {"key": "acupoints", "label": "Pontos de acupuntura aplicados", "type": "points"},
        {"key": "points", "label": "Observações sobre pontos / áreas trabalhadas", "type": "long"},
        {"key": "procedure", "label": "Descrição do atendimento", "type": "long"},
        {"key": "reactions", "label": "Reações durante ou após", "type": "long"},
        {"key": "pain_after", "label": "Intensidade depois (0 a 10)", "type": "scale"},
    ]},
    {"title": "Encaminhamentos", "icon": "🧭", "fields": [
        {"key": "home_guidance", "label": "Orientações para casa", "type": "long"},
        {"key": "next_steps", "label": "Plano para a próxima sessão", "type": "long"},
        {"key": "notes", "label": "Observações", "type": "long"},
    ]},
]

MAX_TEXT = 5000


def _admin(view):
    return login_required(roles_required("admin")(view))


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _clean(form, payload, codes=frozenset()):
    """Mantém só os campos conhecidos, no formato certo (evita lixo e dados gigantes)."""
    data = {}
    for section in form:
        for f in section["fields"]:
            value = payload.get(f["key"])
            if value in (None, "", []):
                continue
            if f["type"] == "points":
                chosen = value if isinstance(value, list) else [value]
                chosen = list(dict.fromkeys(str(v).strip().upper() for v in chosen))  # sem repetidos
                chosen = [c for c in chosen if c in codes]
                if chosen:
                    data[f["key"]] = chosen
            elif f["type"] == "multi":
                allowed = set(f["options"])
                value = [v for v in (value if isinstance(value, list) else [value]) if v in allowed]
                if value:
                    data[f["key"]] = value
            elif f["type"] == "check":
                data[f["key"]] = bool(value)
            elif f["type"] == "scale":
                try:
                    data[f["key"]] = max(0, min(10, int(value)))
                except (TypeError, ValueError):
                    pass
            elif f["type"] == "select":
                if value in f["options"]:
                    data[f["key"]] = value
            else:
                data[f["key"]] = str(value).strip()[:MAX_TEXT]
    return data


def _patient(db, patient_id):
    return db.execute(
        "SELECT id, name, email, phone, active, created_at FROM users WHERE id = ? AND role = 'patient'", (patient_id,)
    ).fetchone()


@records_bp.get("/forms")
@_admin
def forms():
    return jsonify(record=RECORD_FORM, protocol=PROTOCOL_FORM)


@records_bp.get("/patients/<int:patient_id>/file")
@_admin
def patient_file(patient_id):
    """Tudo da ficha do paciente: dados, prontuário e lista de consultas com o protocolo de cada uma."""
    db = get_db()
    patient = _patient(db, patient_id)
    if not patient:
        return jsonify(error="Paciente não encontrado."), 404
    record = db.execute(
        "SELECT data, created_at, updated_at FROM medical_records WHERE patient_user_id = ?", (patient_id,)
    ).fetchone()
    sessions = db.execute(
        """SELECT a.id, a.date, a.start, a."end", a.status, p.data AS protocol, p.updated_at AS protocol_updated_at
           FROM appointments a LEFT JOIN session_protocols p ON p.appointment_id = a.id
           WHERE a.patient_user_id = ? ORDER BY a.date DESC, a.start DESC""",
        (patient_id,),
    ).fetchall()
    return jsonify(
        patient=dict(patient),
        record=None if not record else {**dict(record), "data": json.loads(record["data"])},
        sessions=[{**dict(s), "protocol": json.loads(s["protocol"]) if s["protocol"] else None} for s in sessions],
    )


@records_bp.put("/patients/<int:patient_id>/record")
@_admin
@csrf_required
def save_record(patient_id):
    db = get_db()
    if not _patient(db, patient_id):
        return jsonify(error="Paciente não encontrado."), 404
    data = json.dumps(_clean(RECORD_FORM, request.get_json(silent=True) or {}), ensure_ascii=False)
    now = _now()
    if db.execute("SELECT 1 FROM medical_records WHERE patient_user_id = ?", (patient_id,)).fetchone():
        db.execute("UPDATE medical_records SET data = ?, updated_at = ?, updated_by = ? WHERE patient_user_id = ?",
                   (data, now, session["user_id"], patient_id))
    else:
        db.execute("""INSERT INTO medical_records (patient_user_id, data, created_at, updated_at, updated_by)
                      VALUES (?, ?, ?, ?, ?)""", (patient_id, data, now, now, session["user_id"]))
    db.commit()
    return jsonify(ok=True, updated_at=now)


@records_bp.put("/appointments/<int:appointment_id>/protocol")
@_admin
@csrf_required
def save_protocol(appointment_id):
    db = get_db()
    appt = db.execute("SELECT id, patient_user_id, status FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    if not appt:
        return jsonify(error="Consulta não encontrada."), 404
    if appt["status"] in ("cancelled", "requested"):
        return jsonify(error="Só é possível preencher o protocolo de consultas confirmadas ou realizadas."), 400
    codes = known_codes(db)
    data = json.dumps(_clean(PROTOCOL_FORM, request.get_json(silent=True) or {}, codes), ensure_ascii=False)
    now = _now()
    if db.execute("SELECT 1 FROM session_protocols WHERE appointment_id = ?", (appointment_id,)).fetchone():
        db.execute("UPDATE session_protocols SET data = ?, updated_at = ?, updated_by = ? WHERE appointment_id = ?",
                   (data, now, session["user_id"], appointment_id))
    else:
        db.execute("""INSERT INTO session_protocols
                      (appointment_id, patient_user_id, data, created_at, updated_at, updated_by)
                      VALUES (?, ?, ?, ?, ?, ?)""",
                   (appointment_id, appt["patient_user_id"], data, now, now, session["user_id"]))
    # Preencher o protocolo de uma consulta confirmada marca a consulta como realizada.
    if appt["status"] == "scheduled":
        db.execute("UPDATE appointments SET status = 'done' WHERE id = ?", (appointment_id,))
    db.commit()
    return jsonify(ok=True, updated_at=now)

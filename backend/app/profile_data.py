"""Dados pessoais do cliente (endereço, documentos, contato de emergência…).

Ficam em users.profile (JSON). O próprio cliente edita em "Meus dados" e a clínica vê/edita na ficha.
"""
import json
import re

UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
       "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]

PROFILE_FIELDS = [
    {"title": "Documentos e dados pessoais", "icon": "🪪", "fields": [
        {"key": "birth_date", "label": "Data de nascimento", "type": "date"},
        {"key": "cpf", "label": "CPF", "type": "cpf", "placeholder": "000.000.000-00"},
        {"key": "rg", "label": "RG", "type": "text"},
        {"key": "gender", "label": "Sexo", "type": "select",
         "options": ["Feminino", "Masculino", "Outro", "Prefere não informar"]},
        {"key": "marital_status", "label": "Estado civil", "type": "select",
         "options": ["Solteiro(a)", "Casado(a)", "União estável", "Divorciado(a)", "Viúvo(a)"]},
        {"key": "profession", "label": "Profissão", "type": "text"},
        {"key": "whatsapp", "label": "WhatsApp (se for outro número)", "type": "text", "placeholder": "(19) 90000-0000"},
    ]},
    {"title": "Endereço", "icon": "🏠", "fields": [
        {"key": "cep", "label": "CEP", "type": "cep", "placeholder": "00000-000"},
        {"key": "street", "label": "Rua / avenida", "type": "text"},
        {"key": "number", "label": "Número", "type": "text"},
        {"key": "complement", "label": "Complemento", "type": "text"},
        {"key": "neighborhood", "label": "Bairro", "type": "text"},
        {"key": "city", "label": "Cidade", "type": "text"},
        {"key": "state", "label": "Estado (UF)", "type": "select", "options": UFS},
    ]},
    {"title": "Contato de emergência", "icon": "🆘", "fields": [
        {"key": "emergency_name", "label": "Nome", "type": "text"},
        {"key": "emergency_relation", "label": "Parentesco", "type": "text"},
        {"key": "emergency_phone", "label": "Telefone", "type": "text"},
    ]},
]
_FIELDS = {f["key"]: f for sec in PROFILE_FIELDS for f in sec["fields"]}


def load_profile(raw):
    try:
        data = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}


def _cpf_ok(digits):
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(d) * w for d, w in zip(digits[:size], range(size + 1, 1, -1)))
        if (total * 10 % 11) % 10 != int(digits[size]):
            return False
    return True


def clean_profile(payload):
    """Valida e normaliza. Retorna (dados, erro). Campos desconhecidos são ignorados."""
    if not isinstance(payload, dict):
        return None, "Dados inválidos."
    out = {}
    for key, f in _FIELDS.items():
        v = str(payload.get(key) or "").strip()[:160]
        if not v:
            continue
        if f["type"] == "date" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            return None, f"{f['label']}: data inválida."
        if f["type"] == "select" and v not in f["options"]:
            return None, f"{f['label']}: opção inválida."
        if f["type"] == "cpf":
            digits = re.sub(r"\D", "", v)
            if not _cpf_ok(digits):
                return None, "CPF inválido. Confira os números."
            v = f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
        if f["type"] == "cep":
            digits = re.sub(r"\D", "", v)
            if len(digits) != 8:
                return None, "CEP inválido. Use 8 números."
            v = f"{digits[:5]}-{digits[5:]}"
        out[key] = v
    return out, None

"""Regras do calendário da clínica: horários de atendimento, dias sem atendimento e eventos.

Dia da semana: 0 = segunda ... 6 = domingo.
- Domingo é sempre "Sem atendimento" (fixo).
- Os outros dias (segunda a sábado) a administração liga/desliga no painel (Agenda › ⚙️ Dias de atendimento).
- Eventos (ex.: Reiki voluntário) ficam na tabela events e a administração cria/edita/exclui no painel.
"""
import calendar
import json
from datetime import date, timedelta

from flask import current_app

from .database import get_db, get_setting, set_setting

SUNDAY = 6
# Padrão de fábrica: atendimento de terça a quinta (a administração pode mudar).
DEFAULT_CLOSED = (0, 4, 5)
# Horários que o cliente pode agendar: 9h às 11h e 13h às 19h.
OPENING_WINDOWS = (("09:00", "11:00"), ("13:00", "19:00"))
WEEKDAY_NAMES = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
RECURRENCES = {
    "once": "Só uma vez",
    "weekly": "Toda semana (mesmo dia da semana)",
    "monthly": "Todo mês (mesmo dia do mês)",
    "last_weekday": "Todo mês, no último dia da semana igual (ex.: último sábado)",
    "yearly": "Todo ano (mesma data)",
}


def closed_weekdays():
    """Dias sem atendimento. Os testes podem trocar por app.config["CLOSED_WEEKDAYS"]."""
    if "CLOSED_WEEKDAYS" in current_app.config:
        return tuple(current_app.config["CLOSED_WEEKDAYS"])
    raw = get_setting(get_db(), "closed_weekdays")
    days = json.loads(raw) if raw else DEFAULT_CLOSED
    return tuple(sorted({int(d) for d in days if 0 <= int(d) <= 5} | {SUNDAY}))


def save_closed_weekdays(db, days):
    days = sorted({int(d) for d in days if str(d).isdigit() and 0 <= int(d) <= 5})
    set_setting(db, "closed_weekdays", json.dumps(days))
    return tuple(days) + (SUNDAY,)


def is_closed(day):
    return day.weekday() in closed_weekdays()


def last_saturday(year, month):
    return last_weekday(year, month, 5)


def last_weekday(year, month, weekday):
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _occurrences(ev, start, end):
    """Datas em que um evento acontece entre start e end (inclusive)."""
    first = date.fromisoformat(ev["date"])
    stop = min(end, date.fromisoformat(ev["until"])) if ev.get("until") else end
    rec = ev.get("recurrence") or "once"
    if rec == "once":
        return [first] if start <= first <= stop else []
    out = []
    if rec == "weekly":
        d = first if first >= start else first + timedelta(days=((start - first).days + 6) // 7 * 7)
        while d <= stop:
            out.append(d)
            d += timedelta(days=7)
        return out
    y, m = start.year, start.month
    while (y, m) <= (stop.year, stop.month):
        if rec == "monthly":
            d = date(y, m, min(first.day, calendar.monthrange(y, m)[1]))
        elif rec == "last_weekday":
            d = last_weekday(y, m, first.weekday())
        elif rec == "yearly":
            d = date(y, m, min(first.day, calendar.monthrange(y, m)[1])) if m == first.month else None
        else:
            d = None
        if d and first <= d and start <= d <= stop:
            out.append(d)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def events_between(start, end):
    """Ocorrências dos eventos da clínica entre duas datas (inclusive), em ordem."""
    out = []
    for row in get_db().execute("SELECT * FROM events").fetchall():
        ev = dict(row)
        for d in _occurrences(ev, start, end):
            out.append({"date": d.isoformat(), "id": ev["id"], "key": f"ev{ev['id']}", "title": ev["title"],
                        "icon": ev["icon"] or "📅", "description": ev["description"] or "",
                        "start_time": ev["start_time"], "end_time": ev["end_time"]})
    return sorted(out, key=lambda e: (e["date"], e["start_time"] or ""))

"""Regras fixas do calendário da clínica: dias sem atendimento e eventos que se repetem.

Dia da semana: 0 = segunda ... 6 = domingo.
"""
import calendar
from datetime import date, timedelta

from flask import current_app

# Atendimento só de terça a quinta. Segunda, sexta, sábado e domingo ficam fechados.
# (O sábado do Reiki Para Todos aparece na agenda como evento, mas não abre horários.)
CLOSED_WEEKDAYS = (0, 4, 5, 6)


def closed_weekdays():
    """Pode ser trocado pela configuração do app (os testes usam isso)."""
    return tuple(current_app.config.get("CLOSED_WEEKDAYS", CLOSED_WEEKDAYS))


def is_closed(day):
    return day.weekday() in closed_weekdays()


def last_saturday(year, month):
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - 5) % 7)


# Eventos recorrentes (aparecem na agenda da clínica e na área de todos os clientes).
RECURRING = [
    {"key": "reiki", "title": "Reiki Para Todos", "icon": "🌟", "rule": last_saturday,
     "description": "Encontro mensal de Reiki aberto a todos, no último sábado do mês."},
]


def events_between(start, end):
    """Eventos recorrentes entre duas datas (inclusive), em ordem."""
    out = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        for ev in RECURRING:
            d = ev["rule"](y, m)
            if start <= d <= end:
                out.append({"date": d.isoformat(), "key": ev["key"], "title": ev["title"],
                            "icon": ev["icon"], "description": ev["description"]})
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return sorted(out, key=lambda e: e["date"])

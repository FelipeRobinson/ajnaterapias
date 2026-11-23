"""Financeiro (só a administração): terapias e preços, pagamentos das sessões, pacotes, despesas e relatórios.

Todos os valores são em centavos (inteiros) para não ter erro de arredondamento.
"""
import re
from datetime import date

from flask import Blueprint, jsonify, request

from ..database import IntegrityError, get_db
from ..security import csrf_required, login_required, roles_required

finance_bp = Blueprint("finance", __name__)

METHODS = {"pix": "Pix", "dinheiro": "Dinheiro", "credito": "Cartão de crédito", "debito": "Cartão de débito",
           "transferencia": "Transferência", "outro": "Outro"}
EXPENSE_CATEGORIES = ["Aluguel", "Materiais (agulhas, sementes, óleos…)", "Contas (luz, água, internet)",
                      "Marketing", "Cursos e formação", "Impostos e taxas", "Equipamentos", "Outros"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _admin(view):
    return login_required(roles_required("admin")(view))


def _date(value):
    try:
        return date.fromisoformat(value).isoformat() if DATE_RE.match(str(value or "")) else None
    except ValueError:
        return None


def _cents(value):
    """Aceita inteiro em centavos. Retorna None se inválido ou negativo."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    return v if 0 <= v <= 100_000_000 else None


def _period():
    start, end = _date(request.args.get("from")), _date(request.args.get("to"))
    return (start, end) if start and end and start <= end else (None, None)


def package_usage(db, package_id):
    return db.execute(
        "SELECT COUNT(*) AS n FROM appointments WHERE package_id = ? AND status != 'cancelled'", (package_id,)
    ).fetchone()["n"]


def apply_package(db, appointment_id):
    """Consulta realizada: se o cliente tem pacote com saldo (da mesma terapia, ou pacote sem terapia),
    a sessão passa a ser descontada dele. Chamado pela agenda quando a consulta vira 'realizada'."""
    a = db.execute("SELECT id, patient_user_id, service_id, package_id FROM appointments WHERE id = ?",
                   (appointment_id,)).fetchone()
    if not a or a["package_id"]:
        return None
    if db.execute("SELECT 1 FROM payments WHERE appointment_id = ?", (appointment_id,)).fetchone():
        return None  # já foi paga avulsa
    rows = db.execute(
        "SELECT id, service_id, sessions_total FROM packages WHERE patient_user_id = ? ORDER BY created_at, id",
        (a["patient_user_id"],)).fetchall()
    for p in rows:
        if p["service_id"] and a["service_id"] and p["service_id"] != a["service_id"]:
            continue
        if package_usage(db, p["id"]) < p["sessions_total"]:
            db.execute("UPDATE appointments SET package_id = ? WHERE id = ?", (p["id"], appointment_id))
            return p["id"]
    return None


# ------------------------------------------------------------------ opções
@finance_bp.get("/finance/options")
@_admin
def options():
    return jsonify(methods=METHODS, expense_categories=EXPENSE_CATEGORIES)


# ------------------------------------------------------------------ terapias (serviços) e preços
@finance_bp.get("/services")
@_admin
def services():
    rows = get_db().execute(
        "SELECT id, name, price_cents, active, social FROM services ORDER BY active DESC, social DESC, name").fetchall()
    return jsonify(items=[dict(r) for r in rows])


def _read_service(payload, partial=False):
    data = {}
    if not partial or "name" in payload:
        name = str(payload.get("name") or "").strip()[:80]
        if not name:
            return None, "Informe o nome da terapia."
        data["name"] = name
    if not partial or "price_cents" in payload:
        price = _cents(payload.get("price_cents", 0))
        if price is None:
            return None, "Preço inválido."
        data["price_cents"] = price
    if "active" in payload:
        data["active"] = 1 if payload["active"] else 0
    if "social" in payload:
        data["social"] = 1 if payload["social"] else 0
    return data, None


@finance_bp.post("/services")
@_admin
@csrf_required
def create_service():
    data, error = _read_service(request.get_json(silent=True) or {})
    if error:
        return jsonify(error=error), 400
    db = get_db()
    try:
        db.execute("INSERT INTO services (name, price_cents, social) VALUES (?, ?, ?)",
                   (data["name"], data["price_cents"], data.get("social", 0)))
        db.commit()
    except IntegrityError:
        db.rollback()
        return jsonify(error="Já existe uma terapia com esse nome."), 409
    return jsonify(ok=True), 201


@finance_bp.patch("/services/<int:service_id>")
@_admin
@csrf_required
def update_service(service_id):
    data, error = _read_service(request.get_json(silent=True) or {}, partial=True)
    if error:
        return jsonify(error=error), 400
    if not data:
        return jsonify(error="Nada para alterar."), 400
    db = get_db()
    try:
        cur = db.execute(f"UPDATE services SET {', '.join(f'{k} = ?' for k in data)} WHERE id = ?",
                         (*data.values(), service_id))
        db.commit()
    except IntegrityError:
        db.rollback()
        return jsonify(error="Já existe uma terapia com esse nome."), 409
    if not cur.rowcount:
        return jsonify(error="Terapia não encontrada."), 404
    return jsonify(ok=True)


# ------------------------------------------------------------------ sessões (o que cobrar e o que já foi pago)
SESSION_SQL = """
    SELECT a.id, a.date, a.start, a."end", a.status, a.patient_user_id, u.name AS patient_name,
           a.service_id, s.name AS service_name, a.price_cents, a.package_id,
           COALESCE(s.social, 0) AS social, u.social AS patient_social,
           COALESCE((SELECT SUM(p.amount_cents) FROM payments p WHERE p.appointment_id = a.id), 0) AS paid_cents
    FROM appointments a
    JOIN users u ON u.id = a.patient_user_id
    LEFT JOIN services s ON s.id = a.service_id
"""


def session_row(r):
    d = dict(r)
    price = d["price_cents"] or 0
    if d["package_id"]:
        d["finance_status"] = "package"
    elif d["status"] == "cancelled":
        d["finance_status"] = "cancelled"
    elif not price:
        d["finance_status"] = "no_price"
    elif d["paid_cents"] >= price:
        d["finance_status"] = "paid"
    elif d["paid_cents"]:
        d["finance_status"] = "partial"
    elif d["status"] != "done":
        d["finance_status"] = "upcoming"  # ainda não realizada (dá para receber adiantado)
    else:
        d["finance_status"] = "pending"
    d["due_cents"] = 0 if d["finance_status"] in ("package", "cancelled", "paid", "no_price") else price - d["paid_cents"]
    return d


@finance_bp.get("/finance/sessions")
@_admin
def sessions():
    start, end = _period()
    if not start:
        return jsonify(error="Período inválido."), 400
    rows = get_db().execute(SESSION_SQL + " WHERE a.date BETWEEN ? AND ? ORDER BY a.date, a.start", (start, end)).fetchall()
    return jsonify(items=[session_row(r) for r in rows])


@finance_bp.get("/finance/receivable")
@_admin
def receivable():
    """Tudo que está em aberto: consultas realizadas (ou já passadas) sem pagamento completo."""
    rows = get_db().execute(
        SESSION_SQL + " WHERE a.status = 'done' AND a.package_id IS NULL ORDER BY a.date, a.start").fetchall()
    items = [r for r in map(session_row, rows) if r["due_cents"] > 0]
    return jsonify(items=items, total_cents=sum(r["due_cents"] for r in items))


# ------------------------------------------------------------------ pagamentos recebidos
@finance_bp.get("/finance/payments")
@_admin
def payments():
    start, end = _period()
    if not start:
        return jsonify(error="Período inválido."), 400
    rows = get_db().execute(
        """SELECT p.id, p.date, p.amount_cents, p.method, p.description, p.appointment_id, p.package_id,
                  p.patient_user_id, u.name AS patient_name
           FROM payments p LEFT JOIN users u ON u.id = p.patient_user_id
           WHERE p.date BETWEEN ? AND ? ORDER BY p.date DESC, p.id DESC""", (start, end)).fetchall()
    return jsonify(items=[dict(r) for r in rows])


@finance_bp.post("/finance/payments")
@_admin
@csrf_required
def create_payment():
    payload = request.get_json(silent=True) or {}
    db = get_db()
    amount = _cents(payload.get("amount_cents"))
    if not amount:
        return jsonify(error="Informe o valor recebido."), 400
    method = payload.get("method")
    if method not in METHODS:
        return jsonify(error="Escolha a forma de pagamento."), 400
    day = _date(payload.get("date")) or date.today().isoformat()
    appointment_id = payload.get("appointment_id")
    patient_id = payload.get("patient_user_id")
    package_id = payload.get("package_id")
    if package_id:
        k = db.execute("SELECT id, patient_user_id FROM packages WHERE id = ?", (package_id,)).fetchone()
        if not k:
            return jsonify(error="Pacote não encontrado."), 404
        patient_id = k["patient_user_id"]
    if appointment_id:
        a = db.execute("SELECT id, patient_user_id FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
        if not a:
            return jsonify(error="Consulta não encontrada."), 404
        patient_id = a["patient_user_id"]
    if patient_id and not db.execute("SELECT 1 FROM users WHERE id = ? AND role = 'patient'", (patient_id,)).fetchone():
        return jsonify(error="Cliente não encontrado."), 404
    db.execute(
        """INSERT INTO payments (patient_user_id, appointment_id, package_id, amount_cents, method, date, description)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (patient_id or None, appointment_id or None, package_id or None, amount, method, day,
         str(payload.get("description") or "").strip()[:200] or None))
    db.commit()
    return jsonify(ok=True), 201


@finance_bp.delete("/finance/payments/<int:payment_id>")
@_admin
@csrf_required
def delete_payment(payment_id):
    db = get_db()
    db.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
    db.commit()
    return "", 204


# ------------------------------------------------------------------ pacotes de sessões
@finance_bp.get("/finance/packages")
@_admin
def packages():
    db = get_db()
    rows = db.execute(
        """SELECT k.id, k.patient_user_id, u.name AS patient_name, k.service_id, s.name AS service_name,
                  k.sessions_total, k.price_cents, k.notes, k.created_at,
                  COALESCE((SELECT SUM(p.amount_cents) FROM payments p WHERE p.package_id = k.id), 0) AS paid_cents
           FROM packages k JOIN users u ON u.id = k.patient_user_id LEFT JOIN services s ON s.id = k.service_id
           ORDER BY k.created_at DESC, k.id DESC""").fetchall()
    items = []
    for r in rows:
        d = dict(r)
        d["sessions_used"] = package_usage(db, d["id"])
        items.append(d)
    return jsonify(items=items)


@finance_bp.post("/finance/packages")
@_admin
@csrf_required
def create_package():
    """Vende um pacote. Se vier 'paid_method', já registra o pagamento do valor do pacote."""
    payload = request.get_json(silent=True) or {}
    db = get_db()
    try:
        patient_id = int(payload.get("patient_user_id"))
        total = int(payload.get("sessions_total"))
    except (TypeError, ValueError):
        return jsonify(error="Escolha o cliente e a quantidade de sessões."), 400
    if not 1 <= total <= 200:
        return jsonify(error="Quantidade de sessões inválida."), 400
    if not db.execute("SELECT 1 FROM users WHERE id = ? AND role = 'patient'", (patient_id,)).fetchone():
        return jsonify(error="Cliente não encontrado."), 404
    service_id = payload.get("service_id") or None
    if service_id and not db.execute("SELECT 1 FROM services WHERE id = ?", (service_id,)).fetchone():
        return jsonify(error="Terapia não encontrada."), 404
    price = _cents(payload.get("price_cents", 0))
    if price is None:
        return jsonify(error="Preço inválido."), 400
    paid_method = payload.get("paid_method")
    if paid_method and paid_method not in METHODS:
        return jsonify(error="Forma de pagamento inválida."), 400
    cur = db.execute(
        "INSERT INTO packages (patient_user_id, service_id, sessions_total, price_cents, notes) VALUES (?, ?, ?, ?, ?)",
        (patient_id, service_id, total, price, str(payload.get("notes") or "").strip()[:200] or None))
    package_id = cur.lastrowid if getattr(cur, "lastrowid", None) else db.execute(
        "SELECT MAX(id) AS id FROM packages").fetchone()["id"]
    if paid_method and price:
        db.execute(
            """INSERT INTO payments (patient_user_id, package_id, amount_cents, method, date, description)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (patient_id, package_id, price, paid_method, _date(payload.get("date")) or date.today().isoformat(),
             f"Pacote de {total} sessões"))
    db.commit()
    return jsonify(ok=True, id=package_id), 201


@finance_bp.delete("/finance/packages/<int:package_id>")
@_admin
@csrf_required
def delete_package(package_id):
    db = get_db()
    if package_usage(db, package_id):
        return jsonify(error="Esse pacote já tem sessões usadas e não pode ser excluído."), 409
    db.execute("DELETE FROM payments WHERE package_id = ?", (package_id,))
    db.execute("DELETE FROM packages WHERE id = ?", (package_id,))
    db.commit()
    return "", 204


# ------------------------------------------------------------------ despesas
@finance_bp.get("/finance/expenses")
@_admin
def expenses():
    start, end = _period()
    if not start:
        return jsonify(error="Período inválido."), 400
    rows = get_db().execute(
        "SELECT id, date, category, description, amount_cents, method FROM expenses WHERE date BETWEEN ? AND ? "
        "ORDER BY date DESC, id DESC", (start, end)).fetchall()
    return jsonify(items=[dict(r) for r in rows])


@finance_bp.post("/finance/expenses")
@_admin
@csrf_required
def create_expense():
    payload = request.get_json(silent=True) or {}
    amount = _cents(payload.get("amount_cents"))
    day = _date(payload.get("date"))
    category = str(payload.get("category") or "").strip()[:80]
    if not amount:
        return jsonify(error="Informe o valor da despesa."), 400
    if not day:
        return jsonify(error="Data inválida."), 400
    if not category:
        return jsonify(error="Escolha a categoria."), 400
    method = payload.get("method") or None
    if method and method not in METHODS:
        return jsonify(error="Forma de pagamento inválida."), 400
    db = get_db()
    db.execute("INSERT INTO expenses (date, category, description, amount_cents, method) VALUES (?, ?, ?, ?, ?)",
               (day, category, str(payload.get("description") or "").strip()[:200] or None, amount, method))
    db.commit()
    return jsonify(ok=True), 201


@finance_bp.delete("/finance/expenses/<int:expense_id>")
@_admin
@csrf_required
def delete_expense(expense_id):
    db = get_db()
    db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    db.commit()
    return "", 204


# ------------------------------------------------------------------ relatório anual
@finance_bp.get("/finance/summary")
@_admin
def summary():
    try:
        year = int(request.args.get("year") or date.today().year)
    except ValueError:
        return jsonify(error="Ano inválido."), 400
    db = get_db()
    start, end = f"{year}-01-01", f"{year}-12-31"
    months = [{"month": m, "income_cents": 0, "expense_cents": 0} for m in range(1, 13)]
    for r in db.execute("SELECT date, amount_cents FROM payments WHERE date BETWEEN ? AND ?", (start, end)).fetchall():
        months[int(r["date"][5:7]) - 1]["income_cents"] += r["amount_cents"]
    for r in db.execute("SELECT date, amount_cents FROM expenses WHERE date BETWEEN ? AND ?", (start, end)).fetchall():
        months[int(r["date"][5:7]) - 1]["expense_cents"] += r["amount_cents"]
    for m in months:
        m["balance_cents"] = m["income_cents"] - m["expense_cents"]
    by_category = {}
    for r in db.execute("SELECT category, amount_cents FROM expenses WHERE date BETWEEN ? AND ?", (start, end)).fetchall():
        by_category[r["category"]] = by_category.get(r["category"], 0) + r["amount_cents"]
    by_method = {}
    for r in db.execute("SELECT method, amount_cents FROM payments WHERE date BETWEEN ? AND ?", (start, end)).fetchall():
        by_method[r["method"]] = by_method.get(r["method"], 0) + r["amount_cents"]
    income = sum(m["income_cents"] for m in months)
    expense = sum(m["expense_cents"] for m in months)
    pending = [r for r in map(session_row, db.execute(
        SESSION_SQL + " WHERE a.status = 'done' AND a.package_id IS NULL").fetchall()) if r["due_cents"] > 0]
    # Ambulatório Social: sessões realizadas e quanto entrou por elas no ano
    social = db.execute(
        """SELECT COUNT(*) AS n, COUNT(DISTINCT a.patient_user_id) AS people FROM appointments a
           JOIN services s ON s.id = a.service_id
           WHERE s.social = 1 AND a.status = 'done' AND a.date BETWEEN ? AND ?""", (start, end)).fetchone()
    social_income = db.execute(
        """SELECT COALESCE(SUM(p.amount_cents), 0) AS v FROM payments p
           JOIN appointments a ON a.id = p.appointment_id JOIN services s ON s.id = a.service_id
           WHERE s.social = 1 AND p.date BETWEEN ? AND ?""", (start, end)).fetchone()["v"]
    return jsonify(social={"sessions": social["n"], "patients": social["people"], "income_cents": social_income},
                   year=year, months=months, income_cents=income, expense_cents=expense, balance_cents=income - expense,
                   receivable_cents=sum(r["due_cents"] for r in pending), receivable_count=len(pending),
                   by_category=by_category, by_method=by_method)

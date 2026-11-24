"""Camada do banco de dados: SQLite (local) ou PostgreSQL (web).

A escolha é automática pelo .env:
  - Com DATABASE_URL=postgresql://...  → usa PostgreSQL (ex.: Neon ou Supabase, plano grátis)
  - Sem DATABASE_URL                   → usa SQLite, um arquivo em backend/instance/ajna.db

As rotas escrevem SQL com o marcador "?" e funcionam igual nos dois bancos.
"""
import os
import sqlite3

from flask import current_app, g

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    phone         TEXT,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'patient')),
    active        INTEGER NOT NULL DEFAULT 1,
    avatar        TEXT,
    social        INTEGER NOT NULL DEFAULT 0,
    profile       TEXT,
    onboarded_at  TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS appointments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_user_id INTEGER NOT NULL REFERENCES users(id),
    date            TEXT NOT NULL,
    start           TEXT NOT NULL,
    "end"           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'scheduled',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(date);

-- Horários marcados como indisponíveis pela administração (folga, compromisso, feriado...).
CREATE TABLE IF NOT EXISTS schedule_blocks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    date       TEXT NOT NULL,
    start      TEXT NOT NULL,
    "end"      TEXT NOT NULL,
    reason     TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_schedule_blocks_date ON schedule_blocks(date);

-- Financeiro (só a clínica vê). Valores em centavos.
CREATE TABLE IF NOT EXISTS services (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    price_cents INTEGER NOT NULL DEFAULT 0,
    active      INTEGER NOT NULL DEFAULT 1,
    social      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS packages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_user_id INTEGER NOT NULL REFERENCES users(id),
    service_id      INTEGER REFERENCES services(id),
    sessions_total  INTEGER NOT NULL,
    price_cents     INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS payments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_user_id INTEGER REFERENCES users(id),
    appointment_id  INTEGER REFERENCES appointments(id),
    package_id      INTEGER REFERENCES packages(id),
    amount_cents    INTEGER NOT NULL,
    method          TEXT NOT NULL,
    date            TEXT NOT NULL,
    description     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(date);

CREATE TABLE IF NOT EXISTS expenses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL,
    category     TEXT NOT NULL,
    description  TEXT,
    amount_cents INTEGER NOT NULL,
    method       TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);

-- Alterações de login pendentes, confirmadas por link enviado ao e-mail.
CREATE TABLE IF NOT EXISTS account_changes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    token_hash  TEXT NOT NULL UNIQUE,
    payload     TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Pedidos de "esqueci a senha" (link enviado por e-mail).
CREATE TABLE IF NOT EXISTS password_resets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  TEXT NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
-- Prontuário (ficha fixa do paciente, uma por paciente). Campos em JSON (ver routes/records.py).
CREATE TABLE IF NOT EXISTS medical_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    data            TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    updated_by      INTEGER REFERENCES users(id)
);

-- Protocolo de atendimento (preenchido a cada sessão).
CREATE TABLE IF NOT EXISTS session_protocols (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id  INTEGER NOT NULL UNIQUE REFERENCES appointments(id),
    patient_user_id INTEGER NOT NULL REFERENCES users(id),
    data            TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    updated_by      INTEGER REFERENCES users(id)
);
-- Pontos de acupuntura (361 da OMS + pontos extras criados pela clínica). Editáveis no painel.
CREATE TABLE IF NOT EXISTS acupoints (
    code        TEXT PRIMARY KEY,
    meridian    TEXT NOT NULL,
    number      INTEGER,
    intl_code   TEXT,
    pinyin      TEXT NOT NULL,
    name_pt     TEXT,
    view        TEXT NOT NULL,
    x           REAL NOT NULL,
    y           REAL NOT NULL,
    location    TEXT,
    indications TEXT,
    notes       TEXT,
    custom      INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT,
    pos3d       TEXT,
    details     TEXT
);
-- Parte teórica: diagnósticos da MTC (syndrome), sintomas (symptom) e combinações de pontos (combination).
CREATE TABLE IF NOT EXISTS theory_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,
    name        TEXT NOT NULL,
    group_name  TEXT,
    data        TEXT NOT NULL,
    points      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
-- Eventos da clínica para todos (ex.: Reiki voluntário). recurrence: once, weekly, monthly, last_weekday, yearly.
CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    icon         TEXT,
    description  TEXT,
    date         TEXT NOT NULL,
    recurrence   TEXT NOT NULL DEFAULT 'once',
    until        TEXT,
    start_time   TEXT,
    end_time     TEXT,
    created_at   TEXT NOT NULL
);
-- Configurações gerais (ex.: primary_admin_id = administradora principal).
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    phone         TEXT,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'patient')),
    active        INTEGER NOT NULL DEFAULT 1,
    avatar        TEXT,
    social        INTEGER NOT NULL DEFAULT 0,
    profile       TEXT,
    onboarded_at  TEXT,
    created_at    TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS appointments (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_user_id INTEGER NOT NULL REFERENCES users(id),
    date            TEXT NOT NULL,
    start           TEXT NOT NULL,
    "end"           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'scheduled',
    created_at      TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);
CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(date);

-- Horários marcados como indisponíveis pela administração (folga, compromisso, feriado...).
CREATE TABLE IF NOT EXISTS schedule_blocks (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date       TEXT NOT NULL,
    start      TEXT NOT NULL,
    "end"      TEXT NOT NULL,
    reason     TEXT,
    created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);
CREATE INDEX IF NOT EXISTS idx_schedule_blocks_date ON schedule_blocks(date);

-- Financeiro (só a clínica vê). Valores em centavos.
CREATE TABLE IF NOT EXISTS services (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    price_cents INTEGER NOT NULL DEFAULT 0,
    active      INTEGER NOT NULL DEFAULT 1,
    social      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS packages (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_user_id INTEGER NOT NULL REFERENCES users(id),
    service_id      INTEGER REFERENCES services(id),
    sessions_total  INTEGER NOT NULL,
    price_cents     INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS payments (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_user_id INTEGER REFERENCES users(id),
    appointment_id  INTEGER REFERENCES appointments(id),
    package_id      INTEGER REFERENCES packages(id),
    amount_cents    INTEGER NOT NULL,
    method          TEXT NOT NULL,
    date            TEXT NOT NULL,
    description     TEXT,
    created_at      TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(date);

CREATE TABLE IF NOT EXISTS expenses (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date         TEXT NOT NULL,
    category     TEXT NOT NULL,
    description  TEXT,
    amount_cents INTEGER NOT NULL,
    method       TEXT,
    created_at   TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);

CREATE TABLE IF NOT EXISTS account_changes (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    token_hash  TEXT NOT NULL UNIQUE,
    payload     TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);
-- Pedidos de "esqueci a senha" (link enviado por e-mail).
CREATE TABLE IF NOT EXISTS password_resets (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  TEXT NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
-- Prontuário (ficha fixa do paciente, uma por paciente). Campos em JSON (ver routes/records.py).
CREATE TABLE IF NOT EXISTS medical_records (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    data            TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    updated_by      INTEGER REFERENCES users(id)
);

-- Protocolo de atendimento (preenchido a cada sessão).
CREATE TABLE IF NOT EXISTS session_protocols (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    appointment_id  INTEGER NOT NULL UNIQUE REFERENCES appointments(id),
    patient_user_id INTEGER NOT NULL REFERENCES users(id),
    data            TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    updated_by      INTEGER REFERENCES users(id)
);
-- Pontos de acupuntura (361 da OMS + pontos extras criados pela clínica). Editáveis no painel.
CREATE TABLE IF NOT EXISTS acupoints (
    code        TEXT PRIMARY KEY,
    meridian    TEXT NOT NULL,
    number      INTEGER,
    intl_code   TEXT,
    pinyin      TEXT NOT NULL,
    name_pt     TEXT,
    view        TEXT NOT NULL,
    x           REAL NOT NULL,
    y           REAL NOT NULL,
    location    TEXT,
    indications TEXT,
    notes       TEXT,
    custom      INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT,
    pos3d       TEXT,
    details     TEXT
);
-- Parte teórica: diagnósticos da MTC (syndrome), sintomas (symptom) e combinações de pontos (combination).
CREATE TABLE IF NOT EXISTS theory_items (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind        TEXT NOT NULL,
    name        TEXT NOT NULL,
    group_name  TEXT,
    data        TEXT NOT NULL,
    points      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
-- Eventos da clínica para todos (ex.: Reiki voluntário). recurrence: once, weekly, monthly, last_weekday, yearly.
CREATE TABLE IF NOT EXISTS events (
    id           SERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    icon         TEXT,
    description  TEXT,
    date         TEXT NOT NULL,
    recurrence   TEXT NOT NULL DEFAULT 'once',
    until        TEXT,
    start_time   TEXT,
    end_time     TEXT,
    created_at   TEXT NOT NULL
);
-- Configurações gerais (ex.: primary_admin_id = administradora principal).
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _is_postgres(config):
    return bool(config.get("DATABASE_URL"))


def _integrity_errors():
    errors = [sqlite3.IntegrityError]
    try:
        import psycopg
        errors.append(psycopg.IntegrityError)
    except ImportError:
        pass
    return tuple(errors)


# Use em "except IntegrityError:" — vale para os dois bancos (ex.: e-mail repetido).
IntegrityError = _integrity_errors()


class _PostgresDB:
    """Adapta o psycopg para a mesma interface do sqlite3 usada nas rotas."""

    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row
        self.conn = psycopg.connect(url, row_factory=dict_row, connect_timeout=10)

    def execute(self, sql, params=()):
        return self.conn.execute(sql.replace("?", "%s"), params)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def get_db():
    if "db" not in g:
        if _is_postgres(current_app.config):
            g.db = _PostgresDB(current_app.config["DATABASE_URL"])
        else:
            g.db = sqlite3.connect(current_app.config["DATABASE_PATH"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """Cria as tabelas se ainda não existirem (roda ao ligar o servidor)."""
    if _is_postgres(app.config):
        db = _PostgresDB(app.config["DATABASE_URL"])
        try:
            db.conn.execute(SCHEMA_POSTGRES)
            db.conn.execute("ALTER TABLE acupoints ADD COLUMN IF NOT EXISTS pos3d TEXT")
            db.conn.execute("ALTER TABLE acupoints ADD COLUMN IF NOT EXISTS details TEXT")
            db.conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar TEXT")
            for col in ("service_id INTEGER", "price_cents INTEGER", "package_id INTEGER"):
                db.conn.execute(f"ALTER TABLE appointments ADD COLUMN IF NOT EXISTS {col}")
            db.conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS social INTEGER NOT NULL DEFAULT 0")
            db.conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile TEXT")
            db.conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarded_at TEXT")
            db.conn.execute("ALTER TABLE services ADD COLUMN IF NOT EXISTS social INTEGER NOT NULL DEFAULT 0")
            _seed_services(db)
            _migrate_point_codes(db)
            _seed_acupoints(db)
            _seed_events(db)
            _seed_theory(db)
            db.commit()
        finally:
            db.close()
        return
    os.makedirs(os.path.dirname(app.config["DATABASE_PATH"]) or ".", exist_ok=True)
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        conn.executescript(SCHEMA_SQLITE)
        conn.row_factory = sqlite3.Row
        # colunas novas em bancos criados antes delas existirem
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(acupoints)").fetchall()}
        if "pos3d" not in cols:
            conn.execute("ALTER TABLE acupoints ADD COLUMN pos3d TEXT")
        if "details" not in cols:
            conn.execute("ALTER TABLE acupoints ADD COLUMN details TEXT")
        if "avatar" not in {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}:
            conn.execute("ALTER TABLE users ADD COLUMN avatar TEXT")  # foto de perfil (opcional)
        acols = {r["name"] for r in conn.execute("PRAGMA table_info(appointments)").fetchall()}
        for col in ("service_id INTEGER", "price_cents INTEGER", "package_id INTEGER"):  # financeiro
            if col.split()[0] not in acols:
                conn.execute(f"ALTER TABLE appointments ADD COLUMN {col}")
        # Ambulatório Social (projeto da clínica): marca no paciente e na terapia
        for table in ("users", "services"):
            if "social" not in {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN social INTEGER NOT NULL DEFAULT 0")
        if "profile" not in {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}:
            conn.execute("ALTER TABLE users ADD COLUMN profile TEXT")  # dados pessoais (JSON)
        if "onboarded_at" not in {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}:
            conn.execute("ALTER TABLE users ADD COLUMN onboarded_at TEXT")  # quando viu as boas-vindas
        _seed_services(conn)
        _migrate_point_codes(conn)
        _seed_acupoints(conn)
        _seed_events(conn)
        _seed_theory(conn)
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------ configurações

def get_setting(db, key):
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(db, key, value):
    db.execute("DELETE FROM settings WHERE key = ?", (key,))
    db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, str(value)))


def primary_admin(db):
    """A administradora principal ("chave primária"): recebe as confirmações de alteração de login."""
    admin_id = get_setting(db, "primary_admin_id")
    if not admin_id:
        return None
    return db.execute("SELECT id, name, email FROM users WHERE id = ? AND role = 'admin' AND active = 1",
                      (int(admin_id),)).fetchone()


def _seed_acupoints(db):
    """Grava os pontos padrão que ainda não existem (361 clássicos + auriculoterapia).
    Pontos já existentes (e as edições da clínica) nunca são alterados."""
    from .acupoints_data import all_points, auricular_points
    existing = {r["code"] for r in db.execute("SELECT code FROM acupoints").fetchall()}
    for pt in all_points() + auricular_points():
        if pt["code"] in existing:
            continue
        db.execute(
            """INSERT INTO acupoints (code, meridian, number, intl_code, pinyin, view, x, y, custom)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (pt["code"], pt["meridian"], pt["number"], pt["intl_code"], pt["pinyin"], pt["view"], pt["x"], pt["y"]),
        )


def _migrate_point_codes(db):
    """Bancos antigos usavam as siglas brasileiras (VB20, IG4…). Passa tudo para as siglas chinesas
    (GB20, LI4…), inclusive nos protocolos das sessões e nas combinações, mantendo as edições."""
    import json
    from .acupoints_data import PT_TO_CN, to_cn
    old = [m for m, cn in PT_TO_CN.items() if m != cn]
    rows = db.execute(f"SELECT code FROM acupoints WHERE custom = 0 AND meridian IN ({','.join('?' * len(old))})",
                      old).fetchall()
    if not rows:
        return
    for r in rows:
        # se o ponto novo já foi criado vazio (servidor ligado no meio da troca), fica o antigo, com as edições
        db.execute("DELETE FROM acupoints WHERE code = ?", (to_cn(r["code"]),))
        db.execute("UPDATE acupoints SET code = ?, meridian = ? WHERE code = ?",
                   (to_cn(r["code"]), PT_TO_CN[r["code"].rstrip("0123456789")], r["code"]))
    for r in db.execute("SELECT id, data FROM session_protocols").fetchall():
        data = json.loads(r["data"])
        if data.get("acupoints"):
            data["acupoints"] = [to_cn(c) for c in data["acupoints"]]
            db.execute("UPDATE session_protocols SET data = ? WHERE id = ?", (json.dumps(data, ensure_ascii=False), r["id"]))
    for r in db.execute("SELECT id, points FROM theory_items").fetchall():
        pts = [to_cn(c) for c in json.loads(r["points"] or "[]")]
        db.execute("UPDATE theory_items SET points = ? WHERE id = ?", (json.dumps(pts), r["id"]))


def _seed_events(db):
    """Na primeira vez: o Reiki voluntário (último sábado de cada mês)."""
    if get_setting(db, "events_seeded"):
        return
    from datetime import datetime
    from .calendar_rules import last_saturday
    today = datetime.now().date()
    db.execute("""INSERT INTO events (title, icon, description, date, recurrence, created_at)
                  VALUES (?, ?, ?, ?, 'last_weekday', ?)""",
               ("Reiki voluntário", "🌟", "Encontro mensal de Reiki voluntário, aberto a todos, no último sábado do mês.",
                last_saturday(today.year, today.month).isoformat(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    set_setting(db, "events_seeded", 1)


DEFAULT_SERVICES = ["Acupuntura", "Auriculoterapia", "Reiki", "Ventosaterapia", "Moxabustão"]


SOCIAL_SERVICE = "Ambulatório Social – Acupuntura"  # R$ 50,00 · 60 min (acupuntura sistêmica + auriculoterapia)


def _seed_services(db):
    """Terapias iniciais (preço 0 até a clínica definir no Financeiro) e a do Ambulatório Social."""
    if not db.execute("SELECT COUNT(*) AS n FROM services").fetchone()["n"]:
        for name in DEFAULT_SERVICES:
            db.execute("INSERT INTO services (name, price_cents) VALUES (?, 0)", (name,))
    if not db.execute("SELECT 1 FROM services WHERE social = 1").fetchone():
        db.execute("INSERT INTO services (name, price_cents, social) VALUES (?, 5000, 1)", (SOCIAL_SERVICE,))


def _seed_theory(db):
    from .routes.theory import seed_theory
    seed_theory(db)

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

CREATE TABLE IF NOT EXISTS account_changes (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    token_hash  TEXT NOT NULL UNIQUE,
    payload     TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
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
            db.commit()
        finally:
            db.close()
        return
    os.makedirs(os.path.dirname(app.config["DATABASE_PATH"]) or ".", exist_ok=True)
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        conn.executescript(SCHEMA_SQLITE)
    finally:
        conn.close()

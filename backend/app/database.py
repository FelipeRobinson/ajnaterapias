"""Banco de dados SQLite (módulo sqlite3 do Python, sem serviço externo).

O arquivo do banco fica em backend/instance/ajna.db por padrão (não envie ao Git).
Ao hospedar, aponte DATABASE_PATH para um disco persistente do provedor.
"""
import os
import sqlite3

from flask import current_app, g

SCHEMA = """
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
    end             TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'scheduled',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(date);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE_PATH"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    os.makedirs(os.path.dirname(app.config["DATABASE_PATH"]) or ".", exist_ok=True)
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()

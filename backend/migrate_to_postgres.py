r"""Copia TODOS os dados do SQLite local (ajna.db) para o PostgreSQL da hospedagem.

Use quando for colocar o site no ar (comandos para o PowerShell, na pasta do projeto):
  1. Coloque o DATABASE_URL do PostgreSQL no .env
  2. Simule antes (não grava nada):
        .\.venv\Scripts\python.exe backend\migrate_to_postgres.py --simular
  3. Migre de verdade:
        .\.venv\Scripts\python.exe backend\migrate_to_postgres.py

O SQLite NÃO é alterado (continua como backup).
Por segurança, a migração é cancelada se o PostgreSQL já tiver usuários.
"""
import os
import sqlite3
import sys

from app import create_app
from app.database import _PostgresDB, init_db

# Tabelas na ordem certa (users antes de appointments, por causa da chave estrangeira).
TABLES = {
    "users": ["id", "name", "email", "phone", "password_hash", "role", "active", "created_at"],
    "appointments": ["id", "patient_user_id", "date", "start", '"end"', "status", "created_at"],
}

simular = "--simular" in sys.argv
app = create_app({"INIT_DB": False})  # não conecta em nada até a hora de migrar
sqlite_path = app.config["DATABASE_PATH"]
pg_url = app.config["DATABASE_URL"]

if not pg_url:
    raise SystemExit("Coloque o DATABASE_URL do PostgreSQL no .env antes de migrar.")
if not os.path.exists(sqlite_path):
    raise SystemExit(f"Banco SQLite não encontrado em {sqlite_path}")

src = sqlite3.connect(sqlite_path)
src.row_factory = sqlite3.Row
data = {t: src.execute(f"SELECT {', '.join(cols)} FROM {t} ORDER BY id").fetchall() for t, cols in TABLES.items()}
src.close()

print(f"Origem  (SQLite):     {sqlite_path}")
print("Destino (PostgreSQL): " + pg_url.split("@")[-1].split("?")[0])
for t, rows in data.items():
    print(f"  {t}: {len(rows)} registro(s)")

if simular:
    raise SystemExit("\nSimulação concluída. Nada foi gravado. Rode sem --simular para migrar.")

init_db(app)  # cria as tabelas no PostgreSQL, se ainda não existirem
dst = _PostgresDB(pg_url)
try:
    if dst.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]:
        raise SystemExit("O PostgreSQL já tem usuários. Migração cancelada para não misturar dados.")
    for t, cols in TABLES.items():
        marks = ", ".join(["%s"] * len(cols))
        sql = f"INSERT INTO {t} ({', '.join(cols)}) OVERRIDING SYSTEM VALUE VALUES ({marks})"
        with dst.conn.cursor() as cur:
            cur.executemany(sql, [tuple(r) for r in data[t]])
        # Faz os próximos IDs continuarem depois do maior ID copiado.
        dst.conn.execute(
            f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), COALESCE((SELECT MAX(id) FROM {t}), 0) + 1, false)"
        )
    dst.commit()
    print("\nMigração concluída! Todos os dados estão no PostgreSQL.")
except BaseException:
    dst.rollback()
    raise
finally:
    dst.close()

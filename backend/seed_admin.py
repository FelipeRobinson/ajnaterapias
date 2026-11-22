"""Cria ou atualiza um acesso de administrador no banco SQLite.

Uso (na raiz do projeto):
    python backend/seed_admin.py               cria/atualiza um administrador
    python backend/seed_admin.py --principal   e o marca como ADMINISTRADOR(A) PRINCIPAL
                                               (recebe as confirmações de alteração de login)
"""
import sys
import getpass

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, set_setting

app = create_app()
with app.app_context():
    name = input("Nome do administrador: ").strip() or "Administrador"
    email = input("E-mail do administrador: ").strip().lower()
    password = getpass.getpass("Senha (mín. 12 caracteres): ")
    if not email or len(password) < 12:
        raise SystemExit("Use um e-mail e uma senha com pelo menos 12 caracteres.")
    if getpass.getpass("Repita a senha: ") != password:
        raise SystemExit("As senhas não conferem.")

    db = get_db()
    db.execute(
        """INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'admin')
           ON CONFLICT(email) DO UPDATE SET name = excluded.name, password_hash = excluded.password_hash,
                                            role = 'admin', active = 1""",
        (name, email, generate_password_hash(password)),
    )
    if "--principal" in sys.argv:
        admin_id = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]
        set_setting(db, "primary_admin_id", admin_id)
        print("Marcado(a) como administrador(a) principal.")
    db.commit()
    destino = "PostgreSQL (DATABASE_URL)" if app.config["DATABASE_URL"] else app.config["DATABASE_PATH"]
    print(f"Administrador {email} criado/atualizado em {destino}")

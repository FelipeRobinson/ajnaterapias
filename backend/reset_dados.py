"""APAGA TODOS OS DADOS do banco e deixa só dois acessos de TESTE (1 administrador e 1 cliente).

Uso (na raiz do projeto):
    python backend/reset_dados.py

- Apaga clientes, administradores, sessões, prontuários, protocolos, financeiro, eventos, bloqueios,
  edições do mapa de pontos e da parte teórica. Depois recria o padrão de fábrica
  (pontos da acupuntura chinesa, terapias, diagnósticos, Reiki voluntário).
- Cria os acessos de teste abaixo. São SÓ PARA TESTE: antes de colocar o site no ar,
  crie o acesso real com `python backend/seed_admin.py --principal` e desative/exclua estes.
"""
from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, init_db, set_setting

# Acessos de teste (troque à vontade; a senha do administrador precisa de 12+ caracteres)
TEST_ADMIN = {"name": "Admin Teste", "email": "admin@teste.local", "password": "AdminTeste#2026"}
TEST_CLIENT = {"name": "Cliente Teste", "email": "cliente@teste.local", "password": "Cliente#2026"}

# Ordem: tabelas que apontam para outras primeiro
TABLES = ["payments", "packages", "expenses", "session_protocols", "medical_records", "appointments",
          "schedule_blocks", "account_changes", "password_resets", "events", "theory_items", "acupoints",
          "services", "settings", "users"]

app = create_app()
with app.app_context():
    destino = "PostgreSQL (DATABASE_URL)" if app.config["DATABASE_URL"] else app.config["DATABASE_PATH"]
    if input(f"Apagar TODOS os dados de {destino}? Digite APAGAR para confirmar: ").strip() != "APAGAR":
        raise SystemExit("Nada foi apagado.")
    db = get_db()
    for table in TABLES:
        db.execute(f"DELETE FROM {table}")
    if not app.config["DATABASE_URL"]:
        db.execute("DELETE FROM sqlite_sequence")  # ids voltam a começar do 1
    db.commit()

init_db(app)  # recria o padrão de fábrica

with app.app_context():
    db = get_db()
    for user, role in ((TEST_ADMIN, "admin"), (TEST_CLIENT, "patient")):
        db.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                   (user["name"], user["email"], generate_password_hash(user["password"]), role))
    admin_id = db.execute("SELECT id FROM users WHERE email = ?", (TEST_ADMIN["email"],)).fetchone()["id"]
    set_setting(db, "primary_admin_id", admin_id)
    db.commit()
    print(f"Pronto. Dados apagados em {destino}.")
    print("Acessos de teste criados (as senhas estão no topo deste arquivo):")
    print(f"  Administrador: {TEST_ADMIN['email']}")
    print(f"  Cliente:       {TEST_CLIENT['email']}")

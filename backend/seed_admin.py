"""Cria ou atualiza o único perfil inicial de administrador."""
import getpass
import os

from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

load_dotenv()
uri = os.environ.get("MONGODB_URI")
database_name = os.environ.get("MONGODB_DATABASE", "ajna_terapias")
if not uri:
    raise SystemExit("Defina MONGODB_URI no arquivo .env antes de criar o administrador.")

email = input("E-mail do administrador: ").strip().lower()
password = getpass.getpass("Senha: ")
if not email or len(password) < 12:
    raise SystemExit("Use um e-mail e uma senha com pelo menos 12 caracteres.")

db = MongoClient(uri, tls=True)[database_name]
db.users.update_one(
    {"email": email},
    {"$set": {"email": email, "password_hash": generate_password_hash(password), "role": "admin", "active": True}},
    upsert=True,
)
print("Administrador criado/atualizado com sucesso.")
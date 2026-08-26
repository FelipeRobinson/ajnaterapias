from flask import current_app, g
from pymongo import MongoClient


def get_db():
    """Cria uma conexão somente no servidor; a URI nunca vai para o JavaScript."""
    if "mongo_client" not in g:
        uri = current_app.config["MONGODB_URI"]
        if not uri:
            raise RuntimeError("MONGODB_URI não configurada.")
        g.mongo_client = MongoClient(uri, serverSelectionTimeoutMS=5000, tls=True)
    return g.mongo_client[current_app.config["MONGODB_DATABASE"]]


def close_db(_error=None):
    client = g.pop("mongo_client", None)
    if client:
        client.close()


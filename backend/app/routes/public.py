from flask import Blueprint, current_app, redirect, send_from_directory

public_bp = Blueprint("public", __name__)


@public_bp.get("/")
@public_bp.get("/index.html")
def home():
    return redirect("/frontend/index.html")


# Endereços curtos redirecionam para o arquivo real, para que os caminhos
# relativos (../css, ../img) funcionem igual no servidor e abrindo o arquivo direto.
@public_bp.get("/login")
@public_bp.get("/crm")
def login_page():
    return redirect("/frontend/crm/login.html")


@public_bp.get("/crm/painel")
def crm_panel():
    return redirect("/frontend/crm/painel.html")


@public_bp.get("/cliente")
def client_area():
    return redirect("/frontend/crm/cliente.html")

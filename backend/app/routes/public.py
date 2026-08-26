from flask import Blueprint, current_app, send_from_directory

public_bp = Blueprint("public", __name__)


@public_bp.get("/")
def home():
    return send_from_directory(current_app.static_folder, "index.html")


@public_bp.get("/agenda")
def agenda():
    return send_from_directory(current_app.static_folder, "agenda.html")


@public_bp.get("/crm")
def crm_login():
    return send_from_directory(current_app.static_folder, "crm/login.html")


@public_bp.get("/crm/painel")
def crm_panel():
    return send_from_directory(current_app.static_folder, "crm/painel.html")


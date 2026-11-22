"""Inicia o site. Tudo que muda entre local e web fica no arquivo .env (veja docs/COMANDOS.txt)."""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    if os.getenv("FLASK_ENV") == "production":
        from waitress import serve
        print(f"Servidor de produção em http://{host}:{port}")
        serve(app, host=host, port=port)
    else:
        app.run(host=host, port=port, debug=True)

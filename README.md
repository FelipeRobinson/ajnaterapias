# Ajna Terapias

Site da clínica + CRM com login para clientes e administração.

**Para rodar o site:** veja [docs/COMANDOS.txt](docs/COMANDOS.txt) — ou simplesmente:

```powershell
powershell -ExecutionPolicy Bypass -File .\iniciar.ps1 -Admin
```

## Estrutura

```
index.html          página inicial do site
frontend/           CSS, imagens, scripts e páginas do CRM (crm/)
backend/            servidor Python (Flask) + banco SQLite
  app/routes/       login, área do cliente, painel do administrador
  seed_admin.py     cria/atualiza o administrador
  tests/            testes automáticos
docs/               COMANDOS.txt (como rodar) e PROJETO.txt (anotações)
iniciar.ps1         faz tudo para rodar localmente
requirements.txt    dependências Python
Procfile            comando de início usado na hospedagem
.env.example        modelo das configurações (copie para .env)
```

## Como funciona

- Banco **SQLite**: um arquivo em `backend/instance/ajna.db`, criado automaticamente. Não vai para o Git.
- Login único em `/login`: administrador vai para `/crm/painel`, cliente para `/cliente`.
- Clientes não se cadastram sozinhos: o administrador cria, desativa ou redefine a senha no painel.
- O navegador nunca acessa o banco direto — só chama a API em Python, que confere o login.

## Segurança

- Nunca envie o `.env` ao GitHub (já está no `.gitignore`).
- Na web: HTTPS, `SESSION_COOKIE_SECURE=true` e uma `SECRET_KEY` longa e própria.
- Antes de guardar dados clínicos reais, revise LGPD, backup e controle de acesso.

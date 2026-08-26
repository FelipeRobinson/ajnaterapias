# Ajna Terapias

Estrutura inicial do site público e do CRM da clínica.

## Arquitetura

```
frontend/               site expositor existente e telas do paciente
  index.html            página principal
  agenda.html           agenda do paciente
  crm/                  login e painel administrativo
  css/ e js/            interface sem credenciais sensíveis
backend/                API Flask
  app/routes/           autenticação, paciente, administração e páginas
  seed_admin.py         criação do administrador inicial
```

O MongoDB é acessado somente pelo servidor Python, usando uma URI em variável de ambiente. O JavaScript só chama rotas da API no mesmo domínio. O paciente pode consultar a disponibilidade e os próprios horários; as rotas de pacientes, prontuários e painel exigem `role=admin` em toda requisição.

## Primeiro uso local

1. Crie um ambiente virtual: `py -m venv .venv`
2. Ative-o: `.\.venv\Scripts\Activate.ps1`
3. Instale dependências: `pip install -r requirements.txt`
4. Copie `.env.example` para `.env` e preencha `SECRET_KEY` e `MONGODB_URI`.
5. Crie o ADM: `python backend/seed_admin.py`
6. Inicie: `python backend/run.py`
7. Abra `http://127.0.0.1:5000`.

Para testar a estrutura: `pytest backend/tests`.

## MongoDB Atlas e segurança

- Crie um usuário técnico exclusivo da aplicação, com acesso apenas ao banco `ajna_terapias`; não use uma conta de administração do Atlas no app.
- Cadastre a URI apenas no provedor de hospedagem e no `.env` local. O `.env` já está ignorado pelo Git.
- Em produção, use HTTPS, defina `SESSION_COOKIE_SECURE=true` e uma `SECRET_KEY` aleatória longa.
- Antes de registrar prontuários reais, revise LGPD, retenção de dados, backup, trilha de auditoria e controle de acesso com um profissional adequado.

## Publicação

O projeto precisa ser hospedado como aplicação Python (por exemplo, em um serviço compatível com WSGI) e não como GitHub Pages, pois há autenticação e banco de dados. O domínio público pode ser `www.seudominio.com.br`, e o CRM continuará em `/crm`, protegido por sessão. Não existe forma de tornar um repositório GitHub **público** invisível: para ocultar o código, use repositório privado e hospede a aplicação em uma plataforma separada.

Use um servidor WSGI em produção — por exemplo: `waitress-serve --call 'app:create_app'`, executado dentro de `backend/`.

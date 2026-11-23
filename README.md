<div align="center">

<img src="frontend/img/logo%20(1).png" alt="Logo Ajna Terapias" width="110">

# 🪷 Ajna Terapias

**Site institucional + CRM da clínica, com área do cliente e painel administrativo**

<p>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.1-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/PostgreSQL-na_web-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/SQLite-local-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Bootstrap-5.3-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white" alt="Bootstrap">
</p>
<p>
  <img src="https://img.shields.io/badge/HTML5-E34F26?style=flat-square&logo=html5&logoColor=white" alt="HTML5">
  <img src="https://img.shields.io/badge/CSS3-1572B6?style=flat-square&logo=css3&logoColor=white" alt="CSS3">
  <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=black" alt="JavaScript">
  <img src="https://img.shields.io/badge/testes-pytest_✓-0A9EDC?style=flat-square&logo=pytest&logoColor=white" alt="pytest">
  <img src="https://img.shields.io/badge/servidor-waitress-7800b4?style=flat-square" alt="waitress">
</p>

[🚀 Como rodar](#-como-rodar) •
[📸 Telas](#-telas) •
[🧱 Arquitetura](#-arquitetura) •
[🗄️ Banco de dados](#️-banco-de-dados) •
[🔌 API](#-api) •
[🔐 Segurança](#-segurança) •
[🌐 Publicação](#-colocando-na-web) •
[🗺️ Roadmap](#️-roadmap)

<img src="docs/img/home.png" alt="Página inicial do site" width="100%">

</div>

---

## 📖 Sobre o projeto

O **Ajna Terapias** é o site do Instituto Ajna, um espaço de terapias integrativas (acupuntura, reiki, auriculoterapia, ventosaterapia, shiatsu, reflexologia e massagens). O projeto tem **duas partes**:

| | Parte | O que faz |
|:-:|---|---|
| 🌸 | **Site público** | Apresenta a clínica, a história, os serviços e os canais de contato (WhatsApp e Instagram). |
| 🔒 | **CRM** | Área restrita com **login**. O administrador gerencia os clientes, e cada cliente acompanha as próprias consultas. |

> [!NOTE]
> O site **não usa GitHub Pages**: como tem login e banco de dados, ele roda em um **servidor Python**, no seu computador ou em uma hospedagem.

---

## ✨ Funcionalidades

<table>
<tr>
<td width="50%" valign="top">

### 🌐 Site público
- 🪷 Abertura animada com a identidade visual roxa
- 📜 Seção "Sobre" com a história do instituto
- 💆 Carrossel com as **7 técnicas** de terapia
- 💬 Contato direto por WhatsApp e Instagram
- 📱 Layout responsivo (computador e celular)

</td>
<td width="50%" valign="top">

### 🔐 CRM
- 🔑 **Login único** para clientes e administração
- 🧭 Cada perfil vai para a área certa automaticamente
- 👤 Admin **cria acesso** de cliente (nome, e-mail, telefone, senha)
- 🔁 Admin **redefine senha** e **ativa/desativa** clientes
- 📊 Painel com totais de clientes e consultas do dia
- 📅 Cliente vê **as próprias consultas**
- 📋 **Prontuário** e **protocolo por sessão** (só administração)
- 🧊 **Mapa de pontos**: corpo 3D feminino + orelha 2D (79 pontos), em tela cheia
- 📚 **Parte teórica**: ficha dos pontos, diagnósticos, sintomas, combinações e **galeria da língua** com fotos
- 🧍 Na ficha do paciente, **corpo 3D com os pontos usados nele** (masculino se o sexo no prontuário for Masculino)

</td>
</tr>
</table>

---

## 📸 Telas

<details open>
<summary><b>🔑 Login: clientes e administração</b></summary>
<br>

<img src="docs/img/login.png" alt="Tela de login" width="100%">

| ❌ Senha errada | 📱 No celular |
|:-:|:-:|
| <img src="docs/img/login-erro.png" alt="Login com erro" width="100%"> | <img src="docs/img/login-mobile.png" alt="Login no celular" width="230"> |

</details>

<details open>
<summary><b>🛠️ Painel do administrador</b></summary>
<br>

<img src="docs/img/painel.png" alt="Painel do administrador" width="100%">

</details>

<details>
<summary><b>🙋 Área do cliente</b></summary>
<br>

<img src="docs/img/cliente.png" alt="Área do cliente" width="100%">

</details>

<details>
<summary><b>💆 Seção de serviços do site</b></summary>
<br>

<img src="docs/img/servicos.png" alt="Seção de serviços" width="100%">

</details>

> 💡 Os nomes e e-mails nas telas são **dados fictícios de demonstração**.

---

## 🚀 Como rodar

### ✅ Pré-requisito
- 🐍 **Python 3.12** ([python.org](https://www.python.org/downloads/), marque *"Add to PATH"*) ou:
  ```powershell
  winget install --id Python.Python.3.12 -e
  ```

### ⚡ Jeito rápido: um comando só

Na pasta do projeto, no PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\iniciar.ps1 -Admin
```

O script [`iniciar.ps1`](iniciar.ps1) faz tudo sozinho:

```mermaid
flowchart LR
    A[📦 Cria .venv] --> B[⬇️ Instala dependências]
    B --> C[🔑 Gera .env com chave secreta]
    C --> D[👤 Cria o administrador]
    D --> E[🟢 Liga o servidor]
```

Depois abra 👉 **http://127.0.0.1:5000/login**

Nas próximas vezes, rode sem o `-Admin`:

```powershell
powershell -ExecutionPolicy Bypass -File .\iniciar.ps1
```

<details>
<summary><b>🧩 Passo a passo manual (o que o script faz por dentro)</b></summary>

| # | Etapa | Comando |
|:-:|---|---|
| 1 | Criar o ambiente virtual | `py -m venv .venv` |
| 2 | Instalar as dependências | `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` |
| 3 | Criar a configuração | `Copy-Item docs/.env.example .env` |
| 4 | Criar o administrador | `.\.venv\Scripts\python.exe backend\seed_admin.py` |
| 5 | Ligar o site | `.\.venv\Scripts\python.exe backend\run.py` |
| 🧪 | Rodar os testes | `cd backend; ..\.venv\Scripts\python.exe -m pytest tests; cd ..` |

📄 A lista completa e comentada está em [`docs/COMANDOS.txt`](docs/COMANDOS.txt).

</details>

### 🧭 Endereços

| URL | Página | Quem acessa |
|---|---|---|
| `/` | 🌸 Site público | Todos |
| `/login` | 🔑 Login | Todos |
| `/crm/painel` | 🛠️ Painel da clínica | Somente **admin** |
| `/cliente` | 🙋 Área do cliente | Somente **cliente** |

---

## 🧱 Arquitetura

```mermaid
flowchart LR
    U([👤 Navegador]) -->|HTML, CSS, JS| F[🎨 frontend/]
    U -->|fetch /api/...| B[🐍 Flask<br/>backend/app]
    B -->|DATABASE_URL| P[(🐘 PostgreSQL<br/>Neon/Supabase)]
    B -.->|sem DATABASE_URL| D[(🗄️ SQLite<br/>ajna.db)]
    B -. confere sessão e perfil .-> B
```

> 🔒 O navegador **nunca** acessa o banco direto: o JavaScript chama a API, e o Python confere **quem está logado** e **qual o perfil** antes de ler ou gravar qualquer dado.

### 🔄 Fluxo do login

```mermaid
sequenceDiagram
    actor P as 👤 Pessoa
    participant L as 🔑 /login
    participant A as 🐍 API Flask
    participant D as 🗄️ Banco
    P->>L: e-mail + senha
    L->>A: POST /api/auth/login
    A->>D: busca usuário ativo
    D-->>A: hash da senha + perfil
    A-->>L: cookie de sessão + perfil
    alt perfil = admin
        L->>P: ➡️ /crm/painel
    else perfil = cliente
        L->>P: ➡️ /cliente
    end
```

### 📁 Estrutura de pastas

```
ajnaterapias/
├── 🐍 backend/                  Servidor Python
│   ├── app/
│   │   ├── __init__.py          Cria o app Flask e lê o .env
│   │   ├── database.py          PostgreSQL ou SQLite + criação das tabelas
│   │   ├── security.py          Login obrigatório, perfis e proteção CSRF
│   │   ├── mailer.py            ✉️ envio de e-mails (SMTP ou pasta outbox/)
│   │   ├── acupoints_data.py  ☯ os 361 pontos (códigos, pinyin, meridianos, posições)
│   │   └── routes/
│   │       ├── auth.py          🔑 login, logout, "quem sou eu"
│   │       ├── account.py       🔐 alteração de dados do admin por e-mail (sem tela no painel)
│   │       ├── crm.py           🛠️ painel e gestão de clientes (admin)
│   │       ├── patient.py       🙋 consultas do cliente
│   │       ├── records.py       📋 prontuário e protocolos (campos definidos aqui)
│   │       ├── acupoints.py     ☯ mapa de pontos (editar, extras, uso nas sessões)
│   │       ├── theory.py        📚 parte teórica (diagnósticos, sintomas, combinações)
│   │       └── public.py        🌐 endereços das páginas
│   ├── tests/                   🧪 testes automáticos (pytest)
│   ├── run.py                   🟢 liga o servidor
│   ├── seed_admin.py            👤 cria/atualiza o administrador
│   └── migrate_to_postgres.py   🚚 copia o SQLite local para o PostgreSQL
├── 🎨 frontend/                 Tudo que o navegador vê
│   ├── index.html               🌸 página inicial
│   ├── crm/                     login.html · painel.html · cliente.html
│   ├── css/                     estilos (pages/login.css = tela de login)
│   ├── js/                      JS do site · crm.js (login) · admin.js (painel) · cliente.js (área do cliente)
│   └── img/                     logos, fundo e fotos dos serviços
├── 📚 docs/                     COMANDOS.txt · PROJETO.txt · .env.example · img/
├── ⚡ iniciar.ps1               Faz tudo para rodar localmente
├── 📦 requirements.txt          Dependências Python
└── ☁️ Procfile                  Comando de início na hospedagem
```

---

## 🗄️ Banco de dados

O projeto funciona com **dois bancos**, escolhidos automaticamente pelo `.env`. O código é o mesmo nos dois casos:

| | Banco | Quando | Onde ficam os dados |
|:-:|---|---|---|
| 🐘 | **PostgreSQL** | `DATABASE_URL` preenchida | Online, **sempre ativo** (Neon ou Supabase, plano grátis) |
| 🪶 | **SQLite** | `DATABASE_URL` vazia | Arquivo `backend/instance/ajna.db` no seu PC, ótimo para testar offline |

As tabelas são criadas sozinhas quando o servidor liga.

### 🧭 Plano do projeto: local agora, PostgreSQL no host

```mermaid
flowchart LR
    A["🪶 FASE ATUAL<br/>SQLite local + DBeaver"] -->|compra do host| B["🚚 migrate_to_postgres.py"]
    B --> C["🐘 PostgreSQL online<br/>site no ar"]
```

| Fase | Banco | `DATABASE_URL` no `.env` |
|---|---|---|
| 🛠️ **Agora: desenvolvimento** | SQLite `backend/instance/ajna.db`, visto e editado no **DBeaver** | comentada (`#`) |
| 🌐 **Depois: com host** | PostgreSQL | preenchida |

**Migração (quando chegar a hora):**

```powershell
.\.venv\Scripts\python.exe backend\migrate_to_postgres.py --simular   # só mostra o que vai copiar
.\.venv\Scripts\python.exe backend\migrate_to_postgres.py             # copia tudo
```

> 🛟 O `ajna.db` continua intacto como backup, e a migração se recusa a rodar se o PostgreSQL já tiver usuários.

### 🐘 Ativando o PostgreSQL grátis (Neon)

1. 🆓 Crie uma conta em **[neon.tech](https://neon.tech)** e um projeto (região São Paulo, se houver).
2. 📋 Clique em **Connect** e copie o *connection string*.
3. 📝 Cole no `.env`:
   ```env
   DATABASE_URL=postgresql://usuario:senha@ep-xxxx.sa-east-1.aws.neon.tech/neondb?sslmode=require
   ```
4. 👤 Crie o admin no banco online: `.\.venv\Scripts\python.exe backend\seed_admin.py`
5. 🟢 Ligue o site normalmente.

| Serviço grátis | Limite | Sem uso por um tempo |
|---|---|---|
| **Neon** ⭐ | 0,5 GB | "Dorme" e **acorda sozinho** na próxima conexão |
| **Supabase** | 500 MB | **Pausa após 7 dias**: precisa reativar no painel |

> [!NOTE]
> Os dados do SQLite e do PostgreSQL são **separados**: clientes criados em um não aparecem no outro.

```mermaid
erDiagram
    USERS ||--o{ APPOINTMENTS : "tem"
    USERS {
        int id PK
        text name "nome"
        text email UK "login"
        text phone "telefone"
        text password_hash "senha criptografada"
        text role "admin | patient"
        int active "1 ativo · 0 desativado"
        text created_at
    }
    APPOINTMENTS {
        int id PK
        int patient_user_id FK
        text date "AAAA-MM-DD"
        text start "HH:MM"
        text end "HH:MM"
        text status "scheduled | cancelled"
        text created_at
    }
```

> [!TIP]
> Para ver os dados visualmente: no PostgreSQL, use o **SQL Editor** do próprio Neon/Supabase ou o **DBeaver**. No SQLite, abra `backend/instance/ajna.db` no [DB Browser for SQLite](https://sqlitebrowser.org/).

---

## 🔌 API

Todas as rotas respondem em **JSON**. As que alteram dados exigem o cabeçalho `X-CSRF-Token`.

| Método | Rota | Acesso | Descrição |
|:-:|---|:-:|---|
| 🟢 `GET` | `/api/health` | 🌐 | Verifica se o servidor está no ar |
| 🟡 `POST` | `/api/auth/login` | 🌐 | Entra com `email` e `password` |
| 🟢 `GET` | `/api/auth/me` | 🔑 | Dados de quem está logado |
| 🟡 `POST` | `/api/auth/logout` | 🔑 | Sai da conta |
| 🟢 `GET` | `/api/admin/dashboard` | 🛠️ | Totais de clientes ativos e consultas do dia |
| 🟢 `GET` | `/api/admin/patients` | 🛠️ | Lista os clientes |
| 🟡 `POST` | `/api/admin/patients` | 🛠️ | Cria o acesso de um cliente |
| 🟠 `PATCH` | `/api/admin/patients/<id>` | 🛠️ | Ativa/desativa ou troca a senha |
| 🟢 `GET` | `/api/patient/me/appointments` | 🙋 | Consultas do cliente logado |
| 🟢 `GET` | `/api/patient/availability?date=AAAA-MM-DD` | 🙋🛠️ | Horários ocupados (sem dados de terceiros) |

<sub>🌐 público · 🔑 qualquer pessoa logada · 🛠️ só admin · 🙋 só cliente</sub>

---

## 🔐 Segurança

| | Proteção | Como funciona |
|:-:|---|---|
| 🧂 | **Senhas criptografadas** | Guardadas só como *hash* (werkzeug/scrypt), nunca em texto |
| 🍪 | **Sessão segura** | Cookie `HttpOnly` + `SameSite=Lax` (e `Secure` na web) |
| 🛡️ | **CSRF** | Toda ação que altera dados exige um token da sessão |
| 👮 | **Perfis** | Cada rota confere se é `admin` ou `patient` |
| 🕵️ | **Login discreto** | Mesma mensagem e mesmo tempo de resposta para e-mail inexistente ou senha errada |
| 💉 | **SQL injection** | Todas as consultas usam parâmetros (`?`) |
| 🧼 | **XSS** | Nomes e e-mails são escapados antes de aparecer na tela |
| 🙈 | **Segredos fora do Git** | `.env` e `*.db` estão no `.gitignore` |

> [!WARNING]
> Antes de guardar **dados clínicos reais**, revise a **LGPD**, a política de backup e o controle de acesso.

---

## 🌐 Colocando na web

O código e os comandos **são os mesmos**. Só mudam os valores do `.env` (ou das *Environment Variables* da hospedagem):

| Variável | 💻 Local | ☁️ Web |
|---|---|---|
| `FLASK_ENV` | `development` | `production` |
| `SECRET_KEY` | chave gerada | **outra** chave, longa |
| `HOST` | `127.0.0.1` | `0.0.0.0` |
| `PORT` | `5000` | definida pela hospedagem |
| `SESSION_COOKIE_SECURE` | `false` | `true` (exige HTTPS) |
| `DATABASE_URL` | *(vazio = SQLite)* | `postgresql://...` do Neon/Supabase |

**Passos no Render (plano grátis):**

1. 🔗 Crie um *Web Service* conectado ao repositório do GitHub.
2. 🏗️ Build: `pip install -r requirements.txt`
3. ▶️ Start: `python backend/run.py` (já está no [`Procfile`](Procfile))
4. 🔑 Em *Environment*, cadastre as variáveis da tabela, incluindo `DATABASE_URL`.
5. 👤 Crie o admin rodando `seed_admin.py` no seu PC com o mesmo `DATABASE_URL` no `.env`.

> [!IMPORTANT]
> Com o banco no PostgreSQL, os dados **não se perdem** a cada publicação. No plano grátis do Render, o servidor "dorme" após 15 min sem visitas, e o primeiro acesso depois disso demora ~1 min.

---

## 🙏 Créditos

- Modelo anatômico 3D: **BodyParts3D 4.0**, © The Database Center for Life Science, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — adaptado (ver `frontend/models/anatomy/ATRIBUICAO.md`).
- Modelo 3D feminino: **HuBMAP 3D Reference Organ Set for Female v1.5**, K. Browne e H. Schlehlein, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — adaptado (ver `frontend/models/anatomy-f/ATRIBUICAO.md`).
- Visualização 3D: **[Three.js](https://threejs.org/)** (licença MIT).

---

## 🧪 Testes

```powershell
cd backend; ..\.venv\Scripts\python.exe -m pytest tests; cd ..
```

| Teste | Verifica |
|---|---|
| ✅ `test_health_endpoint` | O servidor responde |
| ✅ `test_admin_creates_patient_who_can_log_in` | Admin cria cliente → cliente entra → cliente **não** acessa o painel; CSRF é exigido |
| ✅ `test_wrong_password` | Senha errada é recusada |
| ✅ `test_duplicate_email_is_rejected` | E-mail repetido é recusado e o banco continua consistente |
| ✅ `test_theory.py` | Parte teórica: classificações, ficha editável, diagnósticos/sintomas/combinações, galeria da língua e bloqueio para pacientes |

Ao todo são **55 testes**.

---

## 🗺️ Roadmap

- [x] 🌸 Site público com identidade visual
- [x] 🔑 Login de clientes e administração
- [x] 🗄️ Banco de dados em Python (SQLite)
- [x] 🐘 Suporte a PostgreSQL online (Neon/Supabase)
- [x] 👤 Gestão de acessos de clientes
- [x] ✏️ Editar e excluir clientes pelo painel
- [x] 🗓️ Agenda semanal no painel (agendar, remarcar, realizar, cancelar)
- [x] 📅 Cliente pede horário pelo portal e a clínica confirma
- [x] 🔐 Admin altera o próprio login com aprovação da administradora principal por e-mail
- [x] 🔑 "Esqueci minha senha" para clientes e administradores
- [x] 📆 Agenda em lista, semana (colunas) e mês (calendário), com o ano
- [x] ⛔ Horários indisponíveis (bloqueiam o painel e o portal do cliente)
- [x] 🚫 Atendimento só de terça a quinta; segunda, sexta, sábado e domingo fechados (exceção só pelo painel)
- [x] 🌟 "Reiki Para Todos" no último sábado de cada mês, na agenda e na área do cliente
- [x] 🔍 Janela do dia com linha do tempo, consultas, bloqueios e eventos
- [x] 🔐 Senha do admin só muda pelo link enviado ao e-mail
- [x] ☰ Menu hambúrguer: faixa com logo no computador e botão no canto no celular
- [x] 📷 Foto de perfil opcional (admin e clientes)
- [ ] 💬 Chat no site para o primeiro atendimento (sem login)
- [x] 📋 Prontuário (ficha fixa) e protocolo por sessão, só para a administração
- [x] ☯ Mapa interativo dos 361 pontos (OMS) ligado aos protocolos
- [x] 🧊 Mapa 3D com camadas (pele, músculos, ossos), orelha e zoom no ponto
- [x] 👂 79 pontos de auriculoterapia (GB/T 13734) com mapa da orelha
- [x] ♀ Corpo feminino no 3D (pele e esqueleto parcial), mais fino e padrão do mapa (sem corpo 2D)
- [x] 🧍 Corpo 3D na ficha do paciente com os pontos dos protocolos dele (♂ para pacientes homens)
- [x] 🧍 Bonequinho em cada sessão com os pontos usados (clique para marcar)
- [x] 📚 Parte teórica do mapa: ficha técnica dos pontos, diagnósticos MTC, sintomas e combinações (cesta)
- [x] 👅 Galeria de diagnóstico pela língua: 31 aspectos com fotos e diagnósticos relacionados
- [x] 💰 Financeiro: terapias e preços, recebimentos, pacotes de sessões, despesas e resumo anual
- [x] 📈 Gráficos do financeiro: barras, saldo acumulado, resultado do mês e pizzas (categoria, forma, terapia, particular x social)
- [x] 📄 Relatório financeiro com filtros (período, tipo, forma, categoria, terapia, cliente, origem, Ambulatório Social) em planilha (Excel) e PDF
- [x] 🖨️ Relatórios do paciente: prontuário completo, ficha de anamnese e ficha de cada consulta (imprimir / PDF)
- [x] 🪪 Dados pessoais do cliente (CPF, endereço, contato de emergência…) editáveis por ele e pela clínica
- [x] 📈 Relatório de acompanhamento do paciente (evolução, gráfico de intensidade, técnicas e pontos)
- [x] 🤝 Ambulatório Social de Acupuntura: marca no paciente, terapia própria (R$ 50,00 · 60 min) e totais no financeiro
- [ ] ☁️ Publicação em hospedagem com domínio próprio

---

<div align="center">

Feito com 💜 por **Felipe Robinson** para o **Instituto Ajna Terapias**

<a href="https://www.instagram.com/institutoajnaterapias/">📷 @institutoajnaterapias</a>

</div>

# 🎫 Ticket System

[![CI](https://github.com/allangsilva97/ticket-system/actions/workflows/ci.yml/badge.svg)](https://github.com/allangsilva97/ticket-system/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![License](https://img.shields.io/badge/license-MIT-green)

Sistema de **tickets de suporte multiempresa** com API REST em **FastAPI** e frontend em JavaScript puro.
Inclui controle de acesso por papel, SLA com alertas automáticos, trilha de auditoria completa e
notificações por e-mail.

---

## ✨ Funcionalidades

| Área | O que faz |
|---|---|
| **Autenticação** | JWT, senhas com bcrypt, bloqueio de login após tentativas falhas, primeiro usuário vira admin |
| **Papéis** | `admin` (tudo), `agent` (tickets da sua empresa ou atribuídos a ele), `client` (tickets da própria empresa) |
| **Empresas** | CRUD, SLA base em horas por empresa, ativação/desativação |
| **Tickets** | Ciclo de vida completo, 6 status, 5 prioridades, 8 categorias, atribuição, filtros e busca |
| **Comentários** | Públicos e internos (notas internas nunca aparecem para o cliente) |
| **Anexos** | Upload/download autenticado, limite de tamanho e extensões configuráveis |
| **SLA** | Prazo calculado pela prioridade; monitor em segundo plano envia alerta (75 %) e aviso de violação **uma única vez** por ticket |
| **Auditoria** | Toda criação/alteração/exclusão registra quem, quando, IP e o diff `antes → depois` |
| **E-mail** | Novo ticket, atribuição, mudança de status, comentário, alerta e violação de SLA (modo log sem SMTP) |
| **Dashboard** | Estatísticas, gráficos por status/prioridade, tendência e conformidade de SLA |
| **i18n** | Interface em inglês, português e espanhol |

## 🧱 Stack

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy 2, Pydantic 2, python-jose, passlib/bcrypt
- **Banco:** SQLite (padrão) — compatível com PostgreSQL/MySQL via `DATABASE_URL`
- **Frontend:** HTML + CSS + JavaScript puro, Chart.js
- **Qualidade:** pytest (31 testes), ruff, GitHub Actions
- **Deploy:** Docker / Docker Compose

## 🚀 Começando

### Pré-requisitos

- Python **3.10 ou superior**
- Git
- (Opcional) Docker

### Instalação

```bash
git clone https://github.com/allangsilva97/ticket-system.git
cd ticket-system
python -m venv .venv
```

Ative o ambiente virtual:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate
```

Instale as dependências e crie o arquivo de configuração:

```bash
pip install -r requirements-dev.txt
cp .env.example .env
```

Edite o `.env` e defina um `SECRET_KEY` aleatório:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Executando

```bash
python create_admin.py admin@empresa.com SenhaForte123 "Administrador"
uvicorn main:app --reload
```

- Aplicação: http://localhost:8000
- Documentação interativa (Swagger): http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

> Sem `create_admin.py`, o **primeiro** usuário registrado em `POST /api/auth/register` vira admin.
> Depois disso, apenas admins podem criar usuários.

### No VS Code

1. Abra a pasta do projeto (`File → Open Folder`).
2. Aceite instalar as extensões recomendadas (Python, Ruff, Docker…).
3. `Terminal → Run Task → Setup: criar venv e instalar dependências`.
4. Pressione **F5** e escolha **API: Uvicorn (reload)** para rodar com depurador.
5. Os testes aparecem na aba **Testing** (pytest já configurado).

### Com Docker

```bash
cp .env.example .env   # ajuste SECRET_KEY
docker compose up -d --build
docker compose exec api python create_admin.py admin@empresa.com SenhaForte123
```

Os dados (SQLite e anexos) ficam no volume `ticket-data`.

## ⚙️ Configuração

Todas as opções ficam no `.env` (veja [`.env.example`](.env.example)). As principais:

| Variável | Padrão | Descrição |
|---|---|---|
| `SECRET_KEY` | *placeholder* | **Obrigatório trocar em produção.** Assina os tokens JWT |
| `DATABASE_URL` | `sqlite:///./tickets.db` | URL SQLAlchemy do banco |
| `CORS_ORIGINS` | `http://localhost:8000,...` | Origens permitidas, separadas por vírgula |
| `APP_URL` | `http://localhost:8000` | URL pública, usada nos links dos e-mails |
| `SMTP_HOST` | *(vazio)* | Servidor SMTP. Vazio = e-mails só vão para o log |
| `SLA_MONITOR_ENABLED` | `true` | Liga o verificador periódico de SLA |
| `SLA_CHECK_INTERVAL_MINUTES` | `15` | Intervalo entre verificações |
| `SLA_WARNING_THRESHOLD` | `0.75` | Fração do prazo que dispara o alerta |
| `MAX_FILE_SIZE_MB` | `10` | Tamanho máximo de anexo |

## 🧪 Testes e lint

```bash
pytest                 # 31 testes, banco SQLite temporário
pytest --cov           # com cobertura
ruff check .           # lint
```

## 📁 Estrutura

```text
├── main.py              # App FastAPI, ciclo de vida, health checks
├── config.py            # Configurações (pydantic-settings / .env)
├── database.py          # Engine, sessão e Base do SQLAlchemy
├── models.py            # Tabelas: User, Company, Ticket, Comment, Attachment, AuditLog
├── schemas.py           # Schemas Pydantic de entrada/saída
├── auth.py              # JWT, hash de senha, dependências de permissão
├── create_admin.py      # Script para criar/redefinir um admin
├── routers/             # Endpoints: auth, companies, tickets, users, dashboard, audit
├── services/            # audit_service, email_service, sla_service
├── static/              # Frontend (index.html, app.js, style.css)
├── tests/               # Testes automatizados
├── docs/                # Documentação adicional
└── .github/             # CI, templates de issue e PR
```

## 📚 Documentação

- [Referência da API](docs/API.md)
- [Arquitetura e regras de negócio](docs/ARCHITECTURE.md)
- [Revisão do script original e correções](docs/REVISAO.md)
- [Como contribuir](CONTRIBUTING.md) · [Segurança](SECURITY.md) · [Changelog](CHANGELOG.md)

## 🗺️ Roadmap

- [ ] Migrações de banco com Alembic
- [ ] Rate limit e fila compartilhados (Redis) para rodar com vários workers
- [ ] Base de conhecimento e portal do cliente
- [ ] Webhooks e relatórios (PDF/Excel)
- [ ] SSO (SAML/OIDC) e MFA

## 📄 Licença

Distribuído sob a licença MIT. Veja [LICENSE](LICENSE).

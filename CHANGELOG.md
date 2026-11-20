# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.
O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa
[Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Corrigido
- `/painel`: o card de login aparecia sempre por cima do painel de gestão (`#login-screen` forçava
  `display: flex` e vencia `.screen { display: none }`).
- Busca de tickets, usuários e empresas: `%` e `_` agora são tratados como texto, não como curinga do `LIKE`.

### Segurança
- `python-jose` substituído por `PyJWT` e dependências atualizadas (FastAPI, Starlette, python-multipart,
  pydantic e outras): `pip-audit` sem vulnerabilidades conhecidas.
- `APP_ENV=production` faz o app recusar `SECRET_KEY` fraca ou padrão (antes só havia um aviso no log).
- 2 novos testes (total: 42).

## [2.0.0] - 2026-11-13

### Adicionado
- **Trilha de auditoria** (`audit_logs`): criação, alteração, exclusão, mudança de status, atribuição,
  comentários, anexos, login e troca de senha, com diff `antes → depois`, usuário e IP.
- `GET /api/audit` (admin, com filtros e paginação) e `GET /api/tickets/{id}/history` (equipe).
- **Monitor de SLA** em segundo plano: alerta ao responsável ao atingir 75 % do prazo e aviso de
  violação para responsável e admins — cada alerta é enviado uma única vez por ticket.
- `GET /api/tickets/{id}/sla` com o estado atual (`ok`, `warning`, `breached`, `closed`, `no_sla`).
- **Notificações por e-mail** (SMTP) para novo ticket, atribuição, status, comentários e SLA.
  Sem `SMTP_HOST` os e-mails são apenas registrados no log.
- Link direto `/#ticket-{id}` no frontend (usado nos e-mails).
- `GET /health/ready` verificando a conexão com o banco.
- Projeto VS Code (`launch.json`, `tasks.json`, extensões recomendadas), Dockerfile, Docker Compose,
  GitHub Actions (lint + testes + build Docker), `pyproject.toml` com ruff/pytest.
- Documentação: README, API, arquitetura, contribuição, segurança, templates de issue/PR.
- 12 novos testes (total: 31).

### Alterado
- Limite de anexos e extensões permitidas agora vêm do `.env` (`MAX_FILE_SIZE_MB`, `ALLOWED_EXTENSIONS`).
- Cálculo de SLA centralizado em `services/sla_service.py`.

### Corrigido
- `services/*.py` eram **diretórios vazios** com nome de arquivo, não módulos Python.
- Arquivo de upload órfão no disco quando a gravação no banco falhava.
- Imports não utilizados.

## [1.0.0]

- Versão inicial (Fase 1): autenticação JWT, papéis, empresas, tickets, comentários, anexos e dashboard.

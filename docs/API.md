# Referência da API

A documentação interativa completa (com schemas e "Try it out") fica em **`/docs`** (Swagger) e
**`/redoc`** quando a aplicação está rodando. Este arquivo é um resumo.

## Autenticação

Faça login com *form data* (`username` = e-mail) e use o token nas demais chamadas:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -d "username=admin@empresa.com&password=SenhaForte123"
```

```bash
curl http://localhost:8000/api/tickets -H "Authorization: Bearer <access_token>"
```

Legenda de acesso: 🌐 público · 👤 qualquer usuário logado · 🛠️ agente ou admin · 🔑 admin

## Auth e usuários — `/api/auth`

| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| POST | `/register` | 🌐 (1º usuário) / 🔑 | Cria usuário. O primeiro vira admin |
| POST | `/login` | 🌐 | Retorna `access_token` e dados do usuário. Bloqueia após 5 falhas |
| GET / PUT | `/me` | 👤 | Ver / editar o próprio perfil |
| PUT | `/me/password` | 👤 | Trocar a própria senha |
| GET | `/users` | 🔑 | Listar usuários |
| GET / PUT / DELETE | `/users/{id}` | 🔑 | Ver / editar / excluir (sem histórico) usuário |

## Empresas — `/api/companies`

| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| POST | `` | 🔑 | Criar empresa |
| GET | `` | 👤 | Listar (não-admins veem só a própria). Filtros: `search`, `is_active`, paginação |
| GET | `/{id}` | 👤 | Detalhes (própria empresa ou admin) |
| PUT / DELETE | `/{id}` | 🔑 | Editar / excluir (somente sem tickets e usuários) |

## Tickets — `/api/tickets`

| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| POST | `` | 👤 | Abrir ticket (cliente só na própria empresa) |
| GET | `` | 👤 | Listar com filtros: `status`, `priority`, `category`, `company_id`, `assignee_id`, `creator_id`, `search`, `date_from`, `date_to`, `overdue_only`, `page`, `page_size` |
| GET | `/my-assigned` | 🛠️ | Últimos 10 tickets atribuídos a mim |
| GET / PUT | `/{id}` | 👤 | Ver / editar (cliente não altera status, prioridade nem responsável) |
| PUT | `/{id}/status` | 👤 | Mudar status (cliente: só reabrir ou cancelar o próprio) |
| PUT | `/{id}/assign` | 🛠️ | Atribuir responsável (abre → em andamento automaticamente) |
| DELETE | `/{id}` | 🔑 | Excluir ticket e anexos |
| GET | `/{id}/sla` | 👤 | Estado do SLA: `ok`, `warning`, `breached`, `closed`, `no_sla` |
| GET | `/{id}/history` | 🛠️ | Trilha de auditoria do ticket |
| POST / GET | `/{id}/comments` | 👤 | Adicionar / listar comentários (cliente não vê internos) |
| PUT / DELETE | `/comments/{comment_id}` | autor ou 🔑 | Editar / excluir comentário |
| POST / GET | `/{id}/attachments` | 👤 | Enviar (multipart `file`) / listar anexos |
| GET | `/attachments/{id}/download` | 👤 | Download autenticado |
| DELETE | `/attachments/{id}` | 👤 | Excluir (cliente: só os próprios) |

### Exemplo: abrir um ticket

```json
POST /api/tickets
{
  "title": "Impressora não imprime",
  "description": "Erro 0x80 ao imprimir",
  "company_id": 1,
  "priority": "high",
  "category": "technical"
}
```

### Exemplo: estado do SLA

```json
GET /api/tickets/42/sla
{ "ticket_id": 42, "status": "warning", "elapsed": 0.81,
  "due_at": "2026-11-13T18:00:00", "time_left": "1h 30m" }
```

## Usuários — `/api/users`

| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| GET | `` | 🛠️ | Listar usuários visíveis |
| GET | `/agents` | 👤 | Agentes/admins para o seletor de responsável |
| GET | `/{id}/tickets` | 👤 | Tickets de um usuário |

## Dashboard — `/api/dashboard`

| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| GET | `/stats` | 👤 | Totais por status/prioridade, atrasados, recentes |
| GET | `/charts/tickets-by-date` | 👤 | Tendência de abertura (`days`) |
| GET | `/charts/sla-compliance` | 👤 | % de tickets fechados dentro do prazo |

## Auditoria — `/api/audit`

| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| GET | `` | 🔑 | Trilha completa. Filtros: `entity_type`, `entity_id`, `action`, `user_id`, `date_from`, `date_to`, paginação |

Cada registro:

```json
{
  "id": 7, "entity_type": "ticket", "entity_id": 42, "action": "assignment",
  "changes": { "assignee_id": { "old": null, "new": 3 }, "status": { "old": "open", "new": "in_progress" } },
  "description": "Ticket assignee changed (fields: assignee_id, status)",
  "user_id": 1, "user_name": "Administrador", "user_role": "admin",
  "ip_address": "127.0.0.1", "created_at": "2026-11-13T14:02:11"
}
```

## Health checks

| Rota | Descrição |
|---|---|
| `GET /health` | Processo no ar (liveness) |
| `GET /health/ready` | Banco respondendo (readiness) — `503` se não |

## Erros

| Código | Significado |
|---|---|
| 400 | Regra de negócio violada ou registro duplicado |
| 401 | Token ausente, inválido ou expirado |
| 403 | Sem permissão para o recurso |
| 404 | Recurso não encontrado |
| 422 | Dados inválidos (`detail` indica o campo) |
| 429 | Muitas tentativas de login (`Retry-After` no cabeçalho) |

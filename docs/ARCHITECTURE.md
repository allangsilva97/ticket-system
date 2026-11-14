# Arquitetura e regras de negócio

## Visão geral

```text
Navegador (static/*.js)  ──HTTP/JSON──►  FastAPI (main.py)
                                          │
                     ┌────────────────────┼──────────────────────┐
                     ▼                    ▼                      ▼
               routers/*            services/*              auth.py
          (validação, permissão)  (auditoria, e-mail, SLA)  (JWT, papéis)
                     │                    │
                     └──────► SQLAlchemy (models.py) ◄──────┘
                                          │
                                   SQLite / PostgreSQL
```

- **Um processo**, sem filas externas. O monitor de SLA é uma tarefa `asyncio` iniciada no
  `lifespan` da aplicação; o trabalho bloqueante (banco/SMTP) roda em thread.
- E-mails disparados por requisições usam `BackgroundTasks`: a mensagem é montada enquanto a
  sessão do banco está aberta e enviada depois da resposta.
- O frontend é servido em `/` e `/static`; anexos **não** são públicos.

## Modelo de dados

| Tabela | Principais campos |
|---|---|
| `users` | e-mail, senha (bcrypt), papel, empresa, idioma, ativo |
| `companies` | nome, contato, fuso, `sla_hours`, ativo |
| `tickets` | título, descrição, status, prioridade, categoria, empresa, criador, responsável, `sla_due_at`, `first_response_at`, `resolved_at`, `closed_at`, `sla_warning_notified_at`, `sla_breach_notified_at` |
| `ticket_comments` | ticket, autor, conteúdo, `is_internal` |
| `ticket_attachments` | ticket, nome original, nome em disco (UUID), tipo, tamanho |
| `audit_logs` | entidade, id, ação, `changes` (JSON), usuário (desnormalizado), IP, data |

As tabelas são criadas automaticamente na inicialização (`Base.metadata.create_all`).

> **Atualizando um banco da versão 1.0:** as colunas `sla_*_notified_at` e a tabela `audit_logs`
> são novas. `create_all` cria a tabela, mas não altera tabelas existentes. Em SQLite, rode:
>
> ```sql
> ALTER TABLE tickets ADD COLUMN sla_warning_notified_at DATETIME;
> ALTER TABLE tickets ADD COLUMN sla_breach_notified_at DATETIME;
> ```

## Permissões

| Ação | Admin | Agente | Cliente |
|---|---|---|---|
| Ver tickets | todos | da sua empresa ou atribuídos a ele | da sua empresa |
| Editar ticket | todos | da sua empresa ou atribuídos | próprios, enquanto abertos (sem status/prioridade/responsável) |
| Mudar status | ✓ | ✓ | reabrir ou cancelar os próprios |
| Atribuir | qualquer agente | agentes da sua empresa | ✗ |
| Comentário interno | ✓ | ✓ | ✗ (nem vê) |
| Empresas / usuários | CRUD | ✗ | ✗ |
| Auditoria | completa | histórico de tickets visíveis | ✗ |

## SLA

Prazo = `sla_hours` da empresa × multiplicador da prioridade, contado a partir da abertura
(horas corridas):

| Prioridade | Multiplicador | Ex.: empresa com 24 h |
|---|---|---|
| critical | 0,25 | 6 h |
| urgent | 0,5 | 12 h |
| high | 0,75 | 18 h |
| medium | 1,0 | 24 h |
| low | 2,0 | 48 h |

- Mudar a prioridade recalcula o prazo e "rearma" os alertas.
- O monitor roda a cada `SLA_CHECK_INTERVAL_MINUTES`:
  - ao atingir `SLA_WARNING_THRESHOLD` (75 %) → e-mail ao responsável;
  - prazo vencido → e-mail ao responsável e a todos os admins.
  - Cada alerta é enviado **uma vez** (marcado em `sla_*_notified_at`).
- Tickets `closed`/`cancelled` são ignorados. Conformidade de SLA no dashboard =
  fechados com `resolved_at <= sla_due_at`.

## Ciclo de vida do ticket

```text
open ──atribuir──► in_progress ──► waiting_customer ──(cliente responde)──► open
  │                    │      └──► waiting_third_party
  └────────────────────┴──────────► closed / cancelled ──(reabrir)──► open
```

- Primeira resposta pública da equipe (ou `open → in_progress`) grava `first_response_at`.
- Fechar grava `closed_at`/`resolved_at`; reabrir limpa os dois.

## Auditoria

`services/audit_service.log()` adiciona o registro **na mesma sessão** da alteração; se a
transação falhar, o log também é descartado. O usuário é gravado por nome/papel além do id,
para que o histórico sobreviva à exclusão do usuário (`ON DELETE SET NULL`). Atualizações sem
mudança real não geram registro.

## Limitações conhecidas

- Rate limit de login e monitor de SLA são por processo: rode **um worker** ou mova para Redis.
- Sem migrações automáticas (Alembic no roadmap).
- SLA em horas corridas (sem horário comercial/feriados).

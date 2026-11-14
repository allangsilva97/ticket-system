# Revisão do script `Project Tickets.txt`

O arquivo original era um script PowerShell (≈10.400 linhas) gerado em uma conversa com IA, que
deveria criar o projeto "Enterprise Ticket System (Fases 1–5)". **Ele não executa**: o PowerShell
falha na análise sintática antes de criar qualquer arquivo e, mesmo corrigido isso, o Python
gerado não importaria. Este documento lista os problemas encontrados e o que foi feito.

## Decisão adotada

Em vez de remendar o gerador, o projeto foi montado a partir da versão **Fase 1 que já funcionava**
(`New project/ticket-system`, 19 testes passando) e as partes aproveitáveis do script foram
**reescritas e integradas**: serviço de auditoria, serviço de SLA, serviço de e-mail, health check
de banco, Docker e documentação. As funcionalidades da Fase 3–5 que no script eram apenas
*stubs* ("implementation pending") ficaram no roadmap do README.

## Erros que impedem a execução do script

| # | Problema | Onde (linha no .txt) |
|---|---|---|
| 1 | O script está **duplicado**, e entre as cópias há texto de conversa ("The patch format is too large…") que o PowerShell tenta executar | 3905–3906 |
| 2 | *Here-strings* `@" … "@` fechados com `"` sozinho em vez de `"@` (40 ocorrências): o resto do arquivo vira uma única string e a análise falha | ex.: 91, 202 |
| 3 | Here-strings **expansíveis** (`@"`) com `${VAR}` e `$(...)` no conteúdo (docker-compose, Makefile, JS): o PowerShell substituiria por vazio, corrompendo os arquivos. Deveria ser `@' … '@` | 71 linhas |
| 4 | Laço escrito em **sintaxe Python** dentro do PowerShell: `for router_name in [...]:` e `Write-File(f"…")` | 8877–8878 |
| 5 | A pasta `nginx/` não está na lista de diretórios criados, então `Write-File "nginx/nginx.conf"` falha | 3918–3926 |
| 6 | `Set-Content -Encoding UTF8` no Windows PowerShell 5.1 grava **BOM** em todos os arquivos (o `.env` passaria a ter a primeira chave inválida) | 25 |
| 7 | Caminho fixo `C:\Users\...\Documents\New project\ticket-system` (sobrescreveria o projeto existente) | 7, 3914 |

## Erros no código Python gerado

| # | Problema | Exemplo |
|---|---|---|
| 8 | **Indentação perdida** em praticamente todas as classes e funções → `IndentationError` | `auth.py`, `models.py`, `schemas.py` |
| 9 | Formatação Markdown "comeu" os sublinhados duplos: `__name__`→`name`, `__file__`→`file`, `__init__`→`init`, `__tablename__`→`tablename`, `__init__.py`→`init.py` | 8725, 8863, 8909, 1987, 8868 |
| 10 | `allow_methods=['*']` virou `['']` (CORS bloquearia tudo) | 8777 |
| 11 | `main.py` importa os routers `auth`, `companies`, `tickets`, `users`, `dashboard`, `audit` que **nunca são gerados**; outros 14 são apenas stubs | 8714 |
| 12 | `/health` usa `datetime.utcnow()` sem importar `datetime` | 8840 |
| 13 | `conn.execute('SELECT 1')` com string pura — inválido no SQLAlchemy 2 (exige `text()`) | 1757, 5228 |
| 14 | Modelo `AuditLog` com `ForeignKey('tenants.id')` para tabela inexistente, `JSON` não importado, `back_populates='audit_logs'` sem o lado correspondente e `json.dumps()` gravado numa coluna `JSON` (dupla codificação) | 9487+ |
| 15 | `config.py`: `SECRET_KEY` obrigatório sem padrão (app não sobe sem `.env`), `CORS_ORIGINS: List[str]` exige JSON no `.env`, `EMAIL_FROM` com domínio `.local` reprovado pelo `EmailStr` | 4943+ |
| 16 | `auth.py` compara `ticket.status in ['open', ...]` (strings) com Enum e `User.id == payload['sub']` (string vs int) | 8583+ |
| 17 | Templates de e-mail usam `{% extends "base.html" %}{% block content %}`, mas o `base.html` usa `{{ content }}` em vez de um bloco → o corpo do e-mail nunca seria renderizado | 8896+ |
| 18 | Monitor de SLA reenviaria **os mesmos alertas a cada 15 minutos** (não registra o envio) | 9219+ |
| 19 | `get_company_business_hours` lê colunas que não existem no modelo (`business_hours_start` etc.) | 9236 |

## Problemas em dependências e testes

| # | Problema |
|---|---|
| 20 | `requirements.txt` com pacotes inexistentes ou com nome errado (`opentelemetry-instrumentor-fastapi`, `rules==3.0.0`), `pydantic` duplicado, ferramentas de teste/carga (`pytest`, `locust`, `playwright`) misturadas às de produção e pacotes pesados que exigem bibliotecas nativas no Windows (`weasyprint`/GTK, `python3-saml`/xmlsec, `sentence-transformers`/torch) para funcionalidades que não existiam |
| 21 | `tests/conftest.py` usa `AsyncClient(app=app)` (removido no httpx 0.28) com `with` em vez de `async with` |
| 22 | `test_token_decode` espera `sub == 1` (int), mas o python-jose exige `sub` string |
| 23 | Testes de modelo usam `UserStatus`/`SUPER_ADMIN`, que não existem no projeto em funcionamento |

## Problemas encontrados no projeto Fase 1 (base)

| # | Problema | Correção |
|---|---|---|
| 24 | `services/audit_service.py`, `email_service.py` e `sla_service.py` eram **pastas vazias** com nome `.py` | Substituídas por módulos reais |
| 25 | Upload deixava arquivo órfão no disco se a gravação no banco falhasse | Remoção do arquivo em caso de erro |
| 26 | Limite e extensões de upload fixos no código | Agora configuráveis no `.env` |
| 27 | Imports não utilizados (`datetime` em `auth.py`, `models.py`, `dashboard.py`) | Removidos |

## Resultado

- 31 testes automatizados passando (19 originais + 12 novos para auditoria, SLA e e-mail).
- `ruff check .` sem erros.
- Projeto pronto para abrir no VS Code (F5 roda a API com depurador) e publicar no GitHub
  com CI configurado.

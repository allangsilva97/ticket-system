# Como contribuir

Obrigado pelo interesse! Este guia explica como propor mudanças.

## Ambiente

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

No VS Code, a tarefa **Setup: criar venv e instalar dependências** faz tudo isso.

## Fluxo de trabalho

1. Abra uma *issue* descrevendo o bug ou a funcionalidade (use os templates).
2. Crie uma branch a partir de `main`: `feat/nome-curto`, `fix/nome-curto` ou `docs/nome-curto`.
3. Faça commits pequenos com mensagens no padrão [Conventional Commits](https://www.conventionalcommits.org/pt-br/):
   `feat: adiciona filtro por categoria`, `fix: corrige cálculo de SLA`.
4. Antes de abrir o PR, rode:

   ```bash
   ruff check .
   pytest
   ```

5. Abra o Pull Request preenchendo o template. O CI precisa passar.

## Padrões de código

- Python 3.10+, linha de até 120 caracteres, lint com **ruff** (`pyproject.toml`).
- Toda regra de permissão nova precisa de teste (veja `tests/test_api.py`).
- Toda alteração de dados feita por um endpoint deve gerar registro de auditoria
  (`services/audit_service.log`) na **mesma transação**.
- Notificações por e-mail rodam em `BackgroundTasks` e nunca podem quebrar a requisição.
- Não faça commit de `.env`, bancos `.db` ou arquivos em `uploads/`.

## Mudanças no banco

O projeto ainda não usa migrações (Alembic está no roadmap). Ao adicionar colunas, documente no
`CHANGELOG.md` e explique como atualizar bancos existentes.

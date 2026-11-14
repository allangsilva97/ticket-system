# Política de segurança

## Reportando uma vulnerabilidade

**Não abra uma issue pública** para problemas de segurança. Use o recurso
[Private vulnerability reporting](https://docs.github.com/pt/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
do GitHub (aba **Security → Report a vulnerability**) com:

- descrição do problema e impacto;
- passos para reproduzir;
- versão/commit afetado.

Respondemos em até 7 dias.

## Checklist para produção

- [ ] `SECRET_KEY` aleatório com 32+ caracteres (o app avisa no log se for o padrão).
- [ ] `.env` fora do controle de versão (já está no `.gitignore`).
- [ ] HTTPS na frente da aplicação (proxy reverso: nginx, Caddy, Traefik…).
- [ ] `CORS_ORIGINS` restrito ao(s) domínio(s) reais.
- [ ] Banco gerenciado (PostgreSQL) com backup, em vez de SQLite.
- [ ] Rodar com **um worker** ou mover o limitador de login para um armazenamento compartilhado (Redis).
- [ ] Credenciais SMTP de uma conta dedicada (ex.: senha de app).

## Proteções existentes

- Senhas com bcrypt; tokens JWT com expiração.
- Bloqueio temporário após 5 falhas de login por conta/IP (20 por IP).
- Cadastro aberto apenas para o primeiro usuário; depois, só admins criam contas.
- Anexos servidos apenas por endpoint autenticado, com checagem de permissão.
- Conteúdo de usuário escapado nos e-mails HTML.
- Trilha de auditoria imutável com usuário e IP.

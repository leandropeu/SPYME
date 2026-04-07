# Prontidao Comercial, Seguranca e LGPD

## Estado atual

O projeto esta funcional para operacao local e demonstracao:

- autenticacao por usuario e token
- perfis `admin`, `operator` e `viewer`
- persistencia em banco SQLite
- eventos, backups e monitoramento periodico

## Bloqueadores para comercializacao

Antes de vender esta aplicacao como produto, estes pontos devem ser tratados como obrigatorios:

1. Migrar de SQLite para um banco transacional de servidor, preferencialmente PostgreSQL.
   Motivo: o SQLite sofre com `database is locked` sob concorrencia de monitoramento, login, backup e operacoes administrativas.

2. Tirar segredos padrao do ambiente.
   Motivo: o projeto ainda aceita valores de desenvolvimento como `SPYGYM_SECRET_SEED` e credenciais administrativas default.

3. Implementar rate limiting e politica de bloqueio para login.
   Motivo: hoje nao existe limitacao contra forca bruta.

4. Mudar o armazenamento do token no frontend.
   Motivo: `localStorage` aumenta impacto de XSS. O ideal comercial e cookie `HttpOnly`, `Secure`, `SameSite`.

5. Criar trilha de auditoria.
   Motivo: alteracoes de usuarios, exclusoes, login/logout, backups e acoes administrativas precisam de log rastreavel.

6. Formalizar retencao e descarte de dados.
   Motivo: LGPD exige minimizacao, prazo de retencao e descarte seguro.

7. Criptografar backups e definir controle de acesso.
   Motivo: backup hoje e funcional, mas precisa de protecao em repouso e governanca.

8. Definir politica de resposta a incidente e rotacao de credenciais.
   Motivo: exigencia operacional minima para ambiente comercial.

## Controles recomendados

### Aplicacao

- Forcar HTTPS em producao
- Adicionar `Secure` e `HttpOnly` nos tokens quando migrar para cookie
- Adicionar rate limiting por IP e por usuario
- Validar senhas com politica minima de complexidade e historico
- Implementar MFA para perfis administrativos
- Registrar logs estruturados sem expor segredos
- Separar ambiente `dev`, `staging` e `prod`

### Banco de dados

- Migrar para PostgreSQL
- Criar rotina de backup cifrado
- Testar restauracao periodicamente
- Aplicar usuario de banco com privilegios minimos
- Monitorar locks, latencia e crescimento

### LGPD

- Mapear dados pessoais coletados
- Definir base legal por fluxo
- Implementar processo de exportacao, correcao e exclusao de dados
- Exibir politica de privacidade e termos de uso
- Formalizar controle de operadores e encarregado
- Revisar contratos com provedores e suboperadores

## Checklist minimo antes de subir em producao

- `SPYGYM_AUTO_SEED_DEMO=false`
- credenciais iniciais removidas
- segredo criptografico exclusivo por ambiente
- frontend servido por HTTPS
- backend atras de proxy reverso
- banco fora de SQLite
- logs centralizados
- backups cifrados e com teste de restauracao
- monitoramento de erro e disponibilidade
- revisao de seguranca e pentest basico

## Ferramentas internas do projeto

- Auditoria de banco: `py -3 scripts\\audit_spygym_db.py`

Esse documento nao substitui consultoria juridica ou DPO, mas serve como baseline tecnico para a evolucao do produto.

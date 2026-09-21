# 01 — Coverage Manifest

**Auditoria:** SmartServ  
**Commit:** `be3286d01735592b84ffc6c857d5efad7a460cfb`  
**Data:** 2026-09-13  
**Estado:** COMPLETO

---

## BACKEND — Código Fonte

| Arquivo | Tipo | Status | Categorias | Achados | Observações |
|---|---|---|---|---|---|
| `SmartservApplication.java` | entrypoint | AUDITADO | arquitetura, config | — | Composição limpa via IoC manual |
| `config/EnvConfig.java` | configuração | AUDITADO | config, segurança | BUILD-001 | NPE em runtime se env var ausente |
| `config/IoCContainer.java` | DI manual | AUDITADO | arquitetura | ARCH-002 | IoC manual funcional mas acoplado |
| `config/RoutesConfig.java` | roteamento | AUDITADO | segurança, arquitetura | — | before/beforeMatched correto |
| `config/CorsConfig.java` | CORS | AUDITADO | segurança | SEC-001 | anyHost() em produção |
| `config/ExceptionConfig.java` | erros | AUDITADO | segurança, qualidade | CONTROL-001 | Boa separação sem stack trace |
| `config/ServerConfig.java` | servidor | AUDITADO | operação | — | Configuração cuidadosa |
| `config/LogsConfig.java` | logging | AUDITADO | operação | PROB-001 | Log level dev em arquivo divergente |
| `config/OpenApiConfig.java` | docs | NÃO FOI POSSÍVEL VERIFICAR | — | — | Arquivo não lido; funcionalidade observada via rotas |
| `security/AuthMiddleware.java` | autenticação | AUDITADO | segurança | CONTROL-002, SEC-002 | OPTIONS bypass correto; `before` global |
| `security/AuthorizationMiddleware.java` | autorização | AUDITADO | segurança | CONTROL-003 | Verificação server-side real |
| `security/AuthContext.java` | contexto | AUDITADO | segurança | — | Imutável, correto |
| `security/jwt/JwtIssuer.java` | JWT | AUDITADO | segurança | CONTROL-004 | HMAC256, issuer, expiração |
| `security/jwt/JwtValidator.java` | JWT | AUDITADO | segurança | CONTROL-004 | Validação com issuer |
| `security/jwt/JwtConstants.java` | constantes | AUDITADO | segurança | — | 8h de duração — aceitável para contexto |
| `security/password/BCryptPasswordHasher.java` | criptografia | AUDITADO | segurança | CONTROL-005 | BCrypt cost 12, correto |
| `security/password/PasswordHasher.java` | interface | AUDITADO | arquitetura | — | Boa abstração |
| `infrastructure/database/ConnectionFactory.java` | banco | AUDITADO | persistência | CONTROL-006, DB-001 | HikariCP correto; maxLifetime alto |
| `infrastructure/jdbc/JdbcCardapioDAO.java` | DAO | AUDITADO | persistência, segurança | CONTROL-007 | PreparedStatement em todas as ops |
| `infrastructure/jdbc/JdbcFuncionarioDAO.java` | DAO | AUDITADO | persistência, segurança | CONTROL-007, CODE-001 | PS ok; senhaHash null em mapFuncionario |
| `infrastructure/jdbc/JdbcPedidoDAO.java` | DAO | AUDITADO | persistência, segurança | CONTROL-007, CONTROL-008, DB-002 | Transação manual no insert |
| `infrastructure/jdbc/JdbcItemPedidoDAO.java` | DAO | AUDITADO | persistência | — | PreparedStatement correto |
| `infrastructure/jdbc/JdbcTransactionManager.java` | transação | AUDITADO | persistência | ARCH-001 | Implementação VAZIA — dead code |
| `service/LoginService.java` | serviço | AUDITADO | segurança, domínio | CONTROL-009, SEC-003 | Brute-force bem implementado; race condition teórica |
| `service/FuncionarioService.java` | serviço | AUDITADO | domínio, segurança | CONTROL-010, CODE-002 | Owner check ok; gerente bypassa senha atual |
| `service/CardapioService.java` | serviço | AUDITADO | domínio | — | Correto |
| `service/PedidoService.java` | serviço | AUDITADO | domínio, segurança | CONTROL-011, DOMAIN-001, DOMAIN-002 | Owner check ok; sem máquina de estados |
| `model/Funcionario.java` | modelo | AUDITADO | domínio | DOMAIN-003 | Anêmico — setters públicos irrestrictos |
| `model/Pedido.java` | modelo | AUDITADO | domínio | DOMAIN-003 | Anêmico — mutável livremente |
| `model/ItemCardapio.java` | modelo | AUDITADO — SEM ACHADOS CRÍTICOS | domínio | — | — |
| `model/ItemPedido.java` | modelo | AUDITADO | domínio | — | — |
| `model/GarcomPedido.java` | modelo | AUDITADO — SEM ACHADOS | domínio | — | Value Object implícito |
| `enums/FuncionarioFuncoes.java` | enum | AUDITADO | segurança | CONTROL-012 | Implementa RouteRole do Javalin |
| `enums/PedidoStatus.java` | enum | AUDITADO | domínio | DOMAIN-002 | Status definidos mas sem transições |
| `enums/CardapioCategoriaItem.java` | enum | AUDITADO — SEM ACHADOS | domínio | — | — |
| `validator/FuncionarioValidator.java` | validação | AUDITADO | domínio | — | Validações razoáveis |
| `validator/LoginValidator.java` | validação | AUDITADO | domínio | — | — |
| `validator/CardapioValidator.java` | validação | AUDITADO | domínio | — | — |
| `validator/PedidoValidator.java` | validação | AUDITADO | domínio | CODE-003 | `validaritens` é privado — nunca chamado na validation pública |
| `routes/CardapioRoutes.java` | roteamento | AUDITADO | segurança | — | Roles corretas |
| `routes/FuncionarioRoutes.java` | roteamento | AUDITADO | segurança | SEC-004 | `GET /funcionarios/{id}` usa `values()` — todos os roles |
| `routes/PedidoRoutes.java` | roteamento | AUDITADO | segurança | — | Roles corretas |
| `routes/LoginRoutes.java` | roteamento | AUDITADO | segurança | — | Sem role = público, correto |
| `mapper/CardapioMapper.java` | mapper | AUDITADO — SEM ACHADOS | arquitetura | — | — |
| `mapper/FuncionarioMapper.java` | mapper | AUDITADO — SEM ACHADOS | arquitetura | — | — |
| `mapper/PedidoMapper.java` | mapper | AUDITADO — SEM ACHADOS | arquitetura | — | — |
| `exception/*.java` (6 arquivos) | exceções | AUDITADO | qualidade | — | Hierarquia clara e adequada |
| `shared/normalization/*.java` (4 arquivos) | normalização | AUDITADO | domínio | — | Normalizers adequados |

---

## DATABASE

| Arquivo | Tipo | Status | Categorias | Achados | Observações |
|---|---|---|---|---|---|
| `01_create_funcionarios.sql` | schema | AUDITADO | banco | CONTROL-013, DB-003 | Constraints, triggers ok; sem FK para validar funcao |
| `02_create_cardapio.sql` | schema | AUDITADO | banco | CONTROL-013 | Constraints bem definidas |
| `03_create_pedidos.sql` | schema | AUDITADO | banco | DB-002, DB-004 | FK para funcionarios; sem FK com CHECK para status cruzado |
| `04_create_item_pedido.sql` | schema | AUDITADO | banco | CONTROL-014, DB-005 | UNIQUE constraint por pedido+item; CASCADE DELETE |
| `05_insert_funcionarios.sql` | seed | AUDITADO | segurança | SEC-005 | Hashes BCrypt (não plaintext), senha padrão única para todos |
| `06_insert_cardapio.sql` | seed | AUDITADO — SEM ACHADOS | dados | — | Dados de teste realistas |
| `07_insert_pedidos.sql` | seed | AUDITADO — SEM ACHADOS | dados | — | — |
| `08_insert_item_pedidos.sql` | seed | AUDITADO — SEM ACHADOS | dados | — | — |

---

## INFRAESTRUTURA

| Arquivo | Tipo | Status | Categorias | Achados | Observações |
|---|---|---|---|---|---|
| `docker-compose.yml` | orquestração | AUDITADO | infra, segurança | SEC-006, INFRA-001 | healthcheck ok; porta 5433 exposta |
| `backend/Dockerfile` | build | AUDITADO | infra, build | INFRA-002 | Multistage correto; sem USER non-root |
| `.env` | configuração | AUDITADO | segurança | SEC-007 | Presente localmente; no .gitignore |
| `.gitignore` | git | AUDITADO | git | GIT-001 | .env ignorado; target ignorado |

---

## FRONTEND

| Arquivo | Tipo | Status | Categorias | Achados | Observações |
|---|---|---|---|---|---|
| `js/auth/login.js` | JS | AUDITADO | segurança | SEC-008 | Token em localStorage |
| `js/auth/componente_topo.js` | JS | AUDITADO — SEM ACHADOS | frontend | — | — |
| `js/cardapio/cadastrar.js` | JS | AUDITADO | frontend | FRONT-001 | URL hardcoded localhost |
| `js/cardapio/listar.js` | JS | AUDITADO | frontend, segurança | SEC-009, FRONT-001 | innerHTML com dados do banco |
| `js/cardapio/deletar.js` | JS | AUDITADO | frontend | FRONT-001 | URL hardcoded |
| `js/cardapio/buscar.js` | JS | AUDITADO — SEM ACHADOS | frontend | — | — |
| `js/funcionario/listar.js` | JS | AUDITADO | frontend, segurança | SEC-009, FRONT-001 | innerHTML, URL hardcoded |
| `js/funcionario/cadastrar.js` | JS | AUDITADO | frontend | FRONT-001 | URL hardcoded |
| `js/funcionario/deletar.js` | JS | AUDITADO | frontend | FRONT-001 | URL hardcoded |
| `js/funcionario/filtrar.js` | JS | AUDITADO — SEM ACHADOS | frontend | — | — |
| `js/funcionario/mascara-telefone.js` | JS | AUDITADO — SEM ACHADOS | frontend | — | — |
| `js/cozinha/listar-pedidos.js` | JS | AUDITADO — SEM ACHADOS | frontend | — | — |
| `pages/admin/*.html` (5 arquivos) | HTML | AUDITADO — SEM ACHADOS | frontend | — | Sem JS inline |
| `pages/garcom/*.html` (3 arquivos) | HTML | AUDITADO — SEM ACHADOS | frontend | — | — |
| `pages/cozinha/fila-pedidos.html` | HTML | AUDITADO — SEM ACHADOS | frontend | — | — |

---

## DOCUMENTAÇÃO

| Arquivo | Tipo | Status | Categorias | Achados | Observações |
|---|---|---|---|---|---|
| `README.md` | docs | AUDITADO | documentação | DOC-001 | Stack table incompleta (falta Java/Javalin) |
| `docs/backend/api.md` | docs | AUDITADO — SEM ACHADOS | documentação | — | Documentação útil |
| `docs/backend/auth.md` | docs | AUDITADO — SEM ACHADOS | documentação | — | Vazio mas arquivo existe |
| `docs/system-design/architecture.md` | docs | AUDITADO — SEM ACHADOS | documentação | — | — |
| `docs/system-design/decisions.md` | docs | AUDITADO — SEM ACHADOS | documentação | — | — |
| `docs/product/backlog.md` | docs | FORA DO ESCOPO | produto | — | — |

---

## GIT

| Verificação | Status | Observações |
|---|---|---|
| .env rastreado | NÃO RASTREADO — CORRETO | `git ls-files .env` retornou vazio |
| Secrets em histórico | NÃO ENCONTRADO | grep em commits não encontrou credenciais |
| Binários rastreados | NÃO ENCONTRADO | — |
| IDE metadata (.idea) | IGNORADO — CORRETO | Em .gitignore |
| target/ | IGNORADO — CORRETO | Em .gitignore |

---

## PROCEDIMENTOS EXECUTADOS

| Verificação | Ferramenta | Resultado |
|---|---|---|
| Árvore de arquivos | `find` | Executado |
| Leitura de source Java | `cat` | Executado — 40+ arquivos |
| Leitura de SQL | `cat` | Executado — 8 arquivos |
| Git log | `git log --oneline -50` | Executado |
| Git status | `git status` | Executado |
| Git ls-files para .env | `git ls-files` | Executado |
| Grep de secrets no código | `grep` | Executado |
| Grep de secrets no histórico | `git log -p` | Executado |
| Análise de frontend JS | `grep` + `cat` | Executado |
| Análise do Dockerfile | `cat` | Executado |
| Análise do docker-compose | `cat` | Executado |
| Build compilado | NÃO EXECUTADO | target/ existe mas não recompilado |
| Testes executados | NÃO EXECUTADO | Sem testes encontrados |
| OWASP Dependency-Check | NÃO EXECUTADO | Ferramenta não disponível |
| Análise estática (SpotBugs/PMD) | NÃO EXECUTADO | Ferramentas não disponíveis |

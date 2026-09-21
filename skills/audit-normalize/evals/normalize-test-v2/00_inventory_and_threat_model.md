# 00 — Inventário, Escopo e Threat Model

**Auditoria:** SmartServ  
**Data/Hora:** 2026-09-13T20:05 (UTC-3)  
**Auditor:** Auditoria Técnica Automatizada (Claude Sonnet 4.6 Thinking via Antigravity)  
**Estado:** COMPLETA

---

## 1. SNAPSHOT DA AUDITORIA

| Campo | Valor |
|---|---|
| Repositório | `/home/oliveira/Projects/JALA/SDA/SDAI/smartserv` |
| Branch | `main` |
| Commit HEAD | `be3286d01735592b84ffc6c857d5efad7a460cfb` |
| Mensagem HEAD | `fix(api): fix waiter order route` |
| Data do Commit | 2026-06-16 23:29:25 -0300 |
| Estado Working Tree | **DIRTY** — 7 arquivos modificados não commitados + 2 untracked |
| Branches locais | `main`, `recuperar-funcionario`, `recuperar-stash` |
| Runtime detectado | Java 21 (eclipse-temurin:21-jre-alpine via Docker) |

### Arquivos com modificações não commitadas
```
 M backend/src/main/java/.../config/LogsConfig.java
 M frontend/public/js/cardapio/cadastrar.js
 M frontend/public/js/funcionario/cadastrar.js
MM frontend/public/pages/admin/cadastro-funcionarios.html
 M frontend/public/pages/admin/cadastro-itens.html
 M frontend/public/pages/admin/lista-cardapio.html
 M frontend/public/pages/admin/lista-funcionarios.html
R  frontend/public/pages/cozinha/filapedidos.html -> fila-pedidos.html
?? frontend/public/js/cozinha/
?? frontend/public/pages/admin/lista-pedidos.html
```

> [!WARNING] A auditoria cobre o estado do working tree, não apenas o último commit. Os arquivos modificados foram lidos em seu estado atual.

---

## 2. DETECÇÃO DE STACK

| Componente | Tecnologia | Versão | Evidência |
|---|---|---|---|
| Linguagem | Java | 21 | `pom.xml` maven.compiler.source/target=21 |
| Servidor HTTP | Javalin | 7.2.2 | `pom.xml` dependency |
| Database | PostgreSQL | 15.1 | `docker-compose.yml` |
| Driver JDBC | PostgreSQL JDBC | 42.7.7 | `pom.xml` |
| Pool de Conexões | HikariCP | 5.1.0 | `pom.xml`, `ConnectionFactory.java` |
| JSON | Jackson Databind | 2.21.3 | `pom.xml` |
| Jackson Dates | jackson-datatype-jsr310 | 2.22.0 | `pom.xml` |
| JWT | Auth0 java-jwt | 4.5.2 | `pom.xml` |
| Hashing de Senha | favre BCrypt | 0.10.2 | `pom.xml` |
| Logging | SLF4J Simple | 2.0.13 | `pom.xml` |
| Compressão | brotli4j | 1.22.0 | `pom.xml` |
| OpenAPI/Swagger | javalin-openapi-plugin | 7.2.2 | `pom.xml` |
| Build System | Maven | 3.9 (via Docker) | `backend/Dockerfile` |
| Containerização | Docker + Compose | - | `docker-compose.yml` |
| Frontend | HTML + JS Vanilla | - | `frontend/public/` |
| Frontend Server | Nginx | latest | `docker-compose.yml` |
| CI/CD | Nenhum | — | Não encontrado |
| Testes | Nenhum | — | `src/test/` ausente |

---

## 3. INVENTÁRIO DE ARQUIVOS

### Backend (src/main)
```
br.com.debuggers.smartserv/
├── SmartservApplication.java
├── config/
│   ├── CorsConfig.java
│   ├── EnvConfig.java
│   ├── ExceptionConfig.java
│   ├── IoCContainer.java
│   ├── LogsConfig.java
│   ├── OpenApiConfig.java
│   ├── RoutesConfig.java
│   └── ServerConfig.java
├── controller/
│   ├── CardapioController.java
│   ├── FuncionarioController.java
│   ├── LoginController.java
│   └── PedidoController.java
├── dao/
│   ├── CardapioDAO.java
│   ├── FuncionarioDAO.java
│   ├── ItemPedidoDAO.java
│   ├── PedidoDAO.java
│   └── TransactionManager.java
├── dto/ (múltiplos request/response por domínio)
├── enums/
│   ├── CardapioCategoriaItem.java
│   ├── FuncionarioFuncoes.java
│   └── PedidoStatus.java
├── exception/
│   ├── AutenticacaoException.java
│   ├── AutorizacaoException.java
│   ├── ConflitoException.java
│   ├── DatabaseException.java
│   ├── RecursoNaoEncontradoException.java
│   └── ValidacaoException.java
├── infrastructure/
│   ├── database/ConnectionFactory.java
│   └── jdbc/
│       ├── JdbcCardapioDAO.java
│       ├── JdbcFuncionarioDAO.java
│       ├── JdbcItemPedidoDAO.java
│       ├── JdbcPedidoDAO.java
│       └── JdbcTransactionManager.java
├── mapper/
│   ├── CardapioMapper.java
│   ├── FuncionarioMapper.java
│   └── PedidoMapper.java
├── model/
│   ├── Funcionario.java
│   ├── GarcomPedido.java
│   ├── ItemCardapio.java
│   ├── ItemPedido.java
│   └── Pedido.java
├── routes/
│   ├── CardapioRoutes.java
│   ├── FuncionarioRoutes.java
│   ├── LoginRoutes.java
│   └── PedidoRoutes.java
├── security/
│   ├── AuthContext.java
│   ├── AuthMiddleware.java
│   ├── AuthorizationMiddleware.java
│   ├── jwt/
│   │   ├── AuthTokenDTO.java
│   │   ├── JwtConstants.java
│   │   ├── JwtIssuer.java
│   │   └── JwtValidator.java
│   └── password/
│       ├── BCryptPasswordHasher.java
│       └── PasswordHasher.java
├── service/
│   ├── CardapioService.java
│   ├── FuncionarioService.java
│   ├── LoginService.java
│   └── PedidoService.java
├── shared/normalization/
│   ├── CategoriaNormalizer.java
│   ├── FuncaoNormalizer.java
│   ├── StatusNormalizer.java
│   └── TelefoneNormalizer.java
└── validator/
    ├── CardapioValidator.java
    ├── FuncionarioValidator.java
    ├── LoginValidator.java
    └── PedidoValidator.java
```

### Database
```
database/
├── 01_create_funcionarios.sql
├── 02_create_cardapio.sql
├── 03_create_pedidos.sql
├── 04_create_item_pedido.sql
├── 05_insert_funcionarios.sql
├── 06_insert_cardapio.sql
├── 07_insert_pedidos.sql
└── 08_insert_item_pedidos.sql
```

### Frontend
```
frontend/public/
├── index.html
├── favicon.svg
├── components/ (navbar, sidebar, profile-tabs HTML)
├── css/ (por domínio: admin, garcom, cozinha, login)
├── js/
│   ├── auth/ (login.js, componente_topo.js)
│   ├── cardapio/ (buscar, cadastrar, deletar, listar)
│   ├── cozinha/ (listar-pedidos)
│   └── funcionario/ (buscar, cadastrar, deletar, filtrar, listar, mascara-telefone)
└── pages/ (admin, garcom, cozinha)
```

---

## 4. ESCOPO DA AUDITORIA

### IN SCOPE
```
backend/src/main/
database/*.sql
docker-compose.yml
backend/Dockerfile
.env (leitura, sem reproduzir segredos)
.gitignore
frontend/public/js/
frontend/public/pages/
README.md
docs/
git history (últimos 50 commits)
```

### OUT OF SCOPE
```
backend/target/               (artefatos gerados)
node_modules/                 (não presente)
frontend/public/assets/images/ (imagens binárias)
docs/images/assets/           (imagens)
.idea/                        (IDE metadata)
```

---

## 5. MATRIZ DE APLICABILIDADE

| Categoria | Status | Tecnologia / Razão |
|---|---|---|
| SQL Injection | APLICÁVEL | JDBC com PreparedStatement — auditado |
| XSS / HTML Injection | APLICÁVEL | Frontend JS usa innerHTML — auditado |
| IDOR / BOLA | APLICÁVEL | API REST com IDs de recurso — auditado |
| Autenticação | APLICÁVEL | JWT HMAC256 + BCrypt — auditado |
| Autorização / RBAC | APLICÁVEL | Role-based via FuncionarioFuncoes — auditado |
| CSRF | NÃO APLICÁVEL | API stateless + JWT Bearer — sem sessão de cookie |
| SSRF | NÃO APLICÁVEL | Nenhum HTTP client server-side encontrado |
| File Security / Upload | NÃO APLICÁVEL | Nenhum upload de arquivo encontrado |
| Secrets / Hardcoded | APLICÁVEL | .env presente, JWT_SECRET declarado |
| Criptografia | APLICÁVEL | BCrypt, HMAC256 JWT |
| Dados sensíveis em logs | APLICÁVEL | SLF4J com debug |
| Dependências / CVE | APLICÁVEL (parcial) | Maven sem análise OWASP Dependency-Check disponível |
| Infraestrutura Docker | APLICÁVEL | Dockerfile + Compose |
| Isolamento de Tenant | NÃO APLICÁVEL | Sistema single-tenant (restaurante único) |
| NoSQL Injection | NÃO APLICÁVEL | Nenhum banco NoSQL |
| OS Command Injection | NÃO APLICÁVEL | Nenhum exec/Runtime.getRuntime() |
| Template Injection | NÃO APLICÁVEL | Nenhum template engine server-side |
| Race Conditions | APLICÁVEL (condicional) | Operações de login têm atualizações não atômicas |

---

## 6. PROPÓSITO E MODELO MENTAL DO SISTEMA

### Objetivo
Sistema de gestão operacional para restaurante, focado em:
- Registro e acompanhamento de pedidos por mesa
- Gerenciamento de funcionários (CRUD)
- Gerenciamento de cardápio (CRUD)
- Controle de acesso por perfil de função

### Atores
| Ator | Papel | Permissões principais |
|---|---|---|
| GERENTE | Administrador | Tudo — funcionários, cardápio, pedidos |
| GARCOM | Operacional | Criar/gerir pedidos próprios, ver cardápio |
| COZINHA | Operacional | Ver pedidos, atualizar status |
| CAIXA | Operacional | Ver/filtrar pedidos por status |

### Fluxo Principal
```
Browser (Nginx) → API (Javalin/Java 21) → PostgreSQL 15
        ↕ JWT Bearer Token
Login → JWT gerado → localStorage → headers Authorization
```

### Entidades do Domínio
- **Funcionario** — identidade, credenciais, bloqueio de conta
- **ItemCardapio** — produto, preço, categoria, disponibilidade
- **Pedido** — mesa, garçom, status, valor total
- **ItemPedido** — item do cardápio dentro de um pedido, quantidade, preço snapshot

---

## 7. THREAT MODEL

### Ativos a Proteger
1. Credenciais dos funcionários (senha_hash, email)
2. Dados de pedidos (valor financeiro)
3. Integridade do cardápio (preços)
4. Controle de acesso por função
5. JWT_SECRET (segredo de assinatura)

### Superfícies de Ataque
1. **POST /login** — endpoint público, aceita email/senha
2. **Todos os endpoints /funcionarios, /cardapio, /pedidos** — requerem JWT válido
3. **Frontend** — JS no browser com token no localStorage
4. **Docker Compose** — .env lido em runtime, porta 5433 exposta ao host

### Trust Boundaries
```
[Browser] --Bearer JWT--> [Javalin API] --JDBC--> [PostgreSQL]
          não confiável        confiar          confiável
```

### Controles Identificados
- JWT HMAC256 com issuer validation
- BCrypt cost factor 12 para senhas
- Brute-force protection: bloqueio após 5 tentativas (30 min)
- RBAC em nível de rota e serviço
- PreparedStatement em todos os DAOs (auditados)
- CORS configurado (wildcard — veja SEC-001)
- ErrorResponse padronizado sem stack trace ao cliente

### Dados Sensíveis
- `senha_hash` — armazenada apenas como BCrypt hash no banco
- `JWT_SECRET` — em .env (ignorado no git — CONFIRMADO)
- `DB_PASSWORD` — em .env (ignorado no git — CONFIRMADO)
- Seed file `05_insert_funcionarios.sql` contém hashes BCrypt (não senhas plaintext)

# 02 — Relatório Analítico

**Auditoria:** SmartServ  
**Commit:** `be3286d01735592b84ffc6c857d5efad7a460cfb`  
**Data:** 2026-09-13  
**Auditor:** Auditoria Técnica Automatizada (Claude Sonnet 4.6 Thinking via Antigravity)

---

## 1. RESUMO EXECUTIVO

O SmartServ é um sistema de gestão operacional para restaurante, desenvolvido com Java 21 + Javalin, PostgreSQL 15, JDBC puro com HikariCP, JWT para autenticação e BCrypt para senhas. O projeto demonstra nível de maturidade **Intermediário a Acadêmico Avançado**, com decisões de segurança acima da média para o contexto, organização de código acima da média e algumas lacunas técnicas identificáveis.

**Pontos fortes expressivos:**
- SQL Injection: ZERO vulnerabilidades encontradas — PreparedStatement em 100% das operações
- Autenticação JWT correta (HMAC256, issuer, expiração)
- BCrypt com cost factor 12
- Brute-force protection com lockout por conta
- Owner check server-side para garçom e funcionário
- Schema PostgreSQL com CHECK constraints abrangentes

**Problemas que requerem atenção:**
- XSS via innerHTML com dados do servidor (P1) → SEC-009
- Sem testes automatizados — cobertura zero
- CORS wildcard em produção (P2) → SEC-001
- JWT em localStorage (P2) → SEC-008
- URLs hardcoded no frontend (P2) → FRONT-001
- TransactionManager como casca vazia (P2) → ARCH-001
- Ausência de máquina de estados para pedidos → DOMAIN-001
- Container root → INFRA-001

---

## 2. SNAPSHOT DA AUDITORIA

| Campo | Valor |
|---|---|
| Repositório | `/home/oliveira/Projects/JALA/SDA/SDAI/smartserv` |
| Branch | `main` |
| Commit | `be3286d01735592b84ffc6c857d5efad7a460cfb` |
| Data/Hora | 2026-09-13T20:05 UTC-3 |
| Estado Working Tree | DIRTY (7 modificados, 2 untracked) |
| Arquivos auditados | 55+ arquivos |
| Testes executados | NENHUM (sem test suite) |

---

## 3. PROPÓSITO DO SISTEMA

**FATO:** Sistema de gestão interna para restaurante com controle de pedidos, cardápio e funcionários.

**FATO:** Três perfis operacionais (GARCOM, COZINHA, CAIXA) e um administrativo (GERENTE).

**INFERÊNCIA:** Projeto acadêmico/educacional em desenvolvimento ativo — indicado por README, equipe "Debuggers", status "Em Desenvolvimento".

**Casos de Uso Implementados:**
1. Login com brute-force protection
2. CRUD de funcionários (somente GERENTE)
3. CRUD de cardápio (somente GERENTE)
4. Criação e gestão de pedidos por garçom
5. Atualização de status de pedidos (cozinha, gerente, garçom, caixa)
6. Visualização de fila de pedidos (cozinha)
7. Troca de senha (própria ou por gerente)

**Funcionalidades documentadas no README mas não implementadas:**
- Estoque (mencionado no README como objetivo)
- Gerenciamento de mesas (tela existe, mas sem backend correspondente completo)
- Pagamento/finalização (CAIXA existe como role mas sem endpoint específico)

---

## 4. STACK DETECTADA

| Componente | Tecnologia | Versão |
|---|---|---|
| Linguagem | Java | 21 (LTS) |
| Servidor HTTP | Javalin | 7.2.2 |
| Banco | PostgreSQL | 15.1 |
| Driver JDBC | postgresql | 42.7.7 |
| Pool de Conexões | HikariCP | 5.1.0 |
| JSON | Jackson Databind | 2.21.3 |
| JWT | Auth0 java-jwt | 4.5.2 |
| Senha | favre BCrypt | 0.10.2 |
| Logging | SLF4J Simple | 2.0.13 |
| OpenAPI | javalin-openapi-plugin | 7.2.2 |
| Build | Maven (Shade plugin) | 3.9 |
| Container | Docker + Compose | — |
| Frontend server | Nginx | latest |
| Frontend | HTML + JS Vanilla | — |
| CI/CD | Nenhum | — |
| Testes | Nenhum | — |

---

## 5. ARQUITETURA

### Visão Geral

```
┌────────────────────────────────────────────────────────────────┐
│                     Docker Compose                             │
│  ┌──────────┐    ┌──────────────────────┐    ┌─────────────┐  │
│  │  Nginx   │───▶│    Javalin API       │───▶│ PostgreSQL  │  │
│  │ :8000    │    │    Java 21 :7070     │    │  15.1 :5432 │  │
│  │ (front)  │    │                      │    │             │  │
│  └──────────┘    │ Routes → Controller  │    └─────────────┘  │
│       ▲          │ → Service → DAO      │                      │
│       │          │ → JDBC → HikariCP    │                      │
│  Browser         └──────────────────────┘                      │
│  (JWT em localStorage)                                         │
└────────────────────────────────────────────────────────────────┘
```

### Camadas (Backend)

O projeto segue uma **Layered Architecture** clara e bem organizada para seu contexto:

```
Routes (roteamento + roles)
    ↓
Controller (deserialização, coordenação)
    ↓
Service (regras de negócio, validação, autorização)
    ↓
DAO Interface (contrato de persistência)
    ↓
JdbcDAO (implementação JDBC)
    ↓
ConnectionFactory (HikariCP)
    ↓
PostgreSQL
```

**Dependências vão do alto nível para baixo** — correto. Services dependem de interfaces DAO (DIP aplicado). Nenhuma dependência circular detectada.

### IoC Manual

O projeto implementa **injeção de dependências manual** via `IoCContainer.java` — sem Spring ou framework de DI. Esta é uma decisão pedagógica intencional e adequada ao contexto acadêmico. O container instancia todas as dependências em cascata e as injeta corretamente.

**Avaliação:** A IoC manual funciona corretamente para este tamanho de projeto. A única inconsistência é a dupla instanciação de `EnvConfig` (ARCH-002).

### Separação de Responsabilidades

| Camada | O que faz | Adequado? |
|---|---|---|
| Routes | Define path, método HTTP e roles autorizadas | ✅ Sim |
| Controller | Deserializa request, chama service, serializa response | ✅ Sim |
| Service | Valida input, verifica autorização, executa regras de negócio | ✅ Sim |
| DAO | Operações CRUD via JDBC | ✅ Sim |
| Validator | Validação de campos | ✅ Sim |
| Normalizer | Normalização de dados (funcao, categoria, status, telefone) | ✅ Sim |
| Mapper | Conversão modelo ↔ DTO | ✅ Sim |

### O que NÃO funciona na arquitetura

- `JdbcTransactionManager` — casca vazia (ARCH-001)
- `TransactionManager` interface não utilizada para nada real
- Modelos anêmicos sem invariantes encapsuladas (DOMAIN-003)

---

## 6. MODELO DE DOMÍNIO

### Entidades Identificadas

```
Funcionario         ItemCardapio        Pedido
─────────────       ────────────        ──────────
id                  id                  id
nome                nome                mesa
funcao (enum)       descricao           status (enum)
email               preco               garcom (GarcomPedido)
senhaHash           categoria (enum)    itens [ItemPedido]
telefone            disponivel          valorTotal
ativo               dataCriacao         dataCriacao
tentativasLogin     dataAtualizacao     dataAtualizacao
bloqueadoAte
ultimoLogin
dataCriacao
dataAtualizacao
```

### Avaliação do Domínio

**FATO:** O domínio é anêmico — entidades são portadoras de dados com setters públicos irrestrictos, sem invariantes encapsuladas. A lógica de negócio vive nos Services.

**Para o contexto:** É aceitável. Domínio anêmico é amplamente utilizado e não é errado per se — é uma troca consciente de encapsulamento por simplicidade.

**Regras identificadas:**
1. Pedido com status ≠ PENDENTE não pode ter itens modificados
2. Garçom só pode manipular pedidos próprios
3. Funcionário comum só pode ver/alterar seu próprio perfil
4. Email único por funcionário
5. Nome único por item do cardápio
6. Item deve estar disponível para ser adicionado ao pedido
7. Pedido com último item removido → pedido deletado automaticamente
8. Senha nova deve diferir da atual (para não-gerente)

**Problema:** Regra 1 está duplicada em 4 locais (DOMAIN-002). Regras 2-3 estão corretamente nos services. Sem máquina de estados explícita (DOMAIN-001).

---

## 7. FLUXOS PRINCIPAIS

### Fluxo de Login
```
POST /login (público)
    → LoginController.login()
    → LoginService.autenticar()
        → Validar email/senha não vazios
        → findByEmailWithPassword()
        → verificarAtivo() (null ou inativo → 401 genérico)
        → verificarBloqueio() (bloqueado_ate > now → 401 genérico)
        → BCrypt.verify(senha, hash)
        → Se falha: incrementar tentativas; se ≥5: bloquear 30min
        → Se sucesso: zerar tentativas, atualizar ultimo_login
        → Gerar JWT (HMAC256, 8h, sub=id, role=funcao)
    → LoginResponse {token, id, funcao}
```

### Fluxo de Requisição Autenticada
```
ANY /endpoint (protegido)
    → before: AuthMiddleware.handle()
        → Extrair Bearer token
        → JwtValidator.validarJwt() → DecodedJWT
        → Criar AuthContext {id, role} no contexto Javalin
    → beforeMatched: AuthorizationMiddleware.handle()
        → Verificar role ∈ routeRoles()
    → Controller → Service → DAO → PostgreSQL
    → Response ou Exception → ExceptionConfig → ErrorResponse JSON
```

### Fluxo de Pedido (Garçom)
```
POST /pedidos
    → Validar request (mesa > 0, itens não vazios)
    → Verificar cada item do cardápio: existe? está disponível?
    → Calcular valorTotal = Σ(preco × quantidade)
    → Transação:
        → INSERT INTO pedidos (mesa, id_funcionario, valor_total)
        → INSERT INTO item_pedido × N
        → COMMIT (ou ROLLBACK se erro)
    → PedidoResponse
```

---

## 8. QUALIDADE DO CÓDIGO

### Pontos Positivos
- Nomenclatura consistente e em Português (adequada para projeto BR)
- Comentários relevantes (em Português)
- Try-with-resources para Connection e PreparedStatement — correto
- Logging estruturado com SLF4J (log.error/debug/info com context)
- Hierarquia de exceções clara e mapeada para HTTP status codes
- Separação limpa de mappers e normalizers
- Uso de BigDecimal para preços monetários — correto

### Pontos de Atenção
- Modelos anêmicos com setters públicos (DOMAIN-003)
- `JdbcTransactionManager` vazio (ARCH-001)
- Convenção de nomenclatura violada: `validaritens` (CODE-003)
- `FuncionarioValidator` tem Logger com classe errada: `LoggerFactory.getLogger(FuncionarioService.class)` em vez de `FuncionarioValidator.class`
- DataCriacao/DataAtualizacao definidas no Java após insert em vez de serem lidas do banco — pode causar divergência de timezone

### Complexidade
- Métodos maiores: `PedidoService.atualizarQuantidade()` e `removerItem()` — longos mas legíveis
- Nenhum método com complexidade ciclomática problemática
- Classes bem dimensionadas para o escopo

---

## 9. SOLID

| Princípio | Status | Evidência |
|---|---|---|
| SRP | ✅ Aplicado | Controllers, Services, DAOs, Validators, Mappers separados |
| OCP | ⚠️ Parcial | DAO interfaces permitem extensão, mas Services são concretos |
| LSP | ✅ Não violado | Implementações de interfaces são corretas |
| ISP | ✅ Aplicado | Interfaces DAO com métodos específicos |
| DIP | ✅ Aplicado | Services dependem de interfaces, não de JdbcDAO diretamente |

---

## 10. DESIGN PATTERNS

| Pattern | Presente? | Evidência |
|---|---|---|
| DAO | ✅ Sim | CardapioDAO, FuncionarioDAO, PedidoDAO, ItemPedidoDAO (interface + implementação) |
| Repository (ish) | ✅ Parcial | Semanticamente similares a Repository |
| Strategy | ✅ Sim | PasswordHasher (BCryptPasswordHasher) |
| Facade | ✅ Implícito | IoCContainer como ponto único de composição |
| Middleware Chain | ✅ Sim | AuthMiddleware → AuthorizationMiddleware via before/beforeMatched |
| DTO | ✅ Sim | Request/Response por operação por entidade |
| Mapper | ✅ Sim | CardapioMapper, FuncionarioMapper, PedidoMapper |
| Builder | ❌ Não | Não necessário neste contexto |
| Observer | ❌ Não | Não necessário neste contexto |

---

## 11. BANCO E PERSISTÊNCIA

### Schema PostgreSQL — Avaliação

| Tabela | PK | UK | FK | Checks | Triggers | Avaliação |
|---|---|---|---|---|---|---|
| funcionarios | ✅ IDENTITY | ✅ email | — | ✅ funcao, nome, email, tentativas | ✅ data_atualizacao | ✅ Excelente |
| cardapio | ✅ IDENTITY | ✅ nome | — | ✅ categoria, preco, nome | ✅ data_atualizacao | ✅ Excelente |
| pedidos | ✅ IDENTITY | — | ✅ funcionarios | ✅ status, mesa, valor_total | ✅ data_atualizacao | ✅ Bom |
| item_pedido | ✅ IDENTITY | ✅ (pedido+item) | ✅ pedidos, cardapio | ✅ quantidade, preco | — | ✅ Bom |

**Positivo:**
- Uso de GENERATED ALWAYS AS IDENTITY (moderno, correto)
- Triggers automáticos para data_atualizacao (elegante)
- CHECK constraints abrangentes
- UNIQUE constraint composta em item_pedido

**Atenção:**
- valor_total denormalizado (DB-004) — risco de inconsistência
- Falta índice em pedidos.id_funcionario (DB-002)

### JDBC e Queries
- **SQL Injection: ZERO vulnerabilidades** — PreparedStatement em 100% das queries
- Try-with-resources garante fechamento de Connection, PreparedStatement e ResultSet
- HikariCP configurado corretamente com validação e keepalive

---

## 12. CONTRATO DOMÍNIO ↔ BANCO

| Aspecto | Domínio | Banco | Consistente? |
|---|---|---|---|
| Enum funcao | FuncionarioFuncoes {GARCOM, COZINHA, CAIXA, GERENTE} | CHECK funcao IN (...) | ✅ Sim |
| Enum categoria | CardapioCategoriaItem {PORCAO, BEBIDA, SOBREMESA, PRATO_PRINCIPAL} | CHECK categoria IN (...) | ✅ Sim |
| Enum status | PedidoStatus {PENDENTE, PREPARANDO, PRONTO, ENTREGUE, FINALIZADO, CANCELADO} | CHECK status IN (...) | ✅ Sim |
| Preço | BigDecimal | decimal(10,2) | ✅ Sim |
| Email único | Verificado no service | UNIQUE constraint | ✅ Dupla proteção |
| Nome item único | Verificado no service | UNIQUE constraint | ✅ Dupla proteção |
| Nullability senha | senhaHash nullable em modelo | VARCHAR(255) NOT NULL | ⚠️ Divergência (CODE-001) |
| DataCriacao | LocalDateTime | TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP | ⚠️ Definida no Java, não lida do DB pós-insert |

---

## 13. BUILD

- Maven com Shade plugin — fat JAR funcional
- Multistage Docker build (build + runtime) — correto e bem estruturado
- Eclipse Temurin 21 JRE Alpine — imagem leve e adequada
- Sem Maven Wrapper — dependência externa do Maven
- Sem perfis Maven para ambientes diferentes
- `mvn clean package -DskipTests` no Dockerfile — correto (não há testes)

---

## 14. GIT

**Positivos:**
- `.env` corretamente no .gitignore
- `target/` corretamente ignorado
- Mensagens de commit semânticas (feat, fix, refactor, docs)
- Histórico de commits legível e bem dividido

**Atenção:**
- Working tree dirty com 7 arquivos modificados (GIT-001)
- Branches `recuperar-funcionario` e `recuperar-stash` locais sem merge/close
- Nenhum secret encontrado no histórico dos últimos 50 commits

---

## 15. TESTES

**Situação:** Ausência total de testes automatizados. Diretório `src/test/` não encontrado.

**Impacto:**
- Nenhuma garantia de regressão
- Nenhuma validação automatizada de regras de negócio
- Qualquer refatoração pode quebrar comportamento existente sem detecção

**Não é incomum em projetos acadêmicos** — mas é a lacuna mais significativa para maturidade de software.

---

## 16. CI/CD

**Situação:** Nenhum pipeline CI/CD encontrado. Sem `.github/workflows/`, `.gitlab-ci.yml`, ou equivalente.

**Impacto:**
- Build manual
- Testes manuais (ou ausentes)
- Deploy manual via `docker-compose up`

**Para o contexto:** Aceitável para projeto local/acadêmico.

---

## 17. CONFIGURAÇÃO

**Correto:**
- Todas as configurações sensíveis via variáveis de ambiente
- `.env` no .gitignore
- EnvConfig centraliza leitura de env vars
- APP_ENV usado para configurar nível de log

**Problemas:**
- Sem validação de env vars obrigatórias (BUILD-001)
- CORS não configurado por ambiente (SEC-001)
- URLs hardcoded no frontend (FRONT-001)
- Sem `.env.example` para documentar variáveis necessárias

---

## 18. DOCUMENTAÇÃO

**Existente:**
- README.md com estrutura clara (objetivos, funcionalidades, setup)
- `docs/backend/api.md` com endpoints documentados
- `docs/system-design/` com arquitetura e decisões
- OpenAPI/Swagger gerado automaticamente em `/swagger`

**Gaps:**
- README com tabela de tecnologias incompleta (DOC-001)
- `docs/backend/auth.md` está vazio
- Sem `.env.example`
- Sem documentação de setup de desenvolvimento completo (Java 21, Maven)

---

## 19. OPERAÇÃO

**Positivos:**
- Health check no Docker Compose para PostgreSQL
- `depends_on: condition: service_healthy` — API aguarda banco
- Request logger configurado (path + status + tempo)
- Leak detection no HikariCP
- Log de startup/shutdown

**Gaps:**
- Sem health endpoint na API
- Sem métricas
- Container executa como root (INFRA-001)
- Sem restart policy para API (somente para postgres: `unless-stopped`)

---

## 20. TRADE-OFFS

| Decisão | Benefício | Custo | Avaliação |
|---|---|---|---|
| JDBC puro (sem ORM) | Controle total, sem magia, pedagogicamente claro | Mais código, sem migrations automáticas | ✅ Adequado para o contexto |
| IoC manual | Sem dependência de framework | Mais código, não escala bem | ✅ Adequado para este tamanho |
| JWT stateless | Sem sessão server-side, escalável | Token não revogável sem blacklist | ✅ Adequado |
| BCrypt cost 12 | Segurança maior | Login ~300ms | ✅ Adequado |
| Javalin (sem Spring) | Leve, simples, educativo | Menos ecosystem | ✅ Escolha coerente |
| SLF4J Simple | Zero config | Sem rotação de log, sem appenders | ✅ Adequado para dev |
| anyHost() CORS | Facilidade de dev | Risco em produção | ⚠️ Requer atenção |
| localStorage para JWT | Simples de implementar | Vulnerável a XSS | ⚠️ Risco se XSS ocorrer |

---

## 21. MATURIDADE PROFISSIONAL

**Classificação: INTERMEDIÁRIO → ACADÊMICO AVANÇADO**

**Justificativa:**

| Dimensão | Nota | Justificativa |
|---|---|---|
| Correção | 6/10 | Funcional, mas com gaps (sem testes, DB-004, SEC-003) |
| Arquitetura | 7/10 | Camadas claras, DIP aplicado, IoC manual. ARCH-001 pesa. |
| Domínio | 5/10 | Anêmico, sem máquina de estados, regras duplicadas |
| Qualidade de código | 6/10 | Boa nomenclatura, logging ok, mas sem testes e com dead code |
| Persistência | 7/10 | Schema excelente, JDBC correto. DB-004 pesa. |
| Segurança | 6/10 | SQL injection zero é excelente. SEC-009 e SEC-001 pesam. |
| Testes | 0/10 | Ausência total |
| Build | 6/10 | Maven + Docker multistage correto. Sem CI. |
| Git | 6/10 | Commits semânticos. Working tree dirty. Sem tags. |
| CI/CD | 0/10 | Inexistente |
| Configuração | 5/10 | Env vars ok. Sem validação. CORS wild. URLs hardcoded. |
| Documentação | 5/10 | README razoável mas incompleto |
| Operação | 4/10 | Health check no compose. Sem health endpoint. Root container. |
| Manutenibilidade | 5/10 | Estrutura boa, zero testes, dead code, domínio anêmico |
| Maturidade profissional | 5/10 | Bom para acadêmico. Não está pronto para produção real. |

---

## 22. SECURITY REVIEW (PASS 2)

> Resultados detalhados em `03_audit_ledger.md`. Resumo abaixo.

### Postura de Segurança Geral

O projeto demonstra **consciência de segurança acima da média para contexto acadêmico**:

- SQL Injection: **PROTEGIDO** — PreparedStatement 100%
- Autenticação: **ADEQUADA** — JWT HMAC256 + BCrypt 12
- Brute-force: **MITIGADO** — lockout após 5 tentativas, 30min
- Autorização: **IMPLEMENTADA** — RBAC + owner check server-side
- Secrets: **ADEQUADO** — fora do código e do git

### Vulnerabilidades / Riscos por Severidade

| Severidade | ID | Descrição |
|---|---|---|
| **P1** | SEC-009 | XSS via innerHTML com dados do servidor |
| **P2** | SEC-001 | CORS wildcard (anyHost) em produção |
| **P2** | SEC-004 | GET /funcionarios/{id} acessível por roles demais |
| **P2** | SEC-005 | Senha padrão única no seed |
| **P2** | SEC-006 | Porta PostgreSQL exposta no host |
| **P2** | SEC-008 | JWT em localStorage (risco potencializado por XSS) |
| **P3** | SEC-002 | Sem rate limiting por IP no /login |
| **P3** | SEC-003 | Race condition teórica nas tentativas de login |
| **P3** | SEC-007 | .env com secrets em texto plano (mitigado pelo gitignore) |

---

## 23. CORRELAÇÃO DE RISCOS

```
SEC-009 (XSS via innerHTML)
    +
SEC-008 (JWT em localStorage)
    =
Roubo de token de qualquer usuário por gerente malicioso
que insira HTML/JS no nome de um item do cardápio.

Caminho:
    GERENTE cria item cardápio com nome="<script>fetch('/api?t='+localStorage.getItem('tokenAutenticacao'))</script>"
    → GARCOM/COZINHA acessa /pages/admin/lista-cardapio.html
    → innerHTML renderiza o script
    → Token do GARCOM é enviado para servidor do atacante
    → Atacante usa token por até 8h (duração JWT)
```

Esta cadeia eleva a prioridade de SEC-009 para P1.

---

## 24. PONTOS FORTES

1. **Zero SQL Injection** — PreparedStatement em todos os DAOs
2. **BCrypt cost 12** — hashing correto de senhas
3. **JWT corretamente implementado** — HMAC256, issuer, expiração
4. **Brute-force protection** — lockout por conta com persistência em banco
5. **Owner check server-side** — garçom não acessa pedidos alheios
6. **Schema PostgreSQL robusto** — CHECK constraints, triggers, FKs
7. **Exception handling** — sem stack trace exposto ao cliente
8. **Separação de camadas** — arquitetura compreensível
9. **Docker com health check** — inicialização ordenada
10. **GENERATED ALWAYS AS IDENTITY** — uso de feature moderna do PostgreSQL

---

## 25. PROBLEMAS PRIORITÁRIOS

1. **[P1] SEC-009** — XSS via innerHTML (potencializado por SEC-008)
2. **[P1] BUILD-001** — NullPointerException se env var ausente
3. **[P2] ARCH-001** — TransactionManager vazio (dead code enganoso)
4. **[P2] SEC-001** — CORS wildcard em produção
5. **[P2] DB-004** — valor_total denormalizado sem garantia de integridade
6. **[P2] FRONT-001** — URLs hardcoded impedindo uso em produção
7. **[P2] INFRA-001** — Container executando como root
8. **[P2] DOMAIN-001** — Sem máquina de estados para pedidos
9. **[P0 para qualidade] Sem testes** — risco de regressão total

---

## 26. PLANO DE EVOLUÇÃO

### P0 — Correções Críticas

**SEC-009 — Sanitizar innerHTML**
```
Problema: XSS via innerHTML com dados do servidor
Objetivo: Eliminar vetor de XSS
Mudança: Substituir innerHTML = `...${dado}...` por textContent ou createElement+appendChild
Justificativa: Previne execução de JS injetado via dados do banco
Impacto esperado: Eliminação do risco de roubo de token
Esforço: 1-2 horas (alterações em cardapio/listar.js e funcionario/listar.js)
```

**BUILD-001 — Validar variáveis de ambiente**
```
Problema: NPE em startup se var ausente
Objetivo: Fail-fast com mensagem clara
Mudança: Adicionar requireNonNull com mensagens descritivas em EnvConfig
Esforço: 30 minutos
```

### P1 — Estabilização

**ARCH-001 — Resolver TransactionManager**
```
Problema: Implementação vazia é enganosa
Objetivo: Dead code removido ou interface corretamente implementada
Mudança: Remover JdbcTransactionManager ou implementar com Connection compartilhada
Esforço: 1-3 horas (remover é trivial; implementar é médio)
```

**SEC-001 — CORS por ambiente**
```
Problema: anyHost() em produção
Mudança: Usar APP_ENV para configurar origens específicas
Esforço: 30 minutos
```

**FRONT-001 — URL base configurável no frontend**
```
Problema: localhost hardcoded
Mudança: const API_BASE = window.API_BASE || 'http://localhost:7070' em arquivo de config JS
Esforço: 2-3 horas (10+ arquivos)
```

**INFRA-001 — Usuário não-root no Dockerfile**
```
Problema: Container como root
Mudança: Adicionar USER appuser no Dockerfile
Esforço: 15 minutos
```

### P2 — Qualidade e Arquitetura

**DOMAIN-001 — Máquina de estados para pedidos**
```
Problema: Qualquer status pode transicionar para qualquer outro
Mudança: Método podeTransicionarPara() em PedidoStatus com grafo de transições
Esforço: 2-4 horas
```

**DB-004 — Calcular valor_total via banco**
```
Mudança: Trigger para recalcular soma ou query com SUM(quantidade×preco)
Esforço: 2-4 horas
```

**SEC-008 — Avaliar alternativa ao localStorage para JWT**
```
Nota: Requer mudanças no servidor (Set-Cookie) e frontend. Considerar na próxima iteração.
Esforço: 4-8 horas
```

### P3 — Evolução

**Testes automatizados**
```
Iniciar com: Testes unitários para LoginService (brute-force), PedidoService (owner check)
Framework: JUnit 5 + Mockito
Depois: Testes de integração com Testcontainers (PostgreSQL real)
Esforço: 8-16 horas para cobertura básica de regras críticas
```

**CI/CD básico**
```
GitHub Actions: build + testes a cada PR
Esforço: 2-4 horas
```

**Migração de schema (Flyway)**
```
Apenas se o projeto crescer e precisar de evolução de schema em produção
Não necessário agora
Esforço: 4-8 horas de setup
```

---

## 27. O QUE NÃO FAZER AGORA

- **NÃO adicionar Spring Boot** — Javalin é adequado; Spring seria overengineering
- **NÃO adicionar ORM (Hibernate/JPA)** — JDBC puro está correto para este contexto
- **NÃO refatorar para microservices** — monolito é correto neste estágio
- **NÃO adicionar Redis/cache** — não há evidência de necessidade
- **NÃO adicionar mensageria (Kafka/RabbitMQ)** — sem requisito que justifique
- **NÃO migrar para Kubernetes** — Docker Compose é mais que suficiente
- **NÃO implementar CQRS/Event Sourcing** — complexidade desnecessária
- **NÃO adicionar GraphQL** — REST é adequado e já documentado com Swagger

---

## 28. LIMITAÇÕES DA AUDITORIA

1. **OWASP Dependency-Check não executado** — CVEs em dependências não verificados
2. **Análise estática automatizada não executada** — SpotBugs/PMD não disponíveis
3. **Testes não executados** — sem test suite disponível
4. **Sem execução da aplicação** — comportamento em runtime não verificado
5. **Arquivos com modificações não commitadas** — parte do frontend auditada em estado divergente do HEAD
6. **OpenApiConfig.java não lido** — funcionalidade inferida pelas dependências e Swagger disponível
7. **Análise de desempenho não realizada** — sem dados de carga

---

## 29. CONCLUSÃO

O SmartServ é um projeto academicamente honesto que demonstra compreensão genuína de conceitos de segurança e arquitetura de software. A ausência de SQL Injection em todos os DAOs, a implementação correta de BCrypt e JWT, e a proteção contra brute-force indicam que os autores pesquisaram e aplicaram boas práticas de segurança deliberadamente.

As lacunas principais são:
1. **Ausência de testes** — risco estrutural que acompanhará qualquer evolução
2. **XSS via innerHTML** — risco concreto que precisa de correção imediata
3. **Configuração não separada por ambiente** — CORS e URLs hardcoded dificultam produção

Para transformar este projeto em software profissional, o caminho prioritário é: corrigir SEC-009, adicionar testes unitários para regras críticas, e resolver ARCH-001. O restante pode ser endereçado incrementalmente.

**O projeto não está pronto para produção real, mas está bem encaminhado para um projeto educacional.**

---

## 30. ANÁLISE DE POSSÍVEL USO DE IA NA GERAÇÃO DO CÓDIGO

```
Indícios de assistência de IA: Moderados a Fortes
Confiança: Média

Indícios compatíveis com IA:
- Uniformidade de estilo e estrutura entre DAOs (todos com padrão idêntico)
- Comentários em Português consistentes mas genéricos
- Boilerplate de try-with-resources idêntico em múltiplos DAOs
- Estrutura de pacotes organizada de forma sistemática
- Exceções hierárquicas bem nomeadas com convenção uniforme

Indícios compatíveis com intervenção humana:
- JdbcTransactionManager vazio (um AI provavelmente implementaria)
- validaritens com nome em minúsculo (violação de convenção — típico de descuido humano)
- URLs hardcoded no frontend (decisão pragmática de desenvolvimento)
- LoggerFactory.getLogger(FuncionarioService.class) em FuncionarioValidator (bug de copiar-colar)
- Working tree com arquivos modificados (evolução iterativa humana)
- Comentários como "// 🚀 Injeta o token simulando o 'Authorize' do Swagger" (voz humana)

Avaliação: Projeto desenvolvido com assistência de IA para estrutura/boilerplate,
com contribuição humana ativa nas decisões de negócio e particularidades.
Comum em desenvolvimento moderno — não afeta a validade da auditoria.
```

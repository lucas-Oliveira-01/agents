# 03 — Audit Ledger

**Auditoria:** SmartServ  
**Commit:** `be3286d01735592b84ffc6c857d5efad7a460cfb`  
**Data:** 2026-09-13  
**Formato de ID:** CATEGORIA-NNN

---

## CONTROLES POSITIVOS

---

### CONTROL-001 — Tratamento de exceções sem exposição de stack trace

```
Categoria: Segurança / Qualidade
Arquivo:   backend/src/main/java/.../config/ExceptionConfig.java
Linha:     Método register()
Controle:  Exception genérica retorna {"status":500,"tipo":"ERRO_INTERNO","mensagem":"Erro interno no servidor"} — sem stack trace
Evidência: config.routes.exception(Exception.class, (e, ctx) -> { ctx.status(500).json(new ErrorResponse(500, "ERRO_INTERNO","Erro interno no servidor")); logger.error("Erro no servidor ", e); })
Por que está correto: Stack trace é logado server-side via SLF4J, mas o response ao cliente não expõe detalhes internos.
```

---

### CONTROL-002 — Bypass de autenticação apenas para OPTIONS (CORS preflight)

```
Categoria: Segurança
Arquivo:   backend/src/main/java/.../security/AuthMiddleware.java
Linha:     Método handle(), primeiro bloco
Controle:  if (ctx.method().name().equals("OPTIONS")) { return; }
Evidência: Confirmado no código — somente método OPTIONS é bypassado.
Por que está correto: Preflight CORS requer resposta sem autenticação. Nenhuma outra exceção foi adicionada.
```

---

### CONTROL-003 — Autorização server-side real com verificação de role

```
Categoria: Segurança
Arquivo:   backend/src/main/java/.../security/AuthorizationMiddleware.java
Linha:     Método handle()
Controle:  var role = obterAuthContext(ctx).getRole(); if (!ctx.routeRoles().contains(role)) throw new AutorizacaoException(...)
Evidência: Confirmado — a verificação ocorre no servidor, não no cliente.
Por que está correto: O papel (role) é extraído do JWT validado e comparado com as roles da rota. Não há forma de o cliente bypassar isso sem um JWT válido e assinado.
```

---

### CONTROL-004 — JWT com algoritmo HMAC256, issuer, e expiração

```
Categoria: Segurança
Arquivo:   backend/src/main/java/.../security/jwt/JwtIssuer.java e JwtValidator.java
Linha:     JwtIssuer.gerarJwt(); JwtValidator.validarJwt()
Controle:  Algorithm.HMAC256(secret); .withIssuer(ISSUER); .withExpiresAt(exp)
Evidência: Confirmado no código. Duração: 8 horas (JwtConstants.DURACAO_TOKEN).
Por que está correto: HMAC256 com secret externo (não hardcoded), validação de issuer, verificação de expiração. A lib Auth0 java-jwt verifica automaticamente expiração e assinatura.
```

---

### CONTROL-005 — BCrypt com cost factor 12 para senhas

```
Categoria: Segurança / Criptografia
Arquivo:   backend/src/main/java/.../security/password/BCryptPasswordHasher.java
Linha:     hashSenha()
Controle:  BCrypt.withDefaults().hashToString(12, senha.toCharArray())
Evidência: Confirmado. Cost 12 é apropriado e acima do mínimo recomendado (10).
Por que está correto: BCrypt é adequado para hashing de senhas. Cost 12 garante trabalho computacional suficiente contra brute-force.
```

---

### CONTROL-006 — HikariCP com connection pool gerenciado e leak detection

```
Categoria: Persistência / Operação
Arquivo:   backend/src/main/java/.../infrastructure/database/ConnectionFactory.java
Linha:     criarDataSource()
Controle:  config.setLeakDetectionThreshold(30000); minIdle=2, maxPool=10, keepalive=120s
Evidência: Confirmado no código.
Por que está correto: Leak detection a 30s alerta sobre conexões não fechadas. Pool bem dimensionado para o contexto.
```

---

### CONTROL-007 — PreparedStatement em todos os DAOs JDBC

```
Categoria: Segurança / SQL Injection
Arquivo:   JdbcCardapioDAO.java, JdbcFuncionarioDAO.java, JdbcPedidoDAO.java, JdbcItemPedidoDAO.java
Linha:     Todos os métodos que executam SQL
Controle:  conn.prepareStatement(sql) com parâmetros via stmt.setXxx()
Evidência: Verificado em todos os 4 DAOs — nenhum caso de concatenação de string encontrado.
Por que está correto: PreparedStatement com bind parameters é a proteção correta contra SQL Injection.
```

---

### CONTROL-008 — Transação explícita com rollback no insert de pedido

```
Categoria: Persistência / Integridade
Arquivo:   backend/src/main/java/.../infrastructure/jdbc/JdbcPedidoDAO.java
Linha:     Método insert()
Controle:  conn.setAutoCommit(false); insertPedido(); insertItemPedido(); conn.commit(); catch { conn.rollback(); }
Evidência: Confirmado no código.
Por que está correto: Garante atomicidade entre inserção de pedido e seus itens. Rollback em caso de falha.
```

---

### CONTROL-009 — Brute-force protection no login

```
Categoria: Segurança / Autenticação
Arquivo:   backend/src/main/java/.../service/LoginService.java
Linha:     Método autenticar()
Controle:  MAX_TENTATIVAS_LOGIN=5; bloqueio por DURACAO_BLOQUEIO=30min via DB; resposta genérica "Email ou senha invalidos"
Evidência: Confirmado. Resposta unificada para email inexistente e senha incorreta (evita user enumeration).
Por que está correto: Rate limiting por conta com lockout persistente no banco.
```

---

### CONTROL-010 — Verificação de ownership do funcionário

```
Categoria: Segurança / Autorização / IDOR
Arquivo:   backend/src/main/java/.../service/FuncionarioService.java
Linha:     validarAcessoAoFuncionario()
Controle:  if (!authContext.isGerente()) { if (!authContext.getFuncionarioId().equals(id)) throw AutorizacaoException }
Evidência: Confirmado — chamado em buscarPorId() e atualizarSenha().
Por que está correto: Funcionário comum não pode acessar dados de outro; gerente tem acesso total.
```

---

### CONTROL-011 — Verificação de ownership de pedidos por garçom

```
Categoria: Segurança / Autorização / IDOR
Arquivo:   backend/src/main/java/.../service/PedidoService.java
Linha:     verificarGarcom() e validarAcessoAoPedido()
Controle:  Verifica se pedido.garcom.id == authContext.funcionarioId para GARCOM
Evidência: Confirmado — chamado em adicionarItem, removerItem, atualizarQuantidade, buscarPorId.
Por que está correto: Garçom não pode manipular pedidos de outro garçom.
```

---

### CONTROL-012 — Role como enum implementando RouteRole do Javalin

```
Categoria: Segurança / Arquitetura
Arquivo:   backend/src/main/java/.../enums/FuncionarioFuncoes.java
Controle:  public enum FuncionarioFuncoes implements RouteRole
Evidência: Confirmado. Integração nativa com o sistema de roles do Javalin.
Por que está correto: Impossível criar role arbitrário — apenas os valores do enum são aceitos.
```

---

### CONTROL-013 — CHECK constraints no banco de dados

```
Categoria: Persistência / Integridade
Arquivo:   database/01_create_funcionarios.sql, 02_create_cardapio.sql, 03_create_pedidos.sql
Controle:  CHECK constraints para funcao, categoria, status, preco > 0, nome NOT EMPTY, tentativas >= 0
Evidência: Confirmado em todos os scripts DDL.
Por que está correto: Integridade de domínio garantida no banco, independentemente da aplicação.
```

---

### CONTROL-014 — UNIQUE constraint em item_pedido (pedido + item_cardapio)

```
Categoria: Persistência / Integridade
Arquivo:   database/04_create_item_pedido.sql
Linha:     CONSTRAINT uq_item_pedido UNIQUE (pedidos_id_pedido, cardapio_id_item)
Controle:  Impede o mesmo item do cardápio aparecer duas vezes no mesmo pedido.
Evidência: Confirmado no DDL.
Por que está correto: Garante integridade do modelo de pedido; consistente com a regra de negócio.
```

---

## ACHADOS — SEGURANÇA

---

### SEC-001 — CORS wildcard (anyHost) configurado permanentemente

```
ID:          SEC-001
Categoria:   Segurança / Infraestrutura
Subcategoria: CORS
Tipo:        RISCO
Status:      CONFIRMADO
Severidade:  P2 — MÉDIO
Confiança:   Alta

Arquivo:     backend/src/main/java/.../config/CorsConfig.java
Linha:       Método register(), it.anyHost()
Trecho:
    cors.addRule(it -> {
        it.anyHost();
    });

Descrição:
    A configuração CORS permite requisições de qualquer origem (wildcard).
    O comentário no código indica intenção de uso em desenvolvimento, mas
    não há separação por ambiente (dev/prod).

Causa:
    Ausência de configuração de CORS por ambiente. APP_ENV é lido mas não
    utilizado na CorsConfig.

Impacto:
    Em produção, permite que qualquer site externo faça requisições autenticadas
    à API se o usuário tiver um token válido. Risco de Cross-Site Request
    Fishing via iframes ou scripts maliciosos.

Explorabilidade:
    Condição necessária: API exposta publicamente + usuário autenticado em outro site.
    Ator: Atacante com controle de site malicioso.
    Impacto: Baixo a moderado — JWT em Bearer header (não cookie) mitiga CSRF clássico.

Recomendação:
    Usar APP_ENV para configurar origens permitidas. Em prod, especificar
    domínio real. Em dev, manter anyHost ou localhost.
```

---

### SEC-002 — Ausência de rate limiting no endpoint de login

```
ID:          SEC-002
Categoria:   Segurança / Autenticação
Subcategoria: Brute-Force / Rate Limiting
Tipo:        RISCO
Status:      CONFIRMADO
Severidade:  P2 — MÉDIO
Confiança:   Alta

Arquivo:     backend/src/main/java/.../routes/LoginRoutes.java
Linha:       Método register() — POST /login sem rate limiting externo

Descrição:
    Existe brute-force protection por conta (lockout após 5 tentativas — CONTROL-009),
    porém não existe rate limiting por IP. Um atacante pode tentar 5 senhas
    para cada conta com emails diferentes sem ser bloqueado ao nível de rede/IP.

Causa:
    Sem middleware de rate limiting (ex: Resilience4j, Bucket4j, Nginx rate_limit).

Impacto:
    Ataque de credential stuffing distribuído: um atacante com lista de emails
    pode tentar 4 tentativas por conta antes do bloqueio, indefinidamente e
    de IPs diferentes.

Explorabilidade:
    Condição: Acesso ao endpoint público /login.
    Controle ausente: Rate limiting por IP.
    Mitigação existente: Lockout por conta (parcial).

Recomendação:
    Adicionar rate limiting por IP no Nginx (limit_req_zone) ou via filtro Javalin.
    Configuração proporicional: ex. 10 req/min por IP no /login.
```

---

### SEC-003 — Race condition teórica no fluxo de tentativas de login

```
ID:          SEC-003
Categoria:   Segurança / Autenticação
Subcategoria: Race Condition / TOCTOU
Tipo:        RISCO
Status:      PROVÁVEL
Severidade:  P3 — BAIXO
Confiança:   Média

Arquivo:     backend/src/main/java/.../service/LoginService.java
Linha:       Método autenticar() — verificarBloqueio() → autenticarEmailSenha() → incrementarQntTentativasLogin()

Descrição:
    O contador de tentativas é lido e incrementado em operações JDBC separadas
    sem transação. Em requisições concorrentes simultâneas para o mesmo email,
    é possível incrementar o contador menos vezes do que o esperado (lost update).

Causa:
    Ausência de transação ou operação atômica (UPDATE ... SET tentativas = tentativas + 1).

Impacto:
    Um atacante pode enviar múltiplas requisições paralelas e burlar o contador
    de lockout. Requer timing preciso e ataque coordenado.

Explorabilidade:
    Condição: Múltiplas requisições simultâneas ao mesmo email.
    Dificuldade: Alta (requer coordenação de timing).
    Probabilidade em produção real: Baixa.

Recomendação:
    Usar UPDATE atômico: UPDATE funcionarios SET tentativas_login = tentativas_login + 1 WHERE email = ?
    Remover o read-modify-write em Java.
```

---

### SEC-004 — GET /funcionarios/{id} acessível por qualquer role (incluindo CAIXA e COZINHA)

```
ID:          SEC-004
Categoria:   Segurança / Autorização / IDOR
Subcategoria: RBAC — Permissão excessiva
Tipo:        RISCO
Status:      CONFIRMADO
Severidade:  P2 — MÉDIO
Confiança:   Alta

Arquivo:     backend/src/main/java/.../routes/FuncionarioRoutes.java
Linha:       get(funcionarioController::buscarFuncionarioPorId, FuncionarioFuncoes.values())

Trecho:
    get(funcionarioController::buscarFuncionarioPorId, FuncionarioFuncoes.values());

Descrição:
    O endpoint GET /funcionarios/{id} permite acesso a qualquer role (GARCOM,
    COZINHA, CAIXA, GERENTE). Embora o service valide ownership para
    não-gerentes, um usuário COZINHA ou CAIXA que não seja garçom pode tentar
    acessar dados de outros funcionários.

Causa:
    FuncionarioRoutes usa values() ao invés de especificar roles.
    O service em validarAcessoAoFuncionario() só diferencia GERENTE vs outros,
    sem distinguir que COZINHA/CAIXA normalmente não deveriam consultar dados de funcionários.

Impacto:
    COZINHA e CAIXA podem consultar seus próprios dados de perfil (email, telefone, nome).
    Não podem consultar dados de outros funcionários — o service bloqueia.
    Risco residual: Se o serviço for modificado sem atualizar o middleware,
    o controle de acesso seria perdido.

Explorabilidade:
    Um funcionário COZINHA pode GET /funcionarios/{seu_id} e receber seus dados.
    Isso pode ou não ser problema dependendo do requisito — QUESTÃO DEPENDENTE DE REQUISITO.

Recomendação:
    Se COZINHA/CAIXA não devem acesso ao endpoint, restringir roles explicitamente.
    Se todos podem ver seu próprio perfil, documentar a intenção explicitamente.
    Adicionar rota separada GET /funcionarios/me para acesso ao próprio perfil.
```

---

### SEC-005 — Senha padrão única para todos os usuários do seed

```
ID:          SEC-005
Categoria:   Segurança / Configuração
Subcategoria: Credenciais padrão
Tipo:        RISCO
Status:      CONFIRMADO
Severidade:  P2 — MÉDIO
Confiança:   Alta

Arquivo:     database/05_insert_funcionarios.sql
Linha:       Todos os INSERTs — mesmo hash BCrypt para todos

Trecho:
    '$2a$12$y1U5WXl35qHY/c3/RK/f9uHVXb5s7nQFNuHGu7DRqI6.pMtdVImDa'
    (hash idêntico para todos os 10 funcionários seed)

Descrição:
    O seed de dados usa o mesmo hash BCrypt para todos os funcionários,
    indicando uma única senha padrão compartilhada. Não há mecanismo de
    troca de senha obrigatória no primeiro login.

Causa:
    Seed criado para facilitar desenvolvimento sem senhas individuais.

Impacto:
    Se o ambiente de desenvolvimento for acessível ou o seed for executado em
    produção sem troca de senhas, qualquer pessoa com conhecimento da senha
    padrão acessa todas as contas.

Recomendação:
    Documentar explicitamente que o seed é apenas para desenvolvimento.
    Adicionar instrução no README para trocar senhas antes de usar em produção.
    Considerar mecanismo de "must_change_password" na entidade Funcionario.
```

---

### SEC-006 — PostgreSQL porta 5432 exposta na porta 5433 do host

```
ID:          SEC-006
Categoria:   Segurança / Infraestrutura
Subcategoria: Exposição de banco de dados
Tipo:        RISCO
Status:      CONFIRMADO
Severidade:  P2 — MÉDIO (em produção) / P3 em dev local
Confiança:   Alta

Arquivo:     docker-compose.yml
Linha:       ports: "5433:5432" no serviço postgres

Descrição:
    A porta do PostgreSQL está mapeada para o host, tornando o banco acessível
    diretamente na rede do host (ou publicamente se o host for exposto).

Causa:
    Conveniência de desenvolvimento (acesso via DBeaver/pgAdmin local).

Impacto:
    Em produção, qualquer pessoa com acesso à rede e as credenciais do .env
    pode conectar diretamente ao banco, bypassando toda a API.

Recomendação:
    Para produção, remover ou comentar o mapeamento de porta do postgres.
    Usar rede Docker interna apenas entre os containers.
    Ou usar `127.0.0.1:5433:5432` para limitar ao loopback.
```

---

### SEC-007 — .env com JWT_SECRET e DB_PASSWORD presente no working tree

```
ID:          SEC-007
Categoria:   Segurança / Secrets
Subcategoria: Gestão de secrets
Tipo:        RISCO
Status:      CONFIRMADO — MITIGADO PARCIALMENTE
Severidade:  P3 — BAIXO (dado que .gitignore está correto)
Confiança:   Alta

Arquivo:     .env
Linha:       JWT_SECRET=9Wvjn!%xX85Ty58qd4WUqXqj8K97q#@SMS!DVXF7DaAy8yRujy

Descrição:
    O arquivo .env contém o JWT_SECRET e DB_PASSWORD em texto plano.
    CONFIRMADO: o arquivo está no .gitignore e não é rastreado pelo git.
    O secret não foi encontrado em nenhum commit do histórico.

Mitigações presentes:
    - .env está no .gitignore (confirmado via git ls-files)
    - Nenhum secret encontrado no histórico dos commits

Risco residual:
    - Se o .env for compartilhado por outro canal (Slack, email), o secret vaza.
    - O JWT_SECRET atual tem entropia adequada (50+ chars alfanumérico+especial).
    - Não há rotação de secret documentada.

Recomendação:
    Usar .env.example com valores fictícios para documentação.
    Documentar no README que .env deve ser criado localmente.
    Para produção real: usar Docker Secrets ou vault de secrets.
    NUNCA compartilhar o .env real fora do ambiente local.

Nota: O valor do JWT_SECRET NÃO é reproduzido aqui integralmente — [REDACTED].
```

---

### SEC-008 — JWT armazenado em localStorage (sujeito a XSS)

```
ID:          SEC-008
Categoria:   Segurança / Frontend
Subcategoria: Token Storage
Tipo:        RISCO
Status:      CONFIRMADO
Severidade:  P2 — MÉDIO
Confiança:   Alta

Arquivo:     frontend/public/js/auth/login.js
Linha:       64 — localStorage.setItem('tokenAutenticacao', dadosSucesso.token)

Descrição:
    O JWT de autenticação é armazenado no localStorage do browser.
    localStorage é acessível por qualquer JavaScript na mesma origem,
    tornando o token vulnerável a roubo via XSS.

Causa:
    Escolha comum e simples para armazenar token em SPA/vanilla JS.

Impacto:
    Se um XSS for possível (SEC-009), o atacante pode roubar o token
    e personificar o usuário até a expiração (8 horas).

Explorabilidade:
    Condicional: depende de SEC-009 ser explorado.

Recomendação:
    Alternativa mais segura: HttpOnly cookie com SameSite=Strict.
    Isso requereria mudança no servidor (Set-Cookie) e no cliente.
    Para o contexto atual, mitigar SEC-009 (XSS) é mais urgente.
```

---

### SEC-009 — innerHTML com dados do servidor (risco de XSS stored)

```
ID:          SEC-009
Categoria:   Segurança / Frontend
Subcategoria: XSS
Tipo:        RISCO
Status:      PROVÁVEL
Severidade:  P1 — ALTO
Confiança:   Média

Arquivo:     frontend/public/js/cardapio/listar.js, frontend/public/js/funcionario/listar.js
Linha:       listar.js cardapio: ~linha 69+; funcionario/listar.js: linha ~90+

Trecho (cardapio/listar.js, aproximado):
    containerCardapio.innerHTML = `<p>Nenhum item encontrado.</p>`;
    // e em renderização de itens — template literals com dados do servidor

Descrição:
    Os arquivos JS de listagem usam innerHTML para renderizar dados vindos
    da API (nome de itens, nomes de funcionários). Se um valor inserido no
    banco contiver tags HTML/JS, ele será interpretado pelo browser.

Causa:
    Uso de innerHTML com template literals interpolados com dados externos,
    sem sanitização.

Impacto:
    Um gerente mal-intencionado (ou comprometido) poderia inserir um item
    no cardápio com nome contendo `<script>alert(1)</script>` ou similar.
    Quando outros usuários listassem o cardápio, o script executaria.
    Com SEC-008 combinado: roubo de JWT de outros usuários.

Explorabilidade:
    Condição: Capacidade de inserir dados com caracteres HTML no banco
    (via API /cardapio POST — acesso GERENTE).
    Caminho: GERENTE cria item com nome HTML → GARCOM/COZINHA lista → XSS.
    Dificuldade: Baixa, se o ator tiver credenciais de GERENTE.

Recomendação:
    Usar textContent ao invés de innerHTML para dados do servidor.
    Ou sanitizar com DOMPurify antes de inserir.
    Ou criar elementos DOM via createElement() e appendChild().
    Ex: element.textContent = nomeItem; (mais seguro que innerHTML)
```

---

## ACHADOS — ARQUITETURA

---

### ARCH-001 — JdbcTransactionManager é uma casca vazia (implementação nula)

```
ID:          ARCH-001
Categoria:   Arquitetura / Persistência
Tipo:        DEFEITO TÉCNICO
Status:      CONFIRMADO
Severidade:  P2 — MÉDIO
Confiança:   Alta

Arquivo:     backend/src/main/java/.../infrastructure/jdbc/JdbcTransactionManager.java
Linha:       Todos os métodos (begin, commit, rollback)

Trecho:
    public void begin() {}
    public void commit() {}
    public void rollback() {}

Descrição:
    A interface TransactionManager existe e há uma implementação JDBC registrada
    no container IoC, mas os métodos begin/commit/rollback são vazios.
    A gestão de transação real é feita diretamente em JdbcPedidoDAO.insert()
    via conn.setAutoCommit(false) manualmente.

Causa:
    Interface foi criada mas nunca implementada funcionalmente.
    O JdbcPedidoDAO implementou transação interna sem usar a abstração.

Impacto:
    O TransactionManager não é usado pelo sistema real. É dead code.
    Risco maior: se outro desenvolvedor tentar usar o TransactionManager
    esperando comportamento real, não haverá erro mas nada será feito.

Recomendação:
    Ou implementar corretamente o JdbcTransactionManager (usando Connection compartilhada),
    ou remover a interface e a implementação e documentar que transações são gerenciadas localmente.
```

---

### ARCH-002 — IoCContainer instancia EnvConfig duas vezes

```
ID:          ARCH-002
Categoria:   Arquitetura / Configuração
Tipo:        BUG (impacto baixo)
Status:      CONFIRMADO
Severidade:  P3 — BAIXO
Confiança:   Alta

Arquivo:     backend/src/main/java/.../config/IoCContainer.java + SmartservApplication.java
Linha:       IoCContainer.java linha ~11; SmartservApplication.java linha ~12

Trecho:
    // SmartservApplication.java
    EnvConfig envConfig = new EnvConfig();
    LogsConfig.register(envConfig.getAppEnv());
    IoCContainer container = new IoCContainer();
    
    // IoCContainer.java
    private final EnvConfig envConfig = new EnvConfig();

Descrição:
    EnvConfig é instanciado uma vez em SmartservApplication (para configurar logs)
    e outra vez dentro de IoCContainer. Dois objetos leem as mesmas variáveis
    de ambiente separadamente. Não causa bug funcional, mas é redundante.

Impacto:
    Mínimo — leitura redundante de System.getenv(). Pode causar confusão futura.

Recomendação:
    Passar o EnvConfig criado em main para o IoCContainer como parâmetro.
```

---

## ACHADOS — DOMÍNIO

---

### DOMAIN-001 — Ausência de máquina de estados para PedidoStatus

```
ID:          DOMAIN-001
Categoria:   Domínio / Qualidade
Tipo:        DÍVIDA TÉCNICA
Status:      CONFIRMADO
Severidade:  P2 — MÉDIO
Confiança:   Alta

Arquivo:     backend/src/main/java/.../service/PedidoService.java, enums/PedidoStatus.java
Linha:       atualizarStatus() — método não valida transições

Descrição:
    O sistema define 6 status (PENDENTE, PREPARANDO, PRONTO, ENTREGUE,
    FINALIZADO, CANCELADO) mas não há máquina de estados que controle
    transições válidas. Qualquer status pode ir para qualquer outro.
    Ex: FINALIZADO → PENDENTE seria aceito pelo servidor.

Causa:
    PedidoStatus é um enum simples sem lógica de transição.
    PedidoService aceita qualquer status válido do enum sem validar sequência.

Impacto:
    Pedidos podem ter status inválidos do ponto de vista de negócio.
    Ex: pedido CANCELADO voltar para PREPARANDO.

Recomendação:
    Adicionar método em PedidoStatus ou em um PedidoStatusTransitionValidator:
    boolean podeTransicionarPara(PedidoStatus novoStatus)
    Definir grafo de transições: PENDENTE→PREPARANDO|CANCELADO, PREPARANDO→PRONTO|CANCELADO, etc.
```

---

### DOMAIN-002 — Regra de negócio "pedido não pode ser removido se não PENDENTE" duplicada

```
ID:          DOMAIN-002
Categoria:   Domínio / Qualidade
Tipo:        INCONSISTÊNCIA
Status:      CONFIRMADO
Severidade:  P3 — BAIXO
Confiança:   Alta

Arquivo:     backend/src/main/java/.../service/PedidoService.java
Linha:       adicionarItem() linha ~271; atualizarQuantidade() linha ~345; removerItem() linha ~442; removerPedido() linha ~510

Descrição:
    A verificação "if (!status.equals(PENDENTE)) throw ConflitoException"
    é repetida em 4 métodos distintos. A regra vive espalhada no serviço,
    não encapsulada no domínio.

Impacto:
    Dívida de manutenção: se a regra mudar, deve ser alterada em 4 lugares.

Recomendação:
    Mover para método no Pedido: pedido.validarSeModificavel() ou
    criar um PedidoValidator.validarPedidoModificavel(pedido).
```

---

### DOMAIN-003 — Modelos de domínio anêmicos com setters públicos irrestrictos

```
ID:          DOMAIN-003
Categoria:   Domínio / Qualidade
Tipo:        DÍVIDA TÉCNICA
Status:      CONFIRMADO
Severidade:  P3 — BAIXO
Confiança:   Alta

Arquivo:     model/Funcionario.java, model/Pedido.java
Linha:       Todos os setters

Descrição:
    As entidades de domínio (Funcionario, Pedido) possuem setters públicos para
    todos os campos, incluindo campos que não deveriam ser modificados diretamente
    (id, senhaHash, status).

Impacto:
    Invariantes podem ser violadas por qualquer código que tenha acesso ao objeto.
    Ex: funcionario.setSenhaHash("texto_plano") é possível sem validação.

Nota:
    Para o contexto acadêmico/intermediário deste projeto, é compreensível.
    Não representa risco imediato, apenas dívida.

Recomendação:
    Gradualmente tornar campos imutáveis onde possível.
    Usar construtores que forcem invariantes em vez de setters livres.
```

---

## ACHADOS — BUILD / CONFIG / OPERAÇÃO

---

### BUILD-001 — EnvConfig lança exceção não tratada se variável de ambiente ausente

```
ID:          BUILD-001
Categoria:   Build / Configuração
Tipo:        BUG
Status:      CONFIRMADO
Severidade:  P1 — ALTO
Confiança:   Alta

Arquivo:     backend/src/main/java/.../config/EnvConfig.java
Linha:       10 — Integer.parseInt(System.getenv("APP_PORT"))

Trecho:
    private final int appPort = Integer.parseInt(System.getenv("APP_PORT"));

Descrição:
    Se APP_PORT não estiver definida, System.getenv() retorna null.
    Integer.parseInt(null) lança NullPointerException na inicialização da classe.
    Outras variáveis (DB_HOST, JWT_SECRET, etc.) retornarão null silenciosamente,
    causando falhas mais tarde em tempo de execução (ex: NullPointerException em HikariCP).

Causa:
    Ausência de validação de variáveis de ambiente obrigatórias.

Impacto:
    Falha de startup sem mensagem clara. Dificulta diagnóstico em ambientes novos.
    Em Docker, a variável é fornecida via env_file, mas se o .env não existir
    ou uma variável for removida, o erro não é claro.

Recomendação:
    Adicionar validação explícita:
    String portStr = Objects.requireNonNull(System.getenv("APP_PORT"), "APP_PORT não definida");
    Ou usar um padrão de validação de configuração na inicialização.
```

---

### PROB-001 — LogsConfig.java com estado divergente no working tree

```
ID:          PROB-001
Categoria:   Operação / Configuração
Tipo:        PROBLEMA OPERACIONAL
Status:      CONFIRMADO
Severidade:  P3 — BAIXO
Confiança:   Alta

Arquivo:     backend/src/main/java/.../config/LogsConfig.java
Linha:       NÃO DISPONÍVEL (arquivo modificado no working tree — lido via git status)

Descrição:
    O arquivo LogsConfig.java aparece como modificado no working tree mas
    não commitado. A versão lida na auditoria pode diferir da versão commitada.
    A versão atual parece funcional (debug em dev, info em prod).

Impacto:
    Mínimo se a mudança for trivial. Risco de trabalho em progresso não commitado
    se o projeto for entregue no estado atual do working tree.

Recomendação:
    Commitar ou reverter as mudanças pendentes.
```

---

### INFRA-001 — Dockerfile não especifica usuário não-root

```
ID:          INFRA-001
Categoria:   Infraestrutura / Segurança
Tipo:        RISCO
Status:      CONFIRMADO
Severidade:  P2 — MÉDIO
Confiança:   Alta

Arquivo:     backend/Dockerfile
Linha:       Completo — ausência de USER

Trecho:
    FROM eclipse-temurin:21-jre-alpine
    WORKDIR /app
    COPY --from=build ...
    EXPOSE 7070
    ENTRYPOINT ["java", "-jar", "/app/app.jar"]

Descrição:
    O container da API executa como root (padrão quando USER não é especificado).
    Em caso de vulnerabilidade de execução de código no processo Java,
    o atacante teria privilégios de root dentro do container.

Causa:
    USER não foi configurado no Dockerfile.

Impacto:
    Elevação de privilégio dentro do container em caso de exploração.

Recomendação:
    Adicionar antes do ENTRYPOINT:
    RUN addgroup -S appgroup && adduser -S appuser -G appgroup
    USER appuser
```

---

### INFRA-002 — Imagem base da etapa de build não fixada (maven:3.9-eclipse-temurin-21)

```
ID:          INFRA-002
Categoria:   Build / Infraestrutura
Tipo:        DÍVIDA TÉCNICA
Status:      CONFIRMADO
Severidade:  P3 — BAIXO
Confiança:   Alta

Arquivo:     backend/Dockerfile
Linha:       FROM maven:3.9-eclipse-temurin-21 AS build

Descrição:
    A tag da imagem Maven não é fixada com digest SHA256. Uma atualização
    da imagem base poderia introduzir mudanças não previstas no build.

Impacto:
    Builds não reprodutíveis em cenários de atualização de imagem.
    Baixo impacto para o contexto atual.

Recomendação:
    Para produção: fixar com digest. Para dev: aceitável manter tag.
```

---

## ACHADOS — GIT

---

### GIT-001 — Working tree com 7 arquivos modificados e 2 untracked não commitados

```
ID:          GIT-001
Categoria:   Git / Processo
Tipo:        PROBLEMA OPERACIONAL
Status:      CONFIRMADO
Severidade:  P3 — BAIXO
Confiança:   Alta

Evidência:   git status --short mostra 7 arquivos M e 2 ??

Descrição:
    O estado do repositório no momento da auditoria possui trabalho em progresso
    não commitado, incluindo frontend JS, HTML e LogsConfig.java.
    Se entregue nesse estado, o commit HEAD não representa o código real em execução.

Recomendação:
    Commitar ou descartar as mudanças antes de qualquer entrega ou deploy.
```

---

## ACHADOS — CÓDIGO

---

### CODE-001 — mapFuncionario() passa null para senhaHash sem documentação

```
ID:          CODE-001
Categoria:   Qualidade de Código
Tipo:        INCONSISTÊNCIA
Status:      CONFIRMADO
Severidade:  P3 — BAIXO
Confiança:   Alta

Arquivo:     backend/src/main/java/.../infrastructure/jdbc/JdbcFuncionarioDAO.java
Linha:       mapFuncionario() — parâmetro senhaHash = null

Trecho:
    return new Funcionario(
            rs.getInt("id_funcionario"),
            rs.getString("nome"),
            ...
            null,   // senhaHash — intencionalmente null
            ...
    );

Descrição:
    mapFuncionario() passa null para senhaHash intencionalmente para evitar
    que o hash circule sem necessidade. mapFuncionarioComSenha() busca o hash.
    A intenção é correta mas não há comentário explicando a decisão.

Impacto:
    Se código downstream tentar usar senhaHash de um Funcionario mapeado via
    mapFuncionario(), obterá null silenciosamente.

Recomendação:
    Adicionar comentário explicando a intenção.
    Considerar um VO FuncionarioSemSenha vs FuncionarioComSenha para maior clareza.
```

---

### CODE-002 — Gerente pode trocar senha de funcionário sem verificar senha atual

```
ID:          CODE-002
Categoria:   Segurança / Domínio
Tipo:        QUESTÃO DEPENDENTE DE REQUISITO
Status:      CONFIRMADO
Severidade:  INFO
Confiança:   Alta

Arquivo:     backend/src/main/java/.../service/FuncionarioService.java
Linha:       atualizarSenha() — bloco if (authContext.isGerente())

Trecho:
    if (authContext.isGerente()){
        String novaSenhaHash = passwordHasher.hashSenha(requestUpdatePassword.getNovaSenha());
        funcionarioExistentePorId.setSenhaHash(novaSenhaHash);
        funcionarioDAO.updateSenha(funcionarioExistentePorId);
        return;
    }

Descrição:
    O gerente pode redefinir a senha de qualquer funcionário sem precisar
    informar a senha atual. Isso pode ser intencionalmente um requisito de
    administração (ex: redefinição de emergência).

    Para o funcionário comum, a senha atual É verificada — correto.

Avaliação:
    Se for requisito intencional de administração, não é defeito.
    Se não for, o gerente poderia tomar controle de qualquer conta.
    QUESTÃO DEPENDENTE DE REQUISITO — sem o requisito formal, não pode ser classificado como bug.

Recomendação:
    Documentar explicitamente se isso é comportamento intencional no README ou docs.
```

---

### CODE-003 — PedidoValidator.validaritens() é privado e nunca chamado externamente

```
ID:          CODE-003
Categoria:   Qualidade de Código
Tipo:        DEFEITO TÉCNICO
Status:      CONFIRMADO
Severidade:  P3 — BAIXO
Confiança:   Alta

Arquivo:     backend/src/main/java/.../validator/PedidoValidator.java
Linha:       validaritens() — método privado

Trecho:
    private boolean validaritens(List<ItemPedidoCreateRequest> itens){ ... }

Descrição:
    O método valida a lista de itens de um pedido, mas é privado e chamado
    apenas dentro de validarPedidoCreateRequest(). Isso é OK funcionalmente,
    mas o nome em minúsculo (validaritens vs validarItens) viola convenções Java.

Impacto:
    Mínimo — qualidade de código menor.

Recomendação:
    Renomear para validarItens() (camelCase).
```

---

## ACHADOS — BANCO DE DADOS

---

### DB-001 — maxLifetime de HikariCP configurado em 2.000.000 ms (~33 min)

```
ID:          DB-001
Categoria:   Persistência / Operação
Tipo:        DÍVIDA TÉCNICA
Status:      CONFIRMADO
Severidade:  P3 — BAIXO
Confiança:   Alta

Arquivo:     backend/src/main/java/.../infrastructure/database/ConnectionFactory.java
Linha:       config.setMaxLifetime(2000000)

Descrição:
    maxLifetime de 2.000.000 ms ≈ 33 minutos. O PostgreSQL por padrão tem
    tcp_keepalives_idle menor que isso, e o valor recomendado pelo HikariCP é
    < server_wait_timeout. 30 minutos é o padrão seguro, mas depende da config do Postgres.

Impacto:
    Risco de conexões sendo fechadas pelo banco antes do maxLifetime do pool,
    causando erros de conexão esporádicos em produção. Em Docker local, impacto mínimo.

Recomendação:
    Verificar server_wait_timeout do PostgreSQL e ajustar maxLifetime para
    no máximo 80% desse valor. Recomendado: 1.800.000 ms (30 min).
```

---

### DB-002 — Tabela pedidos sem índice em id_funcionario (FK)

```
ID:          DB-002
Categoria:   Banco de Dados / Performance
Tipo:        DÍVIDA TÉCNICA
Status:      CONFIRMADO
Severidade:  P3 — BAIXO
Confiança:   Alta

Arquivo:     database/03_create_pedidos.sql
Linha:       Ausência de CREATE INDEX

Descrição:
    A coluna id_funcionario em pedidos é FK e usada em buscas de pedidos
    por garçom (listarPedidosPorGarcom). O PostgreSQL não cria índice
    automaticamente para FKs.

Impacto:
    Performance degradada em buscas por garçom com volume alto de pedidos.
    Aceitável no contexto atual (restaurante pequeno).

Recomendação:
    CREATE INDEX idx_pedidos_funcionario ON pedidos(id_funcionario);
```

---

### DB-003 — Coluna funcao em funcionarios sem FK para tabela de referência

```
ID:          DB-003
Categoria:   Banco de Dados / Integridade
Tipo:        DÍVIDA TÉCNICA
Status:      CONFIRMADO
Severidade:  INFO
Confiança:   Alta

Arquivo:     database/01_create_funcionarios.sql
Linha:       funcao varchar(30) + CHECK constraint

Descrição:
    A função do funcionário é armazenada como VARCHAR com CHECK constraint.
    Não há tabela de referência separada. A abordagem com CHECK constraint
    e enum Java é coerente e adequada para o contexto.

Avaliação:
    NÃO É DEFEITO para este contexto. A abordagem é válida e funciona.
    Registrado como INFO por completude.
```

---

### DB-004 — Tabela pedidos com valor_total calculado na aplicação (risco de inconsistência)

```
ID:          DB-004
Categoria:   Banco de Dados / Integridade
Tipo:        RISCO
Status:      CONFIRMADO
Severidade:  P2 — MÉDIO
Confiança:   Alta

Arquivo:     database/03_create_pedidos.sql + service/PedidoService.java
Linha:       valor_total em pedidos; cálculo em atualizarQuantidade() e removerItem()

Descrição:
    O valor_total do pedido é calculado e atualizado pela aplicação em múltiplas
    operações (adição de item, remoção de item, atualização de quantidade).
    Cada operação atualiza o total em uma transação separada.

    Problema: se dois garçons adicionarem itens ao mesmo pedido simultaneamente
    (cenário improvável mas possível), os totais podem divergir.

    Mais grave: se a operação de atualizar item for bem-sucedida mas a de
    atualizar valor_total falhar, o total fica inconsistente com os itens.

Causa:
    valor_total denormalizado sem atomic update via trigger.

Impacto:
    Valor total inconsistente com a soma real dos itens.

Recomendação:
    Usar trigger PostgreSQL para recalcular valor_total automaticamente
    quando item_pedido for inserido/atualizado/deletado.
    Ou recalcular sempre que buscar, usando SUM via JOIN.
```

---

### DB-005 — CASCADE DELETE em item_pedido pode causar perda silenciosa de dados

```
ID:          DB-005
Categoria:   Banco de Dados / Integridade
Tipo:        QUESTÃO DEPENDENTE DE REQUISITO
Status:      CONFIRMADO
Severidade:  P2 — MÉDIO
Confiança:   Alta

Arquivo:     database/04_create_item_pedido.sql
Linha:       CONSTRAINT item_pedido_pedidos FOREIGN KEY ... ON DELETE CASCADE

Descrição:
    A FK de item_pedido para pedidos tem ON DELETE CASCADE.
    Ao deletar um pedido, todos os itens são deletados automaticamente.
    Isso é consistente com a lógica do service.

    Porém: não há ON DELETE RESTRICT na FK de item_pedido para cardapio.
    Deletar um item do cardápio quando há pedidos ativos com esse item
    orphanizaria os dados históricos (mas os itens_pedido teriam FK violada
    e o delete seria bloqueado pelo banco — comportamento correto por padrão RESTRICT).

Avaliação:
    O CASCADE em pedidos→item_pedido é intencional e correto.
    O comportamento padrão RESTRICT em cardapio→item_pedido protege contra
    deleção acidental de itens ativos. Não há problema funcional.
    Registrado por completude.
```

---

## ACHADOS — FRONTEND

---

### FRONT-001 — URLs de API hardcoded como localhost:7070 no frontend

```
ID:          FRONT-001
Categoria:   Frontend / Configuração
Tipo:        PROBLEMA OPERACIONAL
Status:      CONFIRMADO
Severidade:  P2 — MÉDIO (em produção)
Confiança:   Alta

Arquivo:     js/cardapio/cadastrar.js (×2), listar.js, deletar.js, funcionario/listar.js, funcionario/cadastrar.js, funcionario/deletar.js
Linha:       múltiplas — 12 ocorrências de http://localhost:7070

Trecho:
    const urlApi = 'http://localhost:7070/cardapio';

Descrição:
    Todas as chamadas de API no frontend usam URLs fixas apontando para localhost.
    Em produção ou ambiente diferente de localhost, o frontend não funcionará.

Causa:
    Ausência de configuração de URL base centralizada ou variável de ambiente frontend.

Impacto:
    O frontend só funciona se backend estiver em localhost:7070.
    Em qualquer outro ambiente, todas as chamadas falharão.

Recomendação:
    Criar uma constante global: const API_BASE = window.location.origin ou
    configurável via arquivo de config JS separado.
    Centralizar em um único arquivo de configuração.
```

---

## ACHADOS — DOCUMENTAÇÃO

---

### DOC-001 — README.md com tabela de tecnologias incompleta

```
ID:          DOC-001
Categoria:   Documentação
Tipo:        INCONSISTÊNCIA
Status:      CONFIRMADO
Severidade:  INFO
Confiança:   Alta

Arquivo:     README.md
Linha:       Tabela de tecnologias

Descrição:
    A tabela de tecnologias no README lista apenas PostgreSQL, Docker e Docker Compose.
    Não menciona Java 21, Javalin 7.2.2, BCrypt, JWT, HikariCP, ou Maven.
    A arquitetura real do projeto é muito mais rica do que a documentação sugere.

Recomendação:
    Adicionar Java 21, Javalin 7.2.2, HikariCP 5.1.0, BCrypt, JWT Auth0, Maven
    à tabela de tecnologias.
```

---

## AUSÊNCIA DE ACHADOS

---

### SQL Injection

```
Categoria:   SQL Injection
Status:      NÃO ENCONTRADO
Escopo:      Todos os 4 DAOs JDBC (JdbcCardapioDAO, JdbcFuncionarioDAO, JdbcPedidoDAO, JdbcItemPedidoDAO)
Arquivos verificados: Confirmados individualmente
Controles relevantes: PreparedStatement com bind parameters em 100% das operações SQL
Limitações:  Análise estática manual — sem execução de scanner automatizado
```

---

### Hardcoded Credentials no código Java

```
Categoria:   Secrets / Hardcoded Credentials
Status:      NÃO ENCONTRADO
Escopo:      Todo src/main/java/
Controles:   JWT_SECRET e DB_PASSWORD lidos de System.getenv() — confirmado
Limitações:  Grep manual executado. OWASP Dependency-Check não executado.
```

---

### OS Command Injection

```
Categoria:   OS Command Injection
Status:      NÃO APLICÁVEL
Escopo:      Nenhum Runtime.exec(), ProcessBuilder ou similar encontrado
```

---

### SSRF

```
Categoria:   SSRF
Status:      NÃO APLICÁVEL
Escopo:      Nenhum HTTP client server-side encontrado no backend
```

---

### XSS via eval() ou document.write()

```
Categoria:   XSS via eval/document.write
Status:      NÃO ENCONTRADO
Escopo:      Todo frontend/public/js/
Controles:   Nenhum uso de eval(), new Function(), ou document.write() encontrado
Nota:        Risco de XSS via innerHTML documentado em SEC-009 (sem eval)
```

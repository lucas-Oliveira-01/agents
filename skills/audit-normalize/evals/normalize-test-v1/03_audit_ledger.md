# AUDIT LEDGER

## ARCH-001

Title: Missing transaction boundaries for multi-statement operations

Category: ARCHITECTURE
Subcategory: TRANSACTION_MANAGEMENT
Type: ARCHITECTURAL_DEFECT
Status: CONFIRMED
Severity: P2
Confidence: HIGH

Location:
- `backend/src/main/java/br/com/debuggers/smartserv/service/PedidoService.java`
- `backend/src/main/java/br/com/debuggers/smartserv/infrastructure/jdbc/JdbcTransactionManager.java`

Evidence:
- O `PedidoService` executa operações DB sucessivas como `itemPedidoDAO.insert` seguido de `pedidoDAO.updateValorTotal` (linha 303-307) sem envolver em um bloco de transação (commit/rollback).
- A classe `JdbcTransactionManager` existe mas não é invocada em nenhum `Service`.

Description:
- [Observation]: Múltiplas mutações em diferentes tabelas ocorrem sequencialmente com auto-commit verdadeiro por padrão na Connection.
- [Inference]: Uma falha, exceção ou queda do banco de dados na operação subsequente deixará a operação prévia isolada no banco.
- [Hypothesis]: A equipe planejou gerenciar transações (daí a presença de `TransactionManager`) mas não concluiu a integração via IoC.

Cause:
- A injeção de dependências (`IoCContainer`) não forneceu os gerenciadores de transação para as classes de serviço.

Impact:
- Inconsistência na base de dados (ex: Item criado no pedido, mas o valor total do pedido não ser atualizado).

Exploitability:
- Não aplicável via ator malicioso, mas ocorrerá naturalmente sob uso ou em falhas de rede.

Recommendation:
- Injetar o `TransactionManager` nos serviços e aplicar o padrão `begin`, `commit`, e `rollback` em operações como `criarPedido`, `adicionarItem` e `removerItem`.

---

## SEC-001

Title: Permissive wildcard CORS configuration

Category: SECURITY
Subcategory: CORS
Type: RISK
Status: CONFIRMED
Severity: P3
Confidence: HIGH

Location:
- `backend/src/main/java/br/com/debuggers/smartserv/config/CorsConfig.java:12`

Evidence:
- `it.anyHost();` é configurado globalmente nas opções do Javalin.

Description:
- [Observation]: O servidor aceita requisições originadas de qualquer host/domínio.
- [Inference]: A configuração atual foi definida para facilitar o desenvolvimento (como documentado no próprio código fonte).
- [Limitation]: Como não há variáveis de ambiente separando o CORS por ambiente (`development` vs `production`), presume-se que será a mesma configuração a menos que alterada.

Cause:
- Conveniência de desenvolvimento sem carregamento baseado em `appEnv`.

Impact:
- Se a aplicação web armazenar tokens (ex: cookies) sem proteções `SameSite`, atacantes poderão realizar chamadas autenticadas Cross-Origin.

Exploitability:
- O caminho de ataque (Attack path) depende de condições não demonstradas no ambiente atual (como o armazenamento explícito de tokens de sessão em cookies vulneráveis e a ausência de controles `SameSite` no frontend). Sem essas evidências complementares, permanece classificado como um risco latente (RISK).

Recommendation:
- Ler a variável `APP_ENV`. Caso seja `production`, restringir o CORS ao host do domínio real da aplicação.

---

## TEST-001

Title: Complete absence of automated tests

Category: TESTING
Subcategory: UNIT_TESTS
Type: TECH_DEBT
Status: CONFIRMED
Severity: P3
Confidence: HIGH

Location:
- `backend/src/test` (ausente)
- `backend/pom.xml`

Evidence:
- Nenhuma dependência `junit`, `mockito` ou frameworks equivalentes está declarada no `pom.xml`. 
- Diretório `src/test` não existe no projeto de backend. Nenhuma ferramenta de teste no frontend.

Description:
- [Observation]: Nenhuma linha de teste ou configuração foi identificada.
- [Inference]: A garantia de qualidade foi feita puramente por testes manuais na interface Swagger/Front.

Cause:
- Priorização de requisitos funcionais em detrimento de cobertura de testes.

Impact:
- Regressões indetectáveis de forma automatizada ao se adicionar novas funcionalidades.

Recommendation:
- Introduzir configuração básica de JUnit e implementar testes nos Validadores e Mappers, antes de prosseguir com Mocks de Banco de Dados.

---

## DOC-001

Title: Inconsistency in documented database initialization scripts

Category: DOCUMENTATION
Subcategory: README
Type: INCONSISTENCY
Status: CONFIRMED
Severity: INFO
Confidence: HIGH

Location:
- `README.md`
- `database/`

Evidence:
- O README cita 6 arquivos SQL (01 a 06).
- O diretório `database/` possui 8 arquivos SQL (01 a 08), abrangendo a entidade `item_pedido` que não está documentada.

Description:
- [Observation]: Existe divergência material entre a documentação de instruções e o estado real.
- [Inference]: O desenvolvedor de BD adicionou novas migrações e esqueceu de atualizar o `README.md`.

Cause:
- Falta de sincronização entre README e código fonte.

Impact:
- Confusão no _onboarding_ ou setup local para novos desenvolvedores, embora o Docker trate silenciosamente lendo a pasta.

Recommendation:
- Atualizar a listagem no README.md.

---

## CONTROL-001

Title: Protection against SQL Injection using PreparedStatement

Category: SECURITY
Subcategory: SQL_INJECTION
Status: CONFIRMED

Description:
- A camada DAO (`JdbcPedidoDAO`, `JdbcFuncionarioDAO`, `JdbcCardapioDAO`, `JdbcItemPedidoDAO`) constrói todas as queries usando blocos de concatenação fixos e injeta parâmetros de usuário por meio do `PreparedStatement`.
- Verificado em múltiplas invocações durante a inspeção. Nenhuma query bruta em string contendo variáveis não tratadas foi observada.
- Isso barra de forma eficaz a injeção SQL no trânsito das variáveis aos endpoints HTTP até a base de dados.

---

## CONTROL-002

Title: Secure Password Hashing

Category: SECURITY
Subcategory: PASSWORD_STORAGE
Status: CONFIRMED

Description:
- Senhas salvas em banco (funcionários) são hasheadas via pacote BCrypt `at.favre.lib:bcrypt:0.10.2`.
- Evidenciado na classe `BCryptPasswordHasher.java` usando custo algorítmico 12.
- A aplicação jamais trafega senhas em texto puro de volta ou armazena dessa forma (confirmado via `FuncionarioService`).

---

## CONTROL-003

Title: Authentication Enforcement via Middleware

Category: SECURITY
Subcategory: AUTHENTICATION
Status: CONFIRMED

Description:
- Um middleware `AuthMiddleware.java` é interceptado para todas as rotas da API em `RoutesConfig.java`, exceto para endpoints de documentação Swagger, Redoc e Login.
- Bloqueia acessos sem cabeçalho Authorization válido (Bearer JWT).
- Assinatura validada via HMAC256 de `envConfig.getJwtSecret()`.

---

## CONTROL-004

Title: Role-based Access Control Configuration

Category: SECURITY
Subcategory: AUTHORIZATION
Status: CONFIRMED

Description:
- Endpoints administrativos possuem verificação forte por papéis definidos (`FuncionarioFuncoes.GERENTE`).
- Rotas declaradas com roles específicas forçam validação dentro de `AuthorizationMiddleware.java`.
- Além disso, verificações intra-recurso (`validarAcessoAoFuncionario` e `verificarGarcom`) validam _Ownership_, impedindo o IDOR cruzado entre diferentes Garçons para pedidos de outras mesas.

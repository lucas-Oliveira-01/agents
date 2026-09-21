# ANALYTICAL REPORT

## EXECUTIVE SUMMARY
O projeto SmartServe apresenta uma fundação acadêmica coerente, utilizando Javalin para exposição de APIs REST e JDBC puro para persistência. A auditoria identificou controles positivos importantes, como hashing de senhas via BCrypt e parametrização robusta de queries contra SQL Injection. No entanto, foram detectadas deficiências na integridade dos dados devido à ausência de transações em operações compostas, além de configurações de CORS permissivas e total falta de cobertura de testes automatizados. Esta auditoria realizou uma inspeção focal (7 arquivos integralmente auditados, 1 parcialmente auditado e 160 não auditados, num universo de 168 arquivos mapeados), não devendo ser tomada como certificação integral de segurança do projeto.

## ARCHITECTURE
A arquitetura monolítica segue os padrões de mercado (Controller, Service, DAO). A injeção de dependências é feita manualmente via `IoCContainer`, o que é apropriado para a escolha de stack (Javalin sem Spring).
A maior lacuna arquitetural reside na ausência de **Transaction Management**. Os serviços (ex: `PedidoService`) realizam múltiplas mutações no banco de dados sem utilizar transações, o que fatalmente resultará em dados inconsistentes no caso de falhas parciais. Curiosamente, a interface `TransactionManager` existe no repositório, mas nunca é utilizada.

## SECURITY
**Controles Positivos:**
- Senhas protegidas com `BCrypt` cost 12.
- Acesso bloqueado globalmente por um middleware JWT (exceto rotas públicas).
- Controle de papéis em rotas específicas via `AuthorizationMiddleware`.
- Mitigação de SQL Injection via `PreparedStatement`.
- Verificação de _ownership_ no backend (ex: garçom acessando seus próprios pedidos).

**Findings Identificados:**
- O CORS é liberado para qualquer host (wildcard `*`), caracterizando um risco caso a aplicação seja hospedada diretamente no ambiente produtivo sem um proxy reverso configurado restritivamente.

## CODE QUALITY & TESTING
A qualidade de código geral é adequada para o escopo do projeto, com nomenclatura consistente e separação lógica clara.
Entretanto, a disciplina de testes é inexistente. O repositório não contém diretórios de testes (`src/test`), e nenhuma dependência de teste (como JUnit ou Mockito) está configurada no Maven. Medição de cobertura de testes: NOT_MEASURED (ferramentas de medição não executadas por ausência de framework de testes).

## PERSISTENCE & DATABASE
O sistema adota JDBC cru para operações. Embora eficiente e controlado com HikariCP, não há uso de ferramentas de versionamento de banco (como Flyway ou Liquibase). A inicialização do banco depende da montagem de volume do Docker para o diretório `database/`, executando scripts na ordem alfabética. Notou-se inconsistência entre os scripts declarados na documentação e os scripts reais do diretório.

## PRIORITIZATION
1. **ARCH-001 (P2):** Implementar gerenciamento de transações em operações que afetam múltiplas entidades para evitar corrompimento do estado de negócios.
2. **SEC-001 (P3):** Restringir a configuração de CORS antes de mover qualquer ambiente para acesso público.
3. **TEST-001 (P3):** Introduzir suítes de testes unitários básicos em lógicas críticas de domínio, como o `PedidoValidator` e cálculos de `PedidoService`.
4. **DOC-001 (INFO):** Sincronizar o README com a estrutura real de scripts do banco de dados.

## LIMITATIONS
A auditoria foi limitada pela falta de um ambiente de homologação ou produção e pela total ausência de suíte de testes. Não foi realizada validação dinâmica automatizada de endpoints de segurança (Pentest ou DAST).

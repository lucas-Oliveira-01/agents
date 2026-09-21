# COVERAGE MANIFEST

## APPLICABILITY MATRIX

| Category | Subcategory | State |
|---|---|---|
| SECURITY | AUTHENTICATION | APPLICABLE |
| SECURITY | AUTHORIZATION | APPLICABLE |
| SECURITY | SQL_INJECTION | APPLICABLE |
| SECURITY | CORS | APPLICABLE |
| SECURITY | SECRETS | APPLICABLE |
| ARCHITECTURE | TRANSACTION_MANAGEMENT | APPLICABLE |
| ARCHITECTURE | DEPENDENCY_INJECTION | APPLICABLE |
| TESTING | UNIT_TESTS | APPLICABLE |
| TESTING | INTEGRATION_TESTS | APPLICABLE |
| CI_CD | PIPELINE | NOT_APPLICABLE |
| DATABASE | MIGRATIONS | APPLICABLE |
| DOCUMENTATION | README | APPLICABLE |

## INSPECTION COVERAGE

| Category | Subcategory | State | Result | Scope/Evidence |
|---|---|---|---|---|
| SECURITY | SQL_INJECTION | INSPECTED | NOT_FOUND | DAOs auditados (uso extensivo de PreparedStatement) |
| SECURITY | AUTHENTICATION | INSPECTED | FINDINGS_PRESENT | Middlewares, JwtIssuer, BCryptPasswordHasher |
| SECURITY | AUTHORIZATION | INSPECTED | FINDINGS_PRESENT | Middlewares, RoutesConfig, FuncionarioRoutes |
| SECURITY | CORS | INSPECTED | FINDINGS_PRESENT | CorsConfig.java |
| ARCHITECTURE | TRANSACTION_MANAGEMENT| INSPECTED | FINDINGS_PRESENT | PedidoService, JdbcTransactionManager |
| TESTING | UNIT_TESTS | INSPECTED | FINDINGS_PRESENT | Diretórios de teste ausentes no repositório |
| DATABASE | MIGRATIONS | INSPECTED | NOT_FOUND | Scripts brutos via initdb, sem controle de versão (Flyway/Liquibase) |
| DOCUMENTATION| README | INSPECTED | FINDINGS_PRESENT | README.md x database/*.sql |

## FILE COVERAGE

| File | Type | State | Categories | Findings | Notes |
|---|---|---|---|---|---|
| backend/pom.xml | BUILD | AUDITED | BUILD, DEPENDENCIES | TEST-001 | Dependências analisadas |
| backend/.../CorsConfig.java | SOURCE | AUDITED | SECURITY | SEC-001 | |
| backend/.../PedidoService.java | SOURCE | AUDITED | ARCHITECTURE, DATABASE | ARCH-001 | |
| backend/.../JdbcTransactionManager.java | SOURCE | AUDITED | ARCHITECTURE | ARCH-001 | |
| backend/.../JdbcPedidoDAO.java | SOURCE | PARTIALLY_AUDITED | SECURITY, DATABASE | CONTROL-001 | |
| backend/.../JwtIssuer.java | SOURCE | AUDITED | SECURITY | CONTROL-003 | |
| backend/.../AuthorizationMiddleware.java| SOURCE | AUDITED | SECURITY | CONTROL-004 | |
| database/ | SCRIPT | AUDITED | DATABASE, DOCUMENTATION | DOC-001 | |

## EXECUTION LOG

### Command
```bash
git status --short --untracked-files=all && git log -1 --format="%H"
```
### Result
`f7798ca700166e618389c1d1a9037a1ab2c32e7e`
### Purpose
Verify working tree state and get target commit.
### Status
EXECUTED

### Command
```bash
git ls-files | wc -l && find . -type f -not -path "*/.git/*" | wc -l
```
### Result
168 files
### Purpose
Map total files in the repository.
### Status
EXECUTED

### Command
```bash
tree backend/src/main/java
```
### Result
40 directories, 89 files
### Purpose
Map backend structure.
### Status
EXECUTED

### Command
```bash
ls backend/src/test
```
### Result
`No such file or directory`
### Purpose
Check for existence of test suites.
### Status
EXECUTED

### Command
```bash
cat backend/pom.xml | grep -i version
```
### Result
Versões de dependências (Javalin 7.2.2, PostgreSQL 42.7.7)
### Purpose
Check project dependencies and test frameworks.
### Status
EXECUTED

### Command
```bash
grep -n -A 0 "prepareStatement" backend/src/main/java/br/com/debuggers/smartserv/infrastructure/jdbc/*.java
```
### Result
Múltiplas ocorrências de `PreparedStatement` nos DAOs.
### Purpose
Check SQL injection prevention.
### Status
EXECUTED

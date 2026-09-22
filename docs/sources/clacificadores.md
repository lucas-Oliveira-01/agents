Sim. Você está correto em apontar isso. Eu misturei **classificação semântica feita pelo LLM** com **classificadores determinísticos**, e isso distorceu o desenho que você vinha especificando.

O requisito que você estabeleceu é mais forte:

> **Sempre que uma decisão puder ser feita por algoritmo, regra, análise estrutural ou heurística determinística sem perda relevante de qualidade, não devemos gastar uma chamada de LLM para fazê-la.**

E isso deve valer **dentro das auditorias**, não apenas no `audit-normalize`.

### Onde os classificadores deveriam estar

O desenho correto para as auditorias é aproximadamente:

```text
                    PROJECT
                       │
                       ▼
              ┌─────────────────┐
              │ Discovery       │
              │ determinístico  │
              └────────┬────────┘
                       │
                       ▼
          ┌──────────────────────────┐
          │ CLASSIFICATION PIPELINE  │
          │          sem LLM         │
          └──────────────────────────┘
             │       │       │
             ▼       ▼       ▼
          File     Task    Applicability
          Class.   Class.     Class.
             │       │       │
             └───────┼───────┘
                     ▼
              Audit Planning
                     │
                     ▼
              AuditWorkItems
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
   deterministic            semantic
     analysis                analysis
          │                     │
          │                somente quando
          │                realmente necessário
          │                     │
          └──────────┬──────────┘
                     ▼
                  Evidence
                     │
                     ▼
              Verification
```

E isso é diferente do classificador do `audit-normalize`.

---

## 1. Primeiro classificador: tipo de arquivo

Esse é um caso óbvio em que **não deveria existir LLM**.

Por exemplo:

```text
pom.xml              → BUILD/MAVEN
build.gradle         → BUILD/GRADLE
package.json         → BUILD/NODE
Dockerfile            → INFRASTRUCTURE
docker-compose.yml   → INFRASTRUCTURE
*.sql                 → DATABASE
*.java                → SOURCE/JAVA
*.py                  → SOURCE/PYTHON
*.yml                 → CONFIGURATION/CI
.github/workflows/*  → CI_CD
.gitignore            → GIT
README.md             → DOCUMENTATION
```

Isso pode ser determinado por:

* extensão;
* basename;
* caminho;
* conteúdo estrutural;
* parser;
* assinatura do arquivo.

Não há motivo para consumir LLM.

E esse classificador alimenta o `AuditPlan`.

---

# 2. Classificador de tecnologia / stack

Também deve ser predominantemente determinístico.

Exemplo:

```text
pom.xml
   ↓
Maven
   ↓
pom.xml dependencies
   ↓
Java
Spring/Javalin/etc.
PostgreSQL/etc.
```

Ou:

```text
build.gradle.kts
   ↓
Gradle Kotlin DSL
   ↓
plugins
   ↓
Java 21
JUnit
SpotBugs
PMD
```

Isso é análise estrutural.

LLM só entra se houver uma ambiguidade que realmente não possa ser resolvida por parsing/regras.

---

# 3. Classificador de aplicabilidade

Esse é particularmente importante.

Em vez de:

```text
LLM:
"Será que SSRF é aplicável?"
```

primeiro fazemos:

```text
HTTP client encontrado?
        │
       YES
        ↓
SSRF → APPLICABLE
```

Por exemplo:

```text
requests
axios
fetch
HttpClient
OkHttp
RestTemplate
WebClient
curl
wget
webhooks
proxy
URL.openConnection
```

→ evidência de superfície HTTP.

Então:

```text
SSRF = APPLICABLE
```

Outro exemplo:

```text
frontend JavaScript encontrado
        ↓
XSS = APPLICABLE
```

```text
HTML templating encontrado
        ↓
HTML injection = APPLICABLE
```

```text
upload de arquivos encontrado
        ↓
FILE_SECURITY = APPLICABLE
```

```text
nenhum mecanismo de autenticação encontrado
        ↓
AUTHENTICATION = NOT_DETERMINABLE
```

E aqui existe uma regra arquitetural importante que você já definiu:

```text
incerteza
   ↓
não excluir
```

Portanto um classificador determinístico pode produzir:

```text
APPLICABLE
NOT_APPLICABLE
NOT_DETERMINABLE
```

sem LLM.

---

# 4. Classificador de tarefa

Esse é outro que eu colocaria explicitamente na arquitetura.

Depois da descoberta:

```text
AuditWorkItem
```

pode ser classificado estruturalmente.

Exemplo:

```text
"enumerar arquivos Java"
        ↓
DETERMINISTIC_EXTRACTION
```

```text
"extrair dependências Maven"
        ↓
DETERMINISTIC_EXTRACTION
```

```text
"analisar histórico Git"
        ↓
DETERMINISTIC_ANALYSIS
```

```text
"verificar PreparedStatement"
        ↓
STATIC_SECURITY_ANALYSIS
```

```text
"avaliar se esta regra de negócio é coerente"
        ↓
SEMANTIC_ANALYSIS
```

```text
"correlacionar duas evidências conflitantes"
        ↓
HIGH_VALUE_SEMANTIC_ANALYSIS
```

Isso permite uma divisão muito importante:

```text
             AuditWorkItem
                    │
                    ▼
           ┌────────────────┐
           │ Can algorithm  │
           │ solve this?    │
           └───────┬────────┘
                   │
          ┌────────┴────────┐
         YES                NO
          │                  │
          ▼                  ▼
    deterministic          LLM
       worker             worker
```

Essa é uma das principais fontes de economia.

---

# 5. Classificador de complexidade/risco

Mesmo entre tarefas que precisam de LLM, não devemos mandar tudo para o modelo mais forte.

Podemos ter algo como:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

determinado inicialmente por sinais objetivos:

```text
quantidade de arquivos
quantidade de contexto
número de dependências
número de caminhos
categoria de segurança
presença de conflito
impacto potencial
ambiguidade
quantidade de evidências
```

Exemplo:

```text
"Explique este método de 20 linhas"
        ↓
LOW

"Analise 3 DAOs procurando SQL injection"
        ↓
MEDIUM

"Verifique isolamento de tenant em 40 endpoints"
        ↓
HIGH

"Resolver conflito entre findings de segurança"
        ↓
HIGH/CRITICAL
```

E somente depois:

```text
Task Policy
     ↓
OmniRoute
```

---

# 6. Classificador de sensibilidade

Também deve ser preferencialmente **não-LLM**.

Antes de delegar:

```text
dados da auditoria
       ↓
sensitivity classifier
```

pode detectar:

```text
.env
private key
API key
password
JWT secret
database credential
PII
tokens
certificates
```

e produzir:

```text
PUBLIC
INTERNAL
SENSITIVE
SECRET
UNKNOWN
```

Se:

```text
UNKNOWN
```

→ egress fail-closed.

Não precisamos perguntar a um LLM:

> "Isso parece um segredo?"

quando regex/parser/secret scanner consegue determinar isso de forma muito mais barata e reproduzível.

---

# 7. Classificador de contexto necessário

Outro ponto que faltou na minha resposta anterior.

A auditoria não deve mandar sempre:

```text
repo inteiro
```

para o modelo.

Primeiro deve determinar:

```text
qual contexto esta tarefa realmente precisa?
```

Exemplo:

```text
SQL Injection
    ↓
DAOs
SQL
repositories
database mapping
```

Não:

```text
README
Docker
frontend inteiro
Git history inteira
```

Outro:

```text
CI/CD
    ↓
.github/
Dockerfile
build files
dependency manifests
```

Outro:

```text
IDOR
    ↓
routes
controllers
authentication
authorization
services
ownership queries
schema
```

Isso pode ser feito majoritariamente por:

* dependency graph;
* imports;
* file classification;
* symbol index;
* path rules;
* call graph;
* Git impact;
* search/indexing.

O LLM recebe apenas o contexto que o planner determinou.

---

# 8. E existe ainda um classificador extremamente importante: "LLM é necessário?"

Eu colocaria isso como um **gate explícito**.

```text
                    TASK
                      │
                      ▼
             ┌─────────────────┐
             │ deterministic   │
             │ strategy exists?│
             └────────┬────────┘
                      │
             ┌────────┴────────┐
            YES                NO
             │                  │
             ▼                  ▼
       deterministic       semantic task
          worker                 │
             │                   ▼
             │             complexity
             │             classification
             │                   │
             │                   ▼
             │             Task Policy
             │                   │
             │                   ▼
             │              OmniRoute
             │                   │
             └──────────┬────────┘
                        ▼
                     Evidence
```

Isso deveria ser uma decisão de **orquestração**, não uma decisão improvisada dentro de cada agente.

---

# Onde isso se encaixa na arquitetura atual

A arquitetura fica mais clara assim:

```text
┌─────────────────────────────────────────────┐
│                 DISCOVERY                   │
│                                             │
│ filesystem / Git / manifests / parsers     │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│          DETERMINISTIC CLASSIFIERS          │
│                                             │
│ file type                                   │
│ technology                                  │
│ stack                                       │
│ applicability                               │
│ task type                                   │
│ complexity                                  │
│ sensitivity                                 │
│ context requirements                        │
│ deterministic-vs-semantic                   │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│                AUDIT PLANNER                │
│                                             │
│ scope                                       │
│ work items                                  │
│ dependencies                                │
│ budget                                      │
│ execution policy                            │
│ verification policy                         │
└──────────────────────┬──────────────────────┘
                       ▼
              ┌─────────────────┐
              │  AuditWorkItem  │
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
       deterministic          semantic
          worker               worker
              │                 │
              │                 ▼
              │             Task Policy
              │                 │
              │                 ▼
              │             OmniRoute
              │                 │
              │                 ▼
              │                LLM
              │
              └────────┬────────┘
                       ▼
                    Evidence
                       ▼
                  Verification
                       ▼
                    AuditRun
```

O `audit-normalize` fica **depois disso tudo**:

```text
AuditRun
   ↓
auditor Markdown
   ↓
audit-normalize
   ↓
report_data.json
```

Então sim: **os classificadores das auditorias pertencem principalmente ao Layer 2 / Orchestrator**, enquanto o `audit-normalize` terá seus próprios classificadores de documentos/fontes porque essa é outra responsabilidade.

---

## A economia real

A diferença não é pequena.

Sem isso:

```text
100 arquivos
×
10 categorias
×
LLM
```

Você acaba fazendo dezenas/centenas de chamadas que poderiam ter sido resolvidas por:

```text
filesystem
AST
parser
regex
Git
dependency graph
schema parser
static analysis
rules
```

Com classificação determinística:

```text
1000 arquivos
       │
       ▼
deterministic discovery
       │
       ├── 700 irrelevantes para determinada auditoria
       ├── 200 analisáveis deterministicamente
       └── 100 precisam de raciocínio semântico
                                  │
                                  ▼
                              LLM calls
```

E mesmo esses 100 podem ser divididos:

```text
70 → modelo barato
20 → modelo intermediário
10 → modelo forte
```

E uma parcela ainda pode ser:

```text
cache/reuse
```

ou:

```text
REVALIDATE
```

em vez de:

```text
RUN
```

É justamente aqui que a arquitetura começa a ficar economicamente muito mais eficiente.

A documentação que você já havia definido inclusive coloca explicitamente **audit applicability, audit planning, project profile, dependency graph, Git impact analysis, deterministic evidence, progressive disclosure, REUSE/REVALIDATE/RUN e audit completeness** fora do OmniRoute, porque são decisões do domínio da auditoria. 

E a divisão correta com o OmniRoute continua sendo:

```text
Seu sistema:
    O QUE precisa ser feito?
    POR QUE?
    COM QUE contexto?
    PRECISA de LLM?
    QUAL política?
    QUAL orçamento?
    QUAL qualidade mínima?

OmniRoute:
    QUAL candidato concreto?
    QUAL provider?
    QUAL rota?
    fallback
    quota
    health
    latency
    cost
```



### Portanto, corrigindo o diagnóstico anterior

**Não deveríamos ter uma arquitetura em que "o planner decide e então manda tudo para LLM".**

O desenho correto é:

> **Discovery → classificação determinística → análise determinística quando possível → somente o resíduo semanticamente difícil vai para LLM.**

E isso deve ser uma propriedade arquitetural explícita do `project-audit`, não apenas uma otimização eventual.


O prompt abaixo instrui o agente a **parar a implementação**, recuperar o estado arquitetural existente, incorporar formalmente os classificadores determinísticos e atualizar memória + documentação antes de qualquer novo código.

# CONTEXTO CRÍTICO — ATUALIZAÇÃO ARQUITETURAL OBRIGATÓRIA

Você está trabalhando no projeto `project-audit`, um sistema de auditoria técnica de software orientado a agentes, evidências, execução controlada, persistência de estado e posterior normalização/publicação.

## REGRA MAIS IMPORTANTE

**NÃO ESCREVA NOVO CÓDIGO DE IMPLEMENTAÇÃO AGORA.**

Antes de continuar qualquer implementação, você deve:

1. recuperar e compreender integralmente a arquitetura atual;
2. revisar os documentos arquiteturais existentes;
3. atualizar a arquitetura para incorporar explicitamente a estratégia de classificação determinística;
4. formalizar a fronteira entre análise determinística e análise semântica por LLM;
5. formalizar como classificações entram no planejamento da auditoria;
6. formalizar provenance dessas decisões;
7. atualizar os documentos arquiteturais afetados;
8. atualizar a memória persistente do projeto;
9. revisar consistência entre ADRs, Canonical Data Model, schemas físicos e implementação existente;
10. somente depois disso propor a próxima etapa de implementação.

A arquitetura deve ser atualizada **antes de qualquer código novo**.

---

# 1. OBJETIVO DESTA ATUALIZAÇÃO

O sistema deve seguir explicitamente este princípio:

> **Sempre que uma decisão puder ser resolvida por algoritmo, regra, parser, análise estrutural, análise estática ou heurística determinística sem perda relevante de qualidade, a decisão deve ser tomada sem utilizar LLM.**

LLM deve ser utilizado somente quando:

* a tarefa exige interpretação semântica real;
* a análise determinística não consegue concluir;
* existe ambiguidade material;
* a qualidade perdida por uma solução puramente determinística seria relevante;
* ou a política de auditoria explicitamente exigir raciocínio semântico.

O objetivo não é eliminar LLM.

O objetivo é fazer com que:

```text
LLM = recurso semântico de alto custo
```

e não:

```text
LLM = mecanismo padrão para toda decisão.
```

---

# 2. PRINCÍPIO DE ARQUITETURA

O fluxo conceitual deve evoluir para:

```text
PROJECT
   ↓
DISCOVERY
   ↓
DETERMINISTIC CLASSIFICATION
   ↓
AUDIT PLANNING
   ↓
AUDIT WORK ITEMS
   ↓
DETERMINISTIC ANALYSIS
   │
   ├── conclusão suficiente
   │        ↓
   │      EVIDENCE
   │
   └── ambiguidade / necessidade semântica
            ↓
       SEMANTIC ANALYSIS
            ↓
          LLM
            ↓
        VALIDATION
            ↓
         EVIDENCE
```

Não implemente este fluxo automaticamente.

Primeiro atualize a arquitetura que define esse fluxo.

---

# 3. CLASSIFICADORES DETERMINÍSTICOS

A arquitetura deve reconhecer explicitamente uma camada de classificação determinística.

Ela deve ser composta por classificadores pequenos, especializados e verificáveis.

Não criar necessariamente um único "super-classificador".

A arquitetura deve avaliar a necessidade dos seguintes classificadores:

## 3.1 File Classification

Determinar:

* tipo de arquivo;
* linguagem;
* função provável;
* categoria;
* relevância para determinadas auditorias.

Fontes:

```text
extension
basename
path
content signature
parser
```

Exemplos:

```text
pom.xml
build.gradle
package.json
Dockerfile
*.sql
*.java
*.py
.github/workflows/*
.gitignore
README.md
```

Isso deve ser determinístico sempre que possível.

---

# 4. TECHNOLOGY / STACK CLASSIFICATION

Determinar, sem LLM quando possível:

```text
language
runtime
framework
build system
package manager
ORM
database
frontend
backend
containerization
CI/CD
test framework
authentication technology
```

Utilizar:

```text
manifests
dependency declarations
configuration
directory structure
parsers
known signatures
```

Não utilizar LLM para simplesmente descobrir aquilo que um parser ou regra pode determinar.

---

# 5. APPLICABILITY CLASSIFICATION

A auditoria deve possuir um mecanismo explícito para determinar:

```text
APPLICABLE
NOT_APPLICABLE
NOT_DETERMINABLE
```

Exemplos:

```text
HTTP client encontrado
→ SSRF = APPLICABLE
```

```text
frontend JavaScript encontrado
→ XSS = APPLICABLE
```

```text
upload encontrado
→ FILE_SECURITY = APPLICABLE
```

```text
nenhuma evidência suficiente sobre autenticação
→ AUTHENTICATION = NOT_DETERMINABLE
```

A regra arquitetural é:

```text
uncertainty ≠ not applicable
```

Nunca excluir uma área somente porque o classificador não conseguiu determiná-la.

---

# 6. TASK CLASSIFICATION

Cada `AuditWorkItem` deve poder ser classificado quanto ao tipo de execução necessário.

Exemplos:

```text
DETERMINISTIC_EXTRACTION
DETERMINISTIC_ANALYSIS
STATIC_ANALYSIS
SEMANTIC_ANALYSIS
HIGH_RISK_SEMANTIC_ANALYSIS
```

Os valores finais devem ser definidos pelo modelo arquitetural.

O objetivo é permitir:

```text
task
 ↓
can deterministic machinery solve it?
 ↓
YES → deterministic worker
NO  → semantic worker
```

Não mandar automaticamente todo `AuditWorkItem` para LLM.

---

# 7. COMPLEXITY / RISK CLASSIFICATION

Avaliar se a tarefa pode ser tratada com:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

ou uma taxonomia equivalente definida pela arquitetura.

A classificação deve considerar sinais observáveis, por exemplo:

```text
scope size
context size
number of dependencies
number of execution paths
security sensitivity
ambiguity
potential impact
cross-module dependencies
conflicting evidence
```

Essa classificação deve influenciar:

* estratégia de execução;
* orçamento;
* necessidade de verificação;
* possível escalonamento;
* seleção de política de delegação.

Não deve substituir o sistema de roteamento do OmniRoute.

---

# 8. SENSITIVITY CLASSIFICATION

Antes de qualquer egress para infraestrutura externa, avaliar deterministicamente quando possível:

```text
PUBLIC
INTERNAL
SENSITIVE
SECRET
UNKNOWN
```

ou taxonomia equivalente aprovada pela arquitetura.

Detectar, quando possível:

```text
passwords
API keys
JWT secrets
private keys
database credentials
tokens
.env
PII
certificates
```

A regra continua:

```text
UNKNOWN
   ↓
FAIL CLOSED
```

Não enviar dados externamente quando a política não puder determinar sua segurança.

---

# 9. CONTEXT CLASSIFICATION

A auditoria deve determinar qual contexto é realmente necessário para cada tarefa.

Não enviar automaticamente:

```text
repository inteiro
```

para cada análise.

Exemplo:

```text
SQL Injection
    ↓
DAOs
repositories
SQL
database mapping
relevant configuration
```

Exemplo:

```text
CI/CD
    ↓
.github
Dockerfile
build files
dependency manifests
```

Exemplo:

```text
IDOR
    ↓
routes
controllers
authentication
authorization
services
ownership logic
relevant schema
```

A arquitetura deve formalizar:

```text
context requirements
```

como parte do planejamento.

Isso deve permitir progressive disclosure.

---

# 10. DETERMINISTIC-FIRST GATE

Deve existir uma decisão arquitetural explícita equivalente a:

```text
DETERMINISTIC-FIRST
```

Fluxo:

```text
AuditWorkItem
      ↓
Deterministic Strategy Available?
      │
 ┌────┴────┐
YES        NO
 │          │
 ▼          ▼
Run        Semantic
deterministic analysis
 │          │
 │          ▼
 │         LLM
 │          │
 └────┬─────┘
      ▼
   Evidence
```

Se a análise determinística produzir evidência suficiente:

```text
não chamar LLM.
```

Se produzir resultado inconclusivo:

```text
escalate to semantic analysis
```

A arquitetura deve definir exatamente o que significa:

```text
resultado suficiente
```

e:

```text
resultado inconclusivo.
```

---

# 11. NÃO CRIAR UM SEGUNDO OMNIROUTE

A camada determinística não deve se transformar em um novo sistema de routing de modelos.

A divisão permanece:

## Nosso sistema

Decide:

```text
WHAT
WHY
WHICH TASK
WHICH CONTEXT
WHICH POLICY
WHETHER LLM IS NECESSARY
QUALITY REQUIREMENTS
BUDGET
ESCALATION
VERIFICATION
```

## OmniRoute

Decide:

```text
WHICH PROVIDER
WHICH CONCRETE MODEL
ROUTING
FALLBACK
HEALTH
QUOTA
RATE LIMIT
PROVIDER RETRY
MODEL AVAILABILITY
INFRASTRUCTURE COST/HEALTH
```

Não duplicar:

```text
provider health
provider ranking
provider fallback
quota calculation
model availability
HTTP retry engine
circuit breakers
```

Essas responsabilidades permanecem no OmniRoute.

---

# 12. TASK POLICY

O conceito de `Task Policy` deve ser preservado.

O sistema não deve fazer:

```text
Task
 ↓
choose exact model
```

Deve fazer:

```text
Task
 ↓
choose semantic execution policy
 ↓
OmniRoute
 ↓
concrete model/provider
```

Exemplos:

```text
simple extraction
→ deterministic-first / cheap fallback

coding
→ coding policy

large-context analysis
→ context-optimized policy

critical security
→ quality-first policy

ambiguous business logic
→ semantic analysis policy
```

Os nomes finais devem ser definidos durante o design.

---

# 13. CLASSIFICATION RESULT

Avaliar a necessidade de formalizar uma entidade semelhante a:

```text
ClassificationResult
```

Ela deve permitir rastrear:

```text
classifier_id
classifier_version
input references
result
confidence
evidence
provenance
```

Não adicione isso diretamente aos schemas sem antes revisar o Canonical Data Model.

Primeiro determinar:

```text
isso é entidade canônica?
ou
é metadado operacional do planner?
```

Essa decisão deve ser arquiteturalmente justificada.

---

# 14. PROVENANCE

Toda decisão de classificação que influenciar materialmente a auditoria deve ser rastreável.

Exemplo:

```text
classifier
version
input
decision
evidence
timestamp
policy
```

Deve ser possível responder:

> "Por que esta auditoria decidiu usar LLM para esta tarefa?"

e:

> "Por que esta tarefa foi resolvida deterministicamente?"

Não depender apenas dos logs do agente.

---

# 15. CACHE DETERMINÍSTICO

Preservar e formalizar o conceito de cache determinístico.

Para operações determinísticas:

```text
normalized inputs
+
tool version
+
classifier version
+
policy version
+
context hash
+
output contract
```

podem formar uma identidade determinística.

O cache pode ser fonte de reutilização confiável quando a validade do resultado estiver preservada.

Isso é diferente de:

```text
LLM semantic cache
```

que deve permanecer otimização de infraestrutura.

---

# 16. REUSE / REVALIDATE / REAUDIT

Os classificadores devem alimentar, quando aplicável:

```text
REUSE
REVALIDATE
REAUDIT
```

Exemplo:

```text
mesmo target snapshot
+
mesma ferramenta
+
mesma política
+
mesmo contexto
+
evidência ainda válida
```

→ `REUSE`.

Se alguma dependência mudou:

```text
REVALIDATE
```

Se a validade foi quebrada:

```text
REAUDIT
```

Não permitir que cache contorne a semântica de validade de Evidence.

---

# 17. RELAÇÃO COM EVIDENCE DEPENDENCY GRAPH

A nova arquitetura deve integrar a classificação ao futuro:

```text
Evidence Dependency Graph
```

Exemplo:

```text
File Classification
      ↓
Applicability
      ↓
Context Selection
      ↓
AuditWorkItem
      ↓
Execution
      ↓
Evidence
```

Se uma decisão anterior mudar:

```text
classification changed
        ↓
dependent work invalidated
        ↓
dependent evidence reconsidered
```

Não implementar ainda.

Primeiro definir a semântica.

---

# 18. SNAPSHOT DRIFT

A atualização arquitetural deve preservar a resolução de Snapshot Drift.

Não criar classificadores que permitam continuar silenciosamente depois que:

```text
target snapshot
```

foi alterado.

Se houver drift:

```text
STOP
↓
invalidate affected evidence
↓
invalidate affected classification/work where necessary
↓
prevent COMPLETE publication
```

A nova arquitetura deve explicar quais classificações também dependem do snapshot.

---

# 19. SECURITY AUDITOR

O Security Auditor continua sendo um worker especializado.

Ele:

```text
recebe dados explicitamente delimitados
analisa
produz evidências/resultados
```

Ele não deve:

```text
possuir AuditRun
possuir StateStore
alterar estado canônico
decidir política global
bypassar Execution Gate
bypassar Egress Policy
```

A classificação determinística deve acontecer antes da delegação quando aplicável.

---

# 20. AUDIT-NORMALIZE

Não alterar o contrato congelado do `audit-normalize` para resolver esta necessidade.

Ele continua sendo:

```text
Markdown
 ↓
Discovery
 ↓
Classification
 ↓
Extraction
 ↓
Normalization
 ↓
Deduplication
 ↓
Conflict Analysis
 ↓
Validation
 ↓
Canonical JSON
```

O classificador do `audit-normalize` é outro conceito:

```text
source classification
```

e não deve ser confundido com:

```text
audit task classification
```

ou:

```text
LLM-vs-deterministic execution classification
```

---

# 21. O QUE DEVE SER ATUALIZADO

Antes de qualquer código, localizar os documentos arquiteturais afetados.

No mínimo revisar:

```text
docs/references/canonical-data-model.md
docs/references/audit-architecture-specification.md
docs/references/semantic-validators.md
docs/references/architectural-precedents.md
ADR-08
ADR-09
docs/architecture/project-audit-current-state.md
```

e todos os ADRs/documentos que definam:

```text
AuditPlan
AuditWorkItem
Evidence
AuditRun
execution policy
delegation
budget
provenance
cache
snapshot drift
```

Não presumir que todos precisarão ser modificados.

Classificar cada documento:

```text
NO_CHANGE
REVIEWED
UPDATED
SUPERSEDED
NEW_DOCUMENT_REQUIRED
```

---

# 22. CANONICAL DATA MODEL FIRST

Antes de modificar schemas físicos:

```text
Architecture
      ↓
Canonical Data Model
      ↓
Semantic invariants
      ↓
Physical JSON Schemas
      ↓
Implementation
```

Nunca inverter:

```text
implementation
 ↓
schema
 ↓
architecture
```

Se `ClassificationResult` precisar entrar no modelo canônico, isso deve ser demonstrado primeiro.

---

# 23. NÃO MODIFICAR SCHEMAS APENAS POR CONVENIÊNCIA

Os schemas atuais possuem `additionalProperties: false` como regra de contrato.

Portanto:

> qualquer nova propriedade exige mudança arquitetural explícita e versionada.

Não adicionar:

```text
classification
classifier
execution_kind
complexity
```

aos schemas apenas porque parecem úteis.

Primeiro decidir sua natureza ontológica.

---

# 24. MEMÓRIA PERSISTENTE

Atualize a memória do projeto com o novo entendimento arquitetural.

A memória deve registrar, de forma concisa:

```text
Deterministic-first is a mandatory architectural principle.
```

E:

```text
LLM is an escalation mechanism for semantic work, not the default execution mechanism.
```

Registrar também:

```text
audit task classification
applicability classification
context classification
sensitivity classification
deterministic-vs-semantic gate
```

Mas não duplicar toda a arquitetura na memória.

A documentação do repositório continua sendo a fonte detalhada.

---

# 25. DOCUMENTO NOVO, SE NECESSÁRIO

Se a arquitetura atual não possuir lugar adequado para esta especificação, criar um documento/ADR dedicado, por exemplo:

```text
ADR-10 — Deterministic-First Audit Classification and Semantic Escalation
```

O nome e número devem ser adaptados ao estado real do repositório.

O documento deve responder:

1. Por que classificação determinística é obrigatória?
2. Quais decisões devem ser determinísticas?
3. Quando LLM é permitido?
4. Como tratar ambiguidade?
5. Como classificações entram no AuditPlan?
6. Como são versionadas?
7. Como possuem provenance?
8. Como afetam cache?
9. Como afetam budget?
10. Como afetam REUSE/REVALIDATE/REAUDIT?
11. Como interagem com Snapshot Drift?
12. Como interagem com Evidence Dependency Graph?
13. Como interagem com OmniRoute?
14. Como evitamos criar um segundo router?
15. Como validamos que a arquitetura está sendo seguida?

---

# 26. MATRIZ OBRIGATÓRIA

Criar uma matriz arquitetural semelhante a:

| Decision                     | Deterministic? | LLM allowed? | Evidence required   | Owner             |
| ---------------------------- | -------------- | ------------ | ------------------- | ----------------- |
| File type                    | YES            | NO           | file metadata       | Classifier        |
| Language                     | YES            | NO           | parser/signature    | Classifier        |
| Stack                        | YES            | FALLBACK     | manifests/config    | Classifier        |
| Applicability                | YES            | FALLBACK     | structural evidence | Planner           |
| Context selection            | YES            | FALLBACK     | dependency/index    | Planner           |
| Secret detection             | YES            | FALLBACK     | scanner/rules       | Security boundary |
| Task complexity              | YES            | FALLBACK     | measurable signals  | Planner           |
| Business-rule interpretation | NO             | YES          | project evidence    | Semantic Worker   |
| Cross-finding correlation    | PARTIAL        | YES          | findings/evidence   | Semantic Worker   |
| Provider selection           | NO             | NO           | OmniRoute           | OmniRoute         |

Os valores finais devem ser definidos pelo estudo arquitetural, não copiados cegamente desta tabela.

---

# 27. TESTES ARQUITETURAIS

Antes da implementação final, definir como comprovar:

```text
deterministic task → no LLM call
```

```text
deterministic result sufficient → no escalation
```

```text
ambiguous result → semantic escalation
```

```text
UNKNOWN applicability → scope preserved
```

```text
UNKNOWN egress classification → send blocked
```

```text
snapshot drift → dependent work/evidence invalidated
```

```text
classification change → dependent work reconsidered
```

```text
OmniRoute never decides audit applicability
```

```text
worker cannot mutate canonical state
```

Esses devem virar testes de arquitetura/contrato posteriormente.

---

# 28. ECONOMIA E EFICIÊNCIA

A atualização deve explicitar que eficiência não significa simplesmente:

```text
usar modelo barato
```

A principal economia ocorre antes da chamada:

```text
não executar
↓
não analisar
↓
não enviar contexto
↓
não chamar LLM
```

Portanto:

```text
deterministic classification
+
scope reduction
+
progressive disclosure
+
deterministic cache
+
REUSE
+
REVALIDATE
+
budget
+
semantic escalation
```

são mecanismos de economia.

O OmniRoute continua otimizando a execução das chamadas que realmente precisam acontecer.

---

# 29. REGRA CONTRA OVERENGINEERING

Não criar classificadores sofisticados apenas porque parecem arquiteturalmente elegantes.

Um classificador deve existir quando:

```text
benefício
>
complexidade
```

e especialmente quando:

```text
custo de LLM evitado
>
custo de classificação
```

Preferir:

```text
parser simples
regex controlada
AST
dependency graph
file metadata
Git metadata
schema inspection
static analysis
```

antes de criar um modelo semântico.

---

# 30. CRITÉRIO DE CONCLUSÃO

Você não pode declarar esta etapa concluída apenas porque escreveu um ADR.

Antes de terminar, confirme:

```text
[ ] arquitetura atual foi lida
[ ] Canonical Data Model foi revisado
[ ] ADRs relevantes foram revisados
[ ] AuditPlan foi revisado
[ ] AuditWorkItem foi revisado
[ ] Evidence foi revisado
[ ] Snapshot Drift foi considerado
[ ] Evidence Dependency foi considerado
[ ] OmniRoute boundary foi revisada
[ ] classificadores determinísticos foram definidos
[ ] deterministic-first gate foi definido
[ ] semantic escalation foi definida
[ ] provenance foi definida
[ ] impacto em cache foi definido
[ ] impacto em budget foi definido
[ ] impacto em REUSE/REVALIDATE/REAUDIT foi definido
[ ] impacto em schemas foi analisado
[ ] impacto nos validators foi analisado
[ ] testes arquiteturais foram definidos
[ ] memória foi atualizada
[ ] documentação foi atualizada
[ ] consistência entre documentos foi verificada
[ ] nenhuma implementação nova foi feita
```

---

# 31. REGRA DE PARADA

Se encontrar uma contradição entre:

```text
Canonical Data Model
ADR
Architecture Specification
Schema
Implementation
Memory
```

não escolha silenciosamente uma versão.

Registre:

```text
CONFLICT
```

determine a fonte arquiteturalmente autoritativa e proponha a resolução.

Se a resolução exigir alteração de arquitetura:

```text
ADR / design update
```

antes de código.

---

# 32. SAÍDA OBRIGATÓRIA

Ao terminar esta fase, informe somente:

```text
ARCHITECTURE UPDATE

Status:
ARCHITECTURE UPDATED
ou
ARCHITECTURE UPDATE BLOCKED

Documents reviewed:
...

Documents updated:
...

New ADRs:
...

Canonical model impact:
...

Schema impact:
...

Deterministic classifiers:
...

LLM escalation policy:
...

Evidence dependency impact:
...

Snapshot drift impact:
...

Memory:
UPDATED

Implementation:
NOT STARTED
```

Não implemente a nova arquitetura nesta etapa.

A implementação somente começa depois que a arquitetura revisada estiver consistente e registrada.

---

# PRINCÍPIO FINAL

O sistema não deve perguntar primeiro:

> "Qual LLM devo usar?"

Deve perguntar:

> **"Preciso de uma LLM para resolver este problema?"**

Se a resposta for:

```text
não
```

use computação determinística.

Se for:

```text
talvez
```

tente primeiro reduzir a incerteza deterministicamente.

Somente quando a tarefa realmente exigir raciocínio semântico:

```text
LLM
```

E quando houver LLM:

```text
Orchestrator
→ política semântica
→ OmniRoute
→ modelo/provedor
```

O sistema de auditoria continua sendo responsável pelo **que precisa ser feito**.

O OmniRoute continua sendo responsável por **como executar uma chamada de modelo**.

Essa separação deve permanecer explícita em toda a arquitetura.

Esse é o ponto que eu considero importante: **não peça ao agente apenas para "adicionar classificadores"**. O prompt obriga uma revisão do modelo ontológico, `AuditPlan`, `AuditWorkItem`, Evidence, cache, budget, Snapshot Drift e schemas antes de implementar. Isso evita que ele simplesmente crie uma classe `Classifier` e considere o problema resolvido.


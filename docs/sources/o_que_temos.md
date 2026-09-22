Hoje vocês têm uma arquitetura em que **a parte difícil de execução já foi bastante fechada**, mas a parte de decisão inteligente ainda precisa ser formalizada. O ponto central é separar **decisão determinística**, **decisão barata/heurística** e **raciocínio caro**.

## 1. O que vocês têm hoje

A visão completa é aproximadamente esta:

```text
                         PROJECT-AUDIT SYSTEM
                                 │
                    ┌────────────┴────────────┐
                    │                         │
              CONTROL PLANE              PROJECT DATA
                    │                         │
                    ▼                         │
             TargetSnapshot                   │
                    │                         │
                    ▼                         │
               AuditPlan                      │
                    │                         │
                    ▼                         │
             AuditWorkItems                   │
                    │                         │
             ┌──────┴──────┐                  │
             │             │                  │
             ▼             ▼                  ▼
        Classificação   Aplicabilidade    Contexto
        / Planning       / Scope          do projeto
             │             │
             └──────┬──────┘
                    ▼
              Specialized Auditors
                    │
        ┌───────────┼────────────┐
        ▼           ▼            ▼
   Architecture  Security     Database
      Auditor      Auditor      Auditor
        │           │            │
        └───────────┼────────────┘
                    ▼
                 Evidence
                    │
                    ▼
                AuditRun
                    │
                    ▼
             Semantic Validators
                    │
                    ▼
              can_publish()
                    │
                    ▼
             audit-normalize
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
     report-publish       issue-forge
```

A diferença importante é que **Core não é o auditor**.

O Core coordena.

Os auditores investigam.

O `audit-normalize` normaliza.

Isso evita colocar inteligência demais em um único componente.

---

# 2. O que já está efetivamente fechado

Vocês já fecharam muita coisa.

### Estado e execução

Existe o modelo de:

* `TargetSnapshot`
* `AuditPlan`
* `AuditWorkItem`
* `Attempt`
* `ExecutionReceipt`
* `Evidence`
* `AuditRun`

E as regras de:

```text
retry
recovery
budget
persistence
publication
immutability
provenance
```

já foram endurecidas.

### Segurança de execução

A fronteira também está muito mais clara:

```text
Worker
   ↓
Egress / Capability checks
   ↓
Execution Gate
   ↓
Backend
```

com comportamento fail-closed.

### Delegação

O Core não deveria saber:

```text
qual modelo
qual provider
qual rota
qual fallback
```

Ele pede uma tarefa.

A infraestrutura de delegação resolve a execução concreta. Isso mantém OmniRoute substituível.

### Segurança do prompt

O problema encontrado com `target_surface` foi corrigido estruturalmente.

A solução final não depende de:

```text
blacklist("<")
blacklist(">")
blacklist("</...")
```

mas de serialização estruturada:

```text
project data
    ↓
JSON serialization
    ↓
untrusted block
    ↓
prompt
```

Essa é uma propriedade arquitetural muito mais forte.

### Forense

E uma coisa importante: vocês não aceitaram as primeiras implementações simplesmente porque os testes passaram.

Houve:

```text
agente implementador
        ↓
agente revisor
        ↓
agente forense
        ↓
comparação de patches
        ↓
correções
        ↓
nova verificação
```

Isso revelou problemas que uma única execução teria deixado passar.

---

# 3. O que falta

O principal não é mais "consertar código".

É definir **como o sistema toma decisões**.

Existem dois grandes blocos restantes.

## A. Snapshot Drift

Ainda falta definir formalmente:

```text
Como sabemos que o projeto mudou durante a auditoria?
```

E principalmente:

```text
Se mudou, quais evidências ficaram inválidas?
```

Isso exige o modelo de dependência:

```text
Evidence
   │
   ├── depende de TargetSnapshot
   ├── depende de WorkItem
   ├── depende de Attempt
   └── depende de ExecutionReceipt
```

Sem esse grafo, dizer:

> "invalide as evidências afetadas"

é uma frase, não um algoritmo.

Por isso vocês corretamente pararam aqui.

---

# 4. Security Auditor

O segundo grande bloco é formalizar o auditor especializado.

Hoje sabemos que ele **deve existir**, mas ainda falta congelar completamente:

```text
Input
Output
WorkItems
Evidence
Provenance
Prompt contract
Failure semantics
Delegation
Scope
```

A ideia não é colocar isso dentro do Core.

Seria:

```text
Core
  │
  │ AuditWorkItem
  ▼
Security Auditor
  │
  ├── análise estática
  ├── análise de configuração
  ├── threat model
  ├── security checks
  └── evidências
          │
          ▼
       Evidence
```

---

# 5. E os classificadores? Onde entram?

Aqui está uma das partes mais importantes do design.

**Não coloque um "LLM classificador gigante" no meio de tudo.**

Eu separaria os classificadores por função.

## Classificador 1 — Applicability

Antes de criar trabalho:

```text
Projeto
 ↓
Stack Discovery
 ↓
Applicability Classifier
```

Exemplo:

```text
SQL Injection      → APPLICABLE
XSS                → APPLICABLE
Kubernetes         → NOT_APPLICABLE
GraphQL            → NOT_DETERMINABLE
```

Mas existe uma regra crítica:

```text
NOT_DETERMINABLE
      ↓
não excluir
      ↓
preservar possibilidade de inspeção
```

Esse classificador pode ser majoritariamente determinístico.

Por exemplo:

```text
pom.xml → Java
package.json → Node
Dockerfile → Docker
SQL migrations → Database
HTTP client → SSRF potencialmente aplicável
```

Só usar LLM quando a classificação realmente exigir interpretação.

---

# 6. Classificador 2 — Work Item Routing

Depois da aplicabilidade:

```text
AuditPlan
   ↓
WorkItems
   ↓
Task classification
```

Ele responde:

> Qual especialista precisa analisar isso?

Exemplo:

```text
"Repository concatena SQL"
        ↓
DATABASE / SECURITY

"JWT authorization"
        ↓
SECURITY

"Aggregate invariant"
        ↓
DOMAIN

"Gradle dependency resolution"
        ↓
BUILD
```

Isso pode ser uma combinação de:

```text
rules
+
cheap classifier
+
LLM fallback
```

Não precisa mandar cada arquivo para um modelo caro.

---

# 7. Classificador 3 — Sensitivity / Egress

Esse é diferente.

Ele existe **antes de mandar informação para fora**.

```text
DelegationRequest
       ↓
Sensitivity Classifier
       ↓
Egress Policy
       ↓
Execution Gate
       ↓
OmniRoute
```

Exemplo:

```text
PUBLIC
INTERNAL
SENSITIVE
SECRET
UNKNOWN
```

E:

```text
UNKNOWN
   ↓
DO NOT SEND
```

Esse classificador não é uma ferramenta de auditoria.

É uma ferramenta de **controle de segurança**.

---

# 8. Classificador 4 — Finding / Evidence Triage

Depois que um auditor retorna material:

```text
raw auditor output
       ↓
classifier / validator
       ↓
Evidence?
Finding candidate?
Control?
Anomaly?
Invalid output?
```

Aqui é importante não deixar o LLM "decidir a verdade".

Ele pode sugerir:

```text
"isso parece um finding de authorization"
```

mas a camada determinística valida:

```text
category
status
severity
confidence
provenance
location
schema
```

---

# 9. E aqui está a economia

O grande ganho dessa arquitetura é **não usar o modelo caro para tudo**.

Imagine um projeto com:

```text
20.000 arquivos
```

Uma arquitetura ruim faria:

```text
20.000 arquivos
   ↓
LLM caro
```

Isso é absurdo em custo.

A arquitetura de vocês permite:

```text
20.000 arquivos
       ↓
deterministic discovery
       ↓
cheap classification
       ↓
scope reduction
       ↓
2.000 arquivos relevantes
       ↓
specialized analysis
       ↓
300 work items
       ↓
deep reasoning somente onde necessário
```

A redução acontece **antes** do modelo caro.

---

# 10. E a economia não é somente tokens

Existem pelo menos cinco economias.

### 1. Token economy

Não mandar arquivos irrelevantes para modelos grandes.

### 2. Compute economy

Não executar análises caras quando uma regra determinística resolve.

### 3. Delegation economy

Não chamar OmniRoute/modelo se o resultado já existe.

Daí:

```text
REUSE
REVALIDATE
REAUDIT
```

no `AuditWorkItem`.

### 4. Retry economy

Não repetir trabalho indiscriminadamente.

O sistema sabe:

```text
retryable?
budget?
idempotent?
```

antes de tentar novamente.

### 5. Context economy

O auditor especializado recebe somente o contexto necessário.

Não:

```text
"leia o repositório inteiro"
```

mas:

```text
Security WorkItem
+
arquivos relevantes
+
evidências necessárias
+
TargetSnapshot
+
restrições
```

---

# 11. Por que esse design é bom?

O principal motivo não é "Clean Architecture".

É porque ele separa **responsabilidades epistemológicas**.

Cada camada responde uma pergunta diferente.

### Control Plane

> O que devemos fazer?

### Classificador

> O que parece relevante?

### Auditor

> O que foi encontrado?

### Evidence

> Qual é a evidência observável?

### Validator

> Essa estrutura é válida?

### `AuditRun`

> Qual é o estado da execução?

### `audit-normalize`

> Como transformar diferentes documentos em um dataset canônico?

### Publisher

> Como apresentar o resultado?

Nenhuma camada precisa fingir que sabe a resposta da outra.

---

# 12. E existe uma segunda propriedade muito importante

O sistema não confia cegamente no LLM.

A cadeia é:

```text
LLM output
    ↓
UNTRUSTED
    ↓
schema validation
    ↓
semantic validation
    ↓
provenance
    ↓
Evidence
```

Isso é fundamental.

Um LLM não tem autoridade para dizer:

```text
"isso é uma evidência válida"
```

O sistema determina se aquilo pode virar evidência.

---

# 13. A economia aparece também na escolha do modelo

Aqui entra o OmniRoute.

Você pode ter:

```text
                Task
                 │
          Task Classifier
                 │
       ┌─────────┼─────────┐
       ▼         ▼         ▼
      LOW      MEDIUM     HIGH
       │         │         │
    modelo A   modelo B   modelo C
```

Por exemplo conceitualmente:

```text
file classification
     → modelo barato

simple extraction
     → modelo barato

architecture ambiguity
     → modelo médio

security reasoning
     → modelo forte

critical verification
     → modelo forte + verifier
```

**Os nomes/modelos concretos ainda não precisam ser definidos agora.**

Isso pertence à política de execução/routing.

---

# 14. E o ponto mais importante: os classificadores não mandam no sistema

Eles sugerem/decidem dentro de seus limites.

A autoridade continua:

```text
Control Plane
      ↓
Policy
      ↓
Validators
      ↓
State
```

Não:

```text
LLM
 ↓
"acho que isso é seguro"
 ↓
executa
```

Essa separação é exatamente o que evita que uma classificação errada vire uma ação perigosa.

---

# 15. O desenho completo que eu usaria como modelo mental

```text
                    ┌──────────────────┐
                    │   TARGET SNAPSHOT │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ DISCOVERY        │
                    │ deterministic    │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ CLASSIFIERS      │
                    │ applicability    │
                    │ routing          │
                    │ sensitivity      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ AUDIT PLAN       │
                    │ + WORK ITEMS     │
                    └────────┬─────────┘
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
          Architecture   Security     Database
            Auditor       Auditor      Auditor
                │            │            │
                └────────────┼────────────┘
                             ▼
                         EVIDENCE
                             │
                             ▼
                    ┌──────────────────┐
                    │ SEMANTIC         │
                    │ VALIDATORS       │
                    └────────┬─────────┘
                             │
                             ▼
                       AUDIT RUN
                             │
                     ┌───────┴───────┐
                     ▼               ▼
                can_publish       recovery
                     │
                     ▼
                 NORMALIZE
                     │
                     ▼
              report_data.json
                │           │
                ▼           ▼
             Report       Issues
```

E a delegação externa fica numa fronteira lateral:

```text
Auditor
   │
   ▼
WorkerPort
   │
   ▼
Sensitivity
   │
   ▼
Egress Policy
   │
   ▼
Execution Gate
   │
   ▼
OmniRoute
   │
   ▼
Model
```

Isso é muito melhor do que colocar OmniRoute no centro da arquitetura.

---

# 16. O que falta para chegar lá

Eu dividiria em três grandes fases:

### Fase A — Design

Agora:

```text
ADR Snapshot Drift
ADR/Spec Evidence Dependency
ADR/Spec Security Auditor
```

### Fase B — Implementation

Depois:

```text
Evidence dependency/invalidation
Snapshot Drift
Security Auditor
classifiers necessários
```

### Fase C — Optimization

Só depois de tudo funcionar:

```text
classifier routing
model selection
cache
REUSE
parallelism
budget optimization
token optimization
```

Ou seja: **não precisamos otimizar antes de termos a semântica correta**.

A economia está no desenho desde já, mas a otimização fina de modelos vem depois.

---

## Em uma frase

O que vocês estão construindo não é simplesmente:

> "um agente que lê um projeto e usa LLM para auditá-lo."

É mais próximo de:

> **um sistema de execução auditável que usa LLMs como componentes especializados e não confiáveis dentro de um plano determinístico, com estado, evidência, políticas, provenance, validação e controle de custo.**

Essa é a razão estrutural pela qual o design é forte: **o modelo pode mudar, o OmniRoute pode mudar, os auditores podem mudar e até a estratégia de classificação pode mudar sem destruir o núcleo que garante que a auditoria continue sendo rastreável e controlável.**


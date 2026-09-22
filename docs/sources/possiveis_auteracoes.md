Sim, mas **não precisamos desmontar o que já temos**. A correção é principalmente arquitetural/documental antes de continuar implementando.

O ponto importante é: **a arquitetura atual já possui os lugares conceituais onde esses classificadores cabem**. O que está faltando é torná-los uma responsabilidade explícita e sistemática.

### O que eu não mudaria

Eu manteria:

* `TargetSnapshot`
* `AuditPlan`
* `AuditWorkItem`
* `Attempt`
* `ExecutionReceipt`
* `Evidence`
* `AuditRun`
* `StateStore`
* validators determinísticos
* `WorkerPort`
* fronteira com OmniRoute
* `REUSE / REVALIDATE / REAUDIT`
* orçamento
* provenance
* Execution Gate
* egress policy
* segurança/fail-closed
* `audit-normalize` congelado.

Essas peças não precisam ser substituídas.

A arquitetura já coloca no Orchestrator coisas como **audit planning, applicability, scope, context acquisition, concurrency, task lifecycle, budget, escalation, validation e provenance**, enquanto o OmniRoute permanece responsável pela infraestrutura de roteamento. 

---

# O que eu mudaria

Eu faria **uma alteração conceitual importante**:

## Transformar "classificação determinística" em uma camada explícita do Core.

Hoje temos conceitualmente:

```text
Discovery
    ↓
AuditPlan
    ↓
AuditWorkItems
    ↓
Workers
```

Eu formalizaria:

```text
Discovery
    ↓
Deterministic Classification
    ↓
Audit Planning
    ↓
AuditWorkItems
    ↓
Execution
```

E dentro de `Deterministic Classification`:

```text
File Classification
Technology Classification
Stack Classification
Applicability Classification
Task Classification
Complexity Classification
Sensitivity Classification
Context Classification
Deterministic-vs-Semantic Classification
```

Isso **não significa criar oito serviços gigantes**.

Pode começar como uma coleção pequena de classificadores puros e especializados.

---

# A mudança mais importante: o `AuditWorkItem`

Eu não adicionaria um monte de campos diretamente no `AuditWorkItem`.

Em vez disso, a decisão deveria resultar em algo conceitualmente assim:

```text
AuditWorkItem
    │
    ├── task specification
    ├── scope
    ├── dependencies
    ├── classification
    │      ├── execution_kind
    │      ├── complexity
    │      ├── sensitivity
    │      └── context_requirements
    │
    └── execution policy
```

Por exemplo:

```text
execution_kind = DETERMINISTIC
```

ou:

```text
execution_kind = SEMANTIC
```

ou, se quisermos maior precisão:

```text
execution_kind = DETERMINISTIC_PREFERRED
```

com possibilidade de escalonamento caso a análise determinística não consiga concluir.

---

# E isso muda bastante a economia

Imagine uma auditoria de SQL Injection.

Hoje o raciocínio ingênuo seria:

```text
SQL Injection audit
       ↓
LLM
       ↓
"procure SQL Injection"
```

O desenho que eu acho que deveríamos formalizar é:

```text
SQL Injection
     │
     ▼
Deterministic Classification
     │
     ├── encontra linguagem
     ├── encontra database layer
     ├── encontra SQL
     ├── encontra JDBC/ORM
     ├── encontra queries
     ├── encontra PreparedStatement
     └── identifica arquivos relevantes
             │
             ▼
       deterministic checks
             │
       ┌─────┴─────┐
       │           │
   suficiente   ambíguo
       │           │
       ▼           ▼
    Evidence      LLM
```

O LLM recebe **somente o resíduo que exige interpretação**.

Isso é muito diferente de "usar LLM para auditar SQL".

---

# Portanto, precisamos adicionar um conceito

Eu criaria durante a fase de design algo como:

```text
ClassificationResult
```

Não necessariamente esse nome, mas o conceito.

Algo como:

```text
Classification
├── classifier_id
├── classifier_version
├── input_refs
├── result
├── confidence
├── rationale/evidence
└── provenance
```

E o resultado poderia ser:

```text
DETERMINISTIC
SEMANTIC_REQUIRED
NOT_DETERMINABLE
```

ou classificações específicas derivadas disso.

Isso é importante porque depois poderemos responder:

> "Por que essa auditoria consumiu LLM?"

Não apenas:

> "Porque o agente decidiu."

---

# O LLM vira exceção, não caminho padrão

O fluxo deveria ficar:

```text
                Audit Task
                    │
                    ▼
          ┌───────────────────┐
          │ Deterministic     │
          │ Classification    │
          └─────────┬─────────┘
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
     SOLVABLE             AMBIGUOUS
     WITHOUT LLM              │
          │                   ▼
          │                  LLM
          │                   │
          └─────────┬─────────┘
                    ▼
                 Evidence
```

E mesmo quando chegar ao LLM:

```text
LLM
 ↓
cheap/medium/strong
```

não:

```text
LLM
 ↓
strong
```

automaticamente.

---

# O que isso significa para o estado atual

Eu classificaria assim:

| Parte                                    | Estado                      |
| ---------------------------------------- | --------------------------- |
| Core de execução                         | já existe                   |
| AuditPlan                                | já existe                   |
| AuditWorkItem                            | já existe                   |
| Workers                                  | já existe                   |
| Delegation boundary                      | já existe                   |
| OmniRoute boundary                       | já definida                 |
| Deterministic evidence                   | já é princípio arquitetural |
| Cache determinístico                     | já previsto                 |
| Applicability                            | já pertence ao Orchestrator |
| Context selection                        | já pertence ao Orchestrator |
| **Classifier layer explícita**           | **precisa ser formalizada** |
| **Policy determinística LLM vs non-LLM** | **precisa ser formalizada** |
| Evidence Dependency Graph                | ainda precisa ser projetado |
| Snapshot Drift                           | ainda precisa ser fechado   |
| Security Auditor contract                | já definido                 |
| `audit-normalize`                        | congelado                   |

A própria arquitetura já define que `audit applicability`, `audit planning`, `project profile`, `dependency graph`, `git impact analysis`, `progressive disclosure` e `deterministic evidence` pertencem ao sistema de auditoria, e não ao OmniRoute. 

Então eu **não considero isso uma falha estrutural do que construímos**. É uma lacuna de especificação que ficou evidente agora.

## Minha recomendação de sequência

Eu **não voltaria a codar agora**.

Faria nesta ordem:

```text
1. ADR — Snapshot Drift
          ↓
2. Evidence Dependency / Invalidation
          ↓
3. Deterministic Classification Architecture
          ↓
4. LLM Escalation / Task Policy
          ↓
5. só então implementação
```

O terceiro documento deveria especificar exatamente:

```text
quais classificadores existem
↓
quais são determinísticos
↓
quais inputs usam
↓
quais outputs produzem
↓
quais podem declarar NOT_DETERMINABLE
↓
quando LLM é permitido
↓
como a decisão entra no AuditPlan
↓
como isso aparece na provenance
↓
como o budget é afetado
```

Isso fecha justamente a parte que você estava cobrando: **LLM como recurso caro e excepcional; análise determinística como caminho padrão sempre que a perda de qualidade for aceitavelmente pequena.**

Não vejo necessidade de reescrever a arquitetura existente. Vejo necessidade de **adicionar essa política explicitamente ao modelo arquitetural antes da implementação continuar**.


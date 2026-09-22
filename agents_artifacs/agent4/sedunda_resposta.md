# PROJECT-AUDIT FINALIZATION STATUS

**Status:** `BLOCKED`

A inspeção final confirma que há correções locais seguras concluídas, mas ainda existem decisões arquiteturais indefinidas que impedem declarar `V1 READY` ou gerar `project-audit-finalized.zip`.

## 1. Snapshot Drift

### BLOCKER

**Contract missing:** fonte de verdade para obter o estado/snapshot atual durante a execução.

**Evidence:**

* ADR-06 exige `TargetSnapshot` calculado por um **Context Builder** antes da auditoria. `docs/decisions/target-snapshot-reproducibility.md:13-27`
* A revisão de consistência atribui a construção do snapshot ao **Context Builder**, não ao Orchestrator. `docs/references/final-consistency-review.md:14-20`
* `Orchestrator.detect_snapshot_drift()` recebe um `current_fingerprint` externamente, mas `execute_vertical_slice()` não possui mecanismo contratual para obter esse valor durante a execução.
* Não existe implementação de Context Builder/fonte de snapshot atual dentro de `project-audit`.

**Required decision:** definir arquiteturalmente qual componente fornece o snapshot atual em tempo de execução e como essa informação chega ao Orchestrator.

**Why implementation cannot proceed safely:** criar callback, provider, consulta Git ou nova API diretamente no Core seria uma decisão arquitetural nova.

**Result:**

```text
BLOCKED_BY_UNDEFINED_EXECUTION-TIME-SNAPSHOT-SOURCE
```

O restante do mecanismo já impede publicação quando um fingerprint diferente é fornecido: `validate_snapshot_drift()` alimenta `can_publish()` e bloqueia o estado publicável.

---

## 2. OmniRoute Contract

### BLOCKER

O adapter atual **não envia o contrato canônico** de `delegar_tarefa`.

A implementação ainda constrói:

```text
task_id
instruction
context
target_surface
required_capabilities
```

em `skills/universal/project-audit/src/project_audit/omniroute_backend.py:32-41`.

O schema canônico de `omniroute-delegation` exige:

```text
tarefa
perfil
contexto
task_id
session_id
cache_mode
cache_key
max_tokens
temperature
```

com `tarefa` obrigatória e `additionalProperties: false`.

Validação independente do payload efetivamente produzido pelo adapter:

```text
'tarefa' is a required property
Additional properties are not allowed:
('context', 'instruction', 'required_capabilities', 'target_surface')
```

Portanto, não é apenas diferença nominal; o payload atual é estruturalmente incompatível.

### Por que não corrigi o mapping

A arquitetura define que o Core pede uma **Task Policy**, enquanto OmniRoute resolve modelo/provedor. `docs/decisions/omniroute-policy-gateway.md` e `docs/references/omniroute_context_use.md` não fornecem uma regra para transformar:

```text
AuditWorkItem.auditor
AuditWorkItem.target_surface
AuditWorkItem.decision_basis
ExecutionPolicy
```

em:

```text
tarefa
perfil / policy_id
```

Fazer esse mapping por semelhança seria exatamente a inferência proibida.

**Required decision:** definir explicitamente a origem de `Task Policy/perfil` e a composição canônica de `tarefa` para um `AuditWorkItem`.

**Result:**

```text
BLOCKED_BY_UNDEFINED_OMNIROUTE_TASK_MAPPING
```

---

## 3. OmniRoute Failure Taxonomy

A investigação encontrou somente estas categorias formalmente sustentadas pelo protocolo atual:

| Categoria           | Evidência                                                               | Estado               |
| ------------------- | ----------------------------------------------------------------------- | -------------------- |
| Transport failure   | `MCPTransportError`                                                     | determinável         |
| Gateway unreachable | `GatewayUnreachableError` / `GATEWAY_UNREACHABLE`                       | determinável         |
| Timeout             | transport error genérico no cliente atual                               | **não separado**     |
| Rate limit          | HTTP status pode carregar `429`, mas não há categoria semântica própria | **NOT_DETERMINABLE** |
| Policy rejection    | não há código canônico específico                                       | **NOT_DETERMINABLE** |
| Semantic rejection  | não existe contrato de resposta que a defina                            | **NOT_DETERMINABLE** |
| Invalid response    | ausência/malformed JSON/non-object                                      | determinável         |

Não foram inventados códigos ou classes inexistentes.

Existe ainda uma limitação real: `MCPOmniRouteBackend` captura `Exception` genericamente e converte o resultado para `FAILED`. Isso impede preservar distinções que o contrato MCP poderia fornecer. Não corrigi isso por heurística porque os tipos concretos do gateway não estão definidos no contrato consumido pelo Core.

---

## 4. Egress Order

A fronteira agora é efetivamente:

```text
DelegationRequest
    ↓
Egress Policy
    ↓
Execution Gate
    ↓
backend
```

em `delegation.py:97-135`.

Isso corresponde à composição esperada e não cria um segundo router.

Foi adicionado teste garantindo:

```text
invalid capability
    ↓
ExecutionGate rejection
    ↓
backend not reached
```

`tests/test_delegation.py:147-173`.

O teste existente também confirma:

```text
unknown/sensitive egress
    ↓
DO NOT SEND
    ↓
backend not reached
```

---

## 5. Invalid OmniRoute Responses

Foi corrigida uma violação comprovada: texto arbitrário não pode ser promovido a `SUCCESS`.

Agora são rejeitados:

```text
empty response
malformed JSON
JSON non-object
```

em `omniroute_backend.py:62-116`.

Regressões adicionadas em:

`tests/test_omniroute_backend.py:113-146`.

Isso elimina o comportamento anterior:

```python
{"raw_text": "..."}
→ SUCCESS
```

que poderia transformar resposta inválida em evidência posterior.

---

## 6. Independent Verification

### Project-audit

```text
156 passed
159 warnings
94% coverage
```

A cobertura foi medida com `pytest-cov`.

Testes direcionados de delegação/backend:

```text
11 passed
```

### OmniRoute delegation contract suite

```text
130 passed
```

A suíte completa dessa skill permanece com:

```text
196 passed
```

### `uv run pytest tests/`

**NOT_EXECUTED successfully.**

O `.venv` presente no repositório está quebrado: seu Python 3.14 referencia `libpython3.14.so.1.0`, inexistente no ambiente. Um ambiente temporário separado também não pôde ser sincronizado porque a resolução de dependências exigiu acesso ao PyPI e o ambiente não tinha DNS/rede disponível.

Os resultados acima foram obtidos com Python 3.13.5 e dependências já disponíveis, sem modificar o `.venv` do repositório.

---

# Auditoria independente

[CRITICAL][HIGH][Snapshot execution] **Problem:** não existe fonte contratual para o snapshot atual durante a execução.
**Evidence:** Context Builder é responsável pelo snapshot inicial; Orchestrator aceita somente um fingerprint já fornecido.
**Why:** implementar a obtenção diretamente no Core criaria uma decisão arquitetural.
**Impact:** drift pode ser detectado na publicação quando um fingerprint externo é fornecido, mas não há enforcement determinístico do `STOP → INVALIDATE` durante a execução.
**Verification:** inspeção de ADR-06, final-consistency-review, `orchestrator.py`.
**Correction:** decisão arquitetural necessária.

[CRITICAL][HIGH][OmniRoute contract] **Problem:** payload emitido pelo adapter não valida contra o schema canônico.
**Evidence:** falta `tarefa`; existem quatro propriedades proibidas.
**Why:** o mapping `AuditWorkItem → Task Policy/tarefa` não está definido.
**Impact:** integração real não pode ser declarada conforme.
**Verification:** `Draft202012Validator` aplicado ao payload capturado do adapter.
**Correction:** definir origem e semântica dos campos antes de implementar.

[HIGH][HIGH][Failure taxonomy] **Problem:** o backend reduz várias falhas possíveis a `FAILED`.
**Evidence:** `except Exception` em `omniroute_backend.py`.
**Why:** os tipos/categorias necessários para distinguir timeout, rate-limit e policy rejection não estão definidos no contrato do Core.
**Impact:** retry/recovery futuros não conseguem preservar toda a semântica.
**Verification:** comparação com `normative_reference.md` e `mcp_client.py`.
**Correction:** somente após existir contrato de mapeamento.

[NIT][HIGH][Environment] **Problem:** `.venv` do repositório está inutilizável neste ambiente.
**Evidence:** executável referencia `libpython3.14.so.1.0` ausente.
**Why:** problema ambiental, não alteração de código.
**Impact:** o comando literal `uv run pytest tests/` não pôde ser reproduzido com sucesso.
**Verification:** execução direta do interpreter e `uv`.
**Correction:** NOT_EXECUTED; não alterei o `.venv`.

---

# Git

**Branch**

```text
fix/project-audit-v1-hardening
```

**HEAD**

```text
5c194a33d601eea50e1c21895b51cd26ad9ebdb4
```

As alterações locais desta execução são:

```text
skills/universal/project-audit/src/project_audit/delegation.py
skills/universal/project-audit/src/project_audit/omniroute_backend.py
skills/universal/project-audit/tests/test_delegation.py
skills/universal/project-audit/tests/test_omniroute_backend.py
```

As alterações preexistentes permanecem intactas:

```text
docs/decisions/antigravity-skills-swarm-architecture.md
docs/architecture/forensic-review-resolution-matrix.md
skills/universal/project-audit/.coverage
```

O `.coverage` foi restaurado exatamente ao estado contido no ZIP fornecido.

**Commits desta execução:** `NOT_EXECUTED`.

Não configurei identidade Git automaticamente e não houve tentativa de alterar histórico ou fazer push.

---

# Final Artifact

```text
project-audit-finalized.zip
```

**NOT_PRODUCED**

A stop condition foi atingida: há decisões arquiteturais ausentes necessárias para fechar os blockers com segurança. Gerar um ZIP final neste estado daria aparência de finalização sem que `V1 READY` estivesse demonstrado.

## Estado final

```text
PROJECT-AUDIT FINALIZATION STATUS: BLOCKED

V1 Hardening: PASS
Egress Enforcement: PASS
Invalid OmniRoute Response Handling: PASS

Snapshot Drift: BLOCKED
OmniRoute Canonical Request Mapping: BLOCKED
OmniRoute Failure Taxonomy: INCOMPLETE / PARTLY NOT_DETERMINABLE

Security Auditor: NOT_EXECUTED
Downstream Integration: NOT_EXECUTED

V1 READY: NO
Final ZIP: NOT_PRODUCED
```


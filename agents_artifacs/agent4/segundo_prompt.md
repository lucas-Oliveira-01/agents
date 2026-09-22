# CONTINUATION COMMAND — CLOSE V1 BLOCKERS

Continue a missão a partir do estado atual.

O último relatório classificou corretamente:

```text
PROJECT-AUDIT FINALIZATION STATUS: BLOCKED_BY_V1_HARDENING

```

Não avance para `Security Auditor` nem `Downstream Integration`.

Feche primeiro exclusivamente os blockers ainda comprovados.

## 1. SNAPSHOT DRIFT

Investigue novamente os contratos arquiteturais:

```text
docs/decisions/
docs/references/canonical-data-model.md
docs/references/semantic-validators.md
docs/references/audit-architecture-specification.md
docs/references/final-consistency-review.md

```

Determine se existe no contrato atual uma fonte de verdade para obter o snapshot atual durante a execução.

O fluxo requerido é:

```text
drift detected
    ↓
STOP
    ↓
invalidate affected evidence
    ↓
prevent COMPLETE publication

```

Não invente um callback/provider/API apenas para satisfazer esse requisito.

Caso o contrato não defina como obter o estado atual:

```text
BLOCKED_BY_UNDEFINED_EXECUTION-TIME-SNAPSHOT-SOURCE

```

e não introduza uma nova abstração arquitetural silenciosamente.

## 2. OMNIROUTE CONTRACT

Leia novamente integralmente:

```text
docs/references/omniroute_context_use.md
skills/universal/omniroute-delegation/

```

e compare diretamente com:

```text
skills/universal/project-audit/src/project_audit/delegation.py
skills/universal/project-audit/src/project_audit/omniroute_backend.py

```

Determine exatamente:

```text
DelegationRequest
        ↓
Task Policy / perfil
        ↓
OmniRoute canonical request
        ↓
response contract
        ↓
DelegationResult

```

Não faça mapping por semelhança nominal.

Não transforme:

```text
instruction

```

em:

```text
tarefa

```

nem:

```text
context

```

em:

```text
perfil

```

sem evidência contratual.

Somente implemente o mapping quando a origem dos campos puder ser demonstrada pelos contratos existentes.

## 3. OMNIROUTE FAILURE TAXONOMY

Determine quais erros são realmente expostos pelo protocolo atual.

Não invente:

```text
error codes
exception classes
status categories

```

quando não existirem.

Mapeie somente semânticas comprováveis:

```text
transport failure
timeout
rate limit
policy rejection
invalid response
semantic rejection

```

Quando uma distinção não puder ser determinada:

```text
NOT_DETERMINABLE

```

## 4. EGRESS ORDER

Verifique a implementação real da fronteira.

A descrição esperada deve ser coerente com o contrato:

```text
DelegationRequest
    ↓
Sensitivity Classification
    ↓
EgressPolicy
    ↓
Execution Gate
    ↓
OmniRoute

```

Caso `ExecutionGate` encapsule parte dessa lógica, documente explicitamente a composição.

Não altere a ordem somente por estética.

## 5. REGRESSION TESTS

Adicione testes somente para comportamentos comprovados pelo contrato.

Obrigatórios para os blockers resolvidos:

```text
unknown egress → DO NOT SEND
invalid capability → backend not reached
invalid OmniRoute response → FAILED
drift → affected evidence invalidated
drift → COMPLETE blocked

```

Teste também o contrato real de request/response do OmniRoute.

## 6. INDEPENDENT VERIFICATION

Depois das correções:

```bash
uv run pytest tests/

```

Execute também os testes direcionados da delegação.

Faça uma segunda inspeção independente procurando:

```text
egress bypass
persist invalid state
publish invalid state
snapshot drift bypass
OmniRoute contract mismatch
error taxonomy collapse

```

Não declare V1 READY apenas porque os testes estão verdes.

## 7. GIT

Quando os blockers estiverem efetivamente resolvidos:

- mantenha cada mudança logicamente isolada;
- crie commits;
- não altere identidade Git automaticamente;
- não faça force push;
- preserve alterações não relacionadas.

## 8. FINAL ARTIFACT

Depois da validação final, gere:

```text
project-audit-finalized.zip

```

O ZIP deve conter o estado final completo do repositório, incluindo:

- código;
- testes;
- documentação;
- alterações realizadas.

Excluir:

```text
.venv/
__pycache__/
.pytest_cache/
build temporário/
arquivos temporários/
caches desnecessários/

```

Não incluir secrets reais.

O ZIP só deve ser produzido depois da validação final.

## 9. STOP CONDITION

Se qualquer blocker depender de uma decisão arquitetural não definida:

```text
STOP

```

Não invente a solução.

Nesse caso, reporte:

```text
BLOCKER
Contract missing:
Required decision:
Why implementation cannot proceed safely:

```

E permaneça no estado:

```text
BLOCKED

```

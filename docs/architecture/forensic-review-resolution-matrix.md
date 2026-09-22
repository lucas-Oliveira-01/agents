# Matriz de Resolução — Revisão Forense V1 (Copilot)

A revisão independente identificou 11 achados críticos que passaram na suite de testes original, provando a eficácia dos testes adversariais arquiteturais. Esta matriz desmembra cada achado seguindo a metodologia solicitada antes de qualquer alteração de código.

---

### 1. `can_publish()` aceita execução vazia
* **Status:** Confirmado (P1)
* **Requisito Arquitetural Violado:** ADR-07 / Publication Gate. Uma execução sem evidências, sem work items, ou com coverage `NONE` não provê baseline auditável para publicação.
* **Causa Raiz:** A função `can_publish()` (validators.py) checa se `run.execution_completeness == COMPLETE` e se não há `failed_items` (lista vazia avalia como falsa). Em execuções sem itens, ela aprova ingenuamente.
* **Correção Proposta:** Adicionar verificação explícita: se `len(work_items) == 0` ou `run.coverage_completeness == NONE`, retornar erro `PUBLISH_EMPTY_AUDIT`.
* **Teste de Regressão:** `test_can_publish_rejects_empty_audit` em `test_hardening.py`.
* **Risco de Efeito Colateral:** Baixo. Bloqueará runs de teste que tentem publicar estados prematuros.

---

### 2. `commit_run()` persiste estado semanticamente inválido
* **Status:** Confirmado (P1)
* **Requisito Arquitetural Violado:** Trust Boundaries & Determinism. O State Store não pode registrar um Run que viola invariantes semânticas.
* **Causa Raiz:** No `Orchestrator.commit_run()`, após chamar `validate_run()`, se `report.has_errors` for True, o orquestrador faz apenas um `logger.warning()` e continua para `self.store.save_run(run)`.
* **Correção Proposta:** Alterar `logger.warning` para `raise SemanticValidationError` e interromper a transação se `report.has_errors` for True.
* **Teste de Regressão:** `test_commit_run_raises_on_semantic_errors`.
* **Risco de Efeito Colateral:** Alto. Quebrará testes de integração que injetavam estados inválidos intencionalmente e esperavam que a persistência funcionasse. Os testes precisarão capturar a exceção.

---

### 3. Cobertura ignora `resolved_scope`
* **Status:** Confirmado (P1/P2)
* **Requisito Arquitetural Violado:** Semantic Validators §6 (Coverage Completeness derivable).
* **Causa Raiz:** `validate_coverage_completeness_derivable` usa contagem de itens executados *versus* totais planejados, mas não cruza com os domínios mapeados em `plan.resolved_scope`.
* **Correção Proposta:** Refatorar o validador para garantir que a união dos domínios cobertos pelos `work_items` que tiveram sucesso engloba a totalidade do `resolved_scope`.
* **Teste de Regressão:** `test_coverage_fails_if_resolved_scope_not_met`.
* **Risco de Efeito Colateral:** Médio. Pode exigir que o construtor do Mock Plan nos testes alimente corretamente os domínios.

---

### 4. Snapshot drift detectado mas não produz efeito operacional
* **Status:** Confirmado (P1)
* **Requisito Arquitetural Violado:** ADR-06 (Reproducibility & Target Snapshot). Mudanças no alvo devem interromper/invalidar a auditoria.
* **Causa Raiz:** `Orchestrator.detect_snapshot_drift` é passivo. A execução de itens (vertical slice) não checa ativamente o drift de maneira a abortar o run.
* **Correção Proposta:** Dentro de `execute_vertical_slice` e lógicas incrementais, checar o drift antes de prosseguir com execução/persistência. Se houver drift, forçar `RunFailureState.SNAPSHOT_DRIFT` e interromper.
* **Teste de Regressão:** `test_vertical_slice_aborts_on_snapshot_drift`.
* **Risco de Efeito Colateral:** Alto. Pode ser flacky em testes de longa duração se o mock de snapshot não for rigorosamente imutável.

---

### 5. Egress via OmniRoute sem validator enforcing
* **Status:** Confirmado (P1 - Security Blocker)
* **Requisito Arquitetural Violado:** ADR-05 (Execution Safety & Egress).
* **Causa Raiz:** O `MCPOmniRouteBackend.delegate()` monta o `context_str` e envia para o MCP Tool sem nunca invocar o `validate_egress_policy`. O classificador de sensibilidade não atua sobre a barreira real.
* **Correção Proposta:** O `WorkerPort` deve invocar `validate_egress_policy` passando o context payload *antes* de delegar a tarefa (ou pelo menos checar um classificador de DLP injetado). Se não houver garantia, fail-closed (`DO NOT SEND`).
* **Teste de Regressão:** `test_worker_port_blocks_sensitive_egress_before_dispatch`.
* **Risco de Efeito Colateral:** Baixo/Médio. Garante que nada saia sem validação efetiva na barreira.

---

### 6. Mutabilidade profunda de `AuditPlan` / `TargetSnapshot`
* **Status:** Confirmado (P1)
* **Requisito Arquitetural Violado:** Imutabilidade por design (ADR-04).
* **Causa Raiz:** O decorador `@dataclass(frozen=True)` protege a atribuição de topo, mas listas ou dicionários em Python continuam mutáveis por referência.
* **Correção Proposta:** Mudar campos internos para tipos imutáveis (`tuple` no lugar de `list`, e um dict imutável ou `tuple` de pairs) nos models.
* **Teste de Regressão:** `test_deep_immutability_of_plan_and_snapshot`.
* **Risco de Efeito Colateral:** Médio. Código existente ou mocks de teste que inseriam em listas congeladas vão começar a lançar erro (o que é correto).

---

### 7. `recover_run()` aceita estado `COMPLETE`
* **Status:** Confirmado (P1)
* **Requisito Arquitetural Violado:** ADR-07 §3 (Recovery vs Retry). Não se recupera uma execução que não foi interrompida (já finalizou com sucesso ou falhou de modo não recuperável).
* **Causa Raiz:** `recover_run` não checa o estado atual de `interrupted_run.execution_completeness`.
* **Correção Proposta:** Lançar erro (`IllegalStateTransitionError`) se o run recuperado não estiver em um estado passível de recuperação (e.g., `PARTIAL`, `RUNNING`).
* **Teste de Regressão:** `test_cannot_recover_complete_run`.
* **Risco de Efeito Colateral:** Baixo.

---

### 8. Retry sem verificação de orçamento/idempotência
* **Status:** Confirmado (P1/P2)
* **Requisito Arquitetural Violado:** ADR-07 §3.
* **Causa Raiz:** `retry_attempt()` cria uma nova tentativa sem checar os limites estabelecidos no budget (`ExecutionPolicy`).
* **Correção Proposta:** Alterar `retry_attempt` ou a chamada do orquestrador para verificar a constraint de budget de tentativas/tokens.
* **Teste de Regressão:** `test_retry_budget_exhaustion`.
* **Risco de Efeito Colateral:** Médio. Adiciona gestão estrita de estado.

---

### 9. JSON Schema Validation sem `format_checker`
* **Status:** Confirmado (P2)
* **Requisito Arquitetural Violado:** Schema Validation rigoroso de Layer 2.
* **Causa Raiz:** A lib `jsonschema` requer explícito `format_checker` para verificar UUIDs (`"format": "uuid"`) e datetime. Sem isso, uma string `abc` passa como UUID.
* **Correção Proposta:** Instanciar a validação passando o respectivo `format_checker` em `schema_validator.py`.
* **Teste de Regressão:** `test_schema_rejects_invalid_uuid_format`.
* **Risco de Efeito Colateral:** Alto. Se existirem Mocks de testes que abusam do UUID (e.g., `run_id="run-1"`), eles falharão maciçamente e terão que ser limpos.

---

### 10. Wheel distribution missing schemas
* **Status:** Confirmado (Bug Infra/Distribuição)
* **Requisito Arquitetural Violado:** Portabilidade / Resolubilidade dos Validators de Schema.
* **Causa Raiz:** Os JSON Schemas estão em `docs/references/schemas/`, e o Python build (uv/setuptools) não os empacota na Wheel, quebrando a validação runtime se o pacote for rodado fora do worktree.
* **Correção Proposta:** Reorganizar os schemas físicos para `src/project_audit/schemas/` (ou incluí-los no `MANIFEST.in`/`pyproject.toml` usando `package-data`).
* **Risco de Efeito Colateral:** Baixo. Apenas refatoração estrutural/paths.

---

### 11. State Store não garante single-writer
* **Status:** Confirmado (Design Hardening)
* **Requisito Arquitetural Violado:** Integridade de gravação em concorrência.
* **Causa Raiz:** `_atomic_write` apenas garante rename atômico contra leitores e crash, mas não lock multithread/processo.
* **Correção Proposta:** Adotar `filelock` no `save_run` (ex.: `.run-id.json.lock`) para prevenir race conditions.
* **Risco de Efeito Colateral:** Baixo, mas introduzirá concorrência formal.

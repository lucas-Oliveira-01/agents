# Canonical Data Model (Orchestrator Layer 2)

*Status: IMPLEMENTED — canonical Layer 2 model*

This document defines the semantic ontology of the Orchestrator's internal persisted state (Camada 2). These entities govern the lifecycle, incremental logic, and recovery of the audit process. They are strictly separate from the final Audit Output Contract (Markdown) and the Canonical Normalizer JSON.

## Core Principles
1. **References over Embedding:** `AuditRun` does not embed the entire universe; it references `TargetSnapshots`, `AuditPlans`, and `AuditWorkItems`.
2. **Immutability vs Mutability:** 
   - `TargetSnapshot`, `Evidence`, `FindingFingerprint` are **IMMUTABLE**.
   - `AuditPlan` is **FROZEN-AT-START** (never altered mid-run).
   - `AuditRun` and `AuditWorkItem` are **MUTABLE** (state machines).

---

## 1. TargetSnapshot (Immutable)
Answers: *"What exactly is being audited, and under what rules?"*

- **Project State Identity:**
  - `target_mode`: `COMMIT` | `WORKTREE` | `EXPLICIT_SNAPSHOT`
  - `repository_identity` (e.g., origin URL / project name)
  - `revision_identity` (e.g., commit SHA)
  - `working_tree_state` (dirty/clean flags, untracked files)
  - `submodules_state`
  - `tracked_input_fingerprints` (hashes of critical configs)
- **Methodology State Identity:**
  - `audit_contract_version`
  - `auditor_versions`
  - `policy_version`
- **Snapshot Fingerprint:** A deterministic hash derived from the above.

---

## 2. AuditPlan (Frozen-at-start)
Answers: *"Given the target and constraints, what is the plan?"*

- `plan_id` / `frozen_at` timestamp.
- `target_snapshot_ref`: Link to the target.
- **Scope Resolution:**
  - `requested_scope`: What the user asked for (e.g., `FULL EXCEPT DB`).
  - `applicability_decisions`: Which domains are viable. Must include a `decision_basis` (linking to evidence), avoiding arbitrary confidence scores. If uncertain, `DO NOT EXCLUDE`.
  - `resolved_scope`: The final agreed execution scope.
- **Work & Budget:**
  - `work_items`: Array of planned `AuditWorkItem`s.
  - `budget_envelope`: Global constraints.
  - `execution_policy` & `egress_policy`: Trust boundaries (ADR-05).

---

## 3. AuditWorkItem (Mutable State Machine)
Answers: *"What is the atomic unit of work, and what is its status?"*

- **Immutable Definition:**
  - `work_item_id` / `plan_ref`
  - `auditor` (e.g., `security-audit`)
  - `target_surface` (e.g., `src/auth`)
  - `action`: `REUSE` | `REVALIDATE` | `REAUDIT` (Note: `INVALIDATE` is a property of old evidence, not an action).
  - `decision_basis`: Why this action was chosen (e.g., "methodology version changed").
  - `effective_execution_policy` / `data_egress_policy`
- **Mutable Execution State:**
  - `execution_state` (`PLANNED`, `RUNNING`, `TERMINATED`)
  - `failure_state` (`NONE`, `INFRA_ERROR`, `SAFETY_BLOCK`)
  - `attempts`: Array of `ExecutionAttempt` records (start/end, failure reasons, `ExecutionReceipts`). Allows distinguishing between retry #1 and retry #2.
  - `artifact_refs`: Pointers to the generated Markdown or Evidence.

---

## 4. Evidence & Finding Fingerprint (Immutable)
Answers: *"What objective fact was observed?"*

- `Evidence`:
  - `evidence_id` / `target_ref` / `work_item_ref`
  - `source_ref`: Where the fact lives (lines, config, tool output).
  - `dependencies`: Semantic links (e.g., this evidence relies on `pom.xml`).
  - `validity`: `VALID`, `STALE`, `INVALID`, `NOT_DETERMINABLE` (Evaluated against the current TargetSnapshot).
  - *Note: Evidence is an objective observation, not a technical conclusion.*
- `FindingFingerprint`:
  - A stable identity descriptor (same logical problem across text refactors). Does not embed the full finding narrative.
- `FindingStatus`:
  - Epistemic state: `CANDIDATE`, `PROBABLE`, `CONFIRMED`, `REJECTED`, `NOT_DETERMINABLE`.
  - Must remain independent from lifecycle.
- `FindingLifecycle`:
  - Historical state: `NEW`, `PERSISTING`, `MODIFIED`, `FIXED`, `REGRESSED`, `INVALIDATED`.
  - `INVALIDATED` is not evidence that the finding is fixed; `REGRESSED` requires a prior `FIXED`.

---

## 5. AuditRun (Mutable Aggregate)
Answers: *"What actually happened during this execution?"*

- **Identities & Lineage:**
  - `run_id` / `target_snapshot_ref` / `plan_ref`
  - `previous_run_ref`: Points to an older run for standard incremental audits.
  - `recovery_from_ref`: Points to an interrupted run if this is a reconciliation/recovery execution.
- **State Vectors (Separated):**
  - `execution_completeness`: Are all WorkItems finalized?
  - `coverage_completeness`: Did we audit the full `requested_scope`? (A run can be fully completed operationally, but partially complete in coverage if a module was blocked by the safety gate).
  - `failure_state` / `budget_state`
  - `publication_state`: Enforces the barrier preventing publication of blocked/failed runs.
- **Artifacts:**
  - `work_item_refs` / `artifact_refs`\n## Phase 5 — Immutable Auto-Fix Transaction\n\nAuto-fix is a transaction over immutable audit state, never an in-place mutation of an existing Run/Evidence/Finding record.\nThe transaction is valid only for one independently VERIFIED P0/P1 candidate from a clean COMMIT-target Snapshot A.\n\nThe worker operates in an isolated L3W workspace and may return a patch touching only the candidate's verified source file.\nThe Orchestrator applies the patch only after `git apply --check`, captures Snapshot B, and runs a dedicated post-fix audit.\nA Before/After Ledger records Snapshot A, Snapshot B, patch SHA-256, worker receipt, and post-fix finding presence.\nFindingLifecycle=FIXED is recorded only when the same logical finding identity is absent after the post-fix audit; otherwise\nthe transaction is NOT_FIXED/PERSISTING. The historical source run and its Evidence remain immutable.\n\n

## 6. Operational Recovery and Concurrency (Phase 6)

The canonical state namespace has a physical single-writer boundary represented by
.audit/audit-writer.lock. The lock lifetime covers one audit execution and is released
by the operating system when the writer process exits.

AuditRun is durable before execution begins (RUNNING). A crash therefore leaves a
recoverable run identity and persisted WorkItem attempts. Recovery creates a new frozen
AuditPlan, new WorkItem identities, and a new AuditRun with
recovery_from_ref=<interrupted_run_id>. The interrupted graph remains historical.

A replay is idempotent at the WorkItem boundary: completed successful items are preserved
and skipped; unfinished or failed items are reconstructed as PLANNED and can execute in
the new recovery run.


## Current implementation alignment

This model is implemented by the post-Phase-10 runtime. Earlier phase records may describe later capabilities as future work; those statements are historical and are not current contracts.

Implemented post-baseline extensions include durable FindingRecord lifecycle persistence and immutable Evidence lineage through `derived_from_evidence_ref` for safe incremental reuse. Cross-run WorkItem matching uses logical identity (auditor + target_surface), never generated UUIDs.

## Phase 11 — Change Impact & Reaudit Necessity

Change Impact and Reaudit Necessity are implemented as deterministic planning analysis, not as a new persisted Layer 2 entity. The implementation compares immutable TargetSnapshot input fingerprints and methodology state, propagates impact through existing Evidence dependencies, and explains the existing incremental action in AuditWorkItem.decision_basis.

No Phase 11 schema field is authorized by this model. Rename continuity is represented through deterministic path aliases during incremental evaluation and fresh derived Evidence; historical Evidence remains immutable.


## Phase 12 — Classification Lineage & Reclassification

Classification lineage is an auxiliary immutable planning artifact associated with a `TargetSnapshot` fingerprint. It records the deterministic `ClassificationResult` set needed to compare planning context across incremental runs, but it is not a new canonical Layer 2 entity and does not add fields to the canonical JSON schemas.

The lineage is stored separately from `TargetSnapshot`, `AuditPlan`, `AuditWorkItem`, `Evidence`, `AuditRun`, and `FindingRecord`. Conflicting rewrites for an existing snapshot reference fail closed.

Only explicitly demonstrated classification dependencies may broaden reconsideration of WorkItems. Current direct dependencies are `task-classifier` → exact target surface and `applicability:<category>:<subcategory>` → matching WorkItem target surface. Missing historical lineage fails closed to `REAUDIT`.


## Phase 16 — State Integrity Closure

The frozen-at-start contract is now enforced at the object and persistence boundaries. AuditPlan rejects field reassignment after freeze and persists collection fields in immutable tuple form, including after reload. ApplicabilityDecision and BudgetEnvelope are immutable value objects.

The Orchestrator WorkItem commit gate requires a durable plan reference and passes the WorkItem through the composite semantic validators before StateStore persistence. AuditRun WorkItem references must exactly match the immutable WorkItem set declared by its Plan.

No new canonical entity or JSON schema field is introduced.


## Phase 17 — Immutable Evidence & Execution Trail Closure

The immutable Layer 2 contract is now enforced at construction, reload, and persistence boundaries. ProjectState nested collections, Evidence source/dependency references, and ExecutionReceipt argument/artifact references are normalized to tuples. The Orchestrator rejects Receipt or Evidence persistence when their WorkItem references do not resolve to durable state; Evidence is checked against the persisted WorkItem and its canonical Plan/Snapshot.

No new canonical entity or schema field is introduced.

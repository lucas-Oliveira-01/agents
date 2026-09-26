# Semantic Validators (Orchestrator Layer 2)

*Status: IMPLEMENTED — Phase 2 semantic invariants (core subset)*

While JSON Schemas enforce structure (types, required fields), **Semantic Validators** enforce meaning, invariants, and cross-object consistency. They act as the pure, deterministic gateway that prevents the Orchestrator from corrupting the `.audit/runs/` state.

## Core Properties
1. **Deterministic & Pure:** No LLMs, no network calls, no heuristics.
2. **Monotonic Authority:** Validators only return `PASS`, `WARNING`, `ERROR`, or `UNDETERMINABLE`. They **never** mutate, silently fix, or epistemically elevate an object (e.g., they cannot change `UNKNOWN` to `VALID`).
3. **Strict Epistemology:** Distinguish between `ERROR` (e.g., dangling reference) and `UNDETERMINABLE` (e.g., missing evidence dependency context).

---

## 1. Identity & Canonical Consistency
- `TargetSnapshot` is strictly immutable after creation.
- IDs and fingerprints must be stable and derived deterministically.
- Arrays where order is semantic must follow canonical ordering (to ensure stable hashing/diffing).

## 2. Referential Integrity
- Enforce "foreign-key" style constraints across the JSON files:
  - `AuditWorkItem.plan_ref` must point to an existing `AuditPlan`.
  - `Evidence.work_item_ref` must point to an existing `AuditWorkItem`.
  - `AuditRun.recovery_from_ref` must point to an interrupted/failed previous run.

## 3. State Machine & Cross-Object Transitions
- **AuditWorkItem:** Must follow valid state transitions (`PLANNED` -> `RUNNING` -> `TERMINATED`). It cannot jump back to `RUNNING` after being `TERMINATED` without a formal retry/recovery Attempt.
- **Cross-State:** An `AuditRun` cannot be `COMPLETED` if any of its referenced `AuditWorkItems` is still `RUNNING`.

## 4. Incremental / Reuse Validity (ADR-04)
- **`REUSE`** is only legal if:
  1. Previous evidence exists and is referencable.
  2. Provenance exists.
  3. The `TargetSnapshot` methodology is compatible.
  4. Evidence dependencies are strictly unbroken.
- **Computed Action Match:** If the motor computes the necessity for `REAUDIT`, the persisted `action` cannot be `REUSE` (prevents silent evasion of analysis).

## 5. Evidence & Finding Lifecycle Integrity
- `Evidence = INVALID` cannot coexist with a `WorkItem.action = REUSE` for the same evidence.
- `INVALIDATE ≠ FIXED`: A missing file invalidates the evidence but does not authorize the validator/system to mark the finding lifecycle as `FIXED`. 
- `REGRESSED` requires a compatible prior state (e.g., `FIXED`). `NEW` -> `REGRESSED` is a semantic error.

## 6. Coverage Completeness (Derived, Not Declared)
- Coverage completeness cannot merely be a string `COMPLETE` set by the agent. It must be mathematically derivable:
  - `requested_scope` -> filtered by `applicability` -> yields `selected_scope`.
  - `selected_scope` matches the aggregate of completed/reused `AuditWorkItems`.
- If a WorkItem was `BLOCKED` (e.g., by safety gate), the run coverage is strictly `PARTIAL`.

## 7. Budget & Attempt Consistency (ADR-07)
- If `consumed > allocated` budget, it triggers an `ERROR` (or `WARNING` if policy permits overshoot), and enforces `PARTIAL` state.
- `NON_RETRYABLE` failure + new attempt = `ERROR` (unless explicit human override is present).
- `Attempt #2` cannot exist without `Attempt #1`. Temporal validation ensures `attempt #2 start > attempt #1 finish`.

## 8. Trust, Safety & Egress (ADR-05)
- Egress Policy = `DENY` + Target = `External Model` + Data = `Sensitive` -> `ERROR` (Cannot result in `ALLOWED`).
- Command execution without a validated capability set -> `ERROR`.

## 9. Publication Eligibility (The Final Gate)
- `publication_state` is a derived eligibility check, not an arbitrary flag.
- `can_publish(run) = TRUE` ONLY IF:
  - Target is intact (no Snapshot Drift).
  - Plan is valid and all required work is accounted for.
  - No critical integrity errors exist in the artifacts.
  - No `FAILED` or `BLOCKED` items exist without explicit risk acceptance.


## Phase 2 Implementation Notes

The deterministic semantic layer now exposes a complete state-graph validation entry point,
`validate_state_graph(...)`, covering Snapshot → Plan → WorkItem → Attempt → Run → Evidence
relationships without mutating persisted state.

Coverage is derived from the set of selected audit domains and the set of domains actually
covered by successfully terminated or safely reusable WorkItems. WorkItem count is not used as
a proxy for scope coverage.

Finding lifecycle is independent from finding epistemic status. The lifecycle model includes
`NEW`, `PERSISTING`, `MODIFIED`, `FIXED`, `REGRESSED`, and `INVALIDATED`.
`INVALIDATED -> FIXED` is rejected; `REGRESSED` requires a prior `FIXED` state.

Evidence persistence also enforces exact WorkItem and TargetSnapshot references, and the
optional raw model-output hash is verified deterministically.
## Phase 4 — Independent Verification Gate

Before publication/consolidation, semantic candidates pass through a verifier that is independent of the auditor's narrative.
The verifier consumes the canonical Evidence associated with the WorkItem and exact TargetSnapshot. It does not use raw
LLM output, provider/model metadata, description, impact, or recommendation as proof.

P0/P1 candidates cross the consolidation gate only when their existing epistemic state is CONFIRMED, confidence is HIGH,
and a concrete location is grounded in Evidence.source_refs. The verifier never promotes a candidate; unsuccessful checks
produce REJECTED or NOT_DETERMINABLE. Unverified P0/P1 candidates are excluded from the consolidated semantic set while
the verifier result remains auditable in the execution state and Ledger.

## Phase 6 — Operational Concurrency and Recovery

The writer boundary is now physical, not merely conventional:

- AuditWriterLock serializes a complete audit execution within one .audit namespace.
- Lock acquisition is non-blocking and fails closed when another writer is active.
- The lock file is diagnostic only; recovery never infers staleness from its PID contents.
- Canonical state writes fsync the temporary file before atomic replacement and fsync the parent directory when supported.
- AuditRun=RUNNING is persisted before the first WorkItem executes.
- Orchestrator.prepare_recovery() reconstructs a fresh Plan/WorkItem/Run graph with recovery_from_ref instead of mutating the interrupted run.
- Completed WorkItems are preserved on replay; unresolved items return to PLANNED.
- A completed WorkItem is not executed again during replay, preventing accidental duplicate execution.

These rules are operational invariants in addition to the semantic validators in Sections 1–9.

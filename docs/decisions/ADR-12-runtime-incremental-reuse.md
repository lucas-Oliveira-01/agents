# ADR-12: Runtime Incremental Reuse

**Status:** Accepted

## Context

The repository already contained a deterministic incremental decision matrix (INVALIDATE > REAUDIT > REVALIDATE > REUSE) and tests for it, but the runtime did not consume those decisions when regenerating WorkItems for a new audit execution.

Because WorkItem UUIDs are intentionally regenerated, historical Evidence cannot be matched by UUID alone. Because Evidence is immutable and bound to a specific WorkItem and TargetSnapshot, the runtime also cannot mutate an old Evidence record in place.

## Decision

1. Incremental matching uses the logical key (auditor, target_surface), never a generated WorkItem UUID.
2. Historical Evidence is reusable only when the logical match is one-to-one.
3. Ambiguous or missing historical Evidence fails closed to REAUDIT.
4. A REUSE action creates a new immutable Evidence record for the current WorkItem and current TargetSnapshot.
5. The new Evidence carries derived_from_evidence_ref pointing to the historical Evidence.
6. A reuse receipt records project-audit-incremental-reuse as the execution event.
7. Existing finding records for a reused surface are carried forward as PERSISTING before lifecycle reconciliation.
8. Historical Evidence and historical FindingRecord objects are never mutated in place.
9. REVALIDATE and REAUDIT remain normal executable audit paths.

## Consequences

- Repeated audits can skip deterministic workers when dependency validity proves the prior observation remains reusable.
- Evidence lineage remains explicit and auditable.
- Generated UUIDs do not become part of logical identity.
- Ambiguity costs an additional audit rather than risking incorrect evidence transfer.
- Finding lifecycle reconciliation no longer mistakes an intentionally reused finding for a missing finding and therefore does not infer FIXED merely because a semantic worker was skipped.

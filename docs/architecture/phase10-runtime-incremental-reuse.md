# Phase 10 — Runtime Incremental Reuse

## Status

Implemented on branch phase10-incremental-execution after the Phase 9 deterministic classification baseline.

## Objective

Close the gap between the frozen incremental decision matrix and the real audit runtime.

## Scope

- Match regenerated WorkItems to historical WorkItems by logical identity: auditor + target_surface.
- Treat missing or ambiguous historical Evidence as REAUDIT.
- Execute REUSE without invoking the auditor worker.
- Create a fresh immutable Evidence record bound to the current WorkItem and current TargetSnapshot.
- Preserve explicit Evidence lineage through derived_from_evidence_ref.
- Record an incremental-reuse execution receipt.
- Carry forward non-fixed FindingRecords for reused surfaces before lifecycle reconciliation.
- Keep historical state immutable.

## Runtime behavior

The flow is now:

Discovery -> Classification -> Plan -> Incremental Binding -> WorkItem Execution

For each WorkItem:

- REUSE: create a new Evidence from the valid historical Evidence and terminate safely.
- REVALIDATE: execute the normal worker path.
- REAUDIT: execute the normal worker path.
- ambiguous/missing prior evidence: force REAUDIT.

## Safety invariants

1. No historical Evidence is mutated.
2. No WorkItem UUID is used as logical identity across runs.
3. Ambiguous historical state never authorizes automatic reuse.
4. Reuse is still bounded by the existing dependency matrix.
5. Reused findings are not interpreted as absent during lifecycle reconciliation.
6. The existing writer lock, snapshot checks, egress policy, and independent verification gates remain unchanged.

## Exit criteria

- Stable cross-run matching is tested.
- Ambiguity fails closed.
- Derived Evidence lineage is tested.
- An end-to-end second audit can reuse safe historical Evidence.
- Existing Phase 8/9 acceptance and normalize integration remain green.

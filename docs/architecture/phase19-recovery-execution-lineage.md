# Phase 19 — Recovery Execution Lineage Integrity

## Objective

Close the interaction between the Phase 18 Attempt.receipt_ref referential invariant and
the Phase 6 recovery model that reconstructs fresh WorkItem identities.

## Finding

A completed interrupted WorkItem previously carried its historical Attempts into the new
recovery WorkItem. After Phase 18, this was no longer valid because every non-null
Attempt.receipt_ref must resolve to a durable receipt owned by the current WorkItem.

## Resolution

Recovery now leaves historical Attempts and Receipts attached to the interrupted graph.
Completed work is carried forward only through fresh REUSE Evidence derived from valid
historical Evidence.

The fresh WorkItem is first persisted as PLANNED, then fresh Evidence is persisted, and
only then is it transitioned to TERMINATED/NONE. This preserves the existing Evidence
requirement for successful terminal WorkItems.

When no valid historical Evidence is available, recovery falls back to PLANNED so the item
can be executed again instead of asserting a completed result without proof.

## Invariants

- Fresh recovery WorkItems never contain historical Attempt or receipt_ref values.
- Derived recovery Evidence points to the fresh WorkItem and records its historical source
  through derived_from_evidence_ref.
- Historical WorkItem/Attempt/Receipt/Evidence state is unchanged.
- Successful terminal recovery WorkItems have current-scope Evidence.
- Existing recovery of unfinished items remains PLANNED.
- No JSON schema expansion is required.

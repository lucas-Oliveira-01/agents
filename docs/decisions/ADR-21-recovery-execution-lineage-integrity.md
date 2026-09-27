# ADR-21 — Recovery Execution Lineage Integrity

Status: Accepted
Phase: 19
Date: 2026-09-27

## Context

Phase 18 closed the Attempt.receipt_ref referential boundary: every persisted non-null
receipt reference must resolve to an ExecutionReceipt belonging to the same WorkItem.

The recovery path creates fresh WorkItem identities, but previously copied the interrupted
WorkItem's Attempts unchanged. A copied receipt_ref therefore pointed back to the old
WorkItem and violated the new referential invariant.

## Decision

Recovery never copies historical Attempts or ExecutionReceipt references into a fresh
WorkItem identity.

A completed WorkItem is preserved only when its historical Evidence is available, belongs
to the recovery snapshot, and is VALID. Recovery creates a fresh WorkItem in PLANNED state
with action REUSE, persists it, derives fresh immutable Evidence records using
derived_from_evidence_ref, and only then transitions that WorkItem to TERMINATED/NONE.

Historical WorkItem, Attempt, Receipt, and Evidence records remain unchanged.

When the completed item's valid Evidence cannot be recovered, the fresh WorkItem is
reconstructed as PLANNED and is eligible for normal execution rather than being marked
completed without a proof-bearing Evidence edge.

## Consequences

Recovery has a closed graph under the Phase 18 receipt invariant and retains historical
execution records without cross-linking them into new identities.

No canonical JSON schema, entity, WorkItem action, routing responsibility, or publication
mode is added.

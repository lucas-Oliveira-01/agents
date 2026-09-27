# ADR-22 — Durable Evidence Immutability and Snapshot-Drift Lineage

Status: Accepted
Phase: 20
Date: 2026-09-27

## Context

Evidence, TargetSnapshot, ExecutionReceipt, and frozen AuditPlan are immutable canonical records.
However, StateStore previously overwrote an existing JSON file when the same identity was supplied
with changed data. Snapshot-drift reconciliation also rewrote an existing Evidence record in place
from VALID to STALE.

That behavior contradicted the append-only execution/evidence model and made historical records
mutable at the durable persistence boundary.

## Decision

StateStore treats immutable canonical records as write-once: identical rewrites are idempotent,
conflicting rewrites fail closed. Mutable WorkItem and AuditRun persistence remains replacement-based.

Snapshot drift never rewrites historical Evidence. A fresh STALE Evidence record is created with a
new identity and `derived_from_evidence_ref` pointing to the original observation. The derived record
preserves the historical snapshot/work-item binding while carrying the current methodology policy
in its provenance.

## Consequences

Historical Evidence remains stable and auditable. Drift status becomes an explicit lineage edge
instead of a mutation of the observation itself.

No canonical schema, entity, WorkItem action, routing responsibility, or publication mode is added.

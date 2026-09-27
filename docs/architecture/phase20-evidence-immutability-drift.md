# Phase 20 — Durable Evidence Immutability and Snapshot-Drift Lineage

## Finding

An immutable Evidence model was still exposed to mutable persistence paths: StateStore could
rewrite an existing identity, and snapshot-drift reconciliation wrote VALID → STALE under the same
Evidence ID.

## Resolution

Immutable persistence is now write-once. Same-value persistence is idempotent; conflicting writes
fail closed for TargetSnapshot, frozen AuditPlan, Evidence, and ExecutionReceipt.

Node-level snapshot drift now derives a fresh STALE Evidence record with
`derived_from_evidence_ref` and attaches it to the affected WorkItem. The historical observation
remains unchanged.

## Invariants

- Historical immutable records are never overwritten.
- Same-value persistence remains idempotent.
- Conflicting writes fail before durable replacement.
- STALE Evidence has a distinct identity and explicit lineage.
- The original VALID Evidence remains available for audit and forensic reconstruction.
- Mutable WorkItem/AuditRun state continues to use normal replacement semantics.
- No JSON schema expansion is required.

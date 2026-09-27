# ADR-20 — Execution History Integrity Closure

Status: Accepted
Phase: 18
Date: 2026-09-27

## Context

A fresh audit after Phase 17 found a remaining execution-history boundary in the mutable AuditWorkItem state machine.

retry_attempt() changed a terminated WorkItem to RUNNING and cleared its failure state before start_attempt() validated temporal ordering. A rejected retry could therefore leave the in-memory WorkItem altered even though no new Attempt was created.

Attempt.receipt_ref was also a declared reference to ExecutionReceipt, but the WorkItem persistence gate did not verify that referenced receipts existed or belonged to the same WorkItem.

## Decision

Phase 18 closes these execution-history invariants without changing the canonical JSON schemas.

### Atomic retry transition

retry_attempt() validates the candidate timestamp against the last completed attempt before changing execution_state or failure_state. A rejected retry leaves the WorkItem unchanged.

### Attempt to Receipt referential closure

When a WorkItem contains a non-null Attempt.receipt_ref, Orchestrator.commit_work_item() now requires the referenced ExecutionReceipt to be durable and to point back to the same WorkItem.

The normal lifecycle remains compatible with an in-progress attempt: a WorkItem can be committed while an attempt is still running and has no receipt_ref yet. The receipt is persisted before the completed attempt is committed.

## Consequences

Rejected retry operations are state-preserving, and persisted WorkItems cannot contain dangling or cross-linked execution receipts.

No new entity, schema field, WorkItem action, routing responsibility, or publication mode is introduced.
# ADR-19 — Immutable Evidence & Execution Trail Closure

Status: Accepted  
Phase: 17  
Date: 2026-09-27

## Context

After Phase 16, the canonical Layer 2 state machine and Plan/Run graph were protected at the main persistence boundary. A fresh audit found that several records declared immutable by the canonical model were still only shallowly immutable at construction time.

Specifically:

- ProjectState was frozen but accepted caller-owned mutable collections for submodules and tracked inputs;
- Evidence was frozen but accepted caller-owned mutable source_refs and dependencies;
- ExecutionReceipt was frozen but accepted mutable arguments and artifact_refs;
- commit_receipt() persisted a receipt without requiring its WorkItem reference to resolve to durable state;
- commit_evidence() validated snapshot consistency using the transient WorkItem supplied by the caller, without first requiring that WorkItem identity to exist in the StateStore.

These were persistence-boundary gaps, not new semantic concepts.

## Decision

Phase 17 closes the immutable-object and referential persistence boundaries without changing canonical JSON schemas.

### Deep immutability

Immutable records normalize nested collections at object construction:

- ProjectState.submodules_state and tracked_input_fingerprints;
- Evidence.source_refs and dependencies;
- ExecutionReceipt.arguments and artifact_refs.

The model therefore owns immutable tuple representations instead of retaining mutable caller aliases. Existing TargetSnapshot methodology immutability remains unchanged.

### Receipt referential gate

Orchestrator.commit_receipt() now requires ExecutionReceipt.work_item_ref to resolve to a persisted AuditWorkItem before the receipt is written.

### Evidence referential gate

Orchestrator.commit_evidence() now resolves the persisted WorkItem identified by Evidence.work_item_ref and validates the evidence against that durable WorkItem and its immutable Plan/Snapshot context.

A transient WorkItem object cannot substitute for missing or differently planned canonical state.

## Consequences

The immutable Layer 2 records are protected against nested collection alias mutation, including after StateStore reload.

Execution receipts and Evidence cannot cross the Orchestrator persistence boundary with dangling WorkItem references.

No new canonical entity, schema field, WorkItem action, routing responsibility, or publication mode is introduced.


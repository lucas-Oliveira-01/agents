# ADR-18 — Canonical State Integrity Closure

**Status:** Accepted  
**Phase:** 16  
**Date:** 2026-09-27

## Context

The Layer 2 model defines the Orchestrator as the single writer and states that canonical state transitions are validated before persistence. A fresh audit of main after Phase 15 found two remaining boundary gaps:

1. commit_work_item() performed JSON Schema validation but did not execute the composite semantic WorkItem validators or require the referenced Plan to exist in durable state.
2. AuditRun.work_item_refs was checked against the caller-supplied WorkItems, but not against the immutable WorkItem set held by the frozen AuditPlan. A caller could therefore construct a Run over a strict subset of a larger Plan.
3. AuditPlan.freeze() converted collection fields to tuples but still allowed direct top-level reassignment, and mutable nested applicability decisions could be changed after freeze. Reloaded frozen plans could also expose list-backed collection fields.

These gaps weakened the intended state-machine and graph-closure guarantees at the persistence boundary.

## Decision

Phase 16 closes the canonical state boundary without expanding the JSON schemas.

### WorkItem commit gate

Orchestrator.commit_work_item() now:

- performs structural schema validation;
- requires work_item.plan_ref to resolve to a persisted AuditPlan;
- executes the composite WorkItem semantic validators before saving;
- rejects invalid canonical state before the StateStore write.

### Run ↔ Plan graph closure

validate_run_work_item_references() now verifies that:

- Run references are unique;
- the Run WorkItem set equals the immutable Plan WorkItem set;
- the supplied WorkItem objects remain consistent with the Run references.

A vertical-slice call that receives WorkItems separately materializes those references into the Plan before the Plan is frozen. A non-empty pre-existing Plan whose WorkItem set differs from the supplied slice is rejected.

### Frozen Plan immutability

AuditPlan now rejects field reassignment after freeze(). Frozen instances normalize collection fields to tuples, including when reconstructed from durable storage. ApplicabilityDecision and BudgetEnvelope are immutable value objects, and applicability evidence references are stored as tuples.

## Consequences

The persistence boundary now rejects malformed WorkItem state, dangling Plan references, and Run/Plan WorkItem-set divergence deterministically.

No new canonical entity, schema field, WorkItem action, routing responsibility, LLM/SLM decision, or publication mode is introduced.

The changes may surface previously invalid test fixtures that created WorkItems before their Plan was persisted or built Runs over incomplete Plan graphs; such fixtures must be corrected rather than bypassing the validators.

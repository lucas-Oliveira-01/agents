# Phase 16 — State Integrity Closure

## Objective

Close the remaining Layer 2 persistence gaps discovered by a fresh audit of main after Phase 15.

## Findings addressed

### 1. WorkItem commit was structurally validated but not semantically gated

Before Phase 16, Orchestrator.commit_work_item() called only validate_audit_work_item(). The composite semantic validator existed but was used later by run-level validation. This left a path where invalid WorkItem state could cross the persistence boundary.

Phase 16 makes the WorkItem commit boundary authoritative: the referenced Plan must be durable and the WorkItem semantic validators must pass before StateStore.save_work_item().

### 2. Run graph could be narrower than the frozen Plan

Run validation previously compared AuditRun.work_item_refs with only the WorkItem list supplied by the caller. The immutable Plan itself was not used as the second side of the closure check.

Phase 16 requires exact set equality between the Run references and the Plan's frozen WorkItem set.

### 3. Frozen Plan was only collection-level immutable

AuditPlan.freeze() already converted selected collections to tuples, but arbitrary top-level field reassignment remained possible and nested applicability decisions remained mutable.

Phase 16 makes frozen-plan reassignment fail closed and normalizes immutable nested value objects. Deserialization of a frozen Plan restores the immutable collection representation.

## Invariants after Phase 16

- AuditPlan is immutable after freeze().
- A frozen Plan's WorkItem set is canonical for its Run.
- commit_work_item() cannot persist a WorkItem with a dangling Plan reference.
- commit_work_item() cannot persist a WorkItem failing its semantic state/policy validators.
- AuditRun cannot claim a WorkItem set different from its Plan.
- No canonical schema expansion is required.

## Non-goals

Phase 16 does not change incremental action semantics, classification, applicability, semantic model routing, publication policy, or the Layer 3 normalizer.

Those concerns remain governed by Phases 10–15 and their existing contracts.

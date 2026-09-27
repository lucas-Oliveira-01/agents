# Phase 17 — Immutable Evidence & Execution Trail Closure

## Objective

Close the remaining shallow-immutability and referential persistence gaps in Layer 2 after Phase 16.

## Findings addressed

### 1. Frozen records could retain mutable collection aliases

A frozen dataclass prevents attribute rebinding but does not freeze nested lists supplied by a caller. Phase 17 normalizes the collection fields of ProjectState, Evidence, and ExecutionReceipt to tuples during construction.

This also guarantees that StateStore reloads reconstruct the same immutable representation.

### 2. ExecutionReceipt could reference a non-persisted WorkItem

The Orchestrator is the canonical persistence authority. Phase 17 requires the receipt's WorkItem reference to resolve to durable state before the receipt is saved.

### 3. Evidence could rely on transient WorkItem context

Evidence already had a snapshot-consistency validator, but its context came from the transient object passed to commit_evidence(). Phase 17 first resolves the persisted WorkItem and then performs the snapshot consistency check against that canonical object.

## Invariants after Phase 17

- ProjectState nested collections are immutable tuples.
- Evidence nested source/dependency collections are immutable tuples.
- ExecutionReceipt argument/artifact collections are immutable tuples.
- Every persisted ExecutionReceipt references a durable WorkItem.
- Every persisted Evidence references a durable WorkItem and its canonical Plan/Snapshot context.
- No schema expansion is required.

## Non-goals

Phase 17 does not change incremental action semantics, classification, applicability, change impact, publication policy, OmniRoute routing, or the Layer 3 normalizer.


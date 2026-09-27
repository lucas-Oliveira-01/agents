# Phase 18 — Execution History Integrity Closure

## Objective

Close the remaining mutable execution-history and Attempt-to-Receipt integrity gaps after Phase 17.

## Findings addressed

### 1. Rejected retry could partially mutate WorkItem state

The retry path previously changed state before temporal validation delegated to start_attempt(). Phase 18 validates the candidate timestamp first and only then performs the RUNNING/NONE transition.

### 2. Attempt.receipt_ref was not closed against durable Receipt state

Phase 18 treats a non-null Attempt.receipt_ref as a referential edge. Before a WorkItem is persisted, the referenced ExecutionReceipt must exist and its work_item_ref must equal the containing WorkItem.

## Invariants after Phase 18

- Failed retry precondition checks do not mutate WorkItem state.
- A completed Attempt with a receipt_ref cannot be persisted with a missing Receipt.
- A Receipt referenced by an Attempt cannot belong to another WorkItem.
- Existing retry behavior remains unchanged when the timestamp is valid.
- No schema expansion is required.

## Non-goals

Phase 18 does not change incremental action semantics, classification, applicability, change impact, publication policy, OmniRoute routing, or the Layer 3 normalizer.
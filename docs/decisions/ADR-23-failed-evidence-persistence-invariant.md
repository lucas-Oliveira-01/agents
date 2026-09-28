# ADR-23 — Failed Evidence Persistence Invariant

Status: Accepted
Phase: 20
Date: 2026-09-27

## Context

During the testing of Phase 20 strict immutability contracts, a flaw was discovered in how failed or blocked LLM invocations were handled. When an LLM worker failed (e.g., infrastructure timeout) or was intercepted by a safety policy (`BLOCKED`), the worker correctly produced a transport `Evidence` object encapsulating the failure details. However, the L3 integration loop (`semantic_runner.py`) terminated the `AuditWorkItem` without persisting the failure `Evidence` to the physical `.audit/runs/evidence/` storage. 

Later runtime stages (such as the Phase 20 Evidence integrity validations) attempted to look up the UUID attached to the WorkItem and crashed with a `FileNotFoundError`.

## Decision

The physical persistence of `Evidence` is mandatory for **all** WorkItem terminal states that produce an Evidence UUID, regardless of the operation's success or failure. 

We explicitly enforce `orchestrator.commit_evidence(result.evidence, work_item)` for `FAILED` and `BLOCKED` states in the orchestration runner.

## Consequences

1. **Integrity Maintained:** The fail-closed architecture is preserved. A failed WorkItem still guarantees the physical presence of its root-cause Evidence in the `StateStore`.
2. **Traceability:** Auditors and downstream debuggers can inspect the exact payload/LLM reason that caused the `FAILED` or `BLOCKED` status, as it is perfectly persisted alongside successful inferences.

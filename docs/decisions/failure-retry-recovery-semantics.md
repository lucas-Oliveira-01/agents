# Architecture Decision Record: Failure, Retry & Recovery Semantics (ADR-07)

**Status:** accepted

## Context
In an autonomous, multi-worker auditing system, failures are inevitable: LLM providers time out, workers crash, execution sandboxes deny commands, and targets drift mid-audit. Without rigorous failure semantics, the Orchestrator might infinitely retry non-idempotent operations, confuse a safety block with a network crash, or publish an incomplete audit as "secure."

This ADR defines how the Orchestrator classifies, recovers from, and bounds anomalies.

## Decision

### 1. Separation of Failure Dimensions
We reject monolithic status enums (e.g., `FAILED_SAFETY_BLOCKED`). The execution state of an `AuditWorkItem` is separated into distinct semantic dimensions:
- **Execution State:** `PLANNED`, `RUNNING`, `INTERRUPTED`, `TERMINATED`.
- **Failure Classification:** `INFRASTRUCTURE_ERROR`, `SAFETY_VIOLATION`, `BUDGET_EXHAUSTED`, `SNAPSHOT_DRIFT`, `SCHEMA_VIOLATION`.
- **Retryability:** Is the *failure* inherently retryable? (e.g., `network_timeout` = yes; `sandbox_violation` = no).
- **Idempotency / Retry Eligibility:** Is the *operation* safe to retry? (e.g., `git log` = yes; `docker compose up` = potentially no).

### 2. The Semantic Definitions of Terminal States
- **`BLOCKED`**: The execution was deliberately halted by a policy constraint (e.g., Execution Safety Gate denied a command). This is not an error; the system worked as intended.
- **`FAILED`**: The execution attempted a valid operation but crashed or encountered an unexpected system error (e.g., worker died, provider returned 500).
- **`PARTIAL`**: The execution ended cleanly but did not complete its intended scope (e.g., Budget exhausted mid-audit). It yields valid partial results.

*Invariant: `BLOCKED` ≠ `FAILED` ≠ `PARTIAL` ≠ `SUCCESS`. An audit comprising `PARTIAL` work items must never be published as a `COMPLETE` audit.*

### 3. Retry vs. Recovery
- **Retry:** Re-executing an operation. A failure may be `RETRYABLE`, but a retry is only `RETRY_ALLOWED` if the operation is idempotent, budget permits, and safety policies allow it. Non-idempotent operations are never blindly retried.
- **Recovery:** Reconstructing state from persisted evidence after an interruption (e.g., worker crash). If a worker dies but left a complete, verifiable Markdown output on disk, the Orchestrator can *recover* the finding without needing to *retry* the LLM execution.

### 4. Snapshot Drift Handling
If the working tree changes while an `AuditWorkItem` is `RUNNING` (Snapshot Drift, see ADR-06), the system must immediately:
1. `STOP` execution for affected items.
2. Mark any in-flight evidence as `INVALID`.
3. Prevent publication of the run as `COMPLETE`.
4. Require explicit reconciliation or restart against the new snapshot.

### 5. The Publication Barrier
The Orchestrator acts as the single-writer (ADR-04). It enforces a strict **Publication Barrier**: no `AuditRun` can transition to `PUBLISHED` if any `AuditWorkItem` is `FAILED` or `BLOCKED` without an explicit risk acceptance policy being met.

## Consequences
- **Positive:** Prevents infinite retry loops on non-idempotent or policy-blocked actions.
- **Positive:** Enables cheap recovery from worker crashes without re-spending LLM tokens.
- **Negative:** Increases the complexity of the Orchestrator's internal state machine, requiring meticulous lifecycle management for `AuditWorkItems`.

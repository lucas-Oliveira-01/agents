# Phase 7 — Integrity Closure

## Status

Active hardening baseline for the post-Phase-6 architecture.

## Scope

Phase 7 closes residual integrity gaps rather than introducing new providers or agent features.

## Canonical invariants

- Sensitive data is blocked whenever `allow_sensitive=False`, independently of destination. Unknown sensitivity is fail-closed.
- Discovery accepts regular files only and rejects symlinks and special filesystem entries before any content-following operation.
- Publication is graph-closed: the supplied WorkItems must exactly match the persisted Run and Plan references, and Run/Plan snapshot identity must agree.
- Raw semantic transport Evidence is persisted before a WorkItem becomes terminal on schema or invalid-output failure, allowing deterministic verifier reload.
- Auto-fix execution state is bound to its source AuditRun and immutable source snapshot. A post-fix candidate may be marked FIXED only after COMPLETE execution and FULL coverage with verifier success.
- Finding lifecycle is durable through `FindingRecord` in the local StateStore.
- Finding identity is based on `FindingFingerprint`, which excludes generated narrative and physical source location.

## Snapshot drift

The runtime distinguishes global target drift from node dependency drift.

Global drift remains a publication/completion boundary: a run targeting a different root snapshot cannot be published.

Node dependency drift is reconciled at evidence/work-item level. Evidence depending on changed nodes becomes STALE and affected work items are terminated with `SNAPSHOT_DRIFT`; independent surfaces may continue.

## Acceptance evidence

The phase is considered closed only when the implementation, semantic validators, adversarial regression tests, and current architecture documents describe the same behavior.

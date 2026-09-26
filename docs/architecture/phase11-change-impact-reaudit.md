# Phase 11 — Change Impact & Reaudit Necessity

## Status

Implemented on branch `phase11-change-impact`.

## Objective

Make inter-snapshot change impact an explicit deterministic input to the existing incremental decision matrix.

The phase does not introduce a new WorkItem action, a new router, a semantic classifier, or a canonical schema field.

## Implemented behavior

### Change Impact

`build_change_impact(previous_snapshot, current_snapshot)` compares the canonical TargetSnapshot input fingerprints and methodology state.

It emits deterministic events for:

- `ADDED`
- `MODIFIED`
- `DELETED`
- `RENAMED`
- `DEPENDENCY_CHANGE`
- `CONFIG_CHANGE`
- `METHODOLOGY_CHANGE`

A rename is accepted only when exactly one deleted path and exactly one added path share the same fingerprint. Ambiguous same-fingerprint moves remain add/delete events and cannot authorize reuse.

### Reaudit Necessity

`assess_reaudit_necessity()` explains the existing ADR-04/ADR-12 action decision using the Change Impact result.

The existing precedence remains:

```text
INVALIDATE > REAUDIT > REVALIDATE > REUSE
```

No `RECHECK` action was introduced.

### Rename continuity

When a rename is deterministically proven, the incremental decision layer resolves the historical dependency through a path alias. Safe REUSE therefore remains possible without treating the rename as deletion.

Fresh derived Evidence rewrites source/dependency references to the current path while preserving `derived_from_evidence_ref`.

### Runtime integration

For `previous_run_ref` executions, the runtime now:

1. builds the Change Impact report;
2. feeds it into stable incremental planning;
3. records deterministic impact/reason data in `AuditWorkItem.decision_basis`;
4. passes proven rename aliases into Evidence reuse.

Historical state remains immutable.

## Important boundary

ClassificationResult is still deterministic and upstream of planning. This phase does not persist ClassificationResult history or invent hidden classification dependencies.

When the system cannot prove a dependency relationship, existing fail-closed behavior remains authoritative.

Live Snapshot Drift during an active run remains governed by ADR-08 and is not converted into an inter-snapshot Change Impact event.

## Acceptance

The Phase 11 suite verifies:

- identical snapshots produce no impact;
- source changes produce REAUDIT;
- semantic/config dependency changes produce REVALIDATE;
- deleted dependencies produce INVALIDATE;
- unique renames preserve safe REUSE and rebase Evidence references;
- ambiguous renames do not authorize reuse;
- methodology changes produce explicit REAUDIT;
- the persisted WorkItem decision basis contains the deterministic impact explanation.

The gate runs on Python 3.13 in addition to the existing core, Phase 8, Phase 9, Phase 10, and normalize integration jobs.

## Non-goals

- No Tier 2 / SLM implementation.
- No LLM change-impact classifier.
- No provider/model routing changes.
- No audit-normalize changes.
- No canonical JSON schema changes.

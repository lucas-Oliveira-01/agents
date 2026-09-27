# Phase 13 — Applicability Coverage Closure

**Status:** Implemented on `phase13-applicability-coverage`

## Goal

Close the gap between deterministic file classification and executable audit planning for build, configuration, and documentation surfaces that were already supported by the Engineering Auditor.

## Before

The runtime classified files as `BUILD`, `CONFIG`, and `DOCUMENTATION`, but `classify_applicability()` emitted no corresponding planning decisions. These files could therefore be listed in the file inventory without becoming WorkItems.

## After

`classify_applicability()` now emits:

| Surface | Evidence source | State when present |
|---|---|---|
| `BUILD/MANIFESTS` | `FileKind.BUILD` | `APPLICABLE` |
| `CONFIGURATION/SURFACE` | `FileKind.CONFIG` | `APPLICABLE` |
| `DOCUMENTATION/BASELINE` | `FileKind.DOCUMENTATION` | `APPLICABLE` |

When none is discovered, the state is `NOT_DETERMINABLE`, preserving the project's fail-closed epistemology.

The planner uses the existing applicability-to-WorkItem path. No new execution action is required.

## Deterministic execution

The existing Engineering Auditor handlers are now reachable from the plan:

- `BUILD/MANIFESTS` → build/dependency manifest inventory;
- `CONFIGURATION/SURFACE` → configuration artifact inventory;
- `DOCUMENTATION/BASELINE` → documentation inventory and README operational-section signals.

## Validation

The Phase 13 acceptance suite proves:

1. the three surfaces are `APPLICABLE` when corresponding artifacts exist;
2. the three WorkItems are materialized;
3. Engineering PASS 1 executes all three handlers;
4. missing artifacts remain `NOT_DETERMINABLE`.

The canonical schemas and OmniRoute boundary remain unchanged.
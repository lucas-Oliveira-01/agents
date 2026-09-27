# ADR 15: Applicability Coverage Closure

**Status:** Accepted — implemented by Phase 13

## Context

The deterministic file classifier already recognizes build manifests, configuration artifacts, and documentation artifacts, and the Engineering Auditor already contains deterministic inspection handlers for these categories.

However, `classify_applicability()` did not create corresponding planning decisions. As a result, those files could remain visible in the inventory while never becoming executable Engineering WorkItems. Coverage could therefore be reported as complete for the selected scope without proving that these already-supported deterministic surfaces were inspected.

This is a planning-coverage gap, not a need for new audit logic.

## Decision

Phase 13 makes three existing deterministic surfaces explicit in the applicability matrix:

- `BUILD/MANIFESTS`;
- `CONFIGURATION/SURFACE`;
- `DOCUMENTATION/BASELINE`.

The decision state is:

- `APPLICABLE` when at least one corresponding classified artifact is discovered;
- `NOT_DETERMINABLE` when none is discovered, because absence of a discovered artifact is not proof that the project has no such mechanism;
- `NOT_APPLICABLE` is not synthesized for these surfaces by absence alone.

Each non-`NOT_APPLICABLE` decision becomes a normal `AuditWorkItem` through the existing planner.

No new WorkItem action, canonical Layer 2 entity, schema field, router, or semantic worker is introduced.

## Execution semantics

These WorkItems run through the existing deterministic Engineering Auditor:

- `BUILD/MANIFESTS` → `BUILD-INV-001`;
- `CONFIGURATION/SURFACE` → `CONFIG-INV-001`;
- `DOCUMENTATION/BASELINE` → `DOC-INV-001`.

The resulting Evidence participates in the existing verifier, coverage derivation, Change Impact, and Classification Lineage paths without special cases.

## Invariants

1. A discovered build/config/documentation artifact is not merely inventory metadata; it is plannable.
2. A missing artifact does not become `NOT_APPLICABLE` solely because discovery found nothing.
3. Planning and engineering inspection use the same canonical surface names.
4. Existing coverage semantics remain authoritative; no synthetic coverage is added.
5. Deterministic inspection remains read-only and does not escalate to LLM.
6. Phase 13 does not modify the canonical JSON schemas.

## Acceptance criteria

1. A project with build, configuration, and documentation artifacts receives all three applicability decisions as `APPLICABLE`.
2. The planner materializes all three WorkItems.
3. Engineering PASS 1 executes all three handlers and persists Evidence.
4. A project without the artifacts records `NOT_DETERMINABLE`, not `NOT_APPLICABLE`.
5. Existing Phase 8–12 and normalization acceptance suites remain green.
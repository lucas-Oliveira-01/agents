# Phase 8 — Production Validation / Operationalization

## Status

Proposed and implemented on branch `phase8-production-validation`. This phase is the operational acceptance layer after the Phase 7 integrity baseline.

## Objective

Demonstrate that the existing deterministic-first Project Audit runtime is repeatable and operationally testable across representative target shapes, without introducing new audit capabilities or weakening the existing trust boundaries.

## Scope

### 1. Golden evaluation corpus

The repository contains a small deterministic corpus covering:

- `clean-project`
- `security-vulnerable`
- `partial-coverage`
- `snapshot-drift`
- `auto-fix`

The corpus is a test seed. It does not claim semantic completeness for the represented projects.

### 2. Determinism gate

Repeated discovery over the same immutable filesystem state must produce the same input fingerprint set.

Repeated deterministic inspection must produce the same inspection fingerprint even when the WorkItem identifier changes.

Repeated full audits over the same target must produce the same canonical runtime signature. Volatile identifiers such as Run IDs, WorkItem IDs, Evidence IDs, and timestamps are intentionally excluded from this signature.

### 3. Finding lifecycle acceptance

The operational suite exercises the durable sequence:

`NEW → PERSISTING → MODIFIED → FIXED → REGRESSED`

The suite verifies that lifecycle identity remains stable across narrative/status changes and that `FIXED` is only inferred by a COMPLETE/FULL audit.

### 4. CI acceptance gate

Phase 8 adds a dedicated GitHub Actions job that executes the operational acceptance suite on Python 3.13 in addition to the existing core matrix and normalize integration.

## Invariants

1. Deterministic fingerprints represent observed audit content, not volatile execution identifiers.
2. Discovery remains isolated from symlinks and special filesystem entries.
3. Golden cases are materialized only inside temporary test targets.
4. The acceptance suite does not use network access, provider credentials, or external LLM inference.
5. A passing Phase 8 suite is evidence of runtime repeatability; it is not evidence of semantic completeness for arbitrary projects.
6. Auto-fix remains governed by the immutable transaction and independent-verifier gates established in earlier phases.

## Non-goals

- Adding a new model provider.
- Adding new audit domains.
- Replacing the independent verifier.
- Replacing snapshot semantics.
- Treating deterministic observations as automatically confirmed vulnerabilities or defects.

## Exit criteria

Phase 8 can be considered operationally validated when:

- the golden corpus tests pass;
- deterministic fingerprints are stable across WorkItem identity changes;
- repeated full-audit canonical signatures are stable;
- the complete FindingLifecycle sequence is exercised and persisted;
- the dedicated CI acceptance job is green.

The next phase, if pursued, should be driven by measured gaps from this acceptance layer rather than by adding agents or providers preemptively.

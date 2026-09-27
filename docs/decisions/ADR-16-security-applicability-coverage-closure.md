# ADR 16: Security Applicability Coverage Closure

**Status:** Accepted — implemented by Phase 14

## Context

The Security PASS already contains a deterministic DEBUG_EXPOSURE inspector that emits SEC-DEBUG-001.

However, classify_applicability() did not produce a corresponding SECURITY/DEBUG_EXPOSURE planning decision. The handler was therefore reachable only by direct invocation or custom work item construction, not through the normal applicability → planner → Security PASS path.

This is the same class of planning-coverage gap closed for build, configuration, and documentation surfaces in Phase 13.

## Decision

Phase 14 makes SECURITY/DEBUG_EXPOSURE explicit in the applicability matrix.

The decision state is:

- APPLICABLE when at least one inspectable project artifact is discovered;
- NOT_DETERMINABLE when no inspectable artifact is discovered, because absence of a discovered artifact is not proof that debug exposure is impossible;
- NOT_APPLICABLE is not synthesized from absence alone.

The applicability evidence uses the same deterministic inspection boundary as the existing Security PASS: GENERATED, UNKNOWN, and GIT artifacts are excluded.

The existing planner materializes SECURITY/DEBUG_EXPOSURE as a normal WorkItem.

## Execution semantics

The WorkItem runs through the existing deterministic Security PASS: SECURITY/DEBUG_EXPOSURE → SEC-DEBUG-001.

A deterministic NOT_FOUND result means the surface was inspected and no known debug-exposure pattern matched. It is not equivalent to NOT_APPLICABLE.

A matched pattern remains an observation requiring the existing semantic verification path where applicable; no vulnerability is asserted by the deterministic scanner alone.

## Incremental semantics

No special incremental path is introduced. Existing Classification Lineage, Change Impact, and incremental decision machinery remain authoritative.

## Schema and responsibility impact

No canonical Layer 2 JSON schema changes. No new WorkItem action, canonical entity, OmniRoute route, or semantic worker is introduced. The existing Security PASS remains deterministic and read-only.

## Acceptance criteria

1. A project with an inspectable artifact receives SECURITY/DEBUG_EXPOSURE as APPLICABLE.
2. The planner materializes SECURITY/DEBUG_EXPOSURE.
3. The Security PASS executes SEC-DEBUG-001 through the normal runner path.
4. A project with no inspectable artifacts records NOT_DETERMINABLE.
5. A deterministic debug signal produces an OBSERVED SEC-DEBUG-001.
6. Existing Phase 8–13 and normalization acceptance suites remain green.

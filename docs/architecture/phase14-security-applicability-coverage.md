# Phase 14 — Security Applicability Coverage Closure

**Status:** Implemented on phase14-security-applicability-coverage

## Goal

Close the remaining planning-coverage gap between the deterministic Security PASS and the applicability matrix for the already-supported SECURITY/DEBUG_EXPOSURE surface.

## Before

The Security PASS contained a deterministic DEBUG_EXPOSURE handler and emitted SEC-DEBUG-001, but classify_applicability() emitted no corresponding decision.

The normal runtime could therefore omit the surface from the generated plan even though the security inspector already supported it.

## After

classify_applicability() now emits SECURITY/DEBUG_EXPOSURE as APPLICABLE when at least one inspectable artifact exists. The inspection boundary excludes GENERATED, UNKNOWN, and GIT artifacts, matching the existing Security PASS scanner.

When no inspectable artifact is discovered, the state is NOT_DETERMINABLE. The existing planner then materializes the WorkItem without a new execution action.

## Deterministic execution

The existing Security PASS remains authoritative: SECURITY/DEBUG_EXPOSURE → SEC-DEBUG-001.

A project without a matching pattern can therefore produce NOT_FOUND only after the surface has actually been inspected.

## Incremental behavior

The new applicability result participates in the existing Classification Lineage and Change Impact machinery. No new incremental rule is introduced.

## Validation

The Phase 14 acceptance suite proves explicit applicability, WorkItem materialization, normal Security PASS execution, conservative NOT_DETERMINABLE behavior, and deterministic OBSERVED output for a debug signal.

The canonical schemas and OmniRoute boundary remain unchanged.

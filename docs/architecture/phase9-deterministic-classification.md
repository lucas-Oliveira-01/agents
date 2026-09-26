# Phase 9 — Explicit Deterministic Classification Layer

## Status

Implemented on branch `phase9-deterministic-classification` after the Phase 8 operational-validation baseline.

## Motivation

The current architecture already requires a Deterministic Intelligence Layer and an auditable `ClassificationResult`, but the implementation previously exposed deterministic decisions mainly as separate helper functions.

Phase 9 makes that boundary explicit without introducing LLM calls.

## Scope

### ClassificationResult

Every classification record contains:

- `classifier_id`
- `classifier_version`
- `input_refs`
- `result`
- `confidence`
- `rationale`
- `provenance`

The object is immutable and serializable.

### ProjectProfile

The deterministic profile aggregates:

- complexity
- application type
- persistence
- network direction
- authentication signal
- frontend presence
- container platform
- CI platform
- technology surfaces
- risk surfaces
- deterministic profile fingerprint

### Existing classifier integration

`prepare_audit()` now materializes:

`Discovery -> File/Stack/Surface/Profile/Applicability/Task Classification -> Plan`

The resulting `PreparedAudit` carries both the compact `ProjectProfile` and auditable `ClassificationResult` records.

## Deterministic technology surfaces

The initial surface taxonomy is:

`HTTP`, `DATABASE`, `FILESYSTEM`, `NETWORK`, `AUTH`, `CRYPTO`, `SERIALIZATION`, `PROCESS_EXECUTION`, `CONTAINERS`, `EXTERNAL_SERVICES`.

Detection uses deterministic path/content signatures and existing file classifications.

## Planning contract

Classification remains upstream of execution. It does not confirm findings and does not replace the independent verifier.

`NOT_DETERMINABLE` applicability remains conservative: uncertainty does not silently remove a surface from the plan.

## Safety

The classifier layer:

- performs no network access;
- invokes no LLM;
- does not mutate project files;
- does not mutate canonical audit state;
- derives fingerprints from canonical classification content rather than runtime IDs.

## Acceptance

Phase 9 is accepted when:

1. classification results are emitted and publicly accessible;
2. project profiles are deterministic for the same TargetSnapshot;
3. technology surfaces are stable and sorted;
4. uncertain applicability remains represented in the plan;
5. dedicated classification tests and the existing core/normalize CI remain green.

# ADR 17: Publication Lifecycle Closure

**Status:** Accepted — implemented by Phase 15

## Context

The project-audit runtime already derived publication eligibility through can_publish() and stored RunPublicationState, but there was no runtime transition that crossed the publication barrier. A run could finish with complete execution and artifacts while remaining NOT_PUBLISHED.

## Decision

Phase 15 closes the canonical publication lifecycle inside the single-writer Orchestrator.

The transition is:

NOT_PUBLISHED → PUBLISHED_COMPLETE

only after check_publication_eligibility()/can_publish() returns without errors and all four required Markdown artifacts are physically present as regular non-symlink files.

PUBLISHED_PARTIAL remains reserved. The current model has no explicit partial-publication authorization contract, so it cannot be produced by the publication path.

Publication does not rewrite audit artifacts. It records the validated lifecycle state in the canonical AuditRun through the existing atomic state store.

## Invariants

1. Publication is controlled by the Orchestrator single-writer boundary.
2. Eligibility is derived; callers cannot simply set PUBLISHED_COMPLETE on a new run.
3. A snapshot mismatch, incomplete execution, non-full coverage, failure state, failed WorkItem, invalid REUSE evidence, or missing registered artifact prevents publication.
4. Registered publication artifacts must also exist physically and must not be symlinks.
5. Re-publishing an already published run is idempotent while its required artifacts remain available.
6. PUBLISHED_PARTIAL is rejected until an explicit authorization contract exists.
7. No canonical JSON schema, WorkItem action, auditor, or OmniRoute responsibility changes.

## Acceptance criteria

1. A complete eligible run crosses to PUBLISHED_COMPLETE.
2. The persisted AuditRun records PUBLISHED_COMPLETE.
3. Repeated publication is idempotent.
4. Incomplete execution is rejected and remains NOT_PUBLISHED.
5. Missing physical publication artifacts are rejected.
6. A direct first write of PUBLISHED_COMPLETE is rejected; the transition must go through publish_run().
7. Existing Phase 8–14 and normalization acceptance suites remain green.

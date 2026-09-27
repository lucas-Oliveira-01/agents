# Phase 15 — Publication Lifecycle Closure

**Status:** Implemented on phase15-publication-lifecycle

## Goal

Close the gap between deterministic publication eligibility and the actual AuditRun publication state transition.

## Before

can_publish() and check_publication_eligibility() derived whether a run was eligible, but no runtime operation advanced the canonical RunPublicationState after artifacts were produced.

## After

The Orchestrator now exposes publish_run(). It:

1. evaluates the existing publication eligibility gate;
2. verifies the required Markdown artifacts are physically present and non-symlink regular files;
3. advances the canonical AuditRun from NOT_PUBLISHED to PUBLISHED_COMPLETE through the existing single-writer state store;
4. treats repeated publication of the same valid run as a no-op.

Direct creation of a new PUBLISHED_COMPLETE run is rejected by the Orchestrator. PUBLISHED_PARTIAL remains unsupported until an explicit authorization contract exists.

## Runtime position

The full runtime now publishes only after artifact generation, optional normalization, final snapshot checks, and the NOT_PUBLISHED AuditRun commit have succeeded.

## Validation

The Phase 15 acceptance suite covers successful publication, persisted state, idempotency, incomplete execution rejection, missing artifact rejection, and direct-transition protection.

Canonical schemas and the OmniRoute boundary remain unchanged.

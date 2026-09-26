# Architecture Consistency Closure — Post Phase 10

**Status:** CLOSED  
**Baseline:** `main@118cf4cb3f0f0b1040c21a898244a83781ae4f05)  
**Scope:** Documentation and authority alignment only. No runtime behavior is introduced by this closure.

## Purpose

This document closes documentation drift that remained after Phases 7–10. Earlier architecture records were written before the current implementation existed and contained statuses, assumptions, or terminology that no longer described the active runtime.

The closure does not silently merge conflicting contracts. It records which documents are historical and which documents define the current implementation boundary.

## Current authority

For the post-Phase-10 runtime, the effective order is:

1. Implemented code and executable tests.
2. Accepted ADRs that explicitly describe the implemented runtime.
3. Phase acceptance/architecture records (Phases 7–10).
4. Current-state documentation.
5. Older design drafts and historical implementation records.

Historical documents remain useful as provenance, but they are not alternative current contracts.

## Resolved documentation conflicts

### Canonical Data Model

`docs/references/canonical-data-model.md` was still marked as pre-implementation DRAFT even though Layer 2 contracts are implemented and exercised by the runtime.

Resolution: the document is now marked as an implemented canonical model and explicitly records the post-Phase-10 additions:

- durable FindingRecord lifecycle state;
- immutable Evidence lineage via `derived_from_evidence_ref`;
- logical cross-run WorkItem identity for incremental binding;
- separation of Evidence identity from validity and finding lifecycle.

No new Phase 11 ontology is introduced here.

### Final Consistency Review

`docs/references/final-consistency-review.md` described the pre-schema/pre-runtime checkpoint as though it were the current architectural state.

Resolution: it is retained as a historical pre-implementation review and explicitly points readers to the current ADRs, implementation, and phase records for post-freeze semantics.

### Single-Agent Runtime record

`docs/architecture/single-agent-runtime.md` describes an early Phase 1/2 product boundary and lists later capabilities as not yet implemented.

Resolution: it is marked as a historical phase record. The current runtime state is maintained by `project-audit-current-state.md` and the accepted post-Phase-6/10 decisions.

### ADR-11

ADR-11 remains the historical V1 simplification baseline. Its early single-agent and global-stop-only assumptions must not be read as alternative implementations to the later accepted runtime decisions.

Resolution: later accepted phase decisions supersede the affected operational clauses for the current runtime, notably ADR-08 for snapshot-drift semantics and ADR-12 for incremental reuse.

## Current invariant set after closure

The following are treated as the active cross-document invariants:

- TargetSnapshot and Evidence remain immutable.
- AuditPlan is frozen for an execution.
- WorkItem UUIDs are execution identifiers, not cross-run logical identity.
- REUSE requires valid, compatible historical Evidence and creates fresh derived Evidence.
- Ambiguous or missing historical Evidence fails closed to REAUDIT.
- Finding lifecycle is durable and independent from epistemic status.
- Snapshot drift distinguishes global target identity from node dependency drift.
- Publication remains blocked when the run cannot establish the required integrity/coverage conditions.
- Deterministic classification remains upstream of execution.
- OmniRoute remains responsible for model/provider routing, not audit applicability or global audit decisions.

## Phase 11 boundary

This closure deliberately does not implement Change Impact or Reaudit Necessity.

Those semantics require a dedicated architectural decision before code changes. The next step is a separate ADR defining:

- change-impact identity and classification;
- propagation from changed inputs to dependencies, Evidence, Findings, and WorkItems;
- deterministic REUSE / REVALIDATE / REAUDIT consequences;
- interaction with ClassificationResult;
- provenance and explainability requirements;
- Snapshot Drift boundaries;
- acceptance criteria and measurable incremental-run outcomes.

## Non-goals

- No new classifier implementation.
- No schema extension for Phase 11.
- No LLM/SLM integration.
- No new routing layer.
- No modification of runtime behavior.

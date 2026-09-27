# ADR 14: Classification Lineage and Reclassification

**Status:** Accepted — implemented by Phase 12

## Context

Phase 11 established deterministic Change Impact between immutable TargetSnapshots, but the runtime still had no historical record of the `ClassificationResult` set that participated in a prior planning decision.

Without that history, a later run could not prove that a deterministic task or applicability classification remained unchanged when source fingerprints were unchanged.

The gap is:

```text
TargetSnapshot A
    ↓
ClassificationResult A
    ↓
AuditPlan / WorkItem A
    ↓
TargetSnapshot B
    ↓
ClassificationResult B
    ↓
reclassification decision
```

The implementation must preserve the existing canonical Layer 2 schemas and must not make ClassificationResult a new canonical persisted entity solely for incremental reuse.

## Decision

### 1. Classification lineage is an immutable auxiliary planning artifact

Each prepared audit produces a deterministic classification lineage keyed by the `TargetSnapshot` fingerprint.

The lineage contains the complete deterministic `ClassificationResult` set and a canonical lineage fingerprint.

It is stored in the local audit state namespace as an auxiliary artifact, outside the canonical Layer 2 JSON entities.

The lineage is immutable: an existing snapshot reference may be written again only when the serialized classification set is byte-for-byte equivalent in canonical form. A conflicting rewrite fails closed.

### 2. Classification results have deterministic identity

A result key is:

```text
(classifier_id, input_refs)
```

The complete normalized result payload is hashed to detect:

- `ADDED`;
- `MODIFIED`;
- `DELETED`.

Changes in classifier version, result, confidence, rationale, provenance, or input references therefore become observable as a changed result when they alter the canonical payload.

### 3. Only demonstrably dependent WorkItems are reconsidered

Phase 12 does not treat every project-profile or global classification change as affecting every WorkItem.

For the current runtime, the direct deterministic dependencies are:

- `task-classifier` → the exact `(auditor, target_surface)` task;
- `applicability:<category>:<subcategory>` → the matching `target_surface`.

Global classification results remain planning context until a concrete dependency is established.

This prevents classification churn from broadening audit scope merely by association.

### 4. Material relevant classification changes fail closed

When a relevant historical classification changes, the affected WorkItem is forced through the existing `REAUDIT` path.

No new WorkItem action is introduced and the Phase 11 precedence remains authoritative for ordinary Evidence impact:

```text
INVALIDATE > REAUDIT > REVALIDATE > REUSE
```

The deterministic classification change is an additional upstream reason to reconsider the affected WorkItem, not a replacement for Evidence dependency evaluation.

### 5. Missing historical lineage fails closed

When a previous run predates Phase 12 and no classification lineage can be found for its snapshot, every regenerated WorkItem is treated as affected and the incremental action is `REAUDIT`.

This is intentionally conservative and gives the system a deterministic migration boundary.

## Schema impact

No canonical Layer 2 JSON schema is changed by this ADR.

The auxiliary lineage artifact is stored separately from:

- TargetSnapshot;
- AuditPlan;
- AuditWorkItem;
- Evidence;
- AuditRun;
- FindingRecord.

## Acceptance criteria

1. The same classification input produces the same lineage fingerprint.
2. Reordering ClassificationResults does not change the lineage fingerprint.
3. A result version/result/rationale/input change is detected deterministically.
4. Relevant `task-classifier` changes affect only the matching WorkItem.
5. Relevant applicability changes affect only the matching WorkItem.
6. Unrelated global classification changes do not broaden WorkItem scope.
7. Missing historical lineage fails closed to REAUDIT.
8. Conflicting writes for one snapshot do not overwrite immutable history.
9. Classification reconsideration never mutates historical ClassificationResult data.
10. Runtime planning records the classification-change reason using the existing `AuditWorkItem.decision_basis`.

## Non-goals

- no LLM or SLM classification;
- no new WorkItem action;
- no new canonical Layer 2 entity;
- no audit-normalize changes;
- no OmniRoute routing changes;
- no replacement of ADR-12 reuse;
- no automatic FIXED inference.

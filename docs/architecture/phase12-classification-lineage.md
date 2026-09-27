# Phase 12 — Classification Lineage & Reclassification

## Status

Implemented.

## Objective

Close the remaining Phase 11 boundary around historical `ClassificationResult` state so incremental planning can detect material deterministic classification changes without broadening scope by association.

## Runtime model

```text
previous TargetSnapshot
      ↓
previous ClassificationLineage
      ↓
deterministic comparison
      ↓
affected logical WorkItems
      ↓
existing incremental action matrix
```

## Persisted boundary

Classification lineage is an auxiliary immutable planning artifact under the local audit state namespace. It is indexed by TargetSnapshot fingerprint and is not part of the canonical Layer 2 JSON schemas.

A conflicting rewrite for an existing snapshot fingerprint fails closed.

## Result identity

```text
(classifier_id, input_refs)
```

The complete canonical result payload is hashed to detect `ADDED`, `MODIFIED`, and `DELETED` classification results.

## Dependency boundary

Current direct dependencies are intentionally narrow:

- `task-classifier` affects the exact WorkItem target surface;
- `applicability:<category>:<subcategory>` affects the matching WorkItem;
- global project-profile/stack/technology/file classification does not broaden scope until a concrete dependency is established.

## Reclassification behavior

A material relevant classification change forces the affected WorkItem to `REAUDIT`.

When historical lineage is missing, all regenerated WorkItems fail closed to `REAUDIT`.

No new WorkItem action is introduced.

## Acceptance

The Phase 12 suite covers deterministic fingerprints, order invariance, material result/version changes, relevant task/applicability impact, unrelated classification changes, missing lineage, and immutable-store behavior.

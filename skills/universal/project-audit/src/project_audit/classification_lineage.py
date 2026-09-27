"""Immutable deterministic ClassificationResult lineage for incremental audits.

Phase 12 persists classification observations as an auxiliary planning artifact
keyed by TargetSnapshot identity. It is deliberately separate from the
canonical Layer 2 JSON entities and schemas.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Tuple

from .classification import ClassificationResult


@dataclass(frozen=True)
class ClassificationChange:
    """One deterministic change between two classification lineages."""

    kind: str
    classifier_id: str
    input_refs: Tuple[str, ...]
    previous_digest: Optional[str]
    current_digest: Optional[str]

    @property
    def key(self) -> Tuple[str, Tuple[str, ...]]:
        return self.classifier_id, self.input_refs


@dataclass(frozen=True)
class ClassificationLineage:
    """Immutable classification set associated with one TargetSnapshot."""

    snapshot_ref: str
    results: Tuple[ClassificationResult, ...]
    lineage_fingerprint: str

    @classmethod
    def create(
        cls,
        snapshot_ref: str,
        results: Iterable[ClassificationResult],
    ) -> "ClassificationLineage":
        normalized = tuple(sorted(results, key=classification_result_key))
        payload = [result.to_dict() for result in normalized]
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        fingerprint = hashlib.sha256(canonical).hexdigest()
        return cls(snapshot_ref, normalized, fingerprint)

    def to_dict(self) -> dict:
        return {
            "snapshot_ref": self.snapshot_ref,
            "lineage_fingerprint": self.lineage_fingerprint,
            "results": [result.to_dict() for result in self.results],
        }


def classification_result_key(
    result: ClassificationResult,
) -> Tuple[str, Tuple[str, ...]]:
    return result.classifier_id, tuple(result.input_refs)


def classification_result_digest(result: ClassificationResult) -> str:
    canonical = json.dumps(
        result.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_classification_lineage(
    snapshot_ref: str,
    results: Iterable[ClassificationResult],
) -> ClassificationLineage:
    return ClassificationLineage.create(snapshot_ref, results)


def compare_classification_lineage(
    previous: ClassificationLineage,
    current: ClassificationLineage,
) -> Tuple[ClassificationChange, ...]:
    previous_by_key: Mapping[Tuple[str, Tuple[str, ...]], ClassificationResult] = {
        classification_result_key(result): result for result in previous.results
    }
    current_by_key: Mapping[Tuple[str, Tuple[str, ...]], ClassificationResult] = {
        classification_result_key(result): result for result in current.results
    }

    changes = []
    for key in sorted(set(previous_by_key) | set(current_by_key)):
        old = previous_by_key.get(key)
        new = current_by_key.get(key)
        if old is None:
            changes.append(
                ClassificationChange(
                    kind="ADDED",
                    classifier_id=key[0],
                    input_refs=key[1],
                    previous_digest=None,
                    current_digest=classification_result_digest(new),
                )
            )
        elif new is None:
            changes.append(
                ClassificationChange(
                    kind="DELETED",
                    classifier_id=key[0],
                    input_refs=key[1],
                    previous_digest=classification_result_digest(old),
                    current_digest=None,
                )
            )
        else:
            old_digest = classification_result_digest(old)
            new_digest = classification_result_digest(new)
            if old_digest != new_digest:
                changes.append(
                    ClassificationChange(
                        kind="MODIFIED",
                        classifier_id=key[0],
                        input_refs=key[1],
                        previous_digest=old_digest,
                        current_digest=new_digest,
                    )
                )
    return tuple(changes)


@dataclass(frozen=True)
class ReclassificationImpact:
    """Deterministic classification changes and their affected logical tasks."""

    previous_snapshot_ref: str
    current_snapshot_ref: str
    changes: Tuple[ClassificationChange, ...]
    affected_work_item_keys: Tuple[Tuple[str, str], ...]
    history_complete: bool = True

    @property
    def changed(self) -> bool:
        return bool(self.changes)

    def affects(self, work_item) -> bool:
        return (work_item.auditor, work_item.target_surface) in set(
            self.affected_work_item_keys
        )


def classification_change_affects_work_item(
    change: ClassificationChange,
    work_item,
) -> bool:
    target = str(getattr(work_item, "target_surface", "")).strip().lower()
    classifier_id = change.classifier_id.lower()

    if classifier_id == "task-classifier":
        return bool(change.input_refs) and change.input_refs[0].strip().lower() == target

    if classifier_id.startswith("applicability:"):
        parts = classifier_id.split(":", 2)
        if len(parts) == 3:
            expected = f"{parts[1]}/{parts[2]}".lower()
            return target == expected

    return False


def build_reclassification_impact(
    previous: ClassificationLineage,
    current: ClassificationLineage,
    current_work_items: Iterable[object],
) -> ReclassificationImpact:
    changes = compare_classification_lineage(previous, current)
    affected = set()
    current_items = tuple(current_work_items)
    for change in changes:
        for item in current_items:
            if classification_change_affects_work_item(change, item):
                affected.add((item.auditor, item.target_surface))
    return ReclassificationImpact(
        previous_snapshot_ref=previous.snapshot_ref,
        current_snapshot_ref=current.snapshot_ref,
        changes=changes,
        affected_work_item_keys=tuple(sorted(affected)),
        history_complete=True,
    )


def missing_reclassification_impact(
    current_snapshot_ref: str,
    current_work_items: Iterable[object],
) -> ReclassificationImpact:
    """Fail closed when historical classification lineage is unavailable."""
    affected = tuple(
        sorted(
            {
                (item.auditor, item.target_surface)
                for item in current_work_items
            }
        )
    )
    return ReclassificationImpact(
        previous_snapshot_ref="MISSING",
        current_snapshot_ref=current_snapshot_ref,
        changes=(),
        affected_work_item_keys=affected,
        history_complete=False,
    )

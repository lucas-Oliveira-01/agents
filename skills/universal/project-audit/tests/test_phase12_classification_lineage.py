from __future__ import annotations

from dataclasses import replace

import pytest

from project_audit.classification import ClassificationResult
from project_audit.classification_lineage import (
    build_classification_lineage,
    build_reclassification_impact,
    compare_classification_lineage,
    missing_reclassification_impact,
)
from project_audit.incremental import IncrementalDecision, plan_incremental_actions_stable
from project_audit.state_store import StateStore, StateStoreError
from tests.conftest import FIXED_TS, make_evidence


def result(classifier_id, input_refs, value, version="1"):
    return ClassificationResult(
        classifier_id=classifier_id,
        classifier_version=version,
        input_refs=tuple(input_refs),
        result=value,
        confidence="HIGH",
        rationale="deterministic test",
    )


def test_lineage_fingerprint_is_order_invariant(target_snapshot):
    first = result("task-classifier", ("CODE/GENERAL",), "ENGINEERING")
    second = result("applicability:code:general", ("src/app.py",), "APPLICABLE")
    left = build_classification_lineage(target_snapshot.snapshot_fingerprint, [first, second])
    right = build_classification_lineage(target_snapshot.snapshot_fingerprint, [second, first])
    assert left.lineage_fingerprint == right.lineage_fingerprint


def test_material_result_and_version_changes_are_detected(target_snapshot):
    old = build_classification_lineage(
        target_snapshot.snapshot_fingerprint,
        [result("task-classifier", ("CODE/GENERAL",), "ENGINEERING")],
    )
    new = build_classification_lineage(
        target_snapshot.snapshot_fingerprint,
        [result("task-classifier", ("CODE/GENERAL",), "SECURITY", version="2")],
    )
    changes = compare_classification_lineage(old, new)
    assert len(changes) == 1
    assert changes[0].kind == "MODIFIED"


def test_relevant_task_classification_forces_reaudit(target_snapshot, work_item):
    item = replace(work_item, target_surface="CODE/GENERAL")
    previous = build_classification_lineage(
        target_snapshot.snapshot_fingerprint,
        [result("task-classifier", ("CODE/GENERAL",), "ENGINEERING")],
    )
    current = build_classification_lineage(
        target_snapshot.snapshot_fingerprint,
        [result("task-classifier", ("CODE/GENERAL",), "SECURITY")],
    )
    impact = build_reclassification_impact(previous, current, [item])
    assert impact.affects(item)

    evidence = make_evidence(target_snapshot_ref=target_snapshot.snapshot_fingerprint, work_item_ref="previous")
    bindings = plan_incremental_actions_stable(
        [item],
        [replace(item, work_item_id="previous")],
        {"previous": evidence},
        target_snapshot,
        target_snapshot,
        classification_impact=impact,
    )
    assert bindings[0].decision == IncrementalDecision.REAUDIT
    assert "classification_changed" in item.decision_basis


def test_relevant_applicability_change_forces_only_matching_work_item(target_snapshot, work_item):
    matching = replace(work_item, target_surface="SECURITY/AUTH")
    unrelated = replace(work_item, work_item_id="other", target_surface="CODE/GENERAL")
    previous = build_classification_lineage(
        target_snapshot.snapshot_fingerprint,
        [result("applicability:security:auth", ("auth.py",), "APPLICABLE")],
    )
    current = build_classification_lineage(
        target_snapshot.snapshot_fingerprint,
        [result("applicability:security:auth", ("auth.py",), "NOT_DETERMINABLE")],
    )
    impact = build_reclassification_impact(previous, current, [matching, unrelated])
    assert impact.affects(matching)
    assert not impact.affects(unrelated)


def test_unrelated_global_classification_change_does_not_broaden_scope(target_snapshot, work_item):
    item = replace(work_item, target_surface="CODE/GENERAL")
    previous = build_classification_lineage(
        target_snapshot.snapshot_fingerprint,
        [result("project-profile-classifier", (), "LIBRARY")],
    )
    current = build_classification_lineage(
        target_snapshot.snapshot_fingerprint,
        [result("project-profile-classifier", (), "FULLSTACK")],
    )
    impact = build_reclassification_impact(previous, current, [item])
    assert impact.changed
    assert not impact.affects(item)


def test_missing_history_fails_closed_to_all_work_items(target_snapshot, work_item):
    item = replace(work_item, target_surface="CODE/GENERAL")
    impact = missing_reclassification_impact(target_snapshot.snapshot_fingerprint, [item])
    evidence = make_evidence(target_snapshot_ref=target_snapshot.snapshot_fingerprint, work_item_ref="previous")
    bindings = plan_incremental_actions_stable(
        [item],
        [replace(item, work_item_id="previous")],
        {"previous": evidence},
        target_snapshot,
        target_snapshot,
        classification_impact=impact,
    )
    assert bindings[0].decision == IncrementalDecision.REAUDIT
    assert "classification_history_missing" in item.decision_basis


def test_store_does_not_overwrite_conflicting_lineage(target_snapshot, tmp_path):
    store = StateStore(tmp_path / "state")
    first = build_classification_lineage(
        target_snapshot.snapshot_fingerprint,
        [result("task-classifier", ("CODE/GENERAL",), "ENGINEERING")],
    )
    store.save_classification_lineage(first)
    store.save_classification_lineage(first)

    conflicting = build_classification_lineage(
        target_snapshot.snapshot_fingerprint,
        [result("task-classifier", ("CODE/GENERAL",), "SECURITY")],
    )
    with pytest.raises(StateStoreError, match="immutable"):
        store.save_classification_lineage(conflicting)

    loaded = store.load_classification_lineage(target_snapshot.snapshot_fingerprint)
    assert loaded.lineage_fingerprint == first.lineage_fingerprint
    assert loaded.results == first.results


def test_compare_detects_added_and_deleted_results(target_snapshot):
    previous = build_classification_lineage(
        "old",
        [result("task-classifier", ("CODE/GENERAL",), "ENGINEERING")],
    )
    current = build_classification_lineage(
        "new",
        [result("task-classifier", ("SECURITY/AUTH",), "SECURITY")],
    )
    changes = compare_classification_lineage(previous, current)
    assert [change.kind for change in changes] == ["DELETED", "ADDED"]

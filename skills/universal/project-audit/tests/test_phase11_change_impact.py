from __future__ import annotations

import dataclasses

from project_audit.change_impact import ChangeKind, build_change_impact
from project_audit.incremental import (
    IncrementalDecision,
    assess_reaudit_necessity,
    derive_reused_evidence,
    plan_incremental_actions_stable,
)
from project_audit.models import MethodologyState, TargetSnapshot, TrackedInputFingerprint
from tests.conftest import make_evidence


def snapshot_with_inputs(base_snapshot, inputs, *, policy=None):
    project_state = dataclasses.replace(
        base_snapshot.project_state,
        tracked_input_fingerprints=tuple(inputs),
    )
    methodology = MethodologyState(
        audit_contract_version=base_snapshot.methodology_state.audit_contract_version,
        auditor_versions={**dict(base_snapshot.methodology_state.auditor_versions), "fake-auditor": "0.1.0"},
        policy_version=policy or base_snapshot.methodology_state.policy_version,
    )
    return TargetSnapshot.create(base_snapshot.target_mode, project_state, methodology)


def test_change_impact_is_deterministic_and_empty_for_identical_snapshots(target_snapshot):
    impact = build_change_impact(target_snapshot, target_snapshot)
    assert impact.events == ()
    assert impact.changed_paths == ()
    assert dict(impact.rename_map) == {}


def test_modified_source_produces_reaudit(target_snapshot, work_item):
    from project_audit.models import TrackedInputFingerprint

    previous = snapshot_with_inputs(
        target_snapshot,
        [TrackedInputFingerprint("src/app.py", "a" * 64), TrackedInputFingerprint("settings.yml", "b" * 64)],
    )
    current = snapshot_with_inputs(
        target_snapshot,
        [TrackedInputFingerprint("src/app.py", "c" * 64), TrackedInputFingerprint("settings.yml", "b" * 64)],
    )
    evidence = make_evidence(
        target_snapshot_ref=previous.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
    )
    evidence = dataclasses.replace(evidence, source_refs=("src/app.py:10-20",), dependencies=())
    impact = build_change_impact(previous, current)
    necessity = assess_reaudit_necessity(evidence, impact, previous, current, work_item.auditor)
    assert any(event.kind == ChangeKind.MODIFIED for event in impact.events)
    assert necessity.decision == IncrementalDecision.REAUDIT
    assert "source_dependency_impacted" in necessity.reasons
    assert "src/app.py" in necessity.impacted_paths


def test_semantic_dependency_change_produces_revalidate(target_snapshot, work_item):
    from project_audit.models import TrackedInputFingerprint

    previous = snapshot_with_inputs(
        target_snapshot,
        [TrackedInputFingerprint("src/app.py", "a" * 64), TrackedInputFingerprint("settings.yml", "b" * 64)],
    )
    current = snapshot_with_inputs(
        previous,
        [TrackedInputFingerprint("src/app.py", "a" * 64), TrackedInputFingerprint("settings.yml", "c" * 64)],
    )
    evidence = make_evidence(target_snapshot_ref=previous.snapshot_fingerprint, work_item_ref=work_item.work_item_id)
    evidence = dataclasses.replace(evidence, source_refs=("src/app.py:10",), dependencies=("settings.yml",))
    impact = build_change_impact(previous, current)
    necessity = assess_reaudit_necessity(evidence, impact, previous, current, work_item.auditor)
    assert necessity.decision == IncrementalDecision.REVALIDATE
    assert "semantic_dependency_impacted" in necessity.reasons


def test_deleted_dependency_fails_to_invalidate(target_snapshot, work_item):
    from project_audit.models import TrackedInputFingerprint

    previous = snapshot_with_inputs(
        target_snapshot,
        [TrackedInputFingerprint("src/app.py", "a" * 64), TrackedInputFingerprint("settings.yml", "b" * 64)],
    )
    current = snapshot_with_inputs(
        previous,
        [TrackedInputFingerprint("src/app.py", "a" * 64)],
    )
    evidence = make_evidence(target_snapshot_ref=previous.snapshot_fingerprint, work_item_ref=work_item.work_item_id)
    evidence = dataclasses.replace(evidence, source_refs=("src/app.py:10",), dependencies=("settings.yml",))
    impact = build_change_impact(previous, current)
    necessity = assess_reaudit_necessity(evidence, impact, previous, current, work_item.auditor)
    assert necessity.decision == IncrementalDecision.INVALIDATE
    assert any(event.kind == ChangeKind.DELETED for event in impact.events)


def test_unique_rename_preserves_reuse_and_rebases_evidence(target_snapshot, work_item):
    from project_audit.models import TrackedInputFingerprint

    previous = snapshot_with_inputs(
        target_snapshot,
        [TrackedInputFingerprint("src/old.py", "a" * 64)],
    )
    current = snapshot_with_inputs(
        previous,
        [TrackedInputFingerprint("src/new.py", "a" * 64)],
    )
    prior = make_evidence(target_snapshot_ref=previous.snapshot_fingerprint, work_item_ref="old-wi")
    prior = dataclasses.replace(prior, source_refs=("src/old.py:12-18",), dependencies=())
    impact = build_change_impact(previous, current)
    assert impact.rename_map == {"src/old.py": "src/new.py"}
    necessity = assess_reaudit_necessity(prior, impact, previous, current, work_item.auditor)
    assert necessity.decision == IncrementalDecision.REUSE
    assert "deterministic_rename_continuity" in necessity.reasons

    reused = derive_reused_evidence(
        prior, current, work_item, generated_at=prior.provenance.generated_at, path_aliases=impact.rename_map
    )
    assert reused.source_refs == ("src/new.py:12-18",)
    assert reused.derived_from_evidence_ref == prior.evidence_id


def test_ambiguous_same_fingerprint_rename_does_not_authorize_reuse(target_snapshot, work_item):
    from project_audit.models import TrackedInputFingerprint

    previous = snapshot_with_inputs(
        target_snapshot,
        [TrackedInputFingerprint("src/old-a.py", "a" * 64)],
    )
    current = snapshot_with_inputs(
        previous,
        [TrackedInputFingerprint("src/new-a.py", "a" * 64), TrackedInputFingerprint("src/new-b.py", "a" * 64)],
    )
    prior = make_evidence(target_snapshot_ref=previous.snapshot_fingerprint, work_item_ref="old-wi")
    prior = dataclasses.replace(prior, source_refs=("src/old-a.py:1",), dependencies=())
    impact = build_change_impact(previous, current)
    assert dict(impact.rename_map) == {}
    necessity = assess_reaudit_necessity(prior, impact, previous, current, work_item.auditor)
    assert necessity.decision in {IncrementalDecision.INVALIDATE, IncrementalDecision.REAUDIT}


def test_methodology_change_is_explicit_and_reaudits(target_snapshot, work_item):
    from project_audit.models import TrackedInputFingerprint

    previous = snapshot_with_inputs(target_snapshot, [TrackedInputFingerprint("src/app.py", "a" * 64)])
    changed = TargetSnapshot.create(
        previous.target_mode,
        previous.project_state,
        MethodologyState(
            audit_contract_version="2.0.0",
            auditor_versions=dict(previous.methodology_state.auditor_versions),
            policy_version=previous.methodology_state.policy_version,
        ),
    )
    evidence = make_evidence(target_snapshot_ref=previous.snapshot_fingerprint, work_item_ref=work_item.work_item_id)
    evidence = dataclasses.replace(evidence, source_refs=("src/app.py:1",), dependencies=())
    impact = build_change_impact(previous, changed)
    necessity = assess_reaudit_necessity(evidence, impact, previous, changed, work_item.auditor)
    assert impact.methodology_changed is True
    assert necessity.decision == IncrementalDecision.REAUDIT
    assert "methodology_changed" in necessity.reasons


def test_stable_planner_records_change_reason(target_snapshot, work_item):
    from project_audit.models import TrackedInputFingerprint

    previous = snapshot_with_inputs(target_snapshot, [TrackedInputFingerprint("src/app.py", "a" * 64)])
    current = snapshot_with_inputs(previous, [TrackedInputFingerprint("src/app.py", "b" * 64)])
    previous_item = dataclasses.replace(work_item, work_item_id="00000000-0000-0000-0000-000000000010", target_surface="CODE_QUALITY/GENERAL")
    current_item = dataclasses.replace(work_item, work_item_id="00000000-0000-0000-0000-000000000011", target_surface="CODE_QUALITY/GENERAL")
    evidence = make_evidence(target_snapshot_ref=previous.snapshot_fingerprint, work_item_ref=previous_item.work_item_id)
    evidence = dataclasses.replace(evidence, source_refs=("src/app.py:1",), dependencies=())
    bindings = plan_incremental_actions_stable(
        [current_item], [previous_item], {previous_item.work_item_id: evidence}, previous, current
    )
    assert bindings[0].decision == IncrementalDecision.REAUDIT
    assert "src/app.py" in current_item.decision_basis
    assert "source_dependency_impacted" in current_item.decision_basis
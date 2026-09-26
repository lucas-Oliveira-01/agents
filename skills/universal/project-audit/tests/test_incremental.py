from __future__ import annotations

import dataclasses

from project_audit.incremental import (
    DependencyKind,
    IncrementalDecision,
    bind_decision_to_work_item,
    build_dependency_graph,
    decide_incremental_action,
    normalize_input_ref,
    plan_incremental_actions,
)
from project_audit.models import EvidenceValidity, MethodologyState, TargetSnapshot, WorkItemAction
from tests.conftest import make_evidence, make_work_item


def _input(path, fingerprint):
    from project_audit.models import TrackedInputFingerprint
    return TrackedInputFingerprint(path, fingerprint)


def _snapshot(base_snapshot, *, inputs=None, methodology=None):
    project_state = dataclasses.replace(
        base_snapshot.project_state,
        tracked_input_fingerprints=tuple(
            inputs
            if inputs is not None
            else base_snapshot.project_state.tracked_input_fingerprints
        ),
    )
    return TargetSnapshot.create(
        base_snapshot.target_mode,
        project_state,
        methodology
        or MethodologyState(
            audit_contract_version=base_snapshot.methodology_state.audit_contract_version,
            auditor_versions=dict(base_snapshot.methodology_state.auditor_versions),
            policy_version=base_snapshot.methodology_state.policy_version,
        ),
    )


def _base_with_dependencies(base_snapshot, auditor="fake-auditor"):
    methodology = MethodologyState(
        audit_contract_version=base_snapshot.methodology_state.audit_contract_version,
        auditor_versions={auditor: "0.1.0"},
        policy_version=base_snapshot.methodology_state.policy_version,
    )
    return _snapshot(
        base_snapshot,
        inputs=[
            _input("src/auth.py", "a" * 64),
            _input("pyproject.toml", "b" * 64),
        ],
        methodology=methodology,
    )


def _evidence_for(snapshot, work_item):
    return make_evidence(
        target_snapshot_ref=snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
    )


def test_normalize_input_ref_discards_locations():
    assert normalize_input_ref("./src/app.py:10-20") == "src/app.py"
    assert normalize_input_ref("src/app.py#L12") == "src/app.py"


def test_unchanged_dependencies_are_reused(target_snapshot, work_item):
    previous = _base_with_dependencies(target_snapshot)
    evidence = _evidence_for(previous, work_item)
    assert decide_incremental_action(
        evidence, previous, previous, work_item.auditor
    ) == IncrementalDecision.REUSE


def test_source_change_requires_reaudit(target_snapshot, work_item):
    previous = _base_with_dependencies(target_snapshot)
    evidence = _evidence_for(previous, work_item)
    current = _snapshot(
        previous,
        inputs=[
            _input("src/auth.py", "c" * 64),
            _input("pyproject.toml", "b" * 64),
        ],
    )
    assert decide_incremental_action(
        evidence, previous, current, work_item.auditor
    ) == IncrementalDecision.REAUDIT


def test_deleted_source_invalidates_evidence(target_snapshot, work_item):
    previous = _base_with_dependencies(target_snapshot)
    evidence = _evidence_for(previous, work_item)
    current = _snapshot(previous, inputs=[_input("pyproject.toml", "b" * 64)])
    assert decide_incremental_action(
        evidence, previous, current, work_item.auditor
    ) == IncrementalDecision.INVALIDATE


def test_changed_semantic_dependency_requires_revalidate(target_snapshot, work_item):
    previous = _base_with_dependencies(target_snapshot)
    evidence = _evidence_for(previous, work_item)
    current = _snapshot(
        previous,
        inputs=[
            _input("src/auth.py", "a" * 64),
            _input("pyproject.toml", "c" * 64),
        ],
    )
    assert decide_incremental_action(
        evidence, previous, current, work_item.auditor
    ) == IncrementalDecision.REVALIDATE


def test_deleted_semantic_dependency_invalidates(target_snapshot, work_item):
    previous = _base_with_dependencies(target_snapshot)
    evidence = _evidence_for(previous, work_item)
    current = _snapshot(previous, inputs=[_input("src/auth.py", "a" * 64)])
    assert decide_incremental_action(
        evidence, previous, current, work_item.auditor
    ) == IncrementalDecision.INVALIDATE


def test_breaking_contract_change_requires_reaudit(target_snapshot, work_item):
    previous = _base_with_dependencies(target_snapshot)
    evidence = _evidence_for(previous, work_item)
    method = MethodologyState(
        audit_contract_version="2.0.0",
        auditor_versions=dict(previous.methodology_state.auditor_versions),
        policy_version=previous.methodology_state.policy_version,
    )
    current = _snapshot(previous, methodology=method)
    assert decide_incremental_action(
        evidence, previous, current, work_item.auditor
    ) == IncrementalDecision.REAUDIT


def test_auditor_version_change_requires_revalidate(target_snapshot, work_item):
    previous_method = MethodologyState(
        audit_contract_version=target_snapshot.methodology_state.audit_contract_version,
        auditor_versions={work_item.auditor: "0.1.0"},
        policy_version=target_snapshot.methodology_state.policy_version,
    )
    previous = _snapshot(target_snapshot, methodology=previous_method)
    evidence = _evidence_for(previous, work_item)
    current_method = MethodologyState(
        audit_contract_version=previous_method.audit_contract_version,
        auditor_versions={work_item.auditor: "0.2.0"},
        policy_version=previous_method.policy_version,
    )
    current = _snapshot(previous, methodology=current_method)
    assert decide_incremental_action(
        evidence, previous, current, work_item.auditor
    ) == IncrementalDecision.REVALIDATE


def test_indeterminate_validity_fails_safe_to_reaudit(target_snapshot, work_item):
    previous = _base_with_dependencies(target_snapshot)
    evidence = _evidence_for(previous, work_item)
    unknown = dataclasses.replace(evidence, validity=EvidenceValidity.NOT_DETERMINABLE)
    assert decide_incremental_action(
        unknown, previous, previous, work_item.auditor
    ) == IncrementalDecision.REAUDIT


def test_invalid_evidence_has_highest_precedence(target_snapshot, work_item):
    previous = _base_with_dependencies(target_snapshot)
    evidence = _evidence_for(previous, work_item)
    invalid = dataclasses.replace(evidence, validity=EvidenceValidity.INVALID)
    current = _snapshot(previous, inputs=[])
    assert decide_incremental_action(
        invalid, previous, current, work_item.auditor
    ) == IncrementalDecision.INVALIDATE


def test_missing_dependency_context_fails_safe_to_reaudit(target_snapshot, work_item):
    empty = _evidence_for(target_snapshot, work_item)
    assert not empty.source_refs and not empty.dependencies
    assert decide_incremental_action(
        empty, target_snapshot, target_snapshot, work_item.auditor
    ) == IncrementalDecision.REAUDIT


def test_graph_records_hard_and_soft_edges(target_snapshot, work_item):
    previous = _base_with_dependencies(target_snapshot)
    evidence = _evidence_for(previous, work_item)
    graph = build_dependency_graph(evidence, previous, work_item.auditor)
    assert any(node.kind == DependencyKind.SOURCE for node in graph.nodes)
    assert any(node.kind == DependencyKind.SEMANTIC for node in graph.nodes)
    assert any(node.kind == DependencyKind.METHODOLOGY_CONTRACT for node in graph.nodes)


def test_plan_incremental_actions_binds_reuse(audit_plan, target_snapshot, work_item):
    previous = _base_with_dependencies(target_snapshot)
    evidence = _evidence_for(previous, work_item)
    decisions = plan_incremental_actions(
        [work_item],
        {work_item.work_item_id: evidence},
        previous,
        previous,
    )
    assert decisions == (IncrementalDecision.REUSE,)
    assert work_item.action == WorkItemAction.REUSE
    assert "incremental_decision=REUSE" in work_item.decision_basis


def test_invalidate_decision_maps_to_reaudit_execution(work_item):
    bind_decision_to_work_item(work_item, IncrementalDecision.INVALIDATE)
    assert work_item.action == WorkItemAction.REAUDIT
    assert "incremental_decision=INVALIDATE" in work_item.decision_basis

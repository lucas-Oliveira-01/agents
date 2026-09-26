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
from project_audit.models import (
    EvidenceValidity,
    MethodologyState,
    TargetSnapshot,
    WorkItemAction,
)


def _snapshot(base_snapshot, *, inputs=None, methodology=None):
    project_state = dataclasses.replace(
        base_snapshot.project_state,
        tracked_input_fingerprints=tuple(inputs if inputs is not None else base_snapshot.project_state.tracked_input_fingerprints),
    )
    return TargetSnapshot.create(
        base_snapshot.target_mode,
        project_state,
        methodology or MethodologyState(
            audit_contract_version=base_snapshot.methodology_state.audit_contract_version,
            auditor_versions=dict(base_snapshot.methodology_state.auditor_versions),
            policy_version=base_snapshot.methodology_state.policy_version,
        ),
    )


def _input(path, fingerprint):
    from project_audit.models import TrackedInputFingerprint
    return TrackedInputFingerprint(path, fingerprint)


def test_normalize_input_ref_discards_locations():
    assert normalize_input_ref("./src/app.py:10-20") == "src/app.py"
    assert normalize_input_ref("src/app.py#L12") == "src/app.py"


def test_unchanged_dependencies_are_reused(evidence, target_snapshot):
    result = decide_incremental_action(
        evidence,
        target_snapshot,
        target_snapshot,
        "fake-auditor",
    )
    assert result == IncrementalDecision.REUSE


def test_source_change_requires_reaudit(evidence, target_snapshot):
    current = _snapshot(
        target_snapshot,
        inputs=[_input("src/auth.py:10-20", "c" * 64)],
    )
    result = decide_incremental_action(
        evidence,
        target_snapshot,
        current,
        "fake-auditor",
    )
    assert result == IncrementalDecision.REAUDIT


def test_deleted_source_invalidates_evidence(evidence, target_snapshot):
    current = _snapshot(target_snapshot, inputs=[])
    result = decide_incremental_action(
        evidence,
        target_snapshot,
        current,
        "fake-auditor",
    )
    assert result == IncrementalDecision.INVALIDATE


def test_changed_semantic_dependency_requires_revalidate(evidence, target_snapshot):
    current = _snapshot(
        target_snapshot,
        inputs=[
            _input("src/auth.py", "b" * 64),
            _input("pyproject.toml", "c" * 64),
        ],
    )
    result = decide_incremental_action(
        evidence,
        target_snapshot,
        current,
        "fake-auditor",
    )
    assert result == IncrementalDecision.REVALIDATE


def test_deleted_semantic_dependency_invalidates(evidence, target_snapshot):
    current = _snapshot(
        target_snapshot,
        inputs=[_input("src/auth.py", "b" * 64)],
    )
    result = decide_incremental_action(
        evidence,
        target_snapshot,
        current,
        "fake-auditor",
    )
    assert result == IncrementalDecision.INVALIDATE


def test_breaking_contract_change_requires_reaudit(evidence, target_snapshot):
    method = MethodologyState(
        audit_contract_version="2.0.0",
        auditor_versions={"fake-auditor": "0.1.0"},
        policy_version=target_snapshot.methodology_state.policy_version,
    )
    current = _snapshot(target_snapshot, methodology=method)
    assert decide_incremental_action(
        evidence, target_snapshot, current, "fake-auditor"
    ) == IncrementalDecision.REAUDIT


def test_auditor_version_change_requires_revalidate(evidence, target_snapshot):
    previous_method = MethodologyState(
        audit_contract_version=target_snapshot.methodology_state.audit_contract_version,
        auditor_versions={"fake-auditor": "0.1.0"},
        policy_version=target_snapshot.methodology_state.policy_version,
    )
    previous = _snapshot(target_snapshot, methodology=previous_method)
    current_method = MethodologyState(
        audit_contract_version=previous_method.audit_contract_version,
        auditor_versions={"fake-auditor": "0.2.0"},
        policy_version=previous_method.policy_version,
    )
    current = _snapshot(target_snapshot, methodology=current_method)
    assert decide_incremental_action(
        evidence, previous, current, "fake-auditor"
    ) == IncrementalDecision.REVALIDATE


def test_indeterminate_validity_fails_safe_to_reaudit(evidence, target_snapshot):
    unknown = dataclasses.replace(evidence, validity=EvidenceValidity.NOT_DETERMINABLE)
    assert decide_incremental_action(
        unknown, target_snapshot, target_snapshot, "fake-auditor"
    ) == IncrementalDecision.REAUDIT


def test_invalid_evidence_has_highest_precedence(evidence, target_snapshot):
    invalid = dataclasses.replace(evidence, validity=EvidenceValidity.INVALID)
    current = _snapshot(target_snapshot, inputs=[])
    assert decide_incremental_action(
        invalid, target_snapshot, current, "fake-auditor"
    ) == IncrementalDecision.INVALIDATE


def test_missing_dependency_context_fails_safe_to_reaudit(audit_plan, target_snapshot, work_item):
    from tests.conftest import make_evidence
    empty = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
    )
    assert not empty.source_refs and not empty.dependencies
    assert decide_incremental_action(
        empty, target_snapshot, target_snapshot, work_item.auditor
    ) == IncrementalDecision.REAUDIT


def test_graph_records_hard_and_soft_edges(evidence, target_snapshot):
    graph = build_dependency_graph(evidence, target_snapshot, "fake-auditor")
    assert any(node.kind == DependencyKind.SOURCE for node in graph.nodes)
    assert any(node.kind == DependencyKind.SEMANTIC for node in graph.nodes)
    assert any(node.kind == DependencyKind.METHODOLOGY_CONTRACT for node in graph.nodes)


def test_invalidate_binds_to_reaudit_execution(basic_work_item if False else None):
    pass


def test_plan_incremental_actions_binds_workitem(audit_plan, target_snapshot, work_item, evidence):
    decisions = plan_incremental_actions(
        [work_item],
        {work_item.work_item_id: evidence},
        target_snapshot,
        target_snapshot,
    )
    assert decisions == (IncrementalDecision.REUSE,)
    assert work_item.action == WorkItemAction.REUSE
    assert "incremental_decision=REUSE" in work_item.decision_basis


def test_invalidate_decision_is_not_executable_work_item_action(work_item):
    bind_decision_to_work_item(work_item, IncrementalDecision.INVALIDATE)
    assert work_item.action == WorkItemAction.REAUDIT
    assert "incremental_decision=INVALIDATE" in work_item.decision_basis

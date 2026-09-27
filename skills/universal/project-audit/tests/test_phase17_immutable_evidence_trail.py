from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from project_audit.models import (
    AuditPlan,
    Evidence,
    EvidenceValidity,
    ExecutionPolicy,
    ExecutionReceipt,
    FilesystemAccess,
    NetworkAccess,
    ProjectState,
    Provenance,
    SubmoduleState,
    TargetMode,
    TrackedInputFingerprint,
)
from project_audit.orchestrator import Orchestrator, OrchestratorError
from project_audit.planner import build_target_snapshot
from project_audit.discovery import discover
from project_audit.state_store import StateStore
from tests.conftest import FIXED_TS, make_evidence, make_project_state, make_work_item


@pytest.fixture
def orchestrator(state_store) -> Orchestrator:
    return Orchestrator(state_store)


def _receipt(work_item_id: str, policy: ExecutionPolicy) -> ExecutionReceipt:
    return ExecutionReceipt(
        receipt_id=str(uuid4()),
        work_item_ref=work_item_id,
        command="pytest",
        arguments=["-q", "tests"],
        policy_snapshot=policy,
        started_at=FIXED_TS,
        finished_at=FIXED_TS + timedelta(seconds=1),
        exit_code=0,
        artifact_refs=["artifacts/result.json"],
        environment_summary="test",
    )


def test_project_state_normalizes_nested_collections() -> None:
    submodules = [SubmoduleState(path="vendor/lib", revision="a" * 40)]
    tracked = [
        TrackedInputFingerprint(path="pyproject.toml", fingerprint="b" * 64)
    ]
    state = ProjectState(
        repository_identity="repo",
        revision_identity="rev",
        working_tree_state=make_project_state().working_tree_state,
        submodules_state=submodules,
        tracked_input_fingerprints=tracked,
    )

    assert isinstance(state.submodules_state, tuple)
    assert isinstance(state.tracked_input_fingerprints, tuple)

    submodules.append(SubmoduleState(path="other", revision="c" * 40))
    tracked.append(TrackedInputFingerprint(path="policy.yml", fingerprint="d" * 64))

    assert len(state.submodules_state) == 1
    assert len(state.tracked_input_fingerprints) == 1

    with pytest.raises(AttributeError):
        state.submodules_state.append(submodules[0])


def test_evidence_normalizes_nested_collections_and_is_deeply_immutable(
    target_snapshot, work_item
) -> None:
    source_refs = ["src/app.py:10"]
    dependencies = ["pyproject.toml"]
    evidence = Evidence(
        evidence_id=str(uuid4()),
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
        source_refs=source_refs,
        dependencies=dependencies,
        validity=EvidenceValidity.VALID,
        provenance=Provenance(actor="test", generated_at=FIXED_TS),
        fingerprint="e" * 64,
    )

    source_refs.append("src/other.py:20")
    dependencies.append("README.md")

    assert evidence.source_refs == ("src/app.py:10",)
    assert evidence.dependencies == ("pyproject.toml",)

    with pytest.raises(AttributeError):
        evidence.source_refs.append("hacked")

    with pytest.raises(AttributeError):
        evidence.dependencies.append("hacked")


def test_execution_receipt_normalizes_nested_collections_and_round_trip(
    orchestrator, audit_plan, target_snapshot, work_item, execution_policy
) -> None:
    orchestrator.commit_snapshot(target_snapshot)
    audit_plan.work_items = [work_item]
    orchestrator.freeze_and_commit_plan(audit_plan)
    orchestrator.commit_work_item(work_item)

    receipt = _receipt(work_item.work_item_id, execution_policy)
    orchestrator.commit_receipt(receipt)

    assert isinstance(receipt.arguments, tuple)
    assert isinstance(receipt.artifact_refs, tuple)

    loaded = orchestrator.store.load_receipt(receipt.receipt_id)
    assert isinstance(loaded.arguments, tuple)
    assert isinstance(loaded.artifact_refs, tuple)

    with pytest.raises(AttributeError):
        loaded.arguments.append("--hacked")


def test_commit_receipt_rejects_dangling_work_item(
    orchestrator, execution_policy
) -> None:
    receipt = _receipt(str(uuid4()), execution_policy)

    with pytest.raises(
        OrchestratorError, match="does not resolve to a persisted AuditWorkItem"
    ):
        orchestrator.commit_receipt(receipt)

    with pytest.raises(Exception):
        orchestrator.store.load_receipt(receipt.receipt_id)


def test_commit_evidence_rejects_nonpersisted_work_item(
    orchestrator, audit_plan, target_snapshot, execution_policy, egress_policy
) -> None:
    orchestrator.commit_snapshot(target_snapshot)
    work_item = make_work_item(
        plan_id=audit_plan.plan_id,
        execution_policy=execution_policy,
        egress_policy=egress_policy,
    )
    audit_plan.work_items = [work_item]
    orchestrator.freeze_and_commit_plan(audit_plan)

    evidence = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
    )

    with pytest.raises(
        OrchestratorError, match="does not resolve to a persisted AuditWorkItem"
    ):
        orchestrator.commit_evidence(evidence, work_item)

    with pytest.raises(Exception):
        orchestrator.store.load_evidence(evidence.evidence_id)


def test_commit_evidence_uses_persisted_work_item_reference(
    orchestrator, audit_plan, target_snapshot, work_item
) -> None:
    orchestrator.commit_snapshot(target_snapshot)
    audit_plan.work_items = [work_item]
    orchestrator.freeze_and_commit_plan(audit_plan)
    orchestrator.commit_work_item(work_item)

    evidence = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
    )

    transient = make_work_item(
        plan_id=str(uuid4()),
        execution_policy=work_item.effective_execution_policy,
        egress_policy=work_item.data_egress_policy,
    )
    transient.work_item_id = work_item.work_item_id

    with pytest.raises(OrchestratorError, match="resolves to plan"):
        orchestrator.commit_evidence(evidence, transient)


def test_commit_evidence_positive_path_remains_valid(
    orchestrator, audit_plan, target_snapshot, work_item
) -> None:
    orchestrator.commit_snapshot(target_snapshot)
    audit_plan.work_items = [work_item]
    orchestrator.freeze_and_commit_plan(audit_plan)
    orchestrator.commit_work_item(work_item)

    evidence = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
    )
    orchestrator.commit_evidence(evidence, work_item)

    loaded = orchestrator.store.load_evidence(evidence.evidence_id)
    assert loaded.evidence_id == evidence.evidence_id
    assert loaded.source_refs == evidence.source_refs
    assert loaded.dependencies == evidence.dependencies

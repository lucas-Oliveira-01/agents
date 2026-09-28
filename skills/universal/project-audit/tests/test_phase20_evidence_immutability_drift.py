from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest

from project_audit.models import ExecutionReceipt, EvidenceValidity, TargetMode
from project_audit.runtime import run_full_audit
from project_audit.state_store import StateStore, StateStoreError
from tests.conftest import FIXED_TS


def test_state_store_rejects_conflicting_evidence_rewrite(state_store, evidence) -> None:
    state_store.save_evidence(evidence)
    state_store.save_evidence(evidence)

    conflicting = replace(evidence, validity=EvidenceValidity.STALE)
    with pytest.raises(StateStoreError, match="Evidence is immutable"):
        state_store.save_evidence(conflicting)

    assert state_store.load_evidence(evidence.evidence_id).validity == EvidenceValidity.VALID


def test_state_store_rejects_conflicting_snapshot_rewrite(state_store, target_snapshot) -> None:
    state_store.save_snapshot(target_snapshot)
    state_store.save_snapshot(target_snapshot)

    conflicting = replace(target_snapshot, target_mode=TargetMode.WORKTREE)
    with pytest.raises(StateStoreError, match="TargetSnapshot is immutable"):
        state_store.save_snapshot(conflicting)

    loaded = state_store.load_snapshot(target_snapshot.snapshot_fingerprint)
    assert loaded.target_mode == target_snapshot.target_mode


def test_state_store_rejects_conflicting_frozen_plan_rewrite(state_store, audit_plan) -> None:
    audit_plan.freeze(at=FIXED_TS)
    state_store.save_plan(audit_plan)
    state_store.save_plan(audit_plan)

    conflicting = replace(audit_plan, requested_scope=["changed"])
    with pytest.raises(StateStoreError, match="AuditPlan is immutable"):
        state_store.save_plan(conflicting)


def test_state_store_rejects_conflicting_receipt_rewrite(state_store, work_item) -> None:
    receipt = ExecutionReceipt(
        receipt_id=str(uuid4()),
        work_item_ref=work_item.work_item_id,
        command="test",
        arguments=[],
        policy_snapshot=work_item.effective_execution_policy,
        started_at=FIXED_TS,
        finished_at=FIXED_TS + timedelta(seconds=1),
        exit_code=0,
        artifact_refs=[],
    )
    state_store.save_receipt(receipt)
    state_store.save_receipt(receipt)

    conflicting = replace(receipt, exit_code=1)
    with pytest.raises(StateStoreError, match="ExecutionReceipt is immutable"):
        state_store.save_receipt(conflicting)


def test_snapshot_drift_adds_stale_lineage_without_rewriting_original(tmp_path, monkeypatch) -> None:
    source = tmp_path / "app.py"
    source.write_text("print('before')\n")

    from project_audit.engineering_auditor import EngineeringAuditor

    original = EngineeringAuditor.inspect
    calls = []

    def mutate_after_inspect(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(True)
        source.write_text("print('after')\n")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(EngineeringAuditor, "inspect", mutate_after_inspect)
        run_full_audit(str(tmp_path))

    assert calls
    store = StateStore(tmp_path / ".audit" / "runs")
    stale = [
        store.load_evidence(evidence_id)
        for evidence_id in store.list_evidence_ids()
        if store.load_evidence(evidence_id).validity == EvidenceValidity.STALE
    ]
    assert stale

    for stale_evidence in stale:
        assert stale_evidence.derived_from_evidence_ref is not None
        assert stale_evidence.evidence_id != stale_evidence.derived_from_evidence_ref
        original_evidence = store.load_evidence(stale_evidence.derived_from_evidence_ref)
        assert original_evidence.validity == EvidenceValidity.VALID
        assert original_evidence.target_snapshot_ref == stale_evidence.target_snapshot_ref


def test_security_snapshot_drift_path_has_target_snapshot_builder(tmp_path):
    """Security drift handling must resolve the snapshot helper at runtime."""
    from project_audit.security_runner import build_target_snapshot
    from project_audit.discovery import discover

    assert build_target_snapshot(discover(tmp_path)).snapshot_fingerprint

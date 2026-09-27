from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from project_audit.fake_auditor import FakeAuditorWithSnapshot
from project_audit.models import (
    Evidence,
    EvidenceValidity,
    ExecutionReceipt,
    IllegalAttemptOrderError,
    Provenance,
    WorkItemFailureState,
)
from project_audit.orchestrator import Orchestrator
from project_audit.state_store import StateStore
from tests.conftest import FIXED_TS


def test_attempt_finish_rejects_timestamp_before_start(work_item) -> None:
    attempt = work_item.start_attempt(started_at=FIXED_TS)

    with pytest.raises(IllegalAttemptOrderError):
        attempt.finish(
            finished_at=FIXED_TS - timedelta(seconds=1),
            exit_code=0,
        )

    assert attempt.finished_at is None
    assert work_item.execution_state.value == "RUNNING"


def test_attempt_fail_rejects_timestamp_before_start(work_item) -> None:
    attempt = work_item.start_attempt(started_at=FIXED_TS)

    with pytest.raises(IllegalAttemptOrderError):
        attempt.fail(
            finished_at=FIXED_TS - timedelta(seconds=1),
            reason="INFRA_ERROR",
        )

    assert attempt.finished_at is None
    assert attempt.failure_reason is None


def test_semantic_gate_rejects_injected_attempt_timeline(
    orchestrator, audit_plan, target_snapshot, work_item
) -> None:
    orchestrator.commit_snapshot(target_snapshot)
    audit_plan.work_items = [work_item]
    orchestrator.freeze_and_commit_plan(audit_plan)
    orchestrator.commit_work_item(work_item)

    attempt = work_item.start_attempt(started_at=FIXED_TS)
    # Deliberately bypass the model mutator to test persistence-time defense.
    attempt.finished_at = FIXED_TS - timedelta(seconds=1)

    with pytest.raises(
        Exception,
        match="ATTEMPT_FINISH_BEFORE_START",
    ):
        orchestrator.commit_work_item(work_item)


class FutureReceiptAuditor(FakeAuditorWithSnapshot):
    def execute(self, work_item, started_at=None):
        started = started_at or FIXED_TS
        finished = started + timedelta(seconds=5)
        receipt = ExecutionReceipt(
            receipt_id=str(uuid4()),
            work_item_ref=work_item.work_item_id,
            command="future-receipt",
            arguments=["--target", work_item.target_surface],
            policy_snapshot=work_item.effective_execution_policy,
            started_at=started,
            finished_at=finished,
            exit_code=0,
            artifact_refs=[],
        )
        evidence = Evidence(
            evidence_id=str(uuid4()),
            target_snapshot_ref=self._fingerprint,
            work_item_ref=work_item.work_item_id,
            source_refs=(f"{work_item.target_surface}:1-1",),
            dependencies=(),
            validity=EvidenceValidity.VALID,
            provenance=Provenance(actor="future-receipt", generated_at=finished),
            fingerprint="f" * 64,
        )
        return receipt, evidence


def test_vertical_slice_attempt_finish_matches_receipt_finish(
    tmp_path, target_snapshot, audit_plan, work_item
) -> None:
    orchestrator = Orchestrator(StateStore(tmp_path / ".audit" / "runs"))

    run = orchestrator.execute_vertical_slice(
        snapshot=target_snapshot,
        plan=audit_plan,
        work_items=[work_item],
        auditor=FutureReceiptAuditor(target_snapshot.snapshot_fingerprint),
    )

    persisted = orchestrator.store.load_work_item(work_item.work_item_id)
    receipt = orchestrator.store.load_receipt(persisted.attempts[0].receipt_ref)

    assert persisted.attempts[0].finished_at == receipt.finished_at
    assert run.execution_completeness.value == "COMPLETE"

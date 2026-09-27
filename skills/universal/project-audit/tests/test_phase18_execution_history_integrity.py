from __future__ import annotations

import copy
from datetime import timedelta
from uuid import uuid4

import pytest

from project_audit.models import (
    AuditWorkItem,
    ExecutionReceipt,
    ExecutionState,
    IllegalAttemptOrderError,
    WorkItemFailureState,
)
from project_audit.orchestrator import Orchestrator, OrchestratorError
from tests.conftest import FIXED_TS, make_work_item


@pytest.fixture
def orchestrator(state_store) -> Orchestrator:
    return Orchestrator(state_store)


def _commit_plan_and_item(
    orchestrator,
    audit_plan,
    target_snapshot,
    work_item,
):
    orchestrator.commit_snapshot(target_snapshot)
    audit_plan.work_items = [work_item]
    orchestrator.freeze_and_commit_plan(audit_plan)
    orchestrator.commit_work_item(work_item)


def _receipt(work_item: AuditWorkItem, execution_policy) -> ExecutionReceipt:
    return ExecutionReceipt(
        receipt_id=str(uuid4()),
        work_item_ref=work_item.work_item_id,
        command="test-runner",
        arguments=["--target", work_item.target_surface],
        policy_snapshot=execution_policy,
        started_at=FIXED_TS,
        finished_at=FIXED_TS + timedelta(seconds=1),
        exit_code=0,
        artifact_refs=[],
    )


def test_retry_temporal_rejection_is_atomic(work_item: AuditWorkItem) -> None:
    first = work_item.start_attempt(started_at=FIXED_TS)
    finished = FIXED_TS + timedelta(seconds=10)
    first.fail(finished_at=finished, reason="INFRA_ERROR")
    work_item.terminate(WorkItemFailureState.INFRA_ERROR)

    before = copy.deepcopy(work_item)

    with pytest.raises(IllegalAttemptOrderError):
        work_item.retry_attempt(started_at=FIXED_TS + timedelta(seconds=5))

    assert work_item.execution_state == before.execution_state
    assert work_item.failure_state == before.failure_state
    assert len(work_item.attempts) == len(before.attempts) == 1
    assert work_item.attempts[0].finished_at == before.attempts[0].finished_at
    assert work_item.attempts[0].failure_reason == before.attempts[0].failure_reason


def test_retry_valid_timestamp_still_creates_new_attempt(work_item: AuditWorkItem) -> None:
    first = work_item.start_attempt(started_at=FIXED_TS)
    first.fail(
        finished_at=FIXED_TS + timedelta(seconds=10),
        reason="INFRA_ERROR",
    )
    work_item.terminate(WorkItemFailureState.INFRA_ERROR)

    second = work_item.retry_attempt(started_at=FIXED_TS + timedelta(seconds=10))

    assert work_item.execution_state == ExecutionState.RUNNING
    assert work_item.failure_state == WorkItemFailureState.NONE
    assert len(work_item.attempts) == 2
    assert second.started_at == FIXED_TS + timedelta(seconds=10)


def test_commit_work_item_rejects_dangling_attempt_receipt(
    orchestrator, audit_plan, target_snapshot, execution_policy, work_item
) -> None:
    _commit_plan_and_item(orchestrator, audit_plan, target_snapshot, work_item)

    attempt = work_item.start_attempt(started_at=FIXED_TS)
    attempt.finish(
        finished_at=FIXED_TS + timedelta(seconds=1),
        exit_code=0,
        receipt_ref=str(uuid4()),
    )

    with pytest.raises(
        OrchestratorError, match="does not resolve to a persisted ExecutionReceipt"
    ):
        orchestrator.commit_work_item(work_item)

    persisted = orchestrator.store.load_work_item(work_item.work_item_id)
    assert persisted.attempts == []


def test_commit_work_item_rejects_receipt_belonging_to_another_item(
    orchestrator, audit_plan, target_snapshot, execution_policy, egress_policy
) -> None:
    first = make_work_item(
        plan_id=audit_plan.plan_id,
        target_surface="security/first",
        execution_policy=execution_policy,
        egress_policy=egress_policy,
    )
    second = make_work_item(
        plan_id=audit_plan.plan_id,
        target_surface="security/second",
        execution_policy=execution_policy,
        egress_policy=egress_policy,
    )
    audit_plan.work_items = [first, second]
    orchestrator.commit_snapshot(target_snapshot)
    orchestrator.freeze_and_commit_plan(audit_plan)
    orchestrator.commit_work_item(first)
    orchestrator.commit_work_item(second)

    receipt = _receipt(second, execution_policy)
    orchestrator.commit_receipt(receipt)

    attempt = first.start_attempt(started_at=FIXED_TS)
    attempt.finish(
        finished_at=FIXED_TS + timedelta(seconds=1),
        exit_code=0,
        receipt_ref=receipt.receipt_id,
    )

    with pytest.raises(OrchestratorError, match="belongs to WorkItem"):
        orchestrator.commit_work_item(first)

    persisted = orchestrator.store.load_work_item(first.work_item_id)
    assert persisted.attempts == []


def test_commit_work_item_accepts_persisted_attempt_receipt(
    orchestrator, audit_plan, target_snapshot, execution_policy, work_item
) -> None:
    _commit_plan_and_item(orchestrator, audit_plan, target_snapshot, work_item)

    started = FIXED_TS
    attempt = work_item.start_attempt(started_at=started)
    orchestrator.commit_work_item(work_item)

    receipt = _receipt(work_item, execution_policy)
    orchestrator.commit_receipt(receipt)

    attempt.finish(
        finished_at=FIXED_TS + timedelta(seconds=1),
        exit_code=0,
        receipt_ref=receipt.receipt_id,
    )
    work_item.terminate(WorkItemFailureState.NONE)
    orchestrator.commit_work_item(work_item)

    loaded = orchestrator.store.load_work_item(work_item.work_item_id)
    assert loaded.attempts[0].receipt_ref == receipt.receipt_id
    assert orchestrator.store.load_receipt(receipt.receipt_id).work_item_ref == work_item.work_item_id

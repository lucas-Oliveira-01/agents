from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from project_audit.models import (
    AuditRun,
    ExecutionReceipt,
    ExecutionState,
    EvidenceValidity,
    RunBudgetState,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    RunPublicationState,
    WorkItemAction,
    WorkItemFailureState,
)
from project_audit.orchestrator import Orchestrator
from tests.conftest import FIXED_TS, make_evidence, make_work_item


def _commit_recovery_fixture(
    orchestrator,
    audit_plan,
    target_snapshot,
    execution_policy,
    egress_policy,
    *,
    completed: bool,
):
    item = make_work_item(
        plan_id=audit_plan.plan_id,
        target_surface="CODE/src",
        execution_policy=execution_policy,
        egress_policy=egress_policy,
    )
    audit_plan.work_items = [item]
    orchestrator.commit_snapshot(target_snapshot)
    orchestrator.freeze_and_commit_plan(audit_plan)
    orchestrator.commit_work_item(item)

    receipt_id = None
    if completed:
        receipt = ExecutionReceipt(
            receipt_id=str(uuid4()),
            work_item_ref=item.work_item_id,
            command="test-runner",
            arguments=["--recovery"],
            policy_snapshot=execution_policy,
            started_at=FIXED_TS,
            finished_at=FIXED_TS + timedelta(seconds=1),
            exit_code=0,
            artifact_refs=[],
        )
        receipt_id = receipt.receipt_id
        orchestrator.commit_receipt(receipt)
        attempt = item.start_attempt(started_at=FIXED_TS)
        attempt.finish(
            finished_at=FIXED_TS + timedelta(seconds=1),
            exit_code=0,
            receipt_ref=receipt.receipt_id,
        )
        evidence = make_evidence(
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            work_item_ref=item.work_item_id,
        )
        orchestrator.commit_evidence(evidence, item)
        item.terminate(WorkItemFailureState.NONE)
        orchestrator.commit_work_item(item)

    run = AuditRun(
        run_id=str(uuid4()),
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        plan_ref=audit_plan.plan_id,
        work_item_refs=[item.work_item_id],
        execution_completeness=RunExecutionCompleteness.PARTIAL,
        coverage_completeness=RunCoverageCompleteness.PENDING,
        failure_state=RunFailureState.NONE,
        budget_state=RunBudgetState.HEALTHY,
        publication_state=RunPublicationState.NOT_PUBLISHED,
    )
    orchestrator.commit_run(
        run,
        audit_plan,
        [item],
        known_run_ids=orchestrator.store.list_run_ids(),
    )
    return run, item, receipt_id


def test_recovery_rebinds_completed_evidence_without_copying_receipts(
    state_store, audit_plan, target_snapshot, execution_policy, egress_policy
) -> None:
    orchestrator = Orchestrator(state_store)
    run, original_item, original_receipt_id = _commit_recovery_fixture(
        orchestrator,
        audit_plan,
        target_snapshot,
        execution_policy,
        egress_policy,
        completed=True,
    )

    bundle = orchestrator.prepare_recovery(run.run_id)
    recovered = bundle.work_items[0]

    assert recovered.work_item_id != original_item.work_item_id
    assert recovered.execution_state == ExecutionState.TERMINATED
    assert recovered.failure_state == WorkItemFailureState.NONE
    assert recovered.action == WorkItemAction.REUSE
    assert recovered.attempts == []

    recovered_evidence = [
        orchestrator.store.load_evidence(evidence_id)
        for evidence_id in orchestrator.store.list_evidence_ids()
        if orchestrator.store.load_evidence(evidence_id).work_item_ref == recovered.work_item_id
    ]
    assert len(recovered_evidence) == 1
    assert recovered_evidence[0].validity == EvidenceValidity.VALID
    assert recovered_evidence[0].derived_from_evidence_ref is not None

    original_receipt = orchestrator.store.load_receipt(original_receipt_id)
    original_loaded = orchestrator.store.load_work_item(original_item.work_item_id)
    assert original_receipt.work_item_ref == original_item.work_item_id
    assert original_loaded.attempts[0].receipt_ref == original_receipt_id


def test_recovery_replays_completed_item_when_evidence_is_unavailable(
    state_store, audit_plan, target_snapshot, execution_policy, egress_policy
) -> None:
    orchestrator = Orchestrator(state_store)
    run, original_item, _ = _commit_recovery_fixture(
        orchestrator,
        audit_plan,
        target_snapshot,
        execution_policy,
        egress_policy,
        completed=False,
    )

    original_item.execution_state = ExecutionState.TERMINATED
    original_item.failure_state = WorkItemFailureState.NONE
    orchestrator.commit_work_item(original_item)

    bundle = orchestrator.prepare_recovery(run.run_id)
    recovered = bundle.work_items[0]

    assert recovered.execution_state == ExecutionState.PLANNED
    assert recovered.attempts == []
    assert recovered.action == WorkItemAction.REAUDIT


def test_recovery_completed_item_has_closed_graph(
    state_store, audit_plan, target_snapshot, execution_policy, egress_policy
) -> None:
    orchestrator = Orchestrator(state_store)
    run, _, _ = _commit_recovery_fixture(
        orchestrator,
        audit_plan,
        target_snapshot,
        execution_policy,
        egress_policy,
        completed=True,
    )

    bundle = orchestrator.prepare_recovery(run.run_id)
    loaded_plan = orchestrator.store.load_plan(bundle.plan.plan_id)
    loaded_run = orchestrator.store.load_run(bundle.run.run_id)
    loaded_item = orchestrator.store.load_work_item(bundle.work_items[0].work_item_id)

    assert loaded_plan.is_frozen
    assert loaded_plan.work_items[0].work_item_id == loaded_item.work_item_id
    assert loaded_run.recovery_from_ref == run.run_id
    assert loaded_run.work_item_refs == [loaded_item.work_item_id]
    assert loaded_item.execution_state == ExecutionState.TERMINATED

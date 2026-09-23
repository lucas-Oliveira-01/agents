from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from .context_builder import build_context
from .discovery import DiscoverySnapshot
from .models import (
    AuditRun,
    AuditWorkItem,
    ExecutionState,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    WorkItemFailureState,
)
from .orchestrator import Orchestrator
from .planner import build_target_snapshot
from .semantic_auditor import SemanticAuditor, SemanticReviewResult


def _persist_run_state(
    orchestrator: Orchestrator,
    run: AuditRun,
) -> List[AuditWorkItem]:
    work_items = [
        orchestrator.store.load_work_item(work_item_id)
        for work_item_id in run.work_item_refs
    ]
    plan = orchestrator.store.load_plan(run.plan_ref, work_items=work_items)
    orchestrator.commit_run(
        run,
        plan,
        work_items,
        known_run_ids=orchestrator.store.list_run_ids(),
    )
    return work_items


def execute_semantic_review(
    orchestrator: Orchestrator,
    discovery: DiscoverySnapshot,
    run: AuditRun,
    work_item: AuditWorkItem,
    worker: SemanticAuditor,
) -> SemanticReviewResult:
    """Execute one semantic WorkItem with lifecycle and evidence gates."""
    if work_item.execution_state == ExecutionState.TERMINATED:
        raise ValueError("Cannot semantically review an already terminated WorkItem")

    stored_snapshot = orchestrator.store.load_snapshot(run.target_snapshot_ref)
    current_snapshot = build_target_snapshot(
        discovery,
        target_mode=stored_snapshot.target_mode,
    )
    if current_snapshot.snapshot_fingerprint != stored_snapshot.snapshot_fingerprint:
        raise RuntimeError("Snapshot drift detected before semantic review.")

    orchestrator.commit_work_item(work_item)
    started = datetime.now(timezone.utc)
    attempt = work_item.start_attempt(started_at=started)
    orchestrator.commit_work_item(work_item)

    context = build_context(discovery, work_item.target_surface)
    result = worker.review(work_item, run, context)
    orchestrator.commit_receipt(result.receipt)

    finished = datetime.now(timezone.utc)

    if result.status == "BLOCKED":
        attempt.fail(
            finished_at=finished,
            reason="SAFETY_BLOCK",
            receipt_ref=result.receipt.receipt_id,
        )
        work_item.terminate(failure_state=WorkItemFailureState.SAFETY_BLOCK)
        run.execution_completeness = RunExecutionCompleteness.PARTIAL
        run.coverage_completeness = RunCoverageCompleteness.PARTIAL
        run.failure_state = RunFailureState.SAFETY_BLOCK
        orchestrator.commit_work_item(work_item)
        _persist_run_state(orchestrator, run)
        return result

    if result.status == "FAILED":
        attempt.fail(
            finished_at=finished,
            reason="INFRA_ERROR",
            receipt_ref=result.receipt.receipt_id,
        )
        work_item.terminate(failure_state=WorkItemFailureState.INFRA_ERROR)
        run.execution_completeness = RunExecutionCompleteness.PARTIAL
        run.coverage_completeness = RunCoverageCompleteness.PARTIAL
        run.failure_state = RunFailureState.INFRA_ERROR
        orchestrator.commit_work_item(work_item)
        _persist_run_state(orchestrator, run)
        return result

    if result.status == "INVALID_OUTPUT":
        attempt.fail(
            finished_at=finished,
            reason="SCHEMA_VIOLATION",
            receipt_ref=result.receipt.receipt_id,
        )
        work_item.terminate(failure_state=WorkItemFailureState.SCHEMA_VIOLATION)
        run.execution_completeness = RunExecutionCompleteness.PARTIAL
        run.coverage_completeness = RunCoverageCompleteness.PARTIAL
        run.failure_state = RunFailureState.INFRA_ERROR
        orchestrator.commit_work_item(work_item)
        orchestrator.commit_run(
            run,
            orchestrator.store.load_plan(run.plan_ref, work_items=[work_item]),
            [work_item],
            known_run_ids=orchestrator.store.list_run_ids(),
        )
        return result

    if result.status != "COMPLETED" or result.evidence is None:
        raise ValueError("Semantic auditor returned an unsupported execution state")

    attempt.finish(
        finished_at=finished,
        exit_code=0,
        receipt_ref=result.receipt.receipt_id,
    )
    orchestrator.commit_evidence(result.evidence, work_item)
    work_item.terminate(failure_state=WorkItemFailureState.NONE)
    orchestrator.commit_work_item(work_item)

    current_items = [
        orchestrator.store.load_work_item(work_item_id)
        for work_item_id in run.work_item_refs
    ]
    all_terminal = bool(current_items) and all(
        item.execution_state == ExecutionState.TERMINATED
        for item in current_items
    )
    any_failure = any(
        item.failure_state != WorkItemFailureState.NONE
        for item in current_items
    )
    run.execution_completeness = (
        RunExecutionCompleteness.COMPLETE
        if all_terminal and not any_failure
        else RunExecutionCompleteness.PARTIAL
    )
    run.coverage_completeness = (
        RunCoverageCompleteness.FULL
        if all_terminal and not any_failure
        else RunCoverageCompleteness.PARTIAL
    )
    run.failure_state = RunFailureState.NONE
    _persist_run_state(orchestrator, run)
    return result

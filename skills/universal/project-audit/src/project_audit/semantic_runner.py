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
from .semantic_auditor import SemanticAuditor, SemanticReviewResult


def _persist_run_state(
    orchestrator: Orchestrator,
    run: AuditRun,
    plan_ref: str,
    work_items: List[AuditWorkItem],
) -> None:
    orchestrator.commit_run(
        run,
        orchestrator.store.load_plan(plan_ref, work_items=work_items),
        work_items,
        known_run_ids=orchestrator.store.list_run_ids(),
    )


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

    orchestrator.commit_work_item(work_item)
    started = datetime.now(timezone.utc)
    attempt = work_item.start_attempt(started_at=started)
    orchestrator.commit_work_item(work_item)

    context = build_context(discovery, work_item.target_surface)
    result = worker.review(work_item, run, context)

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
        orchestrator.commit_run(
            run,
            orchestrator.store.load_plan(run.plan_ref, work_items=[work_item]),
            [work_item],
            known_run_ids=orchestrator.store.list_run_ids(),
        )
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
        orchestrator.commit_run(
            run,
            orchestrator.store.load_plan(run.plan_ref, work_items=[work_item]),
            [work_item],
            known_run_ids=orchestrator.store.list_run_ids(),
        )
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

    run.execution_completeness = RunExecutionCompleteness.COMPLETE
    run.coverage_completeness = RunCoverageCompleteness.FULL
    run.failure_state = RunFailureState.NONE

    _persist_run_state(orchestrator, run, run.plan_ref, [work_item])
    return result

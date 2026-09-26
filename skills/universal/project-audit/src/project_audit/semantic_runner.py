from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import List, Optional

from .context_builder import build_context
from .discovery import DiscoverySnapshot
from .models import AuditPlan, AuditRun, AuditWorkItem, EvidenceValidity, ExecutionState, WorkItemFailureState
from .orchestrator import Orchestrator
from .planner import build_target_snapshot
from .semantic_auditor import SemanticAuditor, SemanticReviewResult


def execute_semantic_review(
    orchestrator: Orchestrator,
    discovery: DiscoverySnapshot,
    run: AuditRun,
    work_item: AuditWorkItem,
    worker: SemanticAuditor,
    *,
    plan: Optional[AuditPlan] = None,
    work_items: Optional[List[AuditWorkItem]] = None,
) -> SemanticReviewResult:
    """Execute one semantic WorkItem with lifecycle and evidence gates."""
    if work_item.execution_state == ExecutionState.TERMINATED:
        raise ValueError("Cannot semantically review an already terminated WorkItem")

    plan = plan or orchestrator.store.load_plan(run.plan_ref)
    work_items = work_items if work_items is not None else [work_item]
    orchestrator.check_target_unchanged(discovery.root, run, plan, work_items)

    orchestrator.commit_work_item(work_item)
    started = datetime.now(timezone.utc)
    attempt = work_item.start_attempt(started_at=started)
    orchestrator.commit_work_item(work_item)

    context = build_context(discovery, work_item.target_surface)
    result = worker.review(work_item, run, context)
    changed_paths = orchestrator.check_target_unchanged(
        discovery.root, run, plan, work_items
    )

    if (
        result.evidence is not None
        and orchestrator.is_snapshot_node_affected(
            changed_paths,
            list(result.evidence.source_refs),
        )
    ):
        stale_evidence = replace(
            result.evidence,
            validity=EvidenceValidity.STALE,
        )
        result = replace(
            result,
            status="STALE",
            evidence=stale_evidence,
            raw_errors=tuple(result.raw_errors) + (
                {
                    "error_type": "SNAPSHOT_DRIFT",
                    "message": "Source evidence changed during semantic execution.",
                    "changed_paths": changed_paths,
                },
            ),
        )

    orchestrator.commit_receipt(result.receipt)

    finished = datetime.now(timezone.utc)

    if result.status == "STALE":
        if result.evidence is None:
            raise ValueError("STALE semantic result requires evidence.")
        attempt.fail(
            finished_at=finished,
            reason="SNAPSHOT_DRIFT",
            receipt_ref=result.receipt.receipt_id,
        )
        orchestrator.commit_evidence(result.evidence, work_item)
        work_item.terminate(failure_state=WorkItemFailureState.SNAPSHOT_DRIFT)
        orchestrator.commit_work_item(work_item)
        return result

    if result.status == "BLOCKED":
        attempt.fail(
            finished_at=finished,
            reason="SAFETY_BLOCK",
            receipt_ref=result.receipt.receipt_id,
        )
        work_item.terminate(failure_state=WorkItemFailureState.SAFETY_BLOCK)
        orchestrator.commit_work_item(work_item)
        return result

    if result.status == "FAILED":
        attempt.fail(
            finished_at=finished,
            reason="INFRA_ERROR",
            receipt_ref=result.receipt.receipt_id,
        )
        work_item.terminate(failure_state=WorkItemFailureState.INFRA_ERROR)
        orchestrator.commit_work_item(work_item)
        return result

    if result.status == "SCHEMA_VIOLATION":
        attempt.fail(
            finished_at=finished,
            reason="SCHEMA_VIOLATION",
            receipt_ref=result.receipt.receipt_id,
        )
        work_item.terminate(failure_state=WorkItemFailureState.SCHEMA_VIOLATION)
        orchestrator.commit_work_item(work_item)
        return result

    if result.status == "INVALID_OUTPUT":
        attempt.fail(
            finished_at=finished,
            reason="SCHEMA_VIOLATION",
            receipt_ref=result.receipt.receipt_id,
        )
        work_item.terminate(failure_state=WorkItemFailureState.SCHEMA_VIOLATION)
        orchestrator.commit_work_item(work_item)
        return result

    if result.status == "PARTIAL_COVERAGE":
        if result.evidence is None:
            raise ValueError("PARTIAL_COVERAGE requires valid evidence.")
        attempt.finish(
            finished_at=finished,
            exit_code=0,
            receipt_ref=result.receipt.receipt_id,
        )
        orchestrator.commit_evidence(result.evidence, work_item)
        work_item.terminate(failure_state=WorkItemFailureState.NONE)
        orchestrator.commit_work_item(work_item)
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

    return result

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from .discovery import DiscoverySnapshot
from .engineering_auditor import EngineeringAuditor, EngineeringInspectionResult
from .models import (
    AuditPlan,
    AuditRun,
    AuditWorkItem,
    Evidence,
    EvidenceValidity,
    ExecutionReceipt,
    ExecutionState,
    Provenance,
    RunBudgetState,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    RunPublicationState,
    WorkItemFailureState,
)
from .orchestrator import Orchestrator
from .planner import build_target_snapshot
from .semantic_auditor import SemanticAuditor, SemanticReviewResult
from .semantic_runner import execute_semantic_review


class EngineeringPassResult:
    def __init__(
        self,
        run: AuditRun,
        inspections: Tuple[EngineeringInspectionResult, ...],
        evidence: Tuple[Evidence, ...],
        semantic_reviews: Tuple[SemanticReviewResult, ...] = (),
    ) -> None:
        self.run = run
        self.inspections = inspections
        self.evidence = evidence
        self.semantic_reviews = semantic_reviews


def execute_engineering_pass(
    orchestrator: Orchestrator,
    discovery: DiscoverySnapshot,
    plan: AuditPlan,
    work_items: List[AuditWorkItem],
    auditor: Optional[EngineeringAuditor] = None,
    semantic_worker: Optional[SemanticAuditor] = None,
) -> EngineeringPassResult:
    """Execute only non-security WorkItems as PASS 1 of the single-agent audit."""
    auditor = auditor or EngineeringAuditor()

    snapshot = build_target_snapshot(discovery)
    if snapshot.snapshot_fingerprint != plan.target_snapshot_ref:
        raise ValueError(
            "Discovery state does not match the AuditPlan target snapshot. "
            "Refuse to execute against a different target."
        )
    orchestrator.commit_snapshot(snapshot)
    orchestrator.freeze_and_commit_plan(plan)

    run = AuditRun(
        run_id=str(uuid.uuid4()),
        target_snapshot_ref=plan.target_snapshot_ref,
        plan_ref=plan.plan_id,
        work_item_refs=[item.work_item_id for item in work_items],
        execution_completeness=RunExecutionCompleteness.RUNNING,
        coverage_completeness=RunCoverageCompleteness.PENDING,
        failure_state=RunFailureState.NONE,
        budget_state=RunBudgetState.HEALTHY,
        publication_state=RunPublicationState.NOT_PUBLISHED,
    )

    inspections = []
    evidences = []
    semantic_reviews = []

    for item in work_items:
        if item.target_surface.startswith("SECURITY/"):
            continue

        orchestrator.commit_work_item(item)
        started = datetime.now(timezone.utc)
        attempt = item.start_attempt(started_at=started)
        orchestrator.commit_work_item(item)

        result = auditor.inspect(discovery, item.work_item_id, item.target_surface)
        finished = datetime.now(timezone.utc)

        receipt = ExecutionReceipt(
            receipt_id=str(uuid.uuid4()),
            work_item_ref=item.work_item_id,
            command="project-audit-engineering",
            arguments=[item.target_surface],
            policy_snapshot=item.effective_execution_policy,
            started_at=started,
            finished_at=finished,
            exit_code=0,
            artifact_refs=[],
            environment_summary="deterministic-read-only",
        )
        orchestrator.commit_receipt(receipt)

        evidence = Evidence(
            evidence_id=str(uuid.uuid4()),
            target_snapshot_ref=plan.target_snapshot_ref,
            work_item_ref=item.work_item_id,
            source_refs=result.source_refs,
            dependencies=(),
            validity=EvidenceValidity.VALID,
            provenance=Provenance(
                actor=auditor.ACTOR,
                generated_at=finished,
            ),
            fingerprint=result.fingerprint,
        )

        attempt.finish(
            finished_at=finished,
            exit_code=0,
            receipt_ref=receipt.receipt_id,
        )
        orchestrator.commit_evidence(evidence, item)

        needs_semantic = any(
            getattr(observation, "state", None) == "NOT_DETERMINABLE"
            for observation in result.observations
        )
        if semantic_worker is not None and needs_semantic:
            semantic_result = execute_semantic_review(
                orchestrator,
                discovery,
                run,
                item,
                semantic_worker,
            )
            semantic_reviews.append(semantic_result)
            if semantic_result.evidence is not None:
                evidences.append(semantic_result.evidence)
            if semantic_result.status != "COMPLETED":
                inspections.append(result)
                evidences.append(evidence)
                continue

        if item.execution_state != ExecutionState.TERMINATED:
            item.terminate(failure_state=WorkItemFailureState.NONE)
            orchestrator.commit_work_item(item)

        inspections.append(result)
        evidences.append(evidence)

    executed_items = [
        item for item in work_items
        if not item.target_surface.startswith("SECURITY/")
    ]
    blocked = [item for item in executed_items if item.failure_state == WorkItemFailureState.SAFETY_BLOCK]
    failed = [
        item for item in executed_items
        if item.failure_state not in {WorkItemFailureState.NONE, WorkItemFailureState.SAFETY_BLOCK}
    ]
    succeeded = [
        item for item in executed_items
        if item.execution_state == ExecutionState.TERMINATED
        and item.failure_state == WorkItemFailureState.NONE
    ]
    security_pending = any(
        item.target_surface.startswith("SECURITY/")
        and item.execution_state != ExecutionState.TERMINATED
        for item in work_items
    )

    if blocked or failed:
        if not succeeded and blocked and not failed:
            run.execution_completeness = RunExecutionCompleteness.BLOCKED
            run.coverage_completeness = RunCoverageCompleteness.NONE
        else:
            run.execution_completeness = RunExecutionCompleteness.PARTIAL
            run.coverage_completeness = RunCoverageCompleteness.PARTIAL
        run.failure_state = RunFailureState.INFRA_ERROR if failed else RunFailureState.SAFETY_BLOCK
    elif security_pending:
        run.execution_completeness = RunExecutionCompleteness.PARTIAL
        run.coverage_completeness = RunCoverageCompleteness.PARTIAL
    elif succeeded or not executed_items:
        run.execution_completeness = RunExecutionCompleteness.COMPLETE
        run.coverage_completeness = RunCoverageCompleteness.FULL if succeeded else RunCoverageCompleteness.NONE
        run.failure_state = RunFailureState.NONE

    orchestrator.commit_run(
        run,
        plan,
        work_items,
        known_run_ids=orchestrator.store.list_run_ids(),
    )

    return EngineeringPassResult(run, tuple(inspections), tuple(evidences), tuple(semantic_reviews))

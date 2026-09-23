from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from .discovery import DiscoverySnapshot
from .models import (
    AuditPlan, AuditRun, AuditWorkItem, Evidence, EvidenceValidity,
    ExecutionReceipt, ExecutionState, Provenance,
    RunCoverageCompleteness, RunExecutionCompleteness, RunFailureState,
    RunPublicationState, WorkItemFailureState,
)
from .orchestrator import Orchestrator
from .security_pass import DeterministicSecurityAuditor, SecurityInspectionResult
from .semantic_auditor import SemanticAuditor, SemanticReviewResult
from .semantic_runner import execute_semantic_review


class SecurityPassResult:
    def __init__(
        self,
        run: AuditRun,
        inspections: tuple[SecurityInspectionResult, ...],
        evidence: tuple[Evidence, ...],
        semantic_reviews: tuple[SemanticReviewResult, ...] = (),
    ) -> None:
        self.run = run
        self.inspections = inspections
        self.evidence = evidence
        self.semantic_reviews = semantic_reviews


def execute_security_pass(
    orchestrator: Orchestrator,
    discovery: DiscoverySnapshot,
    plan: AuditPlan,
    work_items: List[AuditWorkItem],
    run: AuditRun,
    auditor: Optional[DeterministicSecurityAuditor] = None,
    semantic_worker: Optional[SemanticAuditor] = None,
) -> SecurityPassResult:
    """Execute the reserved SECURITY/* WorkItems in the existing AuditRun."""
    auditor = auditor or DeterministicSecurityAuditor()

    inspections = []
    evidences = []
    semantic_reviews = []

    for item in work_items:
        if not item.target_surface.startswith("SECURITY/"):
            continue
        if item.execution_state == ExecutionState.TERMINATED:
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
            command="project-audit-security",
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
            target_snapshot_ref=run.target_snapshot_ref,
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
            getattr(observation, "state", None) in {"OBSERVED", "NOT_DETERMINABLE"}
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

    pending = [
        item for item in work_items
        if item.execution_state != ExecutionState.TERMINATED
    ]
    blocked = [
        item for item in work_items
        if item.failure_state == WorkItemFailureState.SAFETY_BLOCK
    ]
    failed = [
        item for item in work_items
        if item.failure_state not in {WorkItemFailureState.NONE, WorkItemFailureState.SAFETY_BLOCK}
    ]
    succeeded = [
        item for item in work_items
        if item.execution_state == ExecutionState.TERMINATED
        and item.failure_state == WorkItemFailureState.NONE
    ]

    if blocked or failed:
        if not succeeded and blocked and not failed:
            run.execution_completeness = RunExecutionCompleteness.BLOCKED
            run.coverage_completeness = RunCoverageCompleteness.NONE
        else:
            run.execution_completeness = RunExecutionCompleteness.PARTIAL
            run.coverage_completeness = RunCoverageCompleteness.PARTIAL
        run.failure_state = RunFailureState.INFRA_ERROR if failed else RunFailureState.SAFETY_BLOCK
    elif pending:
        run.execution_completeness = RunExecutionCompleteness.PARTIAL
        run.coverage_completeness = RunCoverageCompleteness.PARTIAL
    else:
        run.execution_completeness = RunExecutionCompleteness.COMPLETE
        run.coverage_completeness = RunCoverageCompleteness.FULL
        run.failure_state = RunFailureState.NONE

    orchestrator.commit_run(
        run,
        plan,
        work_items,
        known_run_ids=orchestrator.store.list_run_ids(),
    )
    return SecurityPassResult(run, tuple(inspections), tuple(evidences), tuple(semantic_reviews))

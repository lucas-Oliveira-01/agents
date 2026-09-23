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


class EngineeringPassResult:
    def __init__(
        self,
        run: AuditRun,
        inspections: Tuple[EngineeringInspectionResult, ...],
        evidence: Tuple[Evidence, ...],
    ) -> None:
        self.run = run
        self.inspections = inspections
        self.evidence = evidence


def execute_engineering_pass(
    orchestrator: Orchestrator,
    discovery: DiscoverySnapshot,
    plan: AuditPlan,
    work_items: List[AuditWorkItem],
    auditor: Optional[EngineeringAuditor] = None,
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
        item.terminate(failure_state=WorkItemFailureState.NONE)
        orchestrator.commit_work_item(item)

        inspections.append(result)
        evidences.append(evidence)

    security_pending = any(
        item.target_surface.startswith("SECURITY/")
        and item.execution_state != ExecutionState.TERMINATED
        for item in work_items
    )

    completed_engineering = any(
        not item.target_surface.startswith("SECURITY/")
        and item.execution_state == ExecutionState.TERMINATED
        and item.failure_state == WorkItemFailureState.NONE
        for item in work_items
    )

    if security_pending:
        run.execution_completeness = RunExecutionCompleteness.PARTIAL
        run.coverage_completeness = RunCoverageCompleteness.PARTIAL
    elif completed_engineering:
        run.execution_completeness = RunExecutionCompleteness.COMPLETE
        run.coverage_completeness = RunCoverageCompleteness.FULL
    else:
        run.execution_completeness = RunExecutionCompleteness.COMPLETE
        run.coverage_completeness = RunCoverageCompleteness.NONE

    orchestrator.commit_run(
        run,
        plan,
        work_items,
        known_run_ids=orchestrator.store.list_run_ids(),
    )

    return EngineeringPassResult(run, tuple(inspections), tuple(evidences))

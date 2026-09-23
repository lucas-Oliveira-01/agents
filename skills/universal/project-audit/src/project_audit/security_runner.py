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
from .security_pass import DeterministicSecurityAuditor


def execute_security_pass(
    orchestrator: Orchestrator,
    discovery: DiscoverySnapshot,
    plan: AuditPlan,
    work_items: List[AuditWorkItem],
    run: AuditRun,
    auditor: Optional[DeterministicSecurityAuditor] = None,
) -> AuditRun:
    """Execute the reserved SECURITY/* WorkItems in the existing AuditRun."""
    auditor = auditor or DeterministicSecurityAuditor()

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
        item.terminate(failure_state=WorkItemFailureState.NONE)
        orchestrator.commit_work_item(item)

    pending = [
        item for item in work_items
        if item.execution_state != ExecutionState.TERMINATED
    ]
    failed = [
        item for item in work_items
        if item.failure_state != WorkItemFailureState.NONE
    ]

    if failed:
        run.execution_completeness = (
            RunExecutionCompleteness.FAILED
            if all(item.execution_state == ExecutionState.TERMINATED for item in work_items)
            else RunExecutionCompleteness.PARTIAL
        )
        run.failure_state = RunFailureState.INFRA_ERROR
        run.coverage_completeness = RunCoverageCompleteness.PARTIAL
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
    return run

"""
orchestrator.py — Core Orchestrator for project-audit Engine V1

The Orchestrator is the single writer of canonical state (§29).
It coordinates:
  TargetSnapshot → AuditPlan → AuditWorkItem → Attempt → ExecutionReceipt
  → Evidence → Validation → AuditRun → Persistence

Key invariants (enforced here):
  - Workers produce isolated outputs; Orchestrator validates then commits (§29)
  - All state transitions are validated before commit
  - Recovery: loads existing state from disk and reconciles (ADR-07)
  - Snapshot drift detection: stops execution if project changed (§18)
  - RETRY ≠ RECOVERY (ADR-07): distinct code paths
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .fake_auditor import FakeAuditor, FakeAuditorResult, FakeAuditorWithSnapshot
from .models import (
    ApplicabilityDecision,
    AuditPlan,
    AuditRun,
    AuditWorkItem,
    BudgetEnvelope,
    EgressDestination,
    EgressPolicy,
    Evidence,
    EvidenceValidity,
    ExecutionPolicy,
    ExecutionReceipt,
    ExecutionState,
    FilesystemAccess,
    NetworkAccess,
    CredentialAccess,
    MethodologyState,
    ProjectState,
    RunBudgetState,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    RunPublicationState,
    SubmoduleState,
    TargetMode,
    TargetSnapshot,
    TrackedInputFingerprint,
    WorkItemAction,
    WorkItemFailureState,
    WorkingTreeState,
)
from .schema_validator import (
    validate_audit_plan,
    validate_audit_run,
    validate_audit_work_item,
    validate_evidence,
    validate_target_snapshot,
)
from .state_store import StateStore
from .validators import (
    ValidationReport,
    can_publish,
    validate_run,
    validate_snapshot,
    validate_work_item,
)

logger = logging.getLogger(__name__)


class SchemaValidationError(RuntimeError):
    """Raised when an entity fails JSON schema structural validation."""


class OrchestratorError(RuntimeError):
    """Raised on irrecoverable orchestrator errors."""


class SnapshotDriftError(RuntimeError):
    """Raised when snapshot drift is detected during execution (§18)."""


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class Orchestrator:
    """
    Single-writer coordinator for audit execution.

    Usage:
        store = StateStore(Path(".audit/runs"))
        orch = Orchestrator(store)
        run = orch.execute_vertical_slice(snapshot, plan, work_items, auditor)
    """

    def __init__(self, store: StateStore) -> None:
        self.store = store

    # ------------------------------------------------------------------ #
    # Phase 1: Persist and validate TargetSnapshot                        #
    # ------------------------------------------------------------------ #

    def commit_snapshot(self, snapshot: TargetSnapshot) -> TargetSnapshot:
        """Validate, then atomically persist a TargetSnapshot."""
        # Structural gate
        errors = validate_target_snapshot(snapshot.to_dict())
        if errors:
            raise SchemaValidationError(
                f"TargetSnapshot schema validation failed:\n" + "\n".join(errors)
            )
        # Semantic gate
        report = validate_snapshot(snapshot)
        if report.has_errors:
            raise OrchestratorError(
                f"TargetSnapshot semantic validation failed:\n"
                + "\n".join(r.message for r in report.errors())
            )
        self.store.save_snapshot(snapshot)
        logger.info("Snapshot committed: %s", snapshot.snapshot_fingerprint[:16])
        return snapshot

    # ------------------------------------------------------------------ #
    # Phase 2: Freeze and persist AuditPlan                               #
    # ------------------------------------------------------------------ #

    def freeze_and_commit_plan(self, plan: AuditPlan) -> AuditPlan:
        """Freeze the plan (if not already frozen), validate, persist."""
        if not plan.is_frozen:
            plan.freeze()
        # Structural gate (plan_id + work_items refs only)
        errors = validate_audit_plan(plan.to_dict())
        if errors:
            raise SchemaValidationError(
                f"AuditPlan schema validation failed:\n" + "\n".join(errors)
            )
        self.store.save_plan(plan)
        logger.info("Plan frozen and committed: %s", plan.plan_id)
        return plan

    # ------------------------------------------------------------------ #
    # Phase 3: Commit a WorkItem                                           #
    # ------------------------------------------------------------------ #

    def commit_work_item(self, work_item: AuditWorkItem) -> None:
        """Validate and persist a single AuditWorkItem."""
        errors = validate_audit_work_item(work_item.to_dict())
        if errors:
            raise SchemaValidationError(
                f"AuditWorkItem {work_item.work_item_id} schema validation failed:\n"
                + "\n".join(errors)
            )
        self.store.save_work_item(work_item)
        logger.debug("WorkItem committed: %s (%s)", work_item.work_item_id, work_item.execution_state.value)

    # ------------------------------------------------------------------ #
    # Phase 4: Commit an ExecutionReceipt                                  #
    # ------------------------------------------------------------------ #

    def commit_receipt(self, receipt: ExecutionReceipt) -> None:
        """Persist an ExecutionReceipt (evidence of execution)."""
        self.store.save_receipt(receipt)
        logger.debug("ExecutionReceipt committed: %s", receipt.receipt_id)

    # ------------------------------------------------------------------ #
    # Phase 5: Validate and commit Evidence                                #
    # ------------------------------------------------------------------ #

    def commit_evidence(self, evidence: Evidence, work_item: AuditWorkItem) -> None:
        """Validate evidence structural + semantic consistency, then persist."""
        errors = validate_evidence(evidence.to_dict())
        if errors:
            raise SchemaValidationError(
                f"Evidence {evidence.evidence_id} schema validation failed:\n"
                + "\n".join(errors)
            )
        # Evidence work_item_ref must match
        if evidence.work_item_ref != work_item.work_item_id:
            raise OrchestratorError(
                f"Evidence {evidence.evidence_id} work_item_ref mismatch: "
                f"{evidence.work_item_ref} != {work_item.work_item_id}"
            )
        self.store.save_evidence(evidence)
        logger.debug("Evidence committed: %s", evidence.evidence_id)

    # ------------------------------------------------------------------ #
    # Phase 6: Validate and commit AuditRun                               #
    # ------------------------------------------------------------------ #

    def commit_run(
        self,
        run: AuditRun,
        plan: AuditPlan,
        work_items: List[AuditWorkItem],
        known_run_ids: Optional[List[str]] = None,
        interrupted_run_ids: Optional[List[str]] = None,
    ) -> ValidationReport:
        """Validate (structural + semantic), then persist the AuditRun."""
        errors = validate_audit_run(run.to_dict())
        if errors:
            raise SchemaValidationError(
                f"AuditRun {run.run_id} schema validation failed:\n" + "\n".join(errors)
            )
        report = validate_run(run, plan, work_items, known_run_ids, interrupted_run_ids)
        if report.has_errors:
            error_codes = [r.code for r in report.errors()]
            logger.error(
                "AuditRun %s has semantic validation errors: %s",
                run.run_id,
                error_codes,
            )
            raise OrchestratorError(f"Semantic validation failed for run {run.run_id}: {error_codes}")

        self.store.save_run(run)
        logger.info("AuditRun committed: %s (%s)", run.run_id, run.execution_completeness.value)
        return report

    # ------------------------------------------------------------------ #
    # Snapshot drift detection (§18)                                      #
    # ------------------------------------------------------------------ #

    def detect_snapshot_drift(
        self, run: AuditRun, current_fingerprint: str
    ) -> bool:
        """
        Detect if the project changed since the run started.
        Returns True if drift detected (execution must stop).
        """
        if run.target_snapshot_ref != current_fingerprint:
            logger.error(
                "SNAPSHOT DRIFT: run %s was started against %s, "
                "current snapshot is %s",
                run.run_id,
                run.target_snapshot_ref[:16],
                current_fingerprint[:16],
            )
            return True
        return False

    def ensure_snapshot_current(
        self, run: AuditRun, plan: AuditPlan, work_items: List[AuditWorkItem],
        current_fingerprint: str,
    ) -> None:
        """Fail closed for the whole run; keep stale diagnostics, reuse nothing."""
        if (run.failure_state != RunFailureState.SNAPSHOT_DRIFT
                and not self.detect_snapshot_drift(run, current_fingerprint)):
            return
        run.failure_state = RunFailureState.SNAPSHOT_DRIFT
        run.publication_state = RunPublicationState.NOT_PUBLISHED
        run.artifact_refs.clear()
        run.execution_completeness = RunExecutionCompleteness.PARTIAL
        blocked = [i for i in work_items if i.failure_state == WorkItemFailureState.SAFETY_BLOCK]
        complete = [i for i in work_items if i.execution_state == ExecutionState.TERMINATED
                    and i.failure_state == WorkItemFailureState.NONE]
        if not work_items or len(blocked) == len(work_items):
            run.coverage_completeness = RunCoverageCompleteness.NONE
        elif len(complete) == len(work_items):
            run.coverage_completeness = RunCoverageCompleteness.FULL
        else:
            run.coverage_completeness = RunCoverageCompleteness.PARTIAL
        for evidence_id in self.store.list_evidence_ids():
            evidence = self.store.load_evidence(evidence_id)
            if evidence.work_item_ref in run.work_item_refs:
                self.store.save_evidence(replace(evidence, validity=EvidenceValidity.STALE))
        self.commit_run(run, plan, work_items, known_run_ids=self.store.list_run_ids())
        raise SnapshotDriftError("SNAPSHOT_DRIFT: audit is STALE; a full re-run is required.")

    def check_target_unchanged(
        self, root: Path, run: AuditRun, plan: AuditPlan, work_items: List[AuditWorkItem],
    ) -> None:
        from .discovery import discover
        from .planner import build_target_snapshot

        snapshot = self.store.load_snapshot(run.target_snapshot_ref)
        try:
            current = build_target_snapshot(discover(str(root)), snapshot.target_mode)
        except (OSError, ValueError):
            # Missing/unreadable input cannot establish snapshot identity.
            self.ensure_snapshot_current(run, plan, work_items, "UNREADABLE")
            return
        self.ensure_snapshot_current(run, plan, work_items, current.snapshot_fingerprint)

    # ------------------------------------------------------------------ #
    # Recovery (ADR-07): reconstruct state from disk after interruption   #
    # ------------------------------------------------------------------ #

    def recover_run(self, interrupted_run_id: str) -> AuditRun:
        """
        RECOVERY path (≠ RETRY): reconstruct state from persisted artifacts.
        The caller must create a new AuditRun with recovery_from_ref pointing
        to the interrupted run. (ADR-07)
        """
        if not self.store.run_exists(interrupted_run_id):
            raise OrchestratorError(
                f"Recovery failed: run {interrupted_run_id} not found in store."
            )
        interrupted_run = self.store.load_run(interrupted_run_id)
        
        from project_audit.models import RunExecutionCompleteness, IllegalStateTransitionError
        if interrupted_run.execution_completeness == RunExecutionCompleteness.COMPLETE:
            raise IllegalStateTransitionError(
                f"Cannot recover run {interrupted_run_id} because it is already COMPLETE. "
                "Recovery is only for interrupted runs (e.g. PARTIAL or RUNNING)."
            )

        logger.info(
            "Recovery: loaded interrupted run %s (completeness=%s)",
            interrupted_run_id,
            interrupted_run.execution_completeness.value,
        )
        return interrupted_run

    # ------------------------------------------------------------------ #
    # Vertical Slice: full pipeline in one call (for testing/integration) #
    # ------------------------------------------------------------------ #

    def execute_vertical_slice(
        self,
        snapshot: TargetSnapshot,
        plan: AuditPlan,
        work_items: List[AuditWorkItem],
        auditor: FakeAuditorWithSnapshot,
        previous_run_ref: Optional[str] = None,
        recovery_from_ref: Optional[str] = None,
        snapshot_provider: Optional[Callable[[], TargetSnapshot]] = None,
    ) -> AuditRun:
        """
        Execute the full vertical slice:
        TargetSnapshot → AuditPlan → WorkItems → Attempts → Receipts
        → Evidence → Validation → AuditRun → Persistence

        Returns the final committed AuditRun.
        """
        # 1. Commit snapshot
        snapshot = self.commit_snapshot(snapshot)

        # 2. Freeze and commit plan
        plan = self.freeze_and_commit_plan(plan)

        # 3. Create AuditRun
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=snapshot.snapshot_fingerprint,
            plan_ref=plan.plan_id,
            work_item_refs=[wi.work_item_id for wi in work_items],
            execution_completeness=RunExecutionCompleteness.RUNNING,
            coverage_completeness=RunCoverageCompleteness.PENDING,
            failure_state=RunFailureState.NONE,
            budget_state=RunBudgetState.HEALTHY,
            publication_state=RunPublicationState.NOT_PUBLISHED,
            previous_run_ref=previous_run_ref,
            recovery_from_ref=recovery_from_ref,
        )

        collected_evidence: List[Evidence] = []

        def check_snapshot() -> None:
            if snapshot_provider is not None:
                self.ensure_snapshot_current(run, plan, work_items, snapshot_provider().snapshot_fingerprint)
            elif Path(snapshot.project_state.repository_identity).is_dir():
                self.check_target_unchanged(Path(snapshot.project_state.repository_identity), run, plan, work_items)

        check_snapshot()
        # 4. Execute each WorkItem
        for work_item in work_items:
            check_snapshot()
            # Commit initial planned state
            self.commit_work_item(work_item)

            now = datetime.now(timezone.utc)
            attempt = work_item.start_attempt(started_at=now)
            self.commit_work_item(work_item)

            # Worker executes (isolated output — not yet committed to canonical state)
            receipt, evidence = auditor.execute(work_item, started_at=now)

            check_snapshot()
            # Commit receipt (evidence of execution)
            self.commit_receipt(receipt)

            if receipt.exit_code == 126:
                # BLOCKED by safety gate
                attempt.fail(finished_at=now, reason="SAFETY_BLOCK", receipt_ref=receipt.receipt_id)
                work_item.terminate(failure_state=WorkItemFailureState.SAFETY_BLOCK)
            elif receipt.exit_code != 0 or evidence is None:
                # FAILED
                attempt.fail(finished_at=now, reason="INFRA_ERROR", receipt_ref=receipt.receipt_id)
                work_item.terminate(failure_state=WorkItemFailureState.INFRA_ERROR)
            else:
                # SUCCESS: validate and commit evidence
                attempt.finish(finished_at=now, exit_code=0, receipt_ref=receipt.receipt_id)
                self.commit_evidence(evidence, work_item)
                work_item.artifact_refs.append(f"evidence/{evidence.evidence_id}.json")
                work_item.terminate(failure_state=WorkItemFailureState.NONE)
                collected_evidence.append(evidence)

            self.commit_work_item(work_item)

        # 5. Derive and set run state (ADR-07 §2)
        #
        # BLOCKED: the execution was deliberately halted by a policy constraint.
        #          ALL work items were blocked — none attempted valid execution.
        # FAILED:  a valid operation was attempted but crashed/errored.
        # PARTIAL: some items completed, some were blocked or failed — mixed result.
        #          Also covers budget exhaustion: clean end without completing scope.
        #
        # Invariant: BLOCKED ≠ FAILED ≠ PARTIAL ≠ COMPLETE (ADR-07)
        blocked = [wi for wi in work_items if wi.failure_state == WorkItemFailureState.SAFETY_BLOCK]
        failed = [wi for wi in work_items if wi.failure_state == WorkItemFailureState.INFRA_ERROR]
        succeeded = [wi for wi in work_items if wi.failure_state == WorkItemFailureState.NONE
                     and wi.execution_state == ExecutionState.TERMINATED]

        all_blocked = len(blocked) == len(work_items) and work_items
        any_failed = bool(failed)
        any_succeeded = bool(succeeded)

        if any_failed and not any_succeeded:
            # All executed items failed (no partial success)
            run.execution_completeness = RunExecutionCompleteness.FAILED
            run.failure_state = RunFailureState.INFRA_ERROR
        elif all_blocked:
            # ALL work items were blocked by policy — nothing executed
            run.execution_completeness = RunExecutionCompleteness.BLOCKED
            run.failure_state = RunFailureState.SAFETY_BLOCK
        elif (blocked or failed) and any_succeeded:
            # Mixed: some succeeded, some blocked/failed — PARTIAL
            run.execution_completeness = RunExecutionCompleteness.PARTIAL
            if any_failed:
                run.failure_state = RunFailureState.INFRA_ERROR
        elif any_failed:
            # Some failed, some blocked (but none succeeded)
            run.execution_completeness = RunExecutionCompleteness.PARTIAL
            run.failure_state = RunFailureState.INFRA_ERROR
        elif work_items:
            run.execution_completeness = RunExecutionCompleteness.COMPLETE
        else:
            run.execution_completeness = RunExecutionCompleteness.COMPLETE

        # Coverage completeness (derived, not declared — §6)
        # BLOCKED run has NONE coverage (nothing was audited)
        # PARTIAL run has PARTIAL coverage
        # COMPLETE run has FULL coverage
        if all_blocked:
            run.coverage_completeness = RunCoverageCompleteness.NONE
        elif blocked or failed:
            run.coverage_completeness = RunCoverageCompleteness.PARTIAL
        elif work_items:
            run.coverage_completeness = RunCoverageCompleteness.FULL
        else:
            run.coverage_completeness = RunCoverageCompleteness.NONE

        check_snapshot()
        # 6. Commit the run
        known_run_ids = self.store.list_run_ids()
        self.commit_run(run, plan, work_items, known_run_ids=known_run_ids)

        return run

    # ------------------------------------------------------------------ #
    # Publication eligibility check                                        #
    # ------------------------------------------------------------------ #

    def check_publication_eligibility(
        self,
        run: AuditRun,
        plan: AuditPlan,
        work_items: List[AuditWorkItem],
        evidence_list: List[Evidence],
        current_snapshot_fingerprint: str,
    ) -> ValidationReport:
        """
        Derive can_publish() decision from invariants.
        Does NOT publish anything. (§22, §45)
        """
        return can_publish(
            run=run,
            work_items=work_items,
            evidence_list=evidence_list,
            current_snapshot_fingerprint=current_snapshot_fingerprint,
            plan=plan,
        )

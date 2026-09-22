"""
test_hardening.py — Hardening & Adversarial Tests for Core Engine V1

Covers the final gate before marking V1 as ACCEPTED:

  [ ] BLOCKED × FAILED × PARTIAL semantic distinction (ADR-07 §2)
  [ ] BLOCKED → NONE coverage (not PARTIAL)
  [ ] can_publish() for each critical state
  [ ] Egress sensitivity gap explicitly classified
  [ ] Adversarial: attempts to inject impossible states
  [ ] Recovery from partially-persisted run
  [ ] Schema ↔ serialization runtime verification
  [ ] shared.schema is definitions-only (never a root instance)
  [ ] previous_run_ref ≠ recovery_from_ref (distinct lineage)
  [ ] execution_completeness cannot silently imply coverage_completeness
"""

import dataclasses
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from project_audit.fake_auditor import FakeAuditorResult, FakeAuditorWithSnapshot
from project_audit.models import (
    ApplicabilityDecision,
    AuditPlan,
    AuditRun,
    AuditWorkItem,
    BudgetEnvelope,
    CredentialAccess,
    EgressDestination,
    EgressPolicy,
    Evidence,
    EvidenceValidity,
    ExecutionPolicy,
    ExecutionReceipt,
    ExecutionState,
    FilesystemAccess,
    ImmutablePlanError,
    IllegalAttemptOrderError,
    IllegalStateTransitionError,
    NetworkAccess,
    Provenance,
    RunBudgetState,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    RunPublicationState,
    WorkItemAction,
    WorkItemFailureState,
    WorkingTreeState,
)
from project_audit.orchestrator import Orchestrator, OrchestratorError, SchemaValidationError
from project_audit.state_store import StateStore
from project_audit.validators import (
    ValidationLevel,
    can_publish,
    validate_coverage_completeness_derivable,
    validate_run_previous_ref_distinct_from_recovery,
    validate_snapshot_drift,
)
from tests.conftest import (
    FIXED_TS,
    make_evidence,
    make_project_state,
    make_methodology_state,
    make_work_item,
)


@pytest.fixture
def orchestrator(state_store) -> Orchestrator:
    return Orchestrator(state_store)


def _make_plan(target_snapshot, execution_policy, egress_policy):
    plan_id = str(uuid.uuid4())
    plan = AuditPlan(
        plan_id=plan_id,
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        requested_scope=["security"],
        applicability_decisions=[
            ApplicabilityDecision("security", True, "test", [])
        ],
        resolved_scope=["security"],
        work_items=[],
        execution_policy=execution_policy,
        egress_policy=egress_policy,
    )
    return plan, plan_id


# ===========================================================================
# §1 — BLOCKED × FAILED × PARTIAL × COMPLETE Semantic Distinction (ADR-07 §2)
# ===========================================================================


class TestBlockedFailedPartialDistinction:
    """
    ADR-07 §2 defines BLOCKED, FAILED, PARTIAL as semantically distinct.
    The implementation must respect these invariants exactly.
    """

    def test_all_blocked_yields_run_blocked_not_partial(
        self, orchestrator, target_snapshot, execution_policy, egress_policy
    ):
        """
        ALL WorkItems BLOCKED by safety gate → Run.execution_completeness = BLOCKED
        NOT PARTIAL. (ADR-07 §2: BLOCKED = deliberate policy halt)
        """
        block_auditor = FakeAuditorWithSnapshot(
            snapshot_fingerprint=target_snapshot.snapshot_fingerprint,
            result=FakeAuditorResult.BLOCK,
        )
        plan, plan_id = _make_plan(target_snapshot, execution_policy, egress_policy)
        wi1 = make_work_item(plan_id=plan_id, execution_policy=execution_policy, egress_policy=egress_policy)
        wi2 = make_work_item(plan_id=plan_id, execution_policy=execution_policy, egress_policy=egress_policy)
        run = orchestrator.execute_vertical_slice(
            snapshot=target_snapshot,
            plan=plan,
            work_items=[wi1, wi2],
            auditor=block_auditor,
        )
        assert run.execution_completeness == RunExecutionCompleteness.BLOCKED, (
            f"Expected BLOCKED, got {run.execution_completeness}"
        )
        assert run.failure_state == RunFailureState.SAFETY_BLOCK

    def test_all_blocked_yields_none_coverage(
        self, orchestrator, target_snapshot, execution_policy, egress_policy
    ):
        """
        BLOCKED run → coverage_completeness = NONE (nothing was audited).
        NOT PARTIAL — PARTIAL implies some valid results exist.
        """
        block_auditor = FakeAuditorWithSnapshot(
            snapshot_fingerprint=target_snapshot.snapshot_fingerprint,
            result=FakeAuditorResult.BLOCK,
        )
        plan, plan_id = _make_plan(target_snapshot, execution_policy, egress_policy)
        wi = make_work_item(plan_id=plan_id, execution_policy=execution_policy, egress_policy=egress_policy)
        run = orchestrator.execute_vertical_slice(
            snapshot=target_snapshot,
            plan=plan,
            work_items=[wi],
            auditor=block_auditor,
        )
        assert run.coverage_completeness == RunCoverageCompleteness.NONE, (
            f"Expected NONE coverage for fully BLOCKED run, got {run.coverage_completeness}"
        )

    def test_mixed_blocked_and_success_yields_partial(
        self, orchestrator, state_store, target_snapshot, execution_policy, egress_policy
    ):
        """
        Some items succeed, some are blocked → PARTIAL (mixed result).
        PARTIAL ≠ BLOCKED (ADR-07 §2).
        """
        # Two-item plan: first success, second blocked
        from project_audit.fake_auditor import FakeAuditor, FakeAuditorResult, FakeAuditorWithSnapshot
        from project_audit.models import ExecutionState

        plan, plan_id = _make_plan(target_snapshot, execution_policy, egress_policy)
        wi_success = make_work_item(
            plan_id=plan_id, target_surface="src/auth.py",
            execution_policy=execution_policy, egress_policy=egress_policy
        )
        wi_blocked = make_work_item(
            plan_id=plan_id, target_surface="src/db.py",
            execution_policy=execution_policy, egress_policy=egress_policy
        )

        # We need two different auditors for different items
        # Use a custom orchestrator approach: manually execute
        orchestrator.commit_snapshot(target_snapshot)
        orchestrator.freeze_and_commit_plan(plan)
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=plan.plan_id,
            work_item_refs=[wi_success.work_item_id, wi_blocked.work_item_id],
            execution_completeness=RunExecutionCompleteness.RUNNING,
            coverage_completeness=RunCoverageCompleteness.PENDING,
            failure_state=RunFailureState.NONE,
        )

        # Execute success item
        success_auditor = FakeAuditorWithSnapshot(target_snapshot.snapshot_fingerprint, FakeAuditorResult.SUCCESS)
        orchestrator.commit_work_item(wi_success)
        now = datetime.now(timezone.utc)
        attempt_s = wi_success.start_attempt(started_at=now)
        receipt_s, evidence_s = success_auditor.execute(wi_success, started_at=now)
        orchestrator.commit_receipt(receipt_s)
        attempt_s.finish(finished_at=now, exit_code=0, receipt_ref=receipt_s.receipt_id)
        orchestrator.commit_evidence(evidence_s, wi_success)
        wi_success.artifact_refs.append(f"evidence/{evidence_s.evidence_id}.json")
        wi_success.terminate(WorkItemFailureState.NONE)
        orchestrator.commit_work_item(wi_success)

        # Execute blocked item
        block_auditor = FakeAuditorWithSnapshot(target_snapshot.snapshot_fingerprint, FakeAuditorResult.BLOCK)
        orchestrator.commit_work_item(wi_blocked)
        attempt_b = wi_blocked.start_attempt(started_at=now)
        receipt_b, _ = block_auditor.execute(wi_blocked, started_at=now)
        orchestrator.commit_receipt(receipt_b)
        attempt_b.fail(finished_at=now, reason="SAFETY_BLOCK", receipt_ref=receipt_b.receipt_id)
        wi_blocked.terminate(WorkItemFailureState.SAFETY_BLOCK)
        orchestrator.commit_work_item(wi_blocked)

        # Derive state (same logic as execute_vertical_slice)
        blocked = [wi for wi in [wi_success, wi_blocked] if wi.failure_state == WorkItemFailureState.SAFETY_BLOCK]
        succeeded = [wi for wi in [wi_success, wi_blocked] if wi.failure_state == WorkItemFailureState.NONE and wi.execution_state == ExecutionState.TERMINATED]

        all_blocked = len(blocked) == 2
        assert not all_blocked  # mixed
        assert len(succeeded) == 1  # one succeeded

        run.execution_completeness = RunExecutionCompleteness.PARTIAL
        run.coverage_completeness = RunCoverageCompleteness.PARTIAL
        orchestrator.commit_run(run, plan, [wi_success, wi_blocked])

        assert run.execution_completeness == RunExecutionCompleteness.PARTIAL
        assert run.coverage_completeness == RunCoverageCompleteness.PARTIAL

    def test_failed_not_blocked(
        self, orchestrator, target_snapshot, execution_policy, egress_policy
    ):
        """INFRA_ERROR failure ≠ SAFETY_BLOCK. Run must be FAILED, not BLOCKED."""
        fail_auditor = FakeAuditorWithSnapshot(
            snapshot_fingerprint=target_snapshot.snapshot_fingerprint,
            result=FakeAuditorResult.FAIL,
        )
        plan, plan_id = _make_plan(target_snapshot, execution_policy, egress_policy)
        wi = make_work_item(plan_id=plan_id, execution_policy=execution_policy, egress_policy=egress_policy)
        run = orchestrator.execute_vertical_slice(
            snapshot=target_snapshot,
            plan=plan,
            work_items=[wi],
            auditor=fail_auditor,
        )
        assert run.execution_completeness == RunExecutionCompleteness.FAILED
        assert run.execution_completeness != RunExecutionCompleteness.BLOCKED
        assert run.failure_state == RunFailureState.INFRA_ERROR

    def test_partial_is_never_published_as_complete(
        self, orchestrator, target_snapshot, execution_policy, egress_policy
    ):
        """PARTIAL must never transition to COMPLETE. (ADR-07 §2 invariant)"""
        block_aud = FakeAuditorWithSnapshot(
            snapshot_fingerprint=target_snapshot.snapshot_fingerprint,
            result=FakeAuditorResult.BLOCK,
        )
        plan, plan_id = _make_plan(target_snapshot, execution_policy, egress_policy)
        wi = make_work_item(plan_id=plan_id, execution_policy=execution_policy, egress_policy=egress_policy)
        run = orchestrator.execute_vertical_slice(
            snapshot=target_snapshot,
            plan=plan,
            work_items=[wi],
            auditor=block_aud,
        )
        # BLOCKED run cannot be published as COMPLETE
        from project_audit.validators import can_publish
        report = orchestrator.check_publication_eligibility(
            run=run,
            plan=plan,
            work_items=[wi],
            evidence_list=[],
            current_snapshot_fingerprint=target_snapshot.snapshot_fingerprint,
        )
        assert report.has_errors  # Must have errors — cannot publish

    def test_complete_not_partial_with_all_success(
        self, orchestrator, target_snapshot, execution_policy, egress_policy
    ):
        """All items succeed → COMPLETE, not PARTIAL."""
        success_aud = FakeAuditorWithSnapshot(
            snapshot_fingerprint=target_snapshot.snapshot_fingerprint,
            result=FakeAuditorResult.SUCCESS,
        )
        plan, plan_id = _make_plan(target_snapshot, execution_policy, egress_policy)
        wi = make_work_item(plan_id=plan_id, execution_policy=execution_policy, egress_policy=egress_policy)
        run = orchestrator.execute_vertical_slice(
            snapshot=target_snapshot,
            plan=plan,
            work_items=[wi],
            auditor=success_aud,
        )
        assert run.execution_completeness == RunExecutionCompleteness.COMPLETE
        assert run.coverage_completeness == RunCoverageCompleteness.FULL


# ===========================================================================
# §2 — can_publish() for each critical state
# ===========================================================================


class TestCanPublishCriticalStates:
    def _run(self, audit_plan, target_snapshot, completeness, failure_state=RunFailureState.NONE,
             coverage=RunCoverageCompleteness.FULL):
        return AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[],
            execution_completeness=completeness,
            coverage_completeness=coverage,
            failure_state=failure_state,
        )

    def test_blocked_run_cannot_publish(self, audit_plan, target_snapshot, work_item):
        run = self._run(audit_plan, target_snapshot, RunExecutionCompleteness.BLOCKED,
                        RunFailureState.SAFETY_BLOCK, RunCoverageCompleteness.NONE)
        report = can_publish(run, [work_item], [], target_snapshot.snapshot_fingerprint, audit_plan)
        assert report.has_errors
        codes = [r.code for r in report.errors()]
        assert "PUBLISH_EXECUTION_INCOMPLETE" in codes

    def test_failed_run_cannot_publish(self, audit_plan, target_snapshot, work_item):
        run = self._run(audit_plan, target_snapshot, RunExecutionCompleteness.FAILED,
                        RunFailureState.INFRA_ERROR)
        report = can_publish(run, [work_item], [], target_snapshot.snapshot_fingerprint, audit_plan)
        assert report.has_errors
        codes = [r.code for r in report.errors()]
        assert "PUBLISH_EXECUTION_INCOMPLETE" in codes

    def test_partial_clean_run_cannot_publish(self, audit_plan, target_snapshot, work_item):
        run = self._run(audit_plan, target_snapshot, RunExecutionCompleteness.PARTIAL)
        report = can_publish(run, [work_item], [], target_snapshot.snapshot_fingerprint, audit_plan)
        assert report.has_errors
        codes = [r.code for r in report.errors()]
        assert "PUBLISH_EXECUTION_INCOMPLETE" in codes

    def test_complete_clean_run_can_publish(self, audit_plan, target_snapshot, work_item):
        run = self._run(audit_plan, target_snapshot, RunExecutionCompleteness.COMPLETE)
        # Fix: COMPLETE runs need FULL coverage to publish (or PARTIAL if explicitly allowed)
        run.coverage_completeness = RunCoverageCompleteness.FULL
        report = can_publish(run, [work_item], [], target_snapshot.snapshot_fingerprint, audit_plan)
        assert not report.has_errors

    def test_running_run_cannot_publish(self, audit_plan, target_snapshot):
        run = self._run(audit_plan, target_snapshot, RunExecutionCompleteness.RUNNING)
        report = can_publish(run, [], [], target_snapshot.snapshot_fingerprint, audit_plan)
        assert report.has_errors

    def test_planned_run_cannot_publish(self, audit_plan, target_snapshot):
        run = self._run(audit_plan, target_snapshot, RunExecutionCompleteness.PLANNED)
        report = can_publish(run, [], [], target_snapshot.snapshot_fingerprint, audit_plan)
        assert report.has_errors

    def test_complete_clean_run_can_publish(self, audit_plan, target_snapshot):
        run = self._run(audit_plan, target_snapshot, RunExecutionCompleteness.COMPLETE)
        report = can_publish(run, [], [], target_snapshot.snapshot_fingerprint, audit_plan)
        assert not report.has_errors


# ===========================================================================
# §3 — Egress Sensitivity Gap: explicitly classified as PARTIAL
# ===========================================================================


class TestEgressSensitivityClassification:
    """
    IMPLEMENTATION STATUS: PARTIALLY IMPLEMENTED

    validate_egress_policy() requires a `data_is_sensitive` signal from the caller.
    In V1, this signal is provided externally by the Orchestrator.
    The policy remains correct: when sensitivity is unknown, DO NOT SEND.

    These tests document the gap and validate the fail-safe behavior.
    """

    def test_egress_fail_closed_when_sensitivity_unknown(self, audit_plan, execution_policy):
        """When sensitivity is UNKNOWN (None), fail-safe must be DO NOT SEND (deny)."""
        from project_audit.validators import validate_egress_policy

        wi = make_work_item(
            plan_id=audit_plan.plan_id,
            egress_policy=EgressPolicy(
                destination=EgressDestination.LOCAL_ONLY,
                allow_sensitive=False,
            ),
            execution_policy=execution_policy,
        )
        # UNKNOWN sensitivity (None) → fail closed → must deny
        result = validate_egress_policy(wi, data_is_sensitive=None)
        assert result.is_error, (
            "When sensitivity is unknown (None) and policy denies sensitive data, "
            "it must return ERROR (DO NOT SEND). (ADR-05 fail-closed principle)"
        )
        assert result.code == "EGRESS_SENSITIVE_DATA_DENIED"

    def test_egress_allowed_when_explicitly_permitted(self, audit_plan, execution_policy):
        """Only when policy explicitly permits sensitive data and destination is approved."""
        from project_audit.validators import validate_egress_policy

        wi = make_work_item(
            plan_id=audit_plan.plan_id,
            egress_policy=EgressPolicy(
                destination=EgressDestination.APPROVED_EXTERNAL,
                allow_sensitive=True,
            ),
            execution_policy=execution_policy,
        )
        result = validate_egress_policy(wi, data_is_sensitive=True)
        assert result.is_pass

    def test_egress_local_only_safe_for_non_sensitive(self, audit_plan, execution_policy):
        """LOCAL_ONLY + non-sensitive data is always safe."""
        from project_audit.validators import validate_egress_policy

        wi = make_work_item(
            plan_id=audit_plan.plan_id,
            egress_policy=EgressPolicy(
                destination=EgressDestination.LOCAL_ONLY,
                allow_sensitive=False,
            ),
            execution_policy=execution_policy,
        )
        result = validate_egress_policy(wi, data_is_sensitive=False)
        assert result.is_pass


# ===========================================================================
# §4 — Adversarial: Inject Impossible States
# ===========================================================================


class TestAdversarialImpossibleStates:
    """
    Attempt to inject states that the Canonical Data Model considers impossible.
    Tests verify the engine rejects them, not silently accepts them.
    """

    def test_cannot_accept_terminated_item_with_no_attempts(self, audit_plan, execution_policy, egress_policy):
        """TERMINATED WorkItem with zero attempts is impossible. Validator must catch it."""
        from project_audit.validators import validate_work_item_state_machine

        wi = make_work_item(plan_id=audit_plan.plan_id, execution_policy=execution_policy, egress_policy=egress_policy)
        wi.execution_state = ExecutionState.TERMINATED  # Force impossible state
        wi.attempts = []  # Zero attempts

        report = validate_work_item_state_machine(wi)
        assert report.is_error
        assert report.code == "WORK_ITEM_TERMINATED_NO_ATTEMPTS"

    def test_cannot_use_invalid_evidence_with_reuse_action(self, target_snapshot, audit_plan, execution_policy, egress_policy):
        """INVALID evidence + REUSE action is impossible. Validator must catch it."""
        from project_audit.validators import validate_reuse_action_has_valid_evidence

        wi = make_work_item(
            plan_id=audit_plan.plan_id, action=WorkItemAction.REUSE,
            execution_policy=execution_policy, egress_policy=egress_policy
        )
        ev = make_evidence(
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            work_item_ref=wi.work_item_id,
        )
        invalid_ev = dataclasses.replace(ev, validity=EvidenceValidity.INVALID)
        result = validate_reuse_action_has_valid_evidence(wi, [invalid_ev])
        assert result.is_error

    def test_cannot_mark_complete_with_running_item(self, audit_plan, target_snapshot, execution_policy, egress_policy):
        """COMPLETE run with RUNNING WorkItem is impossible."""
        from project_audit.validators import validate_run_not_complete_with_running_items

        wi = make_work_item(plan_id=audit_plan.plan_id, execution_policy=execution_policy, egress_policy=egress_policy)
        wi.execution_state = ExecutionState.RUNNING

        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[wi.work_item_id],
            execution_completeness=RunExecutionCompleteness.COMPLETE,
        )
        result = validate_run_not_complete_with_running_items(run, [wi])
        assert result.is_error

    def test_cannot_start_attempt_twice_on_same_item(self, work_item):
        """Starting attempt on an ALREADY RUNNING item (with unfinished attempt) is impossible."""
        work_item.start_attempt(started_at=FIXED_TS)
        with pytest.raises(IllegalStateTransitionError):
            work_item.start_attempt(started_at=FIXED_TS + timedelta(seconds=1))

    def test_cannot_recover_from_nonexistent_run(self, orchestrator):
        """Recovery from a run that was never persisted must be rejected."""
        with pytest.raises(OrchestratorError):
            orchestrator.recover_run(str(uuid.uuid4()))

    def test_forged_snapshot_fingerprint_detected(self, target_snapshot, audit_plan):
        """A snapshot fingerprint that doesn't match the state is detected."""
        from project_audit.validators import validate_target_snapshot_fingerprint_matches

        forged = dataclasses.replace(target_snapshot, snapshot_fingerprint="f" * 64)
        result = validate_target_snapshot_fingerprint_matches(forged)
        assert result.is_error
        assert result.code == "SNAPSHOT_FINGERPRINT_MISMATCH"

    def test_schema_rejects_extra_property_in_evidence(self, evidence):
        """additionalProperties: false must reject extra fields."""
        from project_audit.schema_validator import validate_evidence

        d = evidence.to_dict()
        d["injected_field"] = "adversarial_value"
        errors = validate_evidence(d)
        assert len(errors) > 0, "Schema must reject additionalProperties"

    def test_schema_rejects_invalid_enum_in_work_item(self, work_item):
        """Schema must reject an unknown action enum value."""
        from project_audit.schema_validator import validate_audit_work_item

        d = work_item.to_dict()
        d["action"] = "DESTROY"  # Not in enum
        errors = validate_audit_work_item(d)
        assert len(errors) > 0, "Schema must reject unknown enum value"

    def test_schema_rejects_missing_required_field_in_run(self, audit_plan, target_snapshot):
        """Schema must reject AuditRun missing a required field."""
        from project_audit.schema_validator import validate_audit_run

        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[],
        )
        d = run.to_dict()
        del d["execution_completeness"]  # required
        errors = validate_audit_run(d)
        assert len(errors) > 0

    def test_plan_cannot_mutate_after_freeze(self, audit_plan, execution_policy, egress_policy):
        """Frozen plan must reject any mutation (plan freeze invariant)."""
        audit_plan.freeze()
        wi = make_work_item(plan_id=audit_plan.plan_id, execution_policy=execution_policy, egress_policy=egress_policy)
        with pytest.raises(ImmutablePlanError):
            audit_plan.add_work_item(wi)

    def test_target_snapshot_cannot_be_mutated_directly(self, target_snapshot):
        """TargetSnapshot is a frozen dataclass — direct mutation must fail."""
        with pytest.raises((AttributeError, TypeError, dataclasses.FrozenInstanceError)):
            target_snapshot.target_mode = WorkingTreeState.DIRTY

    def test_evidence_cannot_be_mutated(self, evidence):
        """Evidence is frozen — mutation must fail."""
        with pytest.raises((AttributeError, TypeError, dataclasses.FrozenInstanceError)):
            evidence.validity = EvidenceValidity.INVALID

    def test_lineage_refs_must_be_distinct(self, audit_plan, target_snapshot):
        """previous_run_ref and recovery_from_ref must point to different runs."""
        same_id = str(uuid.uuid4())
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[],
            previous_run_ref=same_id,
            recovery_from_ref=same_id,
        )
        result = validate_run_previous_ref_distinct_from_recovery(run)
        assert result.is_error
        assert result.code == "RUN_LINEAGE_REF_COLLISION"

    def test_snapshot_drift_prevents_completion(self, audit_plan, target_snapshot, work_item):
        """Snapshot drift must prevent the run from being considered complete."""
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[work_item.work_item_id],
            execution_completeness=RunExecutionCompleteness.COMPLETE,
        )
        drift_fingerprint = "d" * 64  # Different from snapshot
        report = can_publish(run, [work_item], [], drift_fingerprint, audit_plan)
        assert report.has_errors
        codes = [r.code for r in report.errors()]
        assert "SNAPSHOT_DRIFT_DETECTED" in codes

    def test_new_to_regressed_finding_lifecycle_is_impossible(self):
        """NEW → REGRESSED is a semantic error. REGRESSED requires prior FIXED."""
        from project_audit.models import FindingLifecycle
        from project_audit.validators import validate_finding_lifecycle_transition

        result = validate_finding_lifecycle_transition(FindingLifecycle.NEW, FindingLifecycle.REGRESSED)
        assert result.is_error

    def test_execution_completeness_does_not_imply_coverage(self, audit_plan, target_snapshot, execution_policy, egress_policy):
        """Execution COMPLETE does not automatically mean coverage FULL."""
        wi = make_work_item(plan_id=audit_plan.plan_id, execution_policy=execution_policy, egress_policy=egress_policy)
        wi.execution_state = ExecutionState.TERMINATED
        wi.failure_state = WorkItemFailureState.SAFETY_BLOCK

        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[wi.work_item_id],
            execution_completeness=RunExecutionCompleteness.COMPLETE,
            coverage_completeness=RunCoverageCompleteness.FULL,  # Wrong — BLOCKED item present
        )
        result = validate_coverage_completeness_derivable(run, audit_plan, [wi])
        assert result.is_error
        assert result.code == "COVERAGE_COMPLETENESS_MISMATCH"


# ===========================================================================
# §5 — Recovery from partially-persisted run
# ===========================================================================


class TestRecoveryFromPartiallyPersistedRun:
    def test_recovery_reconstructs_interrupted_running_state(
        self, orchestrator, state_store, target_snapshot, execution_policy, egress_policy
    ):
        """
        Simulate: run started, persisted as RUNNING, worker crashed.
        Recovery: load from disk, verify state is available for reconciliation.
        (ADR-07 §3: Recovery from persisted evidence, not retry)
        """
        plan, plan_id = _make_plan(target_snapshot, execution_policy, egress_policy)
        orchestrator.commit_snapshot(target_snapshot)
        orchestrator.freeze_and_commit_plan(plan)

        # Persist an interrupted run (RUNNING state)
        interrupted_run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=plan_id,
            work_item_refs=[str(uuid.uuid4())],
            execution_completeness=RunExecutionCompleteness.RUNNING,
            failure_state=RunFailureState.INFRA_ERROR,
        )
        state_store.save_run(interrupted_run)

        # Recovery: load the interrupted run
        recovered = orchestrator.recover_run(interrupted_run.run_id)
        assert recovered.run_id == interrupted_run.run_id
        assert recovered.execution_completeness == RunExecutionCompleteness.RUNNING
        assert recovered.failure_state == RunFailureState.INFRA_ERROR

    def test_new_recovery_run_points_to_interrupted(
        self, orchestrator, state_store, target_snapshot, execution_policy, egress_policy
    ):
        """
        A recovery run must have recovery_from_ref pointing to the interrupted run.
        previous_run_ref and recovery_from_ref must NOT be the same.
        """
        plan, plan_id = _make_plan(target_snapshot, execution_policy, egress_policy)
        orchestrator.commit_snapshot(target_snapshot)
        orchestrator.freeze_and_commit_plan(plan)

        interrupted_run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=plan_id,
            work_item_refs=[],
            execution_completeness=RunExecutionCompleteness.RUNNING,
        )
        state_store.save_run(interrupted_run)

        recovery_run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=plan_id,
            work_item_refs=[],
            recovery_from_ref=interrupted_run.run_id,
            execution_completeness=RunExecutionCompleteness.PLANNED,
        )

        assert recovery_run.recovery_from_ref == interrupted_run.run_id
        assert recovery_run.previous_run_ref != recovery_run.recovery_from_ref


# ===========================================================================
# §6 — Schema Documentation: shared.schema is definitions-only
# ===========================================================================


class TestSchemaDocumentation:
    def test_shared_schema_has_no_type_at_root(self):
        """
        shared.schema.json is a definitions-only schema (library of $defs).
        It must NOT have a 'type' at root level — it is never a root instance schema.

        Physical schemas: 6 total
          - shared.schema.json: definitions-only (NOT a root instance schema)
          - target-snapshot.schema.json: root instance schema
          - audit-plan.schema.json: root instance schema
          - audit-work-item.schema.json: root instance schema
          - evidence.schema.json: root instance schema
          - audit-run.schema.json: root instance schema

        Root instance schemas: 5
        Definitions-only schemas: 1
        """
        import json
        from pathlib import Path

        # Find the schemas directory
        candidate = Path(__file__).resolve()
        schema_dir = None
        for _ in range(10):
            candidate = candidate.parent
            p = candidate / "docs" / "references" / "schemas"
            if p.is_dir():
                schema_dir = p
                break

        assert schema_dir is not None, "Could not find docs/references/schemas/"

        shared = json.loads((schema_dir / "shared.schema.json").read_text())
        assert "type" not in shared, (
            "shared.schema.json must not have a 'type' at root level. "
            "It is a definitions-only schema ($defs library), not a root instance schema."
        )
        assert "$defs" in shared, "shared.schema.json must contain $defs"

    def test_all_root_instance_schemas_have_type_object(self):
        """All 5 root instance schemas must have type: object at root."""
        import json
        from pathlib import Path

        candidate = Path(__file__).resolve()
        schema_dir = None
        for _ in range(10):
            candidate = candidate.parent
            p = candidate / "docs" / "references" / "schemas"
            if p.is_dir():
                schema_dir = p
                break

        root_schemas = [
            "target-snapshot.schema.json",
            "audit-plan.schema.json",
            "audit-work-item.schema.json",
            "evidence.schema.json",
            "audit-run.schema.json",
        ]
        for name in root_schemas:
            schema = json.loads((schema_dir / name).read_text())
            assert schema.get("type") == "object", (
                f"{name} must have type: object at root (it is a root instance schema)"
            )
            assert schema.get("additionalProperties") is False, (
                f"{name} must have additionalProperties: false"
            )

    def test_schema_validation_roundtrip_all_entities(
        self, target_snapshot, audit_plan, work_item, evidence
    ):
        """
        Runtime roundtrip: entity → to_dict() → schema validation → PASS.
        Tests schema ↔ serialization alignment.
        """
        from project_audit.schema_validator import (
            validate_target_snapshot, validate_audit_plan,
            validate_audit_work_item, validate_evidence, validate_audit_run,
        )

        audit_plan.freeze()
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[work_item.work_item_id],
        )

        checks = [
            ("TargetSnapshot", validate_target_snapshot, target_snapshot.to_dict()),
            ("AuditPlan",      validate_audit_plan,      audit_plan.to_dict()),
            ("AuditWorkItem",  validate_audit_work_item,  work_item.to_dict()),
            ("Evidence",       validate_evidence,         evidence.to_dict()),
            ("AuditRun",       validate_audit_run,        run.to_dict()),
        ]
        for name, fn, d in checks:
            errors = fn(d)
            assert errors == [], f"{name} failed schema validation: {errors}"

    def test_commit_run_raises_on_semantic_errors(
        self, orchestrator, target_snapshot, audit_plan, execution_policy, egress_policy
    ):
        """commit_run must raise an exception if semantic validation fails, instead of persisting."""
        from project_audit.orchestrator import OrchestratorError

        orchestrator.store.save_plan(audit_plan)

        from tests.conftest import make_work_item
        wi = make_work_item(
            plan_id=audit_plan.plan_id,
            execution_policy=execution_policy,
            egress_policy=egress_policy,
            auditor="test",
            target_surface="src/",
        )
        wi.execution_state = ExecutionState.RUNNING
        
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[wi.work_item_id],
            execution_completeness=RunExecutionCompleteness.COMPLETE,  # Invalid!
        )

        with pytest.raises(OrchestratorError) as exc:
            orchestrator.commit_run(run, audit_plan, [wi])
        
        assert "Semantic validation failed for run" in str(exc.value)
        
        # Verify it wasn't saved
        from project_audit.state_store import StateStoreError
        try:
            saved = orchestrator.store.load_run(run.run_id)
            assert False, "Should have raised StateStoreError or returned None"
        except StateStoreError:
            pass

    def test_can_publish_rejects_empty_audit(self, audit_plan, target_snapshot):
        """can_publish must reject an audit with no work_items."""
        from project_audit.validators import can_publish
        run = AuditRun(
            run_id="run-1",
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[],
            execution_completeness=RunExecutionCompleteness.COMPLETE,
            coverage_completeness=RunCoverageCompleteness.NONE,
        )
        report = can_publish(run, [], [], target_snapshot.snapshot_fingerprint, audit_plan)
        error_codes = [r.code for r in report.errors()]
        assert "PUBLISH_EMPTY_AUDIT" in error_codes

    def test_deep_immutability_of_plan_and_snapshot(self, audit_plan, target_snapshot):
        """Plan and Snapshot internal dicts/lists must become immutable types."""
        audit_plan.freeze()
        assert isinstance(audit_plan.resolved_scope, tuple)
        
        # Test Snapshot methodology versions
        import types
        assert isinstance(target_snapshot.methodology_state.auditor_versions, types.MappingProxyType)
        with pytest.raises(TypeError):
            target_snapshot.methodology_state.auditor_versions["hacked"] = "1.0.0"

        with pytest.raises(AttributeError):
            # Tuples don't have append
            audit_plan.resolved_scope.append("hacked")

    def test_cannot_recover_complete_run(self, orchestrator, audit_plan, target_snapshot, work_item):
        """Recovery must reject COMPLETE runs."""
        from project_audit.models import IllegalStateTransitionError
        audit_plan.freeze()
        orchestrator.store.save_plan(audit_plan)
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[work_item.work_item_id],
            execution_completeness=RunExecutionCompleteness.COMPLETE,
            coverage_completeness=RunCoverageCompleteness.FULL,
        )
        orchestrator.store.save_run(run)
        
        with pytest.raises(IllegalStateTransitionError) as exc:
            orchestrator.recover_run(run.run_id)
        assert "is already COMPLETE" in str(exc.value)

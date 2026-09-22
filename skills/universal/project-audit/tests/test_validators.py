"""
test_validators.py — Tests for Semantic Validators

Covers all families from semantic-validators.md:
  §1 Identity & Canonical Consistency
  §2 Referential Integrity
  §3 State Machine
  §4 Incremental / Reuse Validity
  §5 Evidence Lifecycle
  §6 Coverage Completeness
  §7 Attempt Consistency
  §8 Trust, Safety & Egress
  §9 Publication Eligibility
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from project_audit.models import (
    ApplicabilityDecision,
    AuditPlan,
    AuditRun,
    AuditWorkItem,
    CredentialAccess,
    EgressDestination,
    EgressPolicy,
    Evidence,
    EvidenceValidity,
    ExecutionPolicy,
    ExecutionState,
    FilesystemAccess,
    FindingLifecycle,
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
from project_audit.validators import (
    ValidationLevel,
    can_publish,
    validate_attempt_ordering,
    validate_coverage_completeness_derivable,
    validate_coverage_not_full_with_blocked_items,
    validate_egress_policy,
    validate_evidence_invalid_not_reused,
    validate_evidence_work_item_ref,
    validate_execution_gate,
    validate_finding_lifecycle_transition,
    validate_reuse_action_has_valid_evidence,
    validate_run_not_complete_with_running_items,
    validate_run_recovery_ref,
    validate_run_previous_ref_distinct_from_recovery,
    validate_snapshot_drift,
    validate_target_snapshot_fingerprint_matches,
    validate_target_snapshot_immutability,
    validate_work_item_plan_ref,
    validate_work_item_state_machine,
)
from tests.conftest import make_evidence, make_work_item, FIXED_TS


# ---------------------------------------------------------------------------
# §1 — Identity & Canonical Consistency
# ---------------------------------------------------------------------------


class TestSnapshotValidation:
    def test_valid_snapshot_passes(self, target_snapshot):
        r = validate_target_snapshot_immutability(target_snapshot)
        assert r.is_pass

    def test_fingerprint_match_passes(self, target_snapshot):
        r = validate_target_snapshot_fingerprint_matches(target_snapshot)
        assert r.is_pass

    def test_missing_fingerprint_produces_error(self, target_snapshot):
        # Can't mutate frozen, so we patch via object.__setattr__
        import dataclasses
        bad_snap = dataclasses.replace(target_snapshot, snapshot_fingerprint="")
        r = validate_target_snapshot_immutability(bad_snap)
        assert r.is_error

    def test_wrong_fingerprint_produces_error(self, target_snapshot):
        import dataclasses
        bad_snap = dataclasses.replace(target_snapshot, snapshot_fingerprint="c" * 64)
        r = validate_target_snapshot_fingerprint_matches(bad_snap)
        assert r.is_error
        assert r.code == "SNAPSHOT_FINGERPRINT_MISMATCH"


# ---------------------------------------------------------------------------
# §2 — Referential Integrity
# ---------------------------------------------------------------------------


class TestReferentialIntegrity:
    def test_valid_plan_ref(self, work_item, audit_plan):
        r = validate_work_item_plan_ref(work_item, [audit_plan.plan_id])
        assert r.is_pass

    def test_dangling_plan_ref_produces_error(self, work_item):
        r = validate_work_item_plan_ref(work_item, [str(uuid.uuid4())])
        assert r.is_error
        assert r.code == "WORK_ITEM_DANGLING_PLAN_REF"

    def test_valid_evidence_work_item_ref(self, evidence, work_item):
        r = validate_evidence_work_item_ref(evidence, [work_item.work_item_id])
        assert r.is_pass

    def test_dangling_evidence_work_item_ref(self, evidence):
        r = validate_evidence_work_item_ref(evidence, [str(uuid.uuid4())])
        assert r.is_error
        assert r.code == "EVIDENCE_DANGLING_WORK_ITEM_REF"

    def test_recovery_ref_must_point_to_interrupted_run(self, audit_plan, target_snapshot):
        interrupted_run_id = str(uuid.uuid4())
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[],
            recovery_from_ref=interrupted_run_id,
        )
        # known but NOT interrupted
        r = validate_run_recovery_ref(run, [interrupted_run_id], interrupted_run_ids=[])
        assert r.is_error
        assert r.code == "RUN_RECOVERY_REF_NOT_INTERRUPTED"

    def test_valid_recovery_ref(self, audit_plan, target_snapshot):
        interrupted_run_id = str(uuid.uuid4())
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[],
            recovery_from_ref=interrupted_run_id,
        )
        r = validate_run_recovery_ref(
            run, [interrupted_run_id], interrupted_run_ids=[interrupted_run_id]
        )
        assert r.is_pass

    def test_previous_ref_and_recovery_ref_cannot_be_same(self, audit_plan, target_snapshot):
        same_id = str(uuid.uuid4())
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[],
            previous_run_ref=same_id,
            recovery_from_ref=same_id,
        )
        r = validate_run_previous_ref_distinct_from_recovery(run)
        assert r.is_error
        assert r.code == "RUN_LINEAGE_REF_COLLISION"


# ---------------------------------------------------------------------------
# §3 — State Machine
# ---------------------------------------------------------------------------


class TestStateMachineValidation:
    def test_running_with_active_attempt_passes(self, work_item):
        work_item.start_attempt(started_at=FIXED_TS)
        r = validate_work_item_state_machine(work_item)
        assert r.is_pass

    def test_running_without_attempts_fails(self, work_item):
        # Force bad state via direct assignment
        work_item.execution_state = ExecutionState.RUNNING
        r = validate_work_item_state_machine(work_item)
        assert r.is_error
        assert r.code == "WORK_ITEM_RUNNING_NO_ATTEMPTS"

    def test_complete_run_with_running_items_fails(self, audit_plan, target_snapshot, work_item):
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[work_item.work_item_id],
            execution_completeness=RunExecutionCompleteness.COMPLETE,
        )
        work_item.execution_state = ExecutionState.RUNNING
        r = validate_run_not_complete_with_running_items(run, [work_item])
        assert r.is_error
        assert r.code == "RUN_COMPLETE_WITH_RUNNING_ITEMS"


# ---------------------------------------------------------------------------
# §4 — Incremental / Reuse Validity
# ---------------------------------------------------------------------------


class TestReuseValidity:
    def test_reuse_with_valid_evidence_passes(self, audit_plan, target_snapshot):
        wi = make_work_item(plan_id=audit_plan.plan_id, action=WorkItemAction.REUSE)
        ev = make_evidence(target_snapshot_ref=target_snapshot.snapshot_fingerprint, work_item_ref=wi.work_item_id)
        r = validate_reuse_action_has_valid_evidence(wi, [ev])
        assert r.is_pass

    def test_reuse_without_evidence_is_error(self, audit_plan):
        wi = make_work_item(plan_id=audit_plan.plan_id, action=WorkItemAction.REUSE)
        r = validate_reuse_action_has_valid_evidence(wi, [])
        assert r.is_error
        assert r.code == "REUSE_NO_PRIOR_EVIDENCE"

    def test_reuse_with_invalid_evidence_is_error(self, audit_plan, target_snapshot):
        wi = make_work_item(plan_id=audit_plan.plan_id, action=WorkItemAction.REUSE)
        ev = make_evidence(target_snapshot_ref=target_snapshot.snapshot_fingerprint, work_item_ref=wi.work_item_id)
        import dataclasses
        invalid_ev = dataclasses.replace(ev, validity=EvidenceValidity.INVALID)
        r = validate_reuse_action_has_valid_evidence(wi, [invalid_ev])
        assert r.is_error
        assert r.code == "REUSE_INVALID_EVIDENCE"

    def test_reuse_with_not_determinable_evidence_is_error(self, audit_plan, target_snapshot):
        """Fail-safe: NOT_DETERMINABLE must require REAUDIT."""
        wi = make_work_item(plan_id=audit_plan.plan_id, action=WorkItemAction.REUSE)
        ev = make_evidence(target_snapshot_ref=target_snapshot.snapshot_fingerprint, work_item_ref=wi.work_item_id)
        import dataclasses
        nd_ev = dataclasses.replace(ev, validity=EvidenceValidity.NOT_DETERMINABLE)
        r = validate_reuse_action_has_valid_evidence(wi, [nd_ev])
        assert r.is_error
        assert r.code == "REUSE_UNDETERMINABLE_EVIDENCE"

    def test_non_reuse_action_skips_check(self, audit_plan):
        wi = make_work_item(plan_id=audit_plan.plan_id, action=WorkItemAction.REAUDIT)
        r = validate_reuse_action_has_valid_evidence(wi, [])
        assert r.is_pass


# ---------------------------------------------------------------------------
# §5 — Evidence & Finding Lifecycle Integrity
# ---------------------------------------------------------------------------


class TestEvidenceLifecycle:
    def test_invalidate_not_equals_fixed(self, audit_plan, target_snapshot):
        """INVALIDATE ≠ FIXED: invalid evidence + REUSE must error."""
        wi = make_work_item(plan_id=audit_plan.plan_id, action=WorkItemAction.REUSE)
        ev = make_evidence(target_snapshot_ref=target_snapshot.snapshot_fingerprint, work_item_ref=wi.work_item_id)
        import dataclasses
        invalid_ev = dataclasses.replace(ev, validity=EvidenceValidity.INVALID)
        r = validate_evidence_invalid_not_reused(wi, [invalid_ev])
        assert r.is_error
        assert "INVALIDATE" in r.message or "INVALID" in r.message

    def test_finding_new_to_regressed_is_error(self):
        r = validate_finding_lifecycle_transition(FindingLifecycle.NEW, FindingLifecycle.REGRESSED)
        assert r.is_error
        assert r.code == "FINDING_LIFECYCLE_INVALID_REGRESSION"

    def test_finding_fixed_to_regressed_is_valid(self):
        r = validate_finding_lifecycle_transition(FindingLifecycle.FIXED, FindingLifecycle.REGRESSED)
        assert r.is_pass

    def test_finding_new_to_persisting_is_valid(self):
        r = validate_finding_lifecycle_transition(FindingLifecycle.NEW, FindingLifecycle.PERSISTING)
        assert r.is_pass


# ---------------------------------------------------------------------------
# §6 — Coverage Completeness
# ---------------------------------------------------------------------------


class TestCoverageCompleteness:
    def test_full_coverage_with_some_blocked_items_is_error(self, audit_plan, target_snapshot, work_item):
        from tests.conftest import make_work_item
        wi_success = make_work_item(plan_id=audit_plan.plan_id)
        
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[work_item.work_item_id, wi_success.work_item_id],
            coverage_completeness=RunCoverageCompleteness.FULL,
        )
        work_item.failure_state = WorkItemFailureState.SAFETY_BLOCK
        wi_success.failure_state = WorkItemFailureState.NONE
        
        r = validate_coverage_not_full_with_blocked_items(run, [work_item, wi_success])
        assert r.is_error
        assert r.code == "COVERAGE_FULL_WITH_BLOCKED_ITEMS"

    def test_partial_coverage_with_mixed_blocked_items_passes(self, audit_plan, target_snapshot, work_item):
        from tests.conftest import make_work_item
        wi_success = make_work_item(plan_id=audit_plan.plan_id)
        
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[work_item.work_item_id, wi_success.work_item_id],
            coverage_completeness=RunCoverageCompleteness.PARTIAL,
        )
        work_item.failure_state = WorkItemFailureState.SAFETY_BLOCK
        wi_success.failure_state = WorkItemFailureState.NONE
        
        r = validate_coverage_not_full_with_blocked_items(run, [work_item, wi_success])
        assert r.is_pass

    def test_all_blocked_items_requires_none_coverage(self, audit_plan, target_snapshot, work_item):
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[work_item.work_item_id],
            coverage_completeness=RunCoverageCompleteness.PARTIAL, # Claim partial, should be NONE
        )
        work_item.failure_state = WorkItemFailureState.SAFETY_BLOCK
        r = validate_coverage_not_full_with_blocked_items(run, [work_item])
        assert r.is_error
        assert r.code == "COVERAGE_MUST_BE_NONE_ALL_BLOCKED"

    def test_execution_completeness_does_not_imply_coverage_completeness(
        self, audit_plan, target_snapshot, work_item
    ):
        """Execution completeness cannot silently imply coverage completeness. (§33)"""
        # Mix items so coverage should be PARTIAL
        from tests.conftest import make_work_item
        wi_success = make_work_item(plan_id=audit_plan.plan_id)
        wi_success.execution_state = ExecutionState.TERMINATED
        wi_success.failure_state = WorkItemFailureState.NONE
        
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[work_item.work_item_id, wi_success.work_item_id],
            execution_completeness=RunExecutionCompleteness.COMPLETE,
            coverage_completeness=RunCoverageCompleteness.FULL,  # claimed full but one is blocked
        )
        
        work_item.execution_state = ExecutionState.TERMINATED
        work_item.failure_state = WorkItemFailureState.SAFETY_BLOCK
        
        r = validate_coverage_completeness_derivable(run, audit_plan, [work_item, wi_success])
        assert r.is_error
        assert r.code == "COVERAGE_COMPLETENESS_MISMATCH"


# ---------------------------------------------------------------------------
# §7 — Budget & Attempt Consistency
# ---------------------------------------------------------------------------


class TestAttemptConsistency:
    def test_single_attempt_ordering_passes(self, work_item):
        work_item.start_attempt(started_at=FIXED_TS)
        r = validate_attempt_ordering(work_item)
        assert r.is_pass

    def test_temporal_ordering_violation_is_error(self, work_item):
        t1 = FIXED_TS
        t2 = t1 + timedelta(seconds=10)
        t3 = t1 + timedelta(seconds=5)  # Before t2 — violation

        a1 = work_item.start_attempt(started_at=t1)
        a1.finish(finished_at=t2, exit_code=0)
        work_item.terminate()
        # Bypass start_attempt validation to directly set up the violation
        from project_audit.models import Attempt
        a2 = Attempt(attempt_id=str(uuid.uuid4()), started_at=t3)
        work_item.execution_state = ExecutionState.RUNNING
        work_item.attempts.append(a2)
        r = validate_attempt_ordering(work_item)
        assert r.is_error
        assert r.code == "ATTEMPT_ORDERING_TEMPORAL_VIOLATION"


# ---------------------------------------------------------------------------
# §8 — Trust, Safety & Egress
# ---------------------------------------------------------------------------


class TestSafetyAndEgress:
    def test_safe_execution_policy_passes(self, work_item):
        r = validate_execution_gate(work_item)
        assert r.is_pass

    def test_egress_denied_with_sensitive_data(self, work_item):
        r = validate_egress_policy(work_item, data_is_sensitive=True)
        assert r.is_error
        assert r.code == "EGRESS_SENSITIVE_DATA_DENIED"

    def test_egress_allowed_when_policy_permits(self, audit_plan):
        wi = make_work_item(
            plan_id=audit_plan.plan_id,
            egress_policy=EgressPolicy(
                destination=EgressDestination.APPROVED_EXTERNAL,
                allow_sensitive=True,
            ),
        )
        r = validate_egress_policy(wi, data_is_sensitive=True)
        assert r.is_pass

    def test_snapshot_drift_detected(self, target_snapshot, audit_plan):
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[],
        )
        r = validate_snapshot_drift(run, "d" * 64)  # Different fingerprint
        assert r.is_error
        assert r.code == "SNAPSHOT_DRIFT_DETECTED"

    def test_no_snapshot_drift_when_same(self, target_snapshot, audit_plan):
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[],
        )
        r = validate_snapshot_drift(run, target_snapshot.snapshot_fingerprint)
        assert r.is_pass


# ---------------------------------------------------------------------------
# §9 — Publication Eligibility
# ---------------------------------------------------------------------------


class TestPublicationEligibility:
    def _make_run(self, audit_plan, target_snapshot, completeness=RunExecutionCompleteness.COMPLETE):
        return AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[],
            execution_completeness=completeness,
            coverage_completeness=RunCoverageCompleteness.FULL,
            failure_state=RunFailureState.NONE,
        )

    def test_complete_clean_run_can_publish(self, audit_plan, target_snapshot, work_item):
        run = self._make_run(audit_plan, target_snapshot)
        report = can_publish(run, [work_item], [], target_snapshot.snapshot_fingerprint, audit_plan)
        assert not report.has_errors

    def test_snapshot_drift_blocks_publication(self, audit_plan, target_snapshot, work_item):
        run = self._make_run(audit_plan, target_snapshot)
        report = can_publish(run, [work_item], [], "d" * 64, audit_plan)
        error_codes = [r.code for r in report.errors()]
        assert "SNAPSHOT_DRIFT_DETECTED" in error_codes

    def test_incomplete_execution_blocks_publication(self, audit_plan, target_snapshot, work_item):
        run = self._make_run(audit_plan, target_snapshot, RunExecutionCompleteness.PARTIAL)
        report = can_publish(run, [work_item], [], target_snapshot.snapshot_fingerprint, audit_plan)
        error_codes = [r.code for r in report.errors()]
        assert "PUBLISH_EXECUTION_INCOMPLETE" in error_codes

    def test_failed_work_items_block_publication(self, audit_plan, target_snapshot, work_item):
        run = self._make_run(audit_plan, target_snapshot)
        work_item.execution_state = ExecutionState.TERMINATED
        work_item.failure_state = WorkItemFailureState.INFRA_ERROR
        report = can_publish(run, [work_item], [], target_snapshot.snapshot_fingerprint, audit_plan)
        error_codes = [r.code for r in report.errors()]
        assert "PUBLISH_HAS_FAILED_ITEMS" in error_codes

    def test_run_with_failure_state_blocks_publication(self, audit_plan, target_snapshot, work_item):
        run = self._make_run(audit_plan, target_snapshot)
        run.failure_state = RunFailureState.SNAPSHOT_DRIFT
        report = can_publish(run, [work_item], [], target_snapshot.snapshot_fingerprint, audit_plan)
        error_codes = [r.code for r in report.errors()]
        assert "PUBLISH_RUN_FAILURE_STATE" in error_codes

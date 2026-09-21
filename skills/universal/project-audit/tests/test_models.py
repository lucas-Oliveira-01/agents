"""
test_models.py — Tests for domain model invariants

Covers:
  - TargetSnapshot immutability (§8, semantic-validators §1)
  - AuditPlan freeze semantics (§9)
  - AuditWorkItem state machine (§10, §11)
  - Attempt ordering invariants (§11, §33)
  - RETRY ≠ RECOVERY (§12)
  - Evidence immutability (§14)
  - Enum distinctness (§47)
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from project_audit.models import (
    AuditPlan,
    AuditWorkItem,
    Attempt,
    Evidence,
    EvidenceValidity,
    ExecutionState,
    ImmutablePlanError,
    IllegalAttemptOrderError,
    IllegalStateTransitionError,
    MethodologyState,
    ProjectState,
    Provenance,
    SubmoduleState,
    TargetMode,
    TargetSnapshot,
    TrackedInputFingerprint,
    WorkItemAction,
    WorkItemFailureState,
    WorkingTreeState,
)
from tests.conftest import make_project_state, make_methodology_state, make_work_item, FIXED_TS


# ---------------------------------------------------------------------------
# TargetSnapshot — Immutability
# ---------------------------------------------------------------------------


class TestTargetSnapshotImmutability:
    def test_is_frozen_dataclass(self, target_snapshot):
        """TargetSnapshot must be immutable (frozen dataclass)."""
        with pytest.raises((AttributeError, TypeError)):
            target_snapshot.target_mode = TargetMode.WORKTREE

    def test_fingerprint_is_deterministic(self):
        """Same input -> same fingerprint always (determinism §30)."""
        ps = make_project_state()
        ms = make_methodology_state()
        s1 = TargetSnapshot.create(TargetMode.COMMIT, ps, ms)
        s2 = TargetSnapshot.create(TargetMode.COMMIT, ps, ms)
        assert s1.snapshot_fingerprint == s2.snapshot_fingerprint

    def test_different_inputs_produce_different_fingerprints(self):
        """Different project state -> different fingerprint."""
        ps1 = make_project_state(revision="aaa")
        ps2 = make_project_state(revision="bbb")
        ms = make_methodology_state()
        s1 = TargetSnapshot.create(TargetMode.COMMIT, ps1, ms)
        s2 = TargetSnapshot.create(TargetMode.COMMIT, ps2, ms)
        assert s1.snapshot_fingerprint != s2.snapshot_fingerprint

    def test_methodology_change_changes_fingerprint(self):
        """Different methodology -> different fingerprint (ADR-06)."""
        ps = make_project_state()
        ms1 = MethodologyState("1.0.0", {"auditor": "0.1"}, "1.0.0")
        ms2 = MethodologyState("2.0.0", {"auditor": "0.1"}, "1.0.0")
        s1 = TargetSnapshot.create(TargetMode.COMMIT, ps, ms1)
        s2 = TargetSnapshot.create(TargetMode.COMMIT, ps, ms2)
        assert s1.snapshot_fingerprint != s2.snapshot_fingerprint

    def test_fingerprint_is_64_hex_chars(self, target_snapshot):
        fp = target_snapshot.snapshot_fingerprint
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_to_dict_roundtrip_has_required_fields(self, target_snapshot):
        d = target_snapshot.to_dict()
        assert "snapshot_fingerprint" in d
        assert "target_mode" in d
        assert "project_state" in d
        assert "methodology_state" in d


# ---------------------------------------------------------------------------
# AuditPlan — Frozen-at-start
# ---------------------------------------------------------------------------


class TestAuditPlanFreeze:
    def test_unfrozen_plan_allows_mutations(self, audit_plan):
        """Plan before freeze allows work item addition."""
        item = make_work_item(plan_id=audit_plan.plan_id)
        audit_plan.add_work_item(item)
        assert len(audit_plan.work_items) == 1

    def test_freeze_sets_frozen_at(self, audit_plan):
        assert not audit_plan.is_frozen
        audit_plan.freeze()
        assert audit_plan.is_frozen
        assert audit_plan.frozen_at is not None

    def test_frozen_plan_rejects_add_work_item(self, audit_plan):
        audit_plan.freeze()
        item = make_work_item(plan_id=audit_plan.plan_id)
        with pytest.raises(ImmutablePlanError):
            audit_plan.add_work_item(item)

    def test_cannot_freeze_twice(self, audit_plan):
        audit_plan.freeze()
        with pytest.raises(ImmutablePlanError):
            audit_plan.freeze()

    def test_to_dict_includes_frozen_at_when_frozen(self, audit_plan):
        audit_plan.freeze(at=FIXED_TS)
        d = audit_plan.to_dict()
        assert "frozen_at" in d
        assert d["frozen_at"] == FIXED_TS.isoformat()


# ---------------------------------------------------------------------------
# AuditWorkItem — State Machine
# ---------------------------------------------------------------------------


class TestAuditWorkItemStateMachine:
    def test_initial_state_is_planned(self, work_item):
        assert work_item.execution_state == ExecutionState.PLANNED

    def test_valid_transition_planned_to_running(self, work_item):
        work_item.transition(ExecutionState.RUNNING)
        assert work_item.execution_state == ExecutionState.RUNNING

    def test_valid_transition_running_to_terminated(self, work_item):
        work_item.transition(ExecutionState.RUNNING)
        work_item.transition(ExecutionState.TERMINATED)
        assert work_item.execution_state == ExecutionState.TERMINATED

    def test_invalid_transition_planned_to_terminated(self, work_item):
        with pytest.raises(IllegalStateTransitionError):
            work_item.transition(ExecutionState.TERMINATED)

    def test_invalid_transition_terminated_to_running(self, work_item):
        work_item.transition(ExecutionState.RUNNING)
        work_item.transition(ExecutionState.TERMINATED)
        with pytest.raises(IllegalStateTransitionError):
            work_item.transition(ExecutionState.RUNNING)

    def test_terminated_is_terminal_cannot_start_attempt(self, work_item):
        """Cannot call start_attempt() on a TERMINATED WorkItem without retry."""
        now = FIXED_TS
        attempt = work_item.start_attempt(started_at=now)
        attempt.finish(finished_at=now, exit_code=0)
        work_item.terminate()
        with pytest.raises(IllegalStateTransitionError):
            work_item.start_attempt(started_at=now)


# ---------------------------------------------------------------------------
# Attempt Ordering Invariants (§11, §33)
# ---------------------------------------------------------------------------


class TestAttemptOrdering:
    def test_first_attempt_succeeds(self, work_item):
        now = FIXED_TS
        attempt = work_item.start_attempt(started_at=now)
        assert attempt.attempt_id is not None
        assert len(work_item.attempts) == 1

    def test_second_attempt_cannot_start_before_first_finishes(self, work_item):
        now = FIXED_TS
        attempt1 = work_item.start_attempt(started_at=now)
        # attempt1 is not yet finished
        with pytest.raises(IllegalStateTransitionError):
            work_item.start_attempt(started_at=now + timedelta(seconds=1))

    def test_second_attempt_cannot_start_before_first_finished_time(self, work_item):
        """Temporal ordering: attempt[i].started_at >= attempt[i-1].finished_at.

        The model itself raises IllegalAttemptOrderError when start_attempt() is called
        with a timestamp before the previous attempt finished. This is the primary guard.
        The semantic validator also detects this if bad state is injected directly.
        """
        t1 = FIXED_TS
        t2 = t1 + timedelta(seconds=10)
        t_bad = t1 + timedelta(seconds=5)  # Before t2 (finish time of attempt 1)

        # 1. The model guards at attempt creation time
        work_item2 = make_work_item(plan_id=work_item.plan_ref)
        a1 = work_item2.start_attempt(started_at=t1)
        a1.finish(finished_at=t2, exit_code=0)
        work_item2.terminate()
        with pytest.raises(IllegalAttemptOrderError):
            work_item2.retry_attempt(started_at=t_bad)

        # 2. The semantic validator also detects injected bad state (defense in depth)
        from project_audit.models import Attempt
        from project_audit.validators import validate_attempt_ordering
        work_item3 = make_work_item(plan_id=work_item.plan_ref)
        a1b = work_item3.start_attempt(started_at=t1)
        a1b.finish(finished_at=t2, exit_code=0)
        work_item3.terminate()
        # Bypass model guard to inject temporal violation
        bad_attempt = Attempt(attempt_id=str(uuid.uuid4()), started_at=t_bad)
        work_item3.execution_state = ExecutionState.RUNNING
        work_item3.attempts.append(bad_attempt)
        report = validate_attempt_ordering(work_item3)
        assert report.is_error

    def test_attempt_history_is_preserved(self, work_item):
        """Previous attempts are never overwritten."""
        t1 = FIXED_TS
        t2 = t1 + timedelta(seconds=5)

        attempt1 = work_item.start_attempt(started_at=t1)
        attempt1.fail(finished_at=t2, reason="INFRA_ERROR")
        work_item.terminate(WorkItemFailureState.INFRA_ERROR)
        # Retry
        attempt2 = work_item.retry_attempt(started_at=t2)
        attempt2.finish(finished_at=t2 + timedelta(seconds=5), exit_code=0)
        work_item.terminate()

        assert len(work_item.attempts) == 2
        assert work_item.attempts[0].is_failed
        assert not work_item.attempts[1].is_failed

    def test_attempt_cannot_finish_twice(self, work_item):
        now = FIXED_TS
        attempt = work_item.start_attempt(started_at=now)
        attempt.finish(finished_at=now, exit_code=0)
        with pytest.raises(ValueError):
            attempt.finish(finished_at=now, exit_code=0)


# ---------------------------------------------------------------------------
# RETRY ≠ RECOVERY (§12, §33)
# ---------------------------------------------------------------------------


class TestRetryVsRecovery:
    def test_retry_requires_terminated_state(self, work_item):
        """retry_attempt() must require TERMINATED state."""
        with pytest.raises(IllegalStateTransitionError):
            work_item.retry_attempt()

    def test_retry_creates_new_attempt_after_terminate(self, work_item):
        now = FIXED_TS
        a1 = work_item.start_attempt(started_at=now)
        a1.fail(finished_at=now, reason="INFRA_ERROR")
        work_item.terminate(WorkItemFailureState.INFRA_ERROR)
        assert work_item.execution_state == ExecutionState.TERMINATED

        a2 = work_item.retry_attempt(started_at=now)
        assert work_item.execution_state == ExecutionState.RUNNING
        assert len(work_item.attempts) == 2

    def test_retry_resets_failure_state(self, work_item):
        now = FIXED_TS
        a1 = work_item.start_attempt(started_at=now)
        a1.fail(finished_at=now, reason="INFRA_ERROR")
        work_item.terminate(WorkItemFailureState.INFRA_ERROR)
        work_item.retry_attempt(started_at=now)
        # Failure state is cleared on retry
        assert work_item.failure_state == WorkItemFailureState.NONE


# ---------------------------------------------------------------------------
# Evidence immutability (§14)
# ---------------------------------------------------------------------------


class TestEvidenceImmutability:
    def test_evidence_is_frozen_dataclass(self, evidence):
        """Evidence is immutable (frozen dataclass)."""
        with pytest.raises((AttributeError, TypeError)):
            evidence.validity = EvidenceValidity.INVALID

    def test_evidence_has_required_fields(self, evidence):
        d = evidence.to_dict()
        for field in ["evidence_id", "target_snapshot_ref", "work_item_ref",
                      "source_refs", "dependencies", "validity", "provenance", "fingerprint"]:
            assert field in d


# ---------------------------------------------------------------------------
# Enum distinctness (§47)
# ---------------------------------------------------------------------------


class TestEnumDistinctness:
    def test_work_item_actions_are_distinct(self):
        assert WorkItemAction.REUSE != WorkItemAction.REVALIDATE
        assert WorkItemAction.REVALIDATE != WorkItemAction.REAUDIT

    def test_execution_states_are_distinct(self):
        assert ExecutionState.PLANNED != ExecutionState.RUNNING
        assert ExecutionState.RUNNING != ExecutionState.TERMINATED

    def test_failure_states_are_distinct(self):
        assert WorkItemFailureState.NONE != WorkItemFailureState.INFRA_ERROR
        assert WorkItemFailureState.INFRA_ERROR != WorkItemFailureState.SAFETY_BLOCK
        assert WorkItemFailureState.SAFETY_BLOCK != WorkItemFailureState.BUDGET_EXHAUSTED

    def test_evidence_validity_are_distinct(self):
        assert EvidenceValidity.VALID != EvidenceValidity.INVALID
        assert EvidenceValidity.INVALID != EvidenceValidity.NOT_DETERMINABLE

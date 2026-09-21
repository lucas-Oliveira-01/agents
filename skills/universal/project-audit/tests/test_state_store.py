"""
test_state_store.py — Tests for the State Store persistence and recovery

Covers:
  - Atomic write (tempfile + rename)
  - Roundtrip persist + load for all entity types
  - Recovery: load run after simulated crash
  - Listing entity IDs
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from project_audit.models import (
    AuditRun,
    EvidenceValidity,
    ExecutionState,
    RunBudgetState,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    RunPublicationState,
    WorkItemFailureState,
)
from project_audit.state_store import StateStore, StateStoreError
from tests.conftest import make_evidence, FIXED_TS


class TestStateStoreRoundtrip:
    """Each entity must survive a save -> load cycle with no data loss."""

    def test_snapshot_roundtrip(self, state_store, target_snapshot):
        state_store.save_snapshot(target_snapshot)
        loaded = state_store.load_snapshot(target_snapshot.snapshot_fingerprint)
        assert loaded.snapshot_fingerprint == target_snapshot.snapshot_fingerprint
        assert loaded.target_mode == target_snapshot.target_mode
        assert loaded.project_state.revision_identity == target_snapshot.project_state.revision_identity

    def test_snapshot_exists_after_save(self, state_store, target_snapshot):
        assert not state_store.snapshot_exists(target_snapshot.snapshot_fingerprint)
        state_store.save_snapshot(target_snapshot)
        assert state_store.snapshot_exists(target_snapshot.snapshot_fingerprint)

    def test_plan_roundtrip(self, state_store, audit_plan):
        state_store.save_plan(audit_plan)
        loaded = state_store.load_plan(audit_plan.plan_id)
        assert loaded.plan_id == audit_plan.plan_id
        assert loaded.target_snapshot_ref == audit_plan.target_snapshot_ref
        assert loaded.requested_scope == audit_plan.requested_scope
        assert loaded.resolved_scope == audit_plan.resolved_scope

    def test_frozen_plan_roundtrip_preserves_frozen_at(self, state_store, audit_plan):
        audit_plan.freeze(at=FIXED_TS)
        state_store.save_plan(audit_plan)
        loaded = state_store.load_plan(audit_plan.plan_id)
        assert loaded.is_frozen
        assert loaded.frozen_at.isoformat() == FIXED_TS.isoformat()

    def test_work_item_roundtrip(self, state_store, work_item):
        state_store.save_work_item(work_item)
        loaded = state_store.load_work_item(work_item.work_item_id)
        assert loaded.work_item_id == work_item.work_item_id
        assert loaded.auditor == work_item.auditor
        assert loaded.target_surface == work_item.target_surface
        assert loaded.action == work_item.action
        assert loaded.execution_state == work_item.execution_state
        assert loaded.failure_state == work_item.failure_state

    def test_work_item_with_attempts_roundtrip(self, state_store, work_item):
        attempt = work_item.start_attempt(started_at=FIXED_TS)
        attempt.finish(finished_at=FIXED_TS, exit_code=0)
        work_item.terminate()
        state_store.save_work_item(work_item)
        loaded = state_store.load_work_item(work_item.work_item_id)
        assert len(loaded.attempts) == 1
        assert loaded.attempts[0].attempt_id == attempt.attempt_id
        assert loaded.execution_state == ExecutionState.TERMINATED

    def test_evidence_roundtrip(self, state_store, evidence):
        state_store.save_evidence(evidence)
        loaded = state_store.load_evidence(evidence.evidence_id)
        assert loaded.evidence_id == evidence.evidence_id
        assert loaded.work_item_ref == evidence.work_item_ref
        assert loaded.validity == evidence.validity
        assert loaded.fingerprint == evidence.fingerprint
        assert loaded.source_refs == evidence.source_refs

    def test_run_roundtrip(self, state_store, audit_plan, target_snapshot):
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[str(uuid.uuid4())],
            execution_completeness=RunExecutionCompleteness.COMPLETE,
            coverage_completeness=RunCoverageCompleteness.FULL,
            failure_state=RunFailureState.NONE,
            budget_state=RunBudgetState.HEALTHY,
            publication_state=RunPublicationState.NOT_PUBLISHED,
        )
        state_store.save_run(run)
        loaded = state_store.load_run(run.run_id)
        assert loaded.run_id == run.run_id
        assert loaded.execution_completeness == RunExecutionCompleteness.COMPLETE
        assert loaded.coverage_completeness == RunCoverageCompleteness.FULL

    def test_run_with_lineage_roundtrip(self, state_store, audit_plan, target_snapshot):
        prev_id = str(uuid.uuid4())
        rec_id = str(uuid.uuid4())
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[],
            previous_run_ref=prev_id,
        )
        state_store.save_run(run)
        loaded = state_store.load_run(run.run_id)
        assert loaded.previous_run_ref == prev_id
        assert loaded.recovery_from_ref is None

    def test_run_exists_check(self, state_store, audit_plan, target_snapshot):
        run_id = str(uuid.uuid4())
        assert not state_store.run_exists(run_id)
        run = AuditRun(
            run_id=run_id,
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[],
        )
        state_store.save_run(run)
        assert state_store.run_exists(run_id)


class TestStateStoreRecovery:
    """Tests for recovery semantics (ADR-07)."""

    def test_load_nonexistent_raises(self, state_store):
        with pytest.raises(StateStoreError):
            state_store.load_run(str(uuid.uuid4()))

    def test_list_run_ids_empty_initially(self, state_store):
        assert state_store.list_run_ids() == []

    def test_list_run_ids_after_save(self, state_store, audit_plan, target_snapshot):
        run_id = str(uuid.uuid4())
        run = AuditRun(
            run_id=run_id,
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[],
        )
        state_store.save_run(run)
        ids = state_store.list_run_ids()
        assert run_id in ids

    def test_recovery_loads_interrupted_run(self, state_store, audit_plan, target_snapshot):
        """Simulates crash recovery: save a RUNNING run, reload it."""
        run = AuditRun(
            run_id=str(uuid.uuid4()),
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            plan_ref=audit_plan.plan_id,
            work_item_refs=[str(uuid.uuid4())],
            execution_completeness=RunExecutionCompleteness.RUNNING,
            failure_state=RunFailureState.INFRA_ERROR,
        )
        state_store.save_run(run)
        # Simulate crash recovery: load from disk
        loaded = state_store.load_run(run.run_id)
        assert loaded.execution_completeness == RunExecutionCompleteness.RUNNING
        assert loaded.failure_state == RunFailureState.INFRA_ERROR

    def test_atomic_write_completes_fully(self, tmp_path):
        """Verify that tempfile+rename produces a complete file."""
        store = StateStore(tmp_path / "store")
        from tests.conftest import make_project_state, make_methodology_state
        from project_audit.models import TargetMode, TargetSnapshot
        ps = make_project_state()
        ms = make_methodology_state()
        snap = TargetSnapshot.create(TargetMode.COMMIT, ps, ms)
        store.save_snapshot(snap)
        # No partial file should exist
        partial_files = list((tmp_path / "store" / "target_snapshots").glob(".tmp_*"))
        assert len(partial_files) == 0
        # The real file exists
        assert store.snapshot_exists(snap.snapshot_fingerprint)

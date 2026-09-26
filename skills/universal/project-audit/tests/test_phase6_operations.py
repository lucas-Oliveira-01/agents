from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from project_audit.models import (
    AuditRun,
    ExecutionState,
    RunBudgetState,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    RunPublicationState,
    WorkItemFailureState,
)
from project_audit.orchestrator import Orchestrator
from project_audit.state_store import AuditWriterLock, StateStore, StateStoreBusyError, _atomic_write
from tests.conftest import FIXED_TS, make_methodology_state, make_project_state


def test_writer_lock_rejects_second_process(tmp_path: Path) -> None:
    lock_path = tmp_path / ".audit" / "audit-writer.lock"
    lock = AuditWriterLock(lock_path)
    lock.acquire()
    try:
        code = (
            "from pathlib import Path\n"
            "from project_audit.state_store import AuditWriterLock, StateStoreBusyError\n"
            "import sys\n"
            "lock = AuditWriterLock(Path(sys.argv[1]))\n"
            "try:\n"
            "    lock.acquire()\n"
            "except StateStoreBusyError:\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit(1)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(lock_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
    finally:
        lock.release()


def test_writer_lock_releases_after_exception(tmp_path: Path) -> None:
    lock_path = tmp_path / "audit-writer.lock"
    with pytest.raises(RuntimeError):
        with AuditWriterLock(lock_path):
            raise RuntimeError("simulated crash")
    with AuditWriterLock(lock_path):
        pass


def test_atomic_write_fsync_failure_cleans_temp_file(tmp_path: Path, monkeypatch) -> None:
    destination = tmp_path / "state.json"
    real_replace = __import__("project_audit.state_store", fromlist=["os"]).os.replace

    def fail_replace(*args, **kwargs):
        raise OSError("simulated power-loss boundary")

    import project_audit.state_store as module
    monkeypatch.setattr(module.os, "replace", fail_replace)

    with pytest.raises(OSError):
        _atomic_write(destination, {"ok": True})

    assert not list(tmp_path.glob(".tmp_*.json"))
    assert not destination.exists()

    monkeypatch.setattr(module.os, "replace", real_replace)


def test_recovery_builds_new_closed_graph_without_mutating_original(
    state_store: StateStore,
    audit_plan,
    target_snapshot,
    work_item,
) -> None:
    work_item.target_surface = "CODE/src"
    work_item.start_attempt(started_at=FIXED_TS)
    state_store.save_snapshot(target_snapshot)
    audit_plan.work_items = [work_item]
    state_store.save_work_item(work_item)
    audit_plan.freeze(at=FIXED_TS)
    state_store.save_plan(audit_plan)

    run = AuditRun(
        run_id="recovery-source",
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        plan_ref=audit_plan.plan_id,
        work_item_refs=[work_item.work_item_id],
        execution_completeness=RunExecutionCompleteness.RUNNING,
        coverage_completeness=RunCoverageCompleteness.PENDING,
        failure_state=RunFailureState.NONE,
        budget_state=RunBudgetState.HEALTHY,
        publication_state=RunPublicationState.NOT_PUBLISHED,
    )
    state_store.save_run(run)

    bundle = Orchestrator(state_store).recover_run(run.run_id)

    assert bundle.interrupted_run_ref == run.run_id
    assert bundle.run.run_id != run.run_id
    assert bundle.run.recovery_from_ref == run.run_id
    assert bundle.plan.plan_id != audit_plan.plan_id
    assert bundle.plan.is_frozen
    assert len(bundle.work_items) == 1
    recovered_item = bundle.work_items[0]
    assert recovered_item.work_item_id != work_item.work_item_id
    assert recovered_item.plan_ref == bundle.plan.plan_id
    assert recovered_item.execution_state == ExecutionState.PLANNED
    assert recovered_item.failure_state == WorkItemFailureState.NONE

    original = state_store.load_work_item(work_item.work_item_id)
    assert original.execution_state == ExecutionState.RUNNING
    original_run = state_store.load_run(run.run_id)
    assert original_run.execution_completeness == RunExecutionCompleteness.RUNNING


def test_engineering_run_anchor_survives_worker_exception(tmp_path: Path, audit_plan, execution_policy, egress_policy) -> None:
    from project_audit.discovery import discover
    from project_audit.engineering_runner import execute_engineering_pass

    app = tmp_path / "src" / "app.py"
    app.parent.mkdir(parents=True)
    app.write_text("print('x')\n", encoding="utf-8")

    plan = audit_plan
    item = __import__("tests.conftest", fromlist=["make_work_item"]).make_work_item(
        plan.plan_id,
        target_surface="CODE/src",
        execution_policy=execution_policy,
        egress_policy=egress_policy,
    )
    plan.work_items = [item]

    discovery = discover(str(tmp_path))

    class ExplodingAuditor:
        def inspect(self, discovery, work_item_id, target_surface):
            raise RuntimeError("simulated worker crash")

    store = StateStore(tmp_path / ".audit" / "runs")
    orchestrator = Orchestrator(store)

    with pytest.raises(RuntimeError, match="simulated worker crash"):
        execute_engineering_pass(
            orchestrator,
            discovery,
            plan,
            [item],
            auditor=ExplodingAuditor(),
        )

    run_ids = store.list_run_ids()
    assert len(run_ids) == 1
    recovered = store.load_run(run_ids[0])
    assert recovered.execution_completeness == RunExecutionCompleteness.RUNNING
    assert recovered.failure_state == RunFailureState.NONE
    persisted_item = store.load_work_item(item.work_item_id)
    assert persisted_item.execution_state == ExecutionState.RUNNING

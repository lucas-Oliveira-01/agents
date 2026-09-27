from pathlib import Path
from uuid import uuid4

from project_audit.classifiers import (
    ApplicabilityState,
    classify_applicability,
    classify_files,
    classify_stack,
)
from project_audit.discovery import discover
from project_audit.models import (
    AuditRun,
    RunBudgetState,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    RunPublicationState,
)
from project_audit.planner import prepare_audit
from project_audit.orchestrator import Orchestrator
from project_audit.security_pass import DeterministicSecurityAuditor
from project_audit.security_runner import execute_security_pass
from project_audit.state_store import StateStore


def _write(root: Path, relative: str, content: str = "x") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _decisions(root: Path):
    snapshot = discover(str(root))
    classifications = classify_files(snapshot)
    applicability = classify_applicability(snapshot, classify_stack(snapshot))
    return snapshot, classifications, applicability


def test_debug_exposure_is_explicitly_plannable(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')\n")

    snapshot, classifications, applicability = _decisions(tmp_path)
    by_surface = {(item.category, item.subcategory): item for item in applicability}

    decision = by_surface[("SECURITY", "DEBUG_EXPOSURE")]
    assert decision.state == ApplicabilityState.APPLICABLE
    assert "src/app.py" in decision.evidence_paths

    prepared = prepare_audit(snapshot, classifications, applicability)
    assert "SECURITY/DEBUG_EXPOSURE" in {
        item.target_surface for item in prepared.work_items
    }


def test_debug_exposure_handler_is_reached_and_preserves_not_found(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')\n")

    discovery = discover(tmp_path)
    classifications = classify_files(discovery)
    applicability = classify_applicability(discovery, classify_stack(discovery))
    prepared = prepare_audit(discovery, classifications, applicability)
    item = next(
        item
        for item in prepared.work_items
        if item.target_surface == "SECURITY/DEBUG_EXPOSURE"
    )

    orchestrator = Orchestrator(StateStore(tmp_path / ".audit" / "runs"))
    orchestrator.commit_snapshot(prepared.snapshot)
    orchestrator.freeze_and_commit_plan(prepared.plan)
    orchestrator.commit_work_item(item)

    run = AuditRun(
        run_id=str(uuid4()),
        target_snapshot_ref=prepared.snapshot.snapshot_fingerprint,
        plan_ref=prepared.plan.plan_id,
        work_item_refs=[item.work_item_id],
        execution_completeness=RunExecutionCompleteness.RUNNING,
        coverage_completeness=RunCoverageCompleteness.PARTIAL,
        failure_state=RunFailureState.NONE,
        budget_state=RunBudgetState.HEALTHY,
        publication_state=RunPublicationState.NOT_PUBLISHED,
    )

    result = execute_security_pass(
        orchestrator,
        discovery,
        prepared.plan,
        [item],
        run,
    )

    inspected = next(
        inspection for inspection in result.inspections
        if inspection.target_surface == "SECURITY/DEBUG_EXPOSURE"
    )
    assert inspected.observations[0].code == "SEC-DEBUG-001"
    assert inspected.observations[0].state == "NOT_FOUND"


def test_debug_exposure_with_no_discovered_artifacts_remains_not_determinable(
    tmp_path: Path,
) -> None:
    _, _, applicability = _decisions(tmp_path)
    by_surface = {(item.category, item.subcategory): item for item in applicability}

    assert by_surface[("SECURITY", "DEBUG_EXPOSURE")].state == ApplicabilityState.NOT_DETERMINABLE


def test_debug_exposure_signal_is_observed_deterministically(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "debug = True\n")

    discovery = discover(tmp_path)
    inspection = DeterministicSecurityAuditor().inspect(
        discovery,
        "fixture-work-item",
        "SECURITY/DEBUG_EXPOSURE",
    )

    assert inspection.observations[0].code == "SEC-DEBUG-001"
    assert inspection.observations[0].state == "OBSERVED"
    assert "src/app.py" in inspection.observations[0].source_refs

from __future__ import annotations

from pathlib import Path

from project_audit.classifiers import classify_applicability, classify_files, classify_stack
from project_audit.discovery import discover
from project_audit.engineering_auditor import EngineeringAuditor
from project_audit.engineering_runner import execute_engineering_pass
from project_audit.models import RunCoverageCompleteness, RunExecutionCompleteness, WorkItemFailureState
from project_audit.orchestrator import Orchestrator
from project_audit.planner import prepare_audit
from project_audit.state_store import StateStore


def _write(root: Path, relative: str, content: str = "x") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_engineering_auditor_emits_deterministic_observations(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')\n# TODO: follow up\n")
    discovery = discover(tmp_path)

    result = EngineeringAuditor().inspect(
        discovery,
        "work-1",
        "CODE_QUALITY/STATIC_REVIEW",
    )

    assert result.work_item_ref == "work-1"
    assert result.fingerprint
    assert any(obs.code == "CODE-INV-002" for obs in result.observations)
    assert result.source_refs == ("src/app.py",)


def test_engineering_pass_executes_only_non_security_work_items(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')\n")
    discovery = discover(tmp_path)
    files = classify_files(discovery)
    applicability = classify_applicability(discovery, classify_stack(discovery))
    prepared = prepare_audit(discovery, files, applicability)

    orchestrator = Orchestrator(StateStore(tmp_path / ".audit" / "runs"))
    result = execute_engineering_pass(
        orchestrator,
        discovery,
        prepared.plan,
        list(prepared.work_items),
    )

    assert result.inspections
    assert result.evidence
    assert result.run.execution_completeness == RunExecutionCompleteness.PARTIAL
    assert result.run.coverage_completeness == RunCoverageCompleteness.PARTIAL
    assert all(e.target_snapshot_ref == result.run.target_snapshot_ref for e in result.evidence)
    assert all(
        item.failure_state == WorkItemFailureState.NONE
        or item.target_surface.startswith("SECURITY/")
        for item in prepared.work_items
    )

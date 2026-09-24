from __future__ import annotations

from pathlib import Path

from project_audit.classifiers import classify_applicability, classify_files, classify_stack
from project_audit.discovery import discover
from project_audit.engineering_runner import execute_engineering_pass
from project_audit.models import RunCoverageCompleteness, RunExecutionCompleteness
from project_audit.orchestrator import Orchestrator
from project_audit.planner import prepare_audit
from project_audit.security_pass import DeterministicSecurityAuditor
from project_audit.security_runner import SecurityPassResult, execute_security_pass
from project_audit.state_store import StateStore


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_security_auditor_records_sink_without_claiming_exploitability(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/client.py",
        "import requests\nrequests.get(user_url)\n",
    )
    discovery = discover(tmp_path)

    result = DeterministicSecurityAuditor().inspect(
        discovery,
        "work-1",
        "SECURITY/SSRF",
    )

    assert result.source_refs == ("src/client.py",)
    assert result.observations[0].state == "OBSERVED"
    assert "remain to be established" in result.observations[0].summary


def test_security_pass_finishes_same_run_after_engineering_pass(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')\n")
    _write(tmp_path, "src/client.py", "import requests\nrequests.get(user_url)\n")

    discovery = discover(tmp_path)
    files = classify_files(discovery)
    applicability = classify_applicability(discovery, classify_stack(discovery))
    prepared = prepare_audit(discovery, files, applicability)

    orchestrator = Orchestrator(StateStore(tmp_path / ".audit" / "runs"))
    engineering = execute_engineering_pass(
        orchestrator,
        discovery,
        prepared.plan,
        list(prepared.work_items),
    )

    final_run = execute_security_pass(
        orchestrator,
        discovery,
        prepared.plan,
        list(prepared.work_items),
        engineering.run,
    )

    assert isinstance(final_run, SecurityPassResult)
    assert final_run.run.run_id == engineering.run.run_id
    assert final_run.run.execution_completeness == RunExecutionCompleteness.COMPLETE
    assert final_run.run.coverage_completeness == RunCoverageCompleteness.FULL
    assert final_run.run.failure_state.value == "NONE"
    assert final_run.inspections
    assert final_run.evidence

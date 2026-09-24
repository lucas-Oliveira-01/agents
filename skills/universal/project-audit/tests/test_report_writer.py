from __future__ import annotations

from pathlib import Path

from project_audit.classifiers import classify_applicability, classify_files, classify_stack
from project_audit.discovery import discover
from project_audit.engineering_runner import execute_engineering_pass
from project_audit.report_writer import write_audit_artifacts
from project_audit.security_runner import execute_security_pass
from project_audit.orchestrator import Orchestrator
from project_audit.planner import prepare_audit
from project_audit.state_store import StateStore


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_report_writer_emits_required_four_markdown_artifacts(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')\n")
    discovery = discover(tmp_path)
    prepared = prepare_audit(
        discovery,
        classify_files(discovery),
        classify_applicability(discovery, classify_stack(discovery)),
    )

    orchestrator = Orchestrator(StateStore(tmp_path / ".audit" / "runs"))
    engineering = execute_engineering_pass(
        orchestrator,
        discovery,
        prepared.plan,
        list(prepared.work_items),
    )
    security = execute_security_pass(
        orchestrator,
        discovery,
        prepared.plan,
        list(prepared.work_items),
        engineering.run,
    )

    out = tmp_path / ".audit"
    paths = write_audit_artifacts(
        str(out),
        prepared,
        discovery,
        engineering,
        security,
    )

    assert set(paths) == {"inventory", "coverage", "report", "ledger"}
    assert all(Path(path).is_file() for path in paths.values())
    assert "APPLICABILITY MATRIX" in Path(paths["inventory"]).read_text(encoding="utf-8")
    assert "INSPECTION COVERAGE" in Path(paths["coverage"]).read_text(encoding="utf-8")
    assert "Security Review" in Path(paths["report"]).read_text(encoding="utf-8")
    assert "AUDIT LEDGER" in Path(paths["ledger"]).read_text(encoding="utf-8")


def test_report_writer_preflights_existing_artifact_set(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')\n")
    discovery = discover(tmp_path)
    prepared = prepare_audit(
        discovery,
        classify_files(discovery),
        classify_applicability(discovery, classify_stack(discovery)),
    )
    orchestrator = Orchestrator(StateStore(tmp_path / ".audit" / "runs"))
    engineering = execute_engineering_pass(orchestrator, discovery, prepared.plan, list(prepared.work_items))
    security = execute_security_pass(orchestrator, discovery, prepared.plan, list(prepared.work_items), engineering.run)

    out = tmp_path / ".audit"
    out.mkdir(parents=True, exist_ok=True)
    existing = out / "00_inventory.md"
    existing.write_text("existing", encoding="utf-8")

    try:
        write_audit_artifacts(str(out), prepared, discovery, engineering, security)
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing audit artifacts must block the whole write set")

    assert existing.read_text(encoding="utf-8") == "existing"
    assert not (out / "01_coverage.md").exists()
    assert not (out / "02_analytical.md").exists()
    assert not (out / "03_audit_ledger.md").exists()


def test_report_writer_renders_semantic_finding_with_required_fields(tmp_path: Path) -> None:
    from project_audit.semantic_auditor import SemanticFindingCandidate, SemanticReviewResult
    from project_audit.sensitivity import SensitivityState, SensitivityAssessment

    _write(tmp_path, "src/app.py", "print('ok')\n")
    discovery = discover(tmp_path)
    prepared = prepare_audit(
        discovery,
        classify_files(discovery),
        classify_applicability(discovery, classify_stack(discovery)),
    )

    finding = SemanticFindingCandidate(
        title="Example defect",
        category="CODE_QUALITY",
        subcategory="STATIC_REVIEW",
        finding_type="TECHNICAL_DEFECT",
        status="PROBABLE",
        severity="P2",
        confidence="MEDIUM",
        location={"file": "src/app.py", "line": 1},
        evidence="The implementation uses a deterministic example.",
        description="A semantic review produced a candidate.",
        cause="Example cause",
        impact="Example impact",
        exploitability=None,
        recommendation="Confirm against requirements.",
    )
    review = SemanticReviewResult(
        work_item_ref="work-1",
        target_surface="CODE_QUALITY/STATIC_REVIEW",
        status="COMPLETED",
        sensitivity=SensitivityAssessment(
            SensitivityState.PUBLIC,
            tuple(),
            "test",
        ),
        candidates=(finding,),
        raw_output_fingerprint="a" * 64,
        receipt=object(),
        evidence=None,
    )

    from project_audit.report_writer import render_semantic_findings

    rendered = render_semantic_findings((review,))
    assert "SEM-001" in rendered
    assert "Evidence:" in rendered
    assert "Severity: P2" in rendered
    assert "Location: src/app.py:1" in rendered

from __future__ import annotations

from project_audit.normalization_runner import run_audit_normalize


def test_normalization_runner_builds_downstream_command(monkeypatch, tmp_path) -> None:
    calls = {}

    class Completed:
        returncode = 0
        stdout = "Status: VALID\n"
        stderr = ""

    def fake_run(argv, check, capture_output, text):
        calls["argv"] = argv
        calls["check"] = check
        calls["capture_output"] = capture_output
        calls["text"] = text
        output_dir = tmp_path / "normalized"
        output_dir.mkdir(parents=True)
        for name in ("report_data.json", "validation_report.json", "source_manifest.json", "report_data.schema.json"):
            (output_dir / name).write_text("{}\n", encoding="utf-8")
        return Completed()

    monkeypatch.setattr("project_audit.normalization_runner.subprocess.run", fake_run)

    result = run_audit_normalize(
        ["docs/audit/00_inventory_and_threat_model.md", "docs/audit/01_coverage_manifest.md", "docs/audit/02_analytical_report.md", "docs/audit/03_audit_ledger.md"],
        str(tmp_path / "normalized"),
        base_dir="/repo",
        command="audit-normalize",
    )

    assert result.status == "COMPLETED"
    assert result.return_code == 0
    assert calls["argv"] == [
        "audit-normalize",
        "-i",
        "docs/audit/00_inventory_and_threat_model.md",
        "docs/audit/01_coverage_manifest.md",
        "docs/audit/02_analytical_report.md",
        "docs/audit/03_audit_ledger.md",
        "-o",
        str(tmp_path / "normalized"),
        "--base-dir",
        "/repo",
    ]


def test_normalization_runner_does_not_claim_execution_when_command_is_missing(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("audit-normalize")

    monkeypatch.setattr("project_audit.normalization_runner.subprocess.run", fake_run)

    result = run_audit_normalize(["docs/audit/00_inventory_and_threat_model.md"], "docs/audit/normalized")

    assert result.status == "NOT_EXECUTED"
    assert result.return_code is None

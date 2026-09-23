from __future__ import annotations

from project_audit.normalization_runner import run_audit_normalize


def test_normalization_runner_builds_downstream_command(monkeypatch) -> None:
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
        return Completed()

    monkeypatch.setattr("project_audit.normalization_runner.subprocess.run", fake_run)

    result = run_audit_normalize(
        "docs/audit",
        "docs/audit/normalized",
        base_dir="/repo",
        command="audit-normalize",
    )

    assert result.status == "COMPLETED"
    assert result.return_code == 0
    assert calls["argv"] == [
        "audit-normalize",
        "-i",
        "docs/audit",
        "-o",
        "docs/audit/normalized",
        "--base-dir",
        "/repo",
    ]


def test_normalization_runner_does_not_claim_execution_when_command_is_missing(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("audit-normalize")

    monkeypatch.setattr("project_audit.normalization_runner.subprocess.run", fake_run)

    result = run_audit_normalize("docs/audit", "docs/audit/normalized")

    assert result.status == "NOT_EXECUTED"
    assert result.return_code is None

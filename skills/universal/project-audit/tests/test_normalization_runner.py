from __future__ import annotations

from pathlib import Path

from project_audit.normalization_runner import run_audit_normalize


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o700)


def test_normalization_runner_reports_not_executed_when_command_is_missing(tmp_path: Path) -> None:
    result = run_audit_normalize(
        ["a.md"],
        str(tmp_path / "normalized"),
        command=str(tmp_path / "missing-audit-normalize"),
    )

    assert result.status == "NOT_EXECUTED"
    assert result.return_code is None
    assert result.output_dir.endswith("normalized")


def test_normalization_runner_validates_expected_artifacts(tmp_path: Path) -> None:
    executable = tmp_path / "audit-normalize"
    _write_executable(
        executable,
        "#!/bin/sh\nexit 0\n",
    )

    result = run_audit_normalize(
        ["a.md"],
        str(tmp_path / "normalized"),
        command=str(executable),
    )

    assert result.status == "FAILED"
    assert result.return_code == 0


def test_normalization_runner_accepts_success_only_when_all_outputs_exist(tmp_path: Path) -> None:
    executable = tmp_path / "audit-normalize"
    script = """#!/bin/sh
output=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o) output="$2"; shift 2 ;;
    --base-dir) shift 2 ;;
    -i) shift ;;
    *) shift ;;
  esac
done
mkdir -p "$output"
touch "$output/report_data.json"
touch "$output/validation_report.json"
touch "$output/source_manifest.json"
touch "$output/report_data.schema.json"
exit 0
"""
    _write_executable(executable, script)

    result = run_audit_normalize(
        ["00_inventory.md", "01_coverage.md", "02_report.md", "03_ledger.md"],
        str(tmp_path / "normalized"),
        base_dir=str(tmp_path),
        command=str(executable),
    )

    assert result.status == "COMPLETED"
    assert result.return_code == 0
    assert len(result.command) == 10
    assert "--base-dir" in result.command

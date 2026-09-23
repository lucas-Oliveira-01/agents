from __future__ import annotations

from pathlib import Path

import pytest

from project_audit.runtime import run_full_audit


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_run_full_audit_completes_two_pass_runtime_and_writes_artifacts(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')\n")
    _write(tmp_path, "README.md", "# Demo\n\n## Usage\n")

    result = run_full_audit(
        str(tmp_path),
        state_dir=str(tmp_path / ".audit" / "runs"),
        output_dir=str(tmp_path / "docs" / "audit"),
    )

    assert result.security.run.execution_completeness.value == "COMPLETE"
    assert result.security.run.coverage_completeness.value == "FULL"
    assert len(result.artifacts) == 4
    assert all(Path(path).is_file() for path in result.artifacts)
    assert "docs/audit" not in {item.path for item in result.prepared.snapshot.project_state.tracked_input_fingerprints}


def test_run_full_audit_fails_closed_on_existing_artifacts_without_overwrite(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')\n")
    output = tmp_path / "docs" / "audit"
    output.mkdir(parents=True)
    (output / "01_coverage_manifest.md").write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError):
        run_full_audit(
            str(tmp_path),
            state_dir=str(tmp_path / ".audit" / "runs"),
            output_dir=str(output),
        )

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class NormalizationResult:
    status: str
    command: Tuple[str, ...]
    return_code: Optional[int]
    output_dir: str
    stdout: str
    stderr: str


def run_audit_normalize(
    input_paths: List[str],
    output_dir: str,
    base_dir: Optional[str] = None,
    command: str = "audit-normalize",
    timeout_seconds: int = 300,
    execution_state_path: Optional[str] = None,
) -> NormalizationResult:
    """Invoke audit-normalize on this run's Markdown artifacts and execution-state sidecar."""
    argv = [command, "-i"] + list(input_paths) + ["-o", output_dir]
    if base_dir is not None:
        argv.extend(["--base-dir", base_dir])
    if execution_state_path is not None:
        argv.extend(["--execution-state", execution_state_path])

    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        return NormalizationResult(
            status="NOT_EXECUTED",
            command=tuple(argv),
            return_code=None,
            output_dir=output_dir,
            stdout="",
            stderr=str(exc),
        )
    except subprocess.TimeoutExpired as exc:
        return NormalizationResult(
            status="FAILED",
            command=tuple(argv),
            return_code=None,
            output_dir=output_dir,
            stdout=exc.stdout or "",
            stderr="audit-normalize timed out after {} seconds".format(timeout_seconds),
        )
    except OSError as exc:
        return NormalizationResult(
            status="FAILED",
            command=tuple(argv),
            return_code=None,
            output_dir=output_dir,
            stdout="",
            stderr=str(exc),
        )

    status = "COMPLETED" if completed.returncode == 0 else (
        "COMPLETED_WITH_WARNINGS" if completed.returncode == 2 else "FAILED"
    )

    if status.startswith("COMPLETED"):
        expected = (
            Path(output_dir) / "report_data.json",
            Path(output_dir) / "validation_report.json",
            Path(output_dir) / "source_manifest.json",
            Path(output_dir) / "report_data.schema.json",
        )
        if not all(path.is_file() for path in expected):
            status = "FAILED"

    return NormalizationResult(
        status=status,
        command=tuple(argv),
        return_code=completed.returncode,
        output_dir=output_dir,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )

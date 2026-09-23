from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class NormalizationResult:
    status: str
    command: Tuple[str, ...]
    return_code: Optional[int]
    output_dir: str
    stdout: str
    stderr: str


def run_audit_normalize(
    input_dir: str,
    output_dir: str,
    base_dir: Optional[str] = None,
    command: str = "audit-normalize",
) -> NormalizationResult:
    """Invoke audit-normalize as a downstream process without importing its implementation."""
    argv = [command, "-i", input_dir, "-o", output_dir]
    if base_dir is not None:
        argv.extend(["--base-dir", base_dir])

    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
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
    except OSError as exc:
        return NormalizationResult(
            status="FAILED",
            command=tuple(argv),
            return_code=None,
            output_dir=output_dir,
            stdout="",
            stderr=str(exc),
        )

    if completed.returncode == 0:
        status = "COMPLETED"
    elif completed.returncode == 2:
        status = "COMPLETED_WITH_WARNINGS"
    else:
        status = "FAILED"

    return NormalizationResult(
        status=status,
        command=tuple(argv),
        return_code=completed.returncode,
        output_dir=output_dir,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )

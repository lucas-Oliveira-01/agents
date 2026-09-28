"""Capture reproducible acceptance commands without persisting credentials."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone


def redact(text: str) -> str:
    for key, value in os.environ.items():
        if re.search(r"TOKEN|SECRET|PASSWORD|API_KEY|COOKIE|CREDENTIAL", key, re.I) and len(value) > 5:
            text = text.replace(value, "[REDACTED]")
    text = re.sub(r"(?i)(Bearer\s+)[^\s\"']+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)((?:api[_-]?key|password|access[_-]?token|client[_-]?secret)\s*[=:]\s*[\"']?)[^\s\"',}]+", r"\1[REDACTED]", text)
    return text


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("command", nargs=argparse.REMAINDER)
    args = p.parse_args()
    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command
    out = args.root / args.name
    out.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    command = redact(shlex.join(cmd))
    (out / "command.txt").write_text(command + "\n")
    metadata = {"timestamp": started, "cwd": str(Path.cwd()), "command": command,
                "auditor_commit": git("rev-parse", "HEAD"),
                "git_status": git("status", "--short", "--untracked-files=no"),
                "tracked_diff_sha256": hashlib.sha256(git("diff", "HEAD").encode()).hexdigest(),
                "python": sys.version, "redaction": "credential env values and credential-shaped text"}
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    start = time.monotonic()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
    except OSError as exc:
        stdout, stderr, code = "", str(exc), 127
    clean_out, clean_err = redact(stdout), redact(stderr)
    (out / "stdout.log").write_text(clean_out)
    (out / "stderr.log").write_text(clean_err)
    metadata.update(exit_code=code, duration_seconds=round(time.monotonic()-start, 3),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    redaction_applied=(stdout != clean_out or stderr != clean_err))
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    for name, value in [("COMMANDS.txt", command), ("EXECUTION_LOG.txt", json.dumps(metadata))]:
        with (args.root / name).open("a") as f:
            f.write(f"{started} {args.name}: {value}\n")
    print(json.dumps({"artifact": str(out), "exit_code": code, "duration_seconds": metadata["duration_seconds"]}))
    print(clean_out[-6000:])
    if clean_err:
        print(clean_err[-2000:], file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

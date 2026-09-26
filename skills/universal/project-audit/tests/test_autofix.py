from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from project_audit.autofix import (
    AutoFixError,
    apply_patch,
    logical_finding_key,
    validate_worker_patch,
)
from project_audit.models import TargetMode, TargetSnapshot, WorkingTreeState
from tests.conftest import make_project_state, make_methodology_state


def test_logical_finding_key_ignores_line_numbers():
    first = logical_finding_key(
        category="SECURITY",
        subcategory="AUTH",
        finding_type="VULNERABILITY",
        location_file="src/auth.py",
    )
    second = logical_finding_key(
        category="security",
        subcategory="auth",
        finding_type="vulnerability",
        location_file="./src/auth.py",
    )
    assert first == second


def test_validate_worker_patch_accepts_only_verified_file():
    patch = (
        "--- a/src/auth.py\n"
        "+++ b/src/auth.py\n"
        "@@ -1 +1 @@\n"
        "-bad()\n"
        "+good()\n"
    )
    assert validate_worker_patch(patch, expected_file="src/auth.py") == ("src/auth.py",)


def test_validate_worker_patch_rejects_extra_file():
    patch = (
        "--- a/src/auth.py\n+++ b/src/auth.py\n@@ -1 +1 @@\n-a\n+b\n"
        "--- a/src/test.py\n+++ b/src/test.py\n@@ -1 +1 @@\n-a\n+b\n"
    )
    with pytest.raises(AutoFixError):
        validate_worker_patch(patch, expected_file="src/auth.py")


def test_validate_worker_patch_rejects_empty_patch():
    with pytest.raises(AutoFixError):
        validate_worker_patch("", expected_file="src/auth.py")


def test_apply_patch_is_checked_before_mutation(tmp_path: Path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    path = tmp_path / "src" / "auth.py"
    path.parent.mkdir(parents=True)
    path.write_text("bad()\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-qm", "baseline"],
        check=True,
    )

    patch = (
        "--- a/src/auth.py\n"
        "+++ b/src/auth.py\n"
        "@@ -1 +1 @@\n"
        "-bad()\n"
        "+good()\n"
    )
    digest = apply_patch(tmp_path, patch)
    assert len(digest) == 64
    assert path.read_text(encoding="utf-8") == "good()\n"


def test_snapshot_a_requires_clean_commit_target():
    snapshot = TargetSnapshot.create(
        TargetMode.COMMIT,
        make_project_state(tree_state=WorkingTreeState.DIRTY),
        make_methodology_state(),
    )
    assert snapshot.target_mode == TargetMode.COMMIT
    assert snapshot.project_state.working_tree_state == WorkingTreeState.DIRTY

from __future__ import annotations

from pathlib import Path

from project_audit.classifiers import ApplicabilityState, FileKind, classify_applicability, classify_file, classify_stack
from project_audit.discovery import discover
from project_audit.planner import prepare_audit


def _write(root: Path, relative: str, content: str = "x") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_deterministic_file_classification(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')")
    _write(tmp_path, "tests/test_app.py", "def test_ok(): pass")
    _write(tmp_path, "schema.sql", "create table t(id int);")
    _write(tmp_path, "README.md", "# app")
    snapshot = discover(tmp_path)
    classes = {item.path: classify_file(item) for item in snapshot.files}
    assert classes["src/app.py"].kind == FileKind.SOURCE
    assert classes["tests/test_app.py"].kind == FileKind.TEST
    assert classes["schema.sql"].kind == FileKind.DATABASE
    assert classes["README.md"].kind == FileKind.DOCUMENTATION


def test_stack_classification_and_applicability_preserve_uncertainty(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", "[project]\nname='demo'\n")
    _write(tmp_path, "src/client.py", "import httpx\n")
    snapshot = discover(tmp_path)
    stack = classify_stack(snapshot)
    applicability = classify_applicability(snapshot, stack)
    ssrf = next(item for item in applicability if item.subcategory == "SSRF")
    assert ssrf.state == ApplicabilityState.APPLICABLE
    sql = next(item for item in applicability if item.subcategory == "SQL_INJECTION")
    assert sql.state == ApplicabilityState.NOT_DETERMINABLE


def test_prepare_audit_creates_consistent_snapshot_and_work_items(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')")
    snapshot = discover(tmp_path)
    files = tuple(classify_file(item) for item in snapshot.files)
    stack = classify_stack(snapshot)
    applicability = classify_applicability(snapshot, stack)
    prepared = prepare_audit(snapshot, files, applicability)

    assert prepared.snapshot.snapshot_fingerprint == prepared.plan.target_snapshot_ref
    assert all(item.plan_ref == prepared.plan.plan_id for item in prepared.work_items)
    assert all(item.target_surface for item in prepared.work_items)
    assert prepared.plan.work_items


def test_worktree_snapshot_includes_untracked_files_but_excludes_audit_output(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')\n")
    _write(tmp_path, "local-only.txt", "untracked input\n")
    _write(tmp_path, "docs/audit/02_analytical_report.md", "# generated audit\n")

    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "audit@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Audit Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "src/app.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=tmp_path, check=True)

    discovery = discover(tmp_path)
    assert discovery.file("local-only.txt") is not None
    assert discovery.file("docs/audit/02_analytical_report.md") is None

    prepared = prepare_audit(
        discovery,
        classify_files(discovery),
        classify_applicability(discovery, classify_stack(discovery)),
    )
    paths = {item.path for item in prepared.snapshot.project_state.tracked_input_fingerprints}
    assert "local-only.txt" not in paths
    assert "docs/audit/02_analytical_report.md" not in paths

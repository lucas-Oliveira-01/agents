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

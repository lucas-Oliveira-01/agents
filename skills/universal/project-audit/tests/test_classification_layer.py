from pathlib import Path

from project_audit.classification import (
    ClassificationResult,
    ProjectProfile,
    build_classification_results,
    classify_technology_surfaces,
    profile_project,
)
from project_audit.classifiers import classify_applicability, classify_files, classify_stack
from project_audit.discovery import discover
from project_audit.planner import prepare_audit


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fixture_project(root: Path) -> None:
    _write(
        root,
        "pyproject.toml",
        "[project]\nname = \"demo\"\nversion = \"1.0.0\"\n",
    )
    _write(
        root,
        ".github/workflows/ci.yml",
        "name: ci\non: [push]\njobs: {}\n",
    )
    _write(
        root,
        "Dockerfile",
        "FROM python:3.13\n",
    )
    _write(
        root,
        "src/api.py",
        "from fastapi import FastAPI\nimport requests\napp = FastAPI()\n"
        "def authenticate(password):\n    return password\n",
    )
    _write(
        root,
        "src/db.py",
        "import sqlalchemy\nquery = 'select id from users'\n",
    )
    _write(
        root,
        "frontend/App.tsx",
        "export function App() { return <main /> }\n",
    )


def test_project_profile_is_deterministic(tmp_path):
    _fixture_project(tmp_path)

    snapshot = discover(str(tmp_path))
    classifications = classify_files(snapshot)
    stack = classify_stack(snapshot)

    first = profile_project(snapshot, classifications, stack)
    second = profile_project(snapshot, classifications, stack)

    assert first == second
    assert isinstance(first, ProjectProfile)
    assert first.application == "FULLSTACK"
    assert first.network == "OUTBOUND_REST"
    assert first.frontend == "WEB"
    assert first.container == "DOCKER"
    assert first.ci == "GITHUB_ACTIONS"
    assert first.auth == "CUSTOM_OR_UNKNOWN"
    assert "HTTP" in first.technology_surfaces
    assert "DATABASE" in first.technology_surfaces
    assert "AUTH" in first.technology_surfaces
    assert "NETWORK" in first.risk_surfaces


def test_technology_surface_classifier_is_structural(tmp_path):
    _fixture_project(tmp_path)

    snapshot = discover(str(tmp_path))
    classifications = classify_files(snapshot)

    surfaces = classify_technology_surfaces(snapshot, classifications)

    assert surfaces == tuple(sorted(surfaces))
    assert {"HTTP", "NETWORK", "DATABASE", "AUTH", "CONTAINERS"} <= set(surfaces)


def test_classification_results_are_auditable_and_stable(tmp_path):
    _fixture_project(tmp_path)

    snapshot = discover(str(tmp_path))
    classifications = classify_files(snapshot)
    stack = classify_stack(snapshot)
    applicability = classify_applicability(snapshot, stack)
    prepared = prepare_audit(snapshot, classifications, applicability)

    results = prepared.classification_results

    assert results
    assert all(isinstance(item, ClassificationResult) for item in results)
    ids = {item.classifier_id for item in results}
    assert {
        "file-classifier",
        "stack-classifier",
        "technology-surface-classifier",
        "project-profile-classifier",
        "task-classifier",
    } <= ids

    fingerprints = [item.to_dict() for item in results]
    assert fingerprints == [item.to_dict() for item in results]


def test_classification_layer_preserves_uncertain_applicability(tmp_path):
    _fixture_project(tmp_path)

    snapshot = discover(str(tmp_path))
    classifications = classify_files(snapshot)
    stack = classify_stack(snapshot)
    applicability = classify_applicability(snapshot, stack)

    uncertain = [
        item
        for item in applicability
        if item.state.value == "NOT_DETERMINABLE"
    ]

    assert uncertain
    prepared = prepare_audit(snapshot, classifications, applicability)

    uncertain_domains = {
        item.domain
        for item in prepared.plan.applicability_decisions
        if item.applicable.value == "UNKNOWN"
    }
    assert uncertain_domains
    assert all(
        item.target_surface.startswith(tuple(domain.split("/", 1)[0] for domain in uncertain_domains))
        for item in prepared.work_items
        if item.target_surface.split("/", 1)[0] in {domain.split("/", 1)[0] for domain in uncertain_domains}
    )

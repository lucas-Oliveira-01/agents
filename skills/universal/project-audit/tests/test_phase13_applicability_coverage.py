from pathlib import Path

from project_audit.classifiers import ApplicabilityState, classify_applicability, classify_files, classify_stack
from project_audit.discovery import discover
from project_audit.engineering_runner import execute_engineering_pass
from project_audit.orchestrator import Orchestrator
from project_audit.planner import prepare_audit
from project_audit.state_store import StateStore


def _write(root: Path, relative: str, content: str = "x") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _decisions(root: Path):
    snapshot = discover(str(root))
    classifications = classify_files(snapshot)
    applicability = classify_applicability(snapshot, classify_stack(snapshot))
    return snapshot, classifications, applicability


def test_build_configuration_documentation_surfaces_are_plannable(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", "[project]\nname='demo'\n")
    _write(tmp_path, "config.yaml", "service:\n  enabled: true\n")
    _write(tmp_path, "README.md", "# Demo\n\n## Usage\n")
    _write(tmp_path, "src/app.py", "print('ok')\n")

    snapshot, classifications, applicability = _decisions(tmp_path)
    by_surface = {(item.category, item.subcategory): item for item in applicability}

    assert by_surface[("BUILD", "MANIFESTS")].state == ApplicabilityState.APPLICABLE
    assert by_surface[("CONFIGURATION", "SURFACE")].state == ApplicabilityState.APPLICABLE
    assert by_surface[("DOCUMENTATION", "BASELINE")].state == ApplicabilityState.APPLICABLE

    prepared = prepare_audit(snapshot, classifications, applicability)
    surfaces = {item.target_surface for item in prepared.work_items}
    assert {
        "BUILD/MANIFESTS",
        "CONFIGURATION/SURFACE",
        "DOCUMENTATION/BASELINE",
    } <= surfaces


def test_missing_build_configuration_documentation_is_not_downgraded_to_not_applicable(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')\n")

    _, _, applicability = _decisions(tmp_path)
    by_surface = {(item.category, item.subcategory): item for item in applicability}

    assert by_surface[("BUILD", "MANIFESTS")].state == ApplicabilityState.NOT_DETERMINABLE
    assert by_surface[("CONFIGURATION", "SURFACE")].state == ApplicabilityState.NOT_DETERMINABLE
    assert by_surface[("DOCUMENTATION", "BASELINE")].state == ApplicabilityState.NOT_DETERMINABLE


def test_engineering_pass_executes_new_deterministic_surfaces(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", "[project]\nname='demo'\n")
    _write(tmp_path, "config.yaml", "service:\n  enabled: true\n")
    _write(tmp_path, "README.md", "# Demo\n\n## Install\n")
    _write(tmp_path, "src/app.py", "print('ok')\n")

    discovery = discover(tmp_path)
    classifications = classify_files(discovery)
    applicability = classify_applicability(discovery, classify_stack(discovery))
    prepared = prepare_audit(discovery, classifications, applicability)

    orchestrator = Orchestrator(StateStore(tmp_path / ".audit" / "runs"))
    result = execute_engineering_pass(
        orchestrator,
        discovery,
        prepared.plan,
        list(prepared.work_items),
    )

    inspected = {item.target_surface for item in result.inspections}
    assert {
        "BUILD/MANIFESTS",
        "CONFIGURATION/SURFACE",
        "DOCUMENTATION/BASELINE",
    } <= inspected

    observations = {
        item.target_surface: item.observations
        for item in result.inspections
        if item.target_surface in {
            "BUILD/MANIFESTS",
            "CONFIGURATION/SURFACE",
            "DOCUMENTATION/BASELINE",
        }
    }
    assert observations["BUILD/MANIFESTS"][0].code == "BUILD-INV-001"
    assert observations["CONFIGURATION/SURFACE"][0].code == "CONFIG-INV-001"
    assert observations["DOCUMENTATION/BASELINE"][0].code == "DOC-INV-001"

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


def test_run_full_audit_can_explicitly_escalate_semantic_review(tmp_path: Path) -> None:
    from project_audit.delegation import DelegationBackend, DelegationResult, DelegationStatus, WorkerPort
    from project_audit.models import EgressDestination, EgressPolicy
    from project_audit.semantic_auditor import SemanticAuditor

    class SemanticBackend(DelegationBackend):
        def __init__(self) -> None:
            self.calls = 0

        def delegate(self, request):
            self.calls += 1
            return DelegationResult(
                request_id=request.request_id,
                status=DelegationStatus.SUCCESS,
                output_payload={
                    "findings": [{
                        "title": "Semantic review candidate",
                        "category": "SECURITY",
                        "subcategory": "AUTHENTICATION",
                        "type": "RISK",
                        "status": "PROBABLE",
                        "severity": "P2",
                        "confidence": "MEDIUM",
                        "location": {"file": "src/app.py", "line": 1},
                        "evidence": "The semantic worker identified a candidate in the supplied source context.",
                        "description": "Candidate requiring engineering confirmation.",
                        "cause": "Insufficient deterministic evidence.",
                        "impact": "Potential security-relevant behavior.",
                        "exploitability": "Not established by this review.",
                        "recommendation": "Confirm against the complete authentication flow.",
                    }]
                },
                error_message=None,
                provider_info="fake-semantic/v1",
                usage_tokens=10,
            )

    _write(tmp_path, "src/app.py", "print('ok')\n")
    backend = SemanticBackend()
    worker = SemanticAuditor(WorkerPort(backend, "test-semantic"))

    from project_audit.models import EgressDestination, EgressPolicy

    result = run_full_audit(
        str(tmp_path),
        state_dir=str(tmp_path / ".audit" / "runs"),
        output_dir=str(tmp_path / "docs" / "audit"),
        semantic_worker=worker,
        semantic_egress_policy=EgressPolicy(
            destination=EgressDestination.APPROVED_EXTERNAL,
            allow_sensitive=True,
        ),
    )

    assert backend.calls >= 1
    assert result.semantic_reviews
    assert any(review.candidates for review in result.semantic_reviews)
    ledger = Path(result.artifacts[-1]).read_text(encoding="utf-8")
    assert "SEM-001" in ledger
    assert "Semantic review candidate" in ledger

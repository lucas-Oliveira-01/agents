"""Regression tests for node-level snapshot drift semantics."""

from pathlib import Path

import pytest

from project_audit.discovery import discover
from project_audit.engineering_auditor import EngineeringAuditor
from project_audit.models import (
    EgressDestination,
    EgressPolicy,
    EvidenceValidity,
)
from project_audit.orchestrator import Orchestrator
from project_audit.planner import build_target_snapshot, prepare_audit
from project_audit.runtime import run_full_audit
from project_audit.security_pass import DeterministicSecurityAuditor
from project_audit.state_store import StateStore


@pytest.mark.parametrize("mutation", ["edit", "add", "delete", "binary"])
def test_snapshot_fingerprints_every_audited_input(tmp_path, mutation):
    source = tmp_path / "app.py"
    source.write_text("before\n")
    before = build_target_snapshot(discover(tmp_path))
    if mutation == "edit":
        source.write_text("after!\n")
    elif mutation == "add":
        (tmp_path / "new.txt").write_text("new")
    elif mutation == "delete":
        source.unlink()
    else:
        (tmp_path / "data.bin").write_bytes(b"\x00binary")
    after = build_target_snapshot(discover(tmp_path))
    assert before.snapshot_fingerprint != after.snapshot_fingerprint


@pytest.mark.parametrize("phase", ["engineering", "security", "render"])
def test_node_drift_preserves_artifacts_and_marks_run_partial(tmp_path, monkeypatch, phase):
    source = tmp_path / "app.py"
    source.write_text("print('before')\n")

    if phase == "render":
        import project_audit.runtime as runtime
        owner, name = runtime, "write_audit_artifacts"
    else:
        owner = EngineeringAuditor if phase == "engineering" else DeterministicSecurityAuditor
        name = "inspect"

    original = getattr(owner, name)
    calls = []

    def mutate_after_real_operation(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(True)
        source.write_text("print('after')\n")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(owner, name, mutate_after_real_operation)
        result = run_full_audit(str(tmp_path))

    assert calls
    assert result.security.run.failure_state.value == "NONE"
    assert result.security.run.audit_status == "PARTIAL"
    assert result.security.run.publication_state.value == "NOT_PUBLISHED"
    assert result.artifacts
    assert all(Path(path).exists() for path in result.artifacts)

    store = StateStore(tmp_path / ".audit" / "runs")
    stale_evidence = [
        store.load_evidence(evidence_id)
        for evidence_id in store.list_evidence_ids()
        if store.load_evidence(evidence_id).validity == EvidenceValidity.STALE
    ]
    assert stale_evidence


def test_default_runtime_isolates_all_outputs_in_ignored_git_repository(tmp_path):
    import subprocess

    (tmp_path / "app.py").write_text("print('ok')\n")
    result = run_full_audit(str(tmp_path))
    audit = tmp_path / ".audit"
    assert (audit / ".git").is_dir()
    assert "/.audit/" in (tmp_path / ".gitignore").read_text().splitlines()
    assert {Path(p).name for p in result.artifacts} == {
        "00_inventory.md", "01_coverage.md", "02_analytical.md", "03_audit_ledger.md",
    }
    assert all(Path(p).parent == audit for p in result.artifacts)
    assert subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=audit,
        text=True,
    ).strip() == str(audit)
    assert not (tmp_path / "docs").exists()
    assert all(not f.path.startswith(".audit/") for f in result.discovery.files)


@pytest.mark.parametrize("argument", ["state_dir", "output_dir"])
def test_runtime_rejects_output_outside_audit_vault(tmp_path, argument):
    with pytest.raises(ValueError, match=r"\.audit"):
        run_full_audit(str(tmp_path), **{argument: str(tmp_path / "outside")})
    assert not (tmp_path / "outside").exists()


@pytest.mark.parametrize("phase", ["prepare", "engineering", "full"])
def test_cli_initializes_vault_for_each_persistent_phase(tmp_path, monkeypatch, capsys, phase):
    import sys
    from project_audit.__main__ import main

    (tmp_path / "app.py").write_text("print('ok')\n")
    monkeypatch.setattr(
        sys,
        "argv",
        ["project_audit", "--target", str(tmp_path), "--phase", phase],
    )
    ret = main()
    if phase == "full":
        assert ret in (0, 4)
    else:
        assert ret == 0
    assert (tmp_path / ".audit" / ".git").is_dir()
    assert "/.audit/" in (tmp_path / ".gitignore").read_text()
    if phase == "full":
        assert f"output_dir={tmp_path / '.audit'}" in capsys.readouterr().out


def test_drift_during_semantic_network_response_marks_semantic_evidence_stale(tmp_path):
    from project_audit.delegation import (
        DelegationBackend,
        DelegationResult,
        DelegationStatus,
        WorkerPort,
    )
    from project_audit.semantic_auditor import SemanticAuditor

    source = tmp_path / "app.py"
    source.write_text("print('before')\n")

    class MutatingNetwork(DelegationBackend):
        def delegate(self, request):
            source.write_text("print('after')\n")
            return DelegationResult(
                request.request_id,
                DelegationStatus.SUCCESS,
                {"findings": []},
                None,
                "test",
                0,
            )

    result = run_full_audit(
        str(tmp_path),
        semantic_worker=SemanticAuditor(
            WorkerPort(MutatingNetwork(), "test")
        ),
        semantic_egress_policy=EgressPolicy(
            EgressDestination.APPROVED_EXTERNAL,
            True,
        ),
    )

    assert result.security.run.audit_status == "PARTIAL"
    store = StateStore(tmp_path / ".audit" / "runs")
    assert any(
        store.load_evidence(evidence_id).validity == EvidenceValidity.STALE
        for evidence_id in store.list_evidence_ids()
    )


def test_vertical_slice_marks_current_evidence_stale_on_node_drift(tmp_path):
    from project_audit.classifiers import (
        classify_applicability,
        classify_files,
        classify_stack,
    )
    from project_audit.delegation import (
        DelegationBackend,
        DelegationResult,
        DelegationStatus,
        WorkerPort,
    )
    from project_audit.security_auditor import SecurityAuditor

    source = tmp_path / "app.py"
    source.write_text("print('before')\n")
    discovery = discover(tmp_path)
    prepared = prepare_audit(
        discovery,
        classify_files(discovery),
        classify_applicability(discovery, classify_stack(discovery)),
    )

    class MutatingResponse(DelegationBackend):
        def delegate(self, request):
            source.write_text("print('after')\n")
            return DelegationResult(
                request.request_id,
                DelegationStatus.SUCCESS,
                {"findings": []},
                None,
                "test",
                0,
            )

    prepared.plan.egress_policy = EgressPolicy(
        EgressDestination.APPROVED_EXTERNAL,
        True,
    )
    auditor = SecurityAuditor(
        WorkerPort(MutatingResponse(), "test"),
        prepared.snapshot,
    )
    items = auditor.generate_work_items(prepared.plan)
    for item in items:
        item.data_egress_policy = prepared.plan.egress_policy
    prepared.plan.work_items = items
    store = StateStore(tmp_path / ".audit" / "runs")

    run = Orchestrator(store).execute_vertical_slice(
        prepared.snapshot,
        prepared.plan,
        items,
        auditor,
    )

    assert run.audit_status == "PARTIAL"
    assert any(
        store.load_evidence(evidence_id).validity == EvidenceValidity.STALE
        for evidence_id in store.list_evidence_ids()
    )


def test_normalization_drift_preserves_prior_run_and_marks_new_run_partial(tmp_path, monkeypatch):
    import sys
    import project_audit.runtime as runtime

    source = tmp_path / "app.py"
    source.write_text("print('before')\n")
    command = str(Path(sys.executable).parent / "audit-normalize")
    first = run_full_audit(
        str(tmp_path),
        normalize=True,
        normalize_command=command,
    )
    original = runtime.run_audit_normalize

    def normalize_then_mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        source.write_text("print('after')\n")
        return result

    monkeypatch.setattr(runtime, "run_audit_normalize", normalize_then_mutate)
    second = run_full_audit(
        str(tmp_path),
        normalize=True,
        normalize_command=command,
        overwrite_artifacts=True,
    )

    store = StateStore(tmp_path / ".audit" / "runs")
    first_run = store.load_run(first.security.run.run_id)
    second_run = store.load_run(second.security.run.run_id)

    assert first_run.audit_status == "COMPLETE"
    assert second_run.audit_status == "PARTIAL"
    assert second_run.failure_state.value == "NONE"
    assert second_run.artifact_refs
    assert any(
        store.load_evidence(evidence_id).validity == EvidenceValidity.STALE
        for evidence_id in store.list_evidence_ids()
        if store.load_evidence(evidence_id).work_item_ref in second_run.work_item_refs
    )


def test_default_state_path_cannot_escape_through_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    vault = tmp_path / ".audit"
    vault.mkdir()
    (vault / "runs").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match=r"\.audit"):
        run_full_audit(str(tmp_path))
    assert not list(outside.iterdir())


def test_legacy_docs_audit_is_source_now_that_output_lives_in_vault(tmp_path):
    source = tmp_path / "docs" / "audit" / "review.md"
    source.parent.mkdir(parents=True)
    source.write_text("old manual audit")
    before = build_target_snapshot(discover(tmp_path))
    source.write_text("updated manual audit")
    assert build_target_snapshot(discover(tmp_path)).snapshot_fingerprint != before.snapshot_fingerprint


def test_commit_mode_keeps_target_git_clean_and_audit_history_isolated(tmp_path):
    import subprocess
    from project_audit.models import TargetMode

    (tmp_path / "app.py").write_text("print('ok')\n")
    (tmp_path / ".gitignore").write_text("/.audit/\n")
    for args in (
        ["init", "-q"],
        ["add", "app.py", ".gitignore"],
        [
            "-c", "user.name=Audit Test",
            "-c", "user.email=audit@example.invalid",
            "commit", "-qm", "fixture",
        ],
    ):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    result = run_full_audit(str(tmp_path), target_mode=TargetMode.COMMIT)
    assert result.security.run.audit_status == "COMPLETE"
    assert subprocess.check_output(
        ["git", "status", "--porcelain"],
        cwd=tmp_path,
        text=True,
    ) == ""
    assert subprocess.check_output(
        ["git", "check-ignore", ".audit/00_inventory.md"],
        cwd=tmp_path,
        text=True,
    ).strip() == ".audit/00_inventory.md"

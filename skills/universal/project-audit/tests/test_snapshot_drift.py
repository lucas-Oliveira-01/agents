"""ADR-11: real filesystem mutations must abort the whole audit, then re-run."""
import json
from pathlib import Path

import pytest

from project_audit.discovery import discover
from project_audit.engineering_auditor import EngineeringAuditor
from project_audit.security_pass import DeterministicSecurityAuditor
from project_audit.orchestrator import SnapshotDriftError
from project_audit.planner import build_target_snapshot
from project_audit.runtime import run_full_audit
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
def test_mutation_aborts_without_reports_and_fresh_run_succeeds(tmp_path, monkeypatch, phase):
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
        with pytest.raises(SnapshotDriftError, match="SNAPSHOT_DRIFT"):
            run_full_audit(str(tmp_path))

    assert len(calls) == 1
    store = StateStore(tmp_path / ".audit" / "runs")
    stale = store.load_run(store.list_run_ids()[0])
    assert stale.failure_state.value == "SNAPSHOT_DRIFT"
    assert stale.audit_status == "STALE"
    assert stale.to_dict()["audit_status"] == "STALE"
    assert stale.publication_state.value == "NOT_PUBLISHED"
    assert stale.artifact_refs == []
    assert not list((tmp_path / ".audit").glob("*.md"))
    assert all(store.load_evidence(eid).validity.value == "STALE" for eid in store.list_evidence_ids())

    result = run_full_audit(str(tmp_path))
    assert result.security.run.run_id != stale.run_id
    assert result.prepared.snapshot.snapshot_fingerprint != stale.target_snapshot_ref
    assert result.security.run.audit_status == "COMPLETE"
    assert len(result.artifacts) == 4
    assert store.load_run(stale.run_id).audit_status == "STALE"


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
    assert subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=audit, text=True).strip() == str(audit)
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
    monkeypatch.setattr(sys, "argv", ["project_audit", "--target", str(tmp_path), "--phase", phase])
    ret = main()
    if phase == "full":
        assert ret in (0, 4)
    else:
        assert ret == 0
    assert (tmp_path / ".audit" / ".git").is_dir()
    assert "/.audit/" in (tmp_path / ".gitignore").read_text()
    if phase == "full":
        assert f"output_dir={tmp_path / '.audit'}" in capsys.readouterr().out


def test_drift_during_semantic_network_response_aborts_before_evidence(tmp_path):
    from project_audit.delegation import WorkerPort, DelegationBackend, DelegationResult, DelegationStatus
    from project_audit.models import EgressPolicy, EgressDestination
    from project_audit.semantic_auditor import SemanticAuditor

    source = tmp_path / "app.py"
    source.write_text("print('before')\n")

    class MutatingNetwork(DelegationBackend):
        def delegate(self, request):
            source.write_text("print('after')\n")
            return DelegationResult(request.request_id, DelegationStatus.SUCCESS,
                                    {"findings": []}, None, "test", 0)

    with pytest.raises(SnapshotDriftError):
        run_full_audit(str(tmp_path), semantic_worker=SemanticAuditor(WorkerPort(MutatingNetwork(), "test")),
                       semantic_egress_policy=EgressPolicy(EgressDestination.APPROVED_EXTERNAL, True))
    store = StateStore(tmp_path / ".audit" / "runs")
    assert store.load_run(store.list_run_ids()[0]).audit_status == "STALE"
    assert not list((tmp_path / ".audit").glob("*.md"))


def test_vertical_slice_checks_live_snapshot_between_worker_steps(tmp_path):
    from project_audit.classifiers import classify_applicability, classify_files, classify_stack
    from project_audit.delegation import WorkerPort, DelegationBackend, DelegationResult, DelegationStatus
    from project_audit.models import EgressPolicy, EgressDestination
    from project_audit.orchestrator import Orchestrator
    from project_audit.planner import prepare_audit
    from project_audit.security_auditor import SecurityAuditor

    source = tmp_path / "app.py"
    source.write_text("print('before')\n")
    discovery = discover(tmp_path)
    prepared = prepare_audit(discovery, classify_files(discovery), classify_applicability(discovery, classify_stack(discovery)))
    prepared.plan.egress_policy = EgressPolicy(EgressDestination.APPROVED_EXTERNAL, True)

    class MutatingResponse(DelegationBackend):
        def delegate(self, request):
            source.write_text("print('after')\n")
            return DelegationResult(request.request_id, DelegationStatus.SUCCESS, {"findings": []}, None, "test", 0)

    auditor = SecurityAuditor(WorkerPort(MutatingResponse(), "test"), prepared.snapshot)
    items = auditor.generate_work_items(prepared.plan)
    prepared.plan.work_items = items
    store = StateStore(tmp_path / ".audit" / "runs")
    with pytest.raises(SnapshotDriftError):
        Orchestrator(store).execute_vertical_slice(prepared.snapshot, prepared.plan, items, auditor)
    assert store.load_run(store.list_run_ids()[0]).audit_status == "STALE"
    assert not store.list_evidence_ids()


def test_normalization_drift_restores_previous_artifacts(tmp_path, monkeypatch):
    import sys
    import project_audit.runtime as runtime
    source = tmp_path / "app.py"
    source.write_text("print('before')\n")
    command = str(Path(sys.executable).parent / "audit-normalize")
    first = run_full_audit(str(tmp_path), normalize=True, normalize_command=command)
    prior_paths = [Path(p) for p in first.security.run.artifact_refs]
    prior_bytes = {p: p.read_bytes() for p in prior_paths}
    original = runtime.run_audit_normalize

    def normalize_then_mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        source.write_text("print('after')\n")
        return result

    monkeypatch.setattr(runtime, "run_audit_normalize", normalize_then_mutate)
    with pytest.raises(SnapshotDriftError):
        run_full_audit(str(tmp_path), normalize=True, normalize_command=command, overwrite_artifacts=True)
    assert {p: p.read_bytes() for p in prior_paths} == prior_bytes
    store = StateStore(tmp_path / ".audit" / "runs")
    statuses = [store.load_run(rid).audit_status for rid in store.list_run_ids()]
    assert sorted(statuses) == ["COMPLETE", "STALE"]


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
    for args in (["init", "-q"], ["add", "app.py", ".gitignore"],
                 ["-c", "user.name=Audit Test", "-c", "user.email=audit@example.invalid", "commit", "-qm", "fixture"]):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    result = run_full_audit(str(tmp_path), target_mode=TargetMode.COMMIT)
    assert result.security.run.audit_status == "COMPLETE"
    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=tmp_path, text=True) == ""
    assert subprocess.check_output(["git", "check-ignore", ".audit/00_inventory.md"], cwd=tmp_path, text=True).strip() == ".audit/00_inventory.md"

"""Regression tests for L3W sandboxing, memory bubbles, and lifecycle control."""

import sys
from pathlib import Path

import pytest

from omniroute_delegation.contracts import DelegateKind, ExecutionState
from omniroute_delegation.exceptions import SandboxError, SandboxUnavailableError
from omniroute_delegation.l3w_delegate import L3WConfig, L3WDelegate
from omniroute_delegation.worker_manager import (
    MemoryMode,
    MemoryScope,
    MemoryScopeConfig,
    SandboxPolicy,
    WorkerManager,
    WorkspaceSandbox,
)


@pytest.mark.asyncio
async def test_workspace_sandbox_never_uses_repository_root(tmp_path: Path):
    source = tmp_path / "repo"
    source.mkdir()
    (source / "app.py").write_text("print('ok')", encoding="utf-8")

    sandbox = await WorkspaceSandbox.create(source_root=str(source))
    try:
        assert sandbox.root != source.resolve()
        assert sandbox.root != source.resolve().parent
        assert (sandbox.root / "app.py").exists()

        (sandbox.root / "app.py").write_text("print('changed')", encoding="utf-8")
        assert (source / "app.py").read_text(encoding="utf-8") == "print('ok')"
    finally:
        await sandbox.cleanup()


@pytest.mark.asyncio
async def test_workspace_path_escape_is_rejected(tmp_path: Path):
    sandbox = await WorkspaceSandbox.create(workspace_dir=str(tmp_path / "sandbox"))
    try:
        with pytest.raises(SandboxError):
            sandbox.assert_inside(str(tmp_path / "outside.txt"))
    finally:
        await sandbox.cleanup()


def test_memory_bubble_scopes_environment_and_orders(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    memory_root = tmp_path / "memory"

    scope = MemoryScope(
        MemoryScopeConfig(
            mode=MemoryMode.BUBBLE,
            bubble_id="bubble-a",
            root_dir=memory_root,
            cleanup=False,
        )
    )
    environment = scope.prepare(workspace, {"PATH": "/usr/bin"})
    scope.append_order("Inspect the failing test.")

    assert environment["AI_MEMORY_SCOPE"] == "bubble"
    assert environment["AI_MEMORY_BUBBLE_ID"] == "bubble-a"
    assert environment["AI_MEMORY_PROJECT"] == "worker_bubble_bubble-a"
    assert "Inspect the failing test." in scope.orders_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_worker_manager_enforces_timeout(tmp_path: Path):
    manager = WorkerManager()
    workspace = await WorkspaceSandbox.create(workspace_dir=str(tmp_path / "workspace"))

    result = await manager.run(
        command=[sys.executable, "-c", "import time; time.sleep(2)"],
        workspace=workspace,
        timeout=0.2,
        environment={"PATH": "/usr/bin", "PYTHONPATH": str(Path.cwd() / "src")},
        policy=SandboxPolicy(require_os_sandbox=False, use_bwrap=False),
    )

    assert result.timed_out
    assert result.execution_state == ExecutionState.TIMED_OUT.value
    assert manager.active_worker_ids == []


@pytest.mark.asyncio
async def test_l3w_delegate_preserves_state_across_orders(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    memory_root = tmp_path / "memory"

    delegate = L3WDelegate()
    config = L3WConfig(
        harness_executable=sys.executable,
        harness_args=[
            "-c",
            "from pathlib import Path; Path('worker_state.txt').write_text('stateful', encoding='utf-8'); print('WORKER_OK')",
        ],
        workspace_dir=str(workspace),
        memory_mode=MemoryMode.BUBBLE,
        memory_bubble_id="orders-a",
        memory_root=str(memory_root),
        strict_sandbox=False,
        use_bwrap=False,
        cleanup_memory=True,
        persist_workspace=False,
    )

    session = await delegate.start(config)
    first = await session.execute_order("First order")
    second = await session.execute_order("Second order")

    assert first.delegate_kind == DelegateKind.L3W
    assert first.state == ExecutionState.SUCCESS
    assert second.state == ExecutionState.SUCCESS
    assert (workspace / "worker_state.txt").exists()

    await delegate.stop(session.session_id, success=True)
    assert not (memory_root / "orders-a").exists()


@pytest.mark.asyncio
async def test_strict_sandbox_fails_closed_when_bwrap_is_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("shutil.which", lambda name: None)
    manager = WorkerManager()
    workspace = await WorkspaceSandbox.create(workspace_dir=str(tmp_path / "workspace"))

    with pytest.raises(SandboxUnavailableError):
        await manager.run(
            command=[sys.executable, "-c", "print('should not run')"],
            workspace=workspace,
            timeout=5,
            environment={"PATH": "/usr/bin"},
            policy=SandboxPolicy(require_os_sandbox=True, use_bwrap=True),
        )

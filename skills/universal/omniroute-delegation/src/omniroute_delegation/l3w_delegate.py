"""Stateful L3W worker facade with isolated workspace and memory scope."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from pydantic import BaseModel, Field

from .contracts import AuditContract, DelegateKind, DelegationTask, ExecutionState, LeafContract
from .exceptions import WorkerManagerError
from .worker_manager import (
    MemoryMode,
    MemoryScope,
    MemoryScopeConfig,
    SandboxPolicy,
    WorkerManager,
    WorkspaceSandbox,
)


class L3WConfig(BaseModel):
    """Runtime policy selected by the Level 2 orchestrator."""

    harness_executable: str = "opencode"
    harness_args: List[str] = Field(default_factory=list)
    timeout_seconds: float = 1800.0
    repository_root: Optional[str] = None
    workspace_dir: Optional[str] = None
    memory_mode: MemoryMode = MemoryMode.BUBBLE
    memory_bubble_id: Optional[str] = None
    memory_root: Optional[str] = None
    cleanup_memory: bool = True
    consolidate_memory: bool = False
    inherit_environment: List[str] = Field(
        default_factory=lambda: ["PATH", "HOME", "USER", "LANG", "LC_ALL"]
    )
    memory_write_paths: List[str] = Field(default_factory=list)
    memory_mounts: Dict[str, str] = Field(default_factory=dict)
    memory_sandbox_path: str = "/l3w-memory"
    strict_sandbox: bool = True
    use_bwrap: bool = True
    sandbox_read_only_paths: List[str] = Field(default_factory=list)
    persist_workspace: bool = False


@dataclass
class L3WSession:
    """Stateful task context persisted across multiple worker orders."""

    session_id: str
    config: L3WConfig
    workspace: WorkspaceSandbox
    memory: MemoryScope
    manager: WorkerManager
    order_count: int = 0

    def add_order(self, instruction: str) -> None:
        self.memory.append_order(instruction)

    async def execute_order(
        self,
        task: str,
        target_file: Optional[str] = None,
    ) -> AuditContract:
        self.add_order(task)

        command = [self.config.harness_executable]
        command.extend(self.config.harness_args)
        command.extend(["--task", task])

        if target_file:
            target = self.workspace.assert_inside(target_file)
            relative = target.relative_to(self.workspace.root).as_posix()
            command.extend(["--target", f"/workspace/{relative}"])

        environment = _build_environment(self.config, self.memory)
        policy = _build_policy(self.config, self.memory)

        result = await self.manager.run(
            command=command,
            workspace=self.workspace,
            timeout=self.config.timeout_seconds,
            environment=environment,
            policy=policy,
        )
        self.order_count += 1

        state = ExecutionState(result.execution_state)
        leaf = LeafContract(raw_output=result.output)

        return AuditContract(
            state=state,
            findings=leaf.findings,
            raw_errors=(
                [{"worker_output": result.output}]
                if state not in {ExecutionState.SUCCESS, ExecutionState.PARTIAL_COVERAGE}
                and result.output
                else []
            ),
            attempts=self.order_count,
            delegate_kind=DelegateKind.L3W,
            leaf=leaf,
            worker_id=result.worker_id,
            workspace_dir=result.workspace_dir,
            changed_files=result.changed_files,
        )

    async def finalize(self, success: bool) -> None:
        self.memory.finalize(self.workspace.root, success)
        if not self.config.persist_workspace:
            await self.workspace.cleanup()


class L3WDelegate:
    """Stateful worker service for isolated OpenCode harness execution."""

    kind = DelegateKind.L3W

    def __init__(self, manager: Optional[WorkerManager] = None) -> None:
        self._manager = manager or WorkerManager()
        self._sessions: dict[str, L3WSession] = {}

    async def start(self, config: Optional[L3WConfig] = None) -> L3WSession:
        effective = config or L3WConfig()
        if effective.timeout_seconds <= 0:
            raise WorkerManagerError("L3W timeout must be positive.")

        workspace = await WorkspaceSandbox.create(
            source_root=effective.repository_root,
            workspace_dir=effective.workspace_dir,
        )
        memory = MemoryScope(
            MemoryScopeConfig(
                mode=effective.memory_mode,
                bubble_id=effective.memory_bubble_id,
                root_dir=Path(effective.memory_root).expanduser()
                if effective.memory_root
                else None,
                cleanup=effective.cleanup_memory,
                consolidate=effective.consolidate_memory,
                sandbox_mount=effective.memory_sandbox_path,
            )
        )
        base_environment = _base_environment(effective.inherit_environment)
        memory.prepare(workspace.root, base_environment)

        session = L3WSession(
            session_id=os.urandom(8).hex(),
            config=effective,
            workspace=workspace,
            memory=memory,
            manager=self._manager,
        )
        self._sessions[session.session_id] = session
        return session

    async def issue_order(
        self,
        session_id: str,
        task: str,
        target_file: Optional[str] = None,
    ) -> AuditContract:
        session = self._sessions.get(session_id)
        if session is None:
            raise WorkerManagerError(f"Unknown L3W session: {session_id}")
        return await session.execute_order(task, target_file=target_file)

    async def add_order(self, session_id: str, instruction: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            raise WorkerManagerError(f"Unknown L3W session: {session_id}")
        session.add_order(instruction)

    async def stop(self, session_id: str, success: bool = True) -> None:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return
        await session.manager.shutdown_all()
        await session.finalize(success)

    async def execute(
        self,
        task: DelegationTask,
        workspace_dir: str,
        harness: str,
    ) -> AuditContract:
        config = L3WConfig(
            harness_executable=harness,
            workspace_dir=workspace_dir,
            persist_workspace=True,
        )
        session = await self.start(config)
        try:
            return await session.execute_order(task.task)
        finally:
            await self.stop(session.session_id, success=True)


def _base_environment(names: Sequence[str]) -> Mapping[str, str]:
    return {name: value for name in names if (value := os.environ.get(name)) is not None}


def _build_environment(
    config: L3WConfig,
    memory: MemoryScope,
) -> Mapping[str, str]:
    environment = dict(_base_environment(config.inherit_environment))
    environment.update(memory.environment_overrides())
    environment["L3W_EXECUTION_MODE"] = "stateful"
    environment["L3W_WORKSPACE_ROOT"] = "/workspace"
    return environment


def _build_policy(config: L3WConfig, memory: MemoryScope) -> SandboxPolicy:
    writable = list(config.memory_write_paths)
    if memory.root_dir:
        writable.append(str(memory.root_dir))
    return SandboxPolicy(
        require_os_sandbox=config.strict_sandbox,
        use_bwrap=config.use_bwrap,
        writable_paths=tuple(dict.fromkeys(writable)),
        additional_read_only_paths=tuple(config.sandbox_read_only_paths),
        writable_bindings={**config.memory_mounts, **({str(memory.root_dir): config.memory_sandbox_path} if memory.root_dir else {})},
    )

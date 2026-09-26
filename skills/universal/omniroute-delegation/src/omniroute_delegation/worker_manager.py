"""Workspace sandboxing, memory bubbles, and supervised worker lifecycle management."""

from __future__ import annotations

import asyncio
import ctypes
import json
import os
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from .contracts import ExecutionState
from .exceptions import (
    MemoryScopeError,
    SandboxError,
    SandboxUnavailableError,
    WorkerManagerError,
)


class MemoryMode(str, Enum):
    GLOBAL = "GLOBAL"
    BUBBLE = "BUBBLE"


@dataclass(frozen=True)
class MemoryScopeConfig:
    mode: MemoryMode = MemoryMode.BUBBLE
    bubble_id: Optional[str] = None
    root_dir: Optional[Path] = None
    cleanup: bool = True
    consolidate: bool = False


@dataclass
class MemoryScope:
    """Owns task-scoped memory identity and order injection."""

    config: MemoryScopeConfig
    bubble_id: Optional[str] = None
    root_dir: Optional[Path] = None
    orders_file: Optional[Path] = None
    environment: Dict[str, str] = field(default_factory=dict)

    def prepare(self, workspace: Path, base_environment: Mapping[str, str]) -> Dict[str, str]:
        env = dict(base_environment)
        if self.config.mode == MemoryMode.GLOBAL:
            env["AI_MEMORY_SCOPE"] = "global"
            self.environment = env
            return env

        self.bubble_id = self.config.bubble_id or f"l3w-{uuid.uuid4().hex[:12]}"
        base = self.config.root_dir or (Path.home() / ".cache" / "omniroute-delegation" / "l3w")
        self.root_dir = Path(base).expanduser().resolve() / self.bubble_id
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.orders_file = self.root_dir / "orders.jsonl"

        env["AI_MEMORY_SCOPE"] = "bubble"
        env["AI_MEMORY_BUBBLE_ID"] = self.bubble_id
        env["AI_MEMORY_PROJECT"] = f"worker_bubble_{self.bubble_id}"
        env["AI_MEMORY_ROOT"] = str(self.root_dir)
        env["AI_MEMORY_ORDERS_FILE"] = str(self.orders_file)
        env["L3W_MEMORY_BUBBLE_ID"] = self.bubble_id
        env["L3W_MEMORY_BUBBLE_ROOT"] = str(self.root_dir)

        metadata = {
            "bubble_id": self.bubble_id,
            "workspace_dir": str(workspace),
            "mode": self.config.mode.value,
        }
        (self.root_dir / "scope.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        self.environment = env
        return env

    def environment_overrides(self) -> Dict[str, str]:
        return dict(self.environment)

    def append_order(self, instruction: str, source: str = "l2") -> None:
        if not self.orders_file:
            raise MemoryScopeError("Memory scope has not been prepared.")
        record = {
            "order_id": uuid.uuid4().hex,
            "source": source,
            "instruction": instruction,
        }
        with self.orders_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def finalize(self, workspace: Path, success: bool) -> Optional[Path]:
        if self.config.mode == MemoryMode.GLOBAL:
            return None
        if not self.root_dir:
            raise MemoryScopeError("Memory scope was never prepared.")

        handoff = workspace / ".l3w" / "memory_handoff.json"
        handoff.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "bubble_id": self.bubble_id,
            "success": success,
            "consolidate": self.config.consolidate,
            "root_dir": str(self.root_dir),
            "orders_file": str(self.orders_file),
        }
        handoff.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        if self.config.cleanup and not self.config.consolidate:
            shutil.rmtree(self.root_dir, ignore_errors=True)
        return handoff


@dataclass(frozen=True)
class SandboxPolicy:
    """Controls OS-level worker isolation."""

    require_os_sandbox: bool = True
    use_bwrap: bool = True
    read_only_paths: Sequence[str] = (
        "/usr",
        "/usr/local",
        "/bin",
        "/sbin",
        "/lib",
        "/lib64",
        "/etc",
    )
    writable_paths: Sequence[str] = ()
    additional_read_only_paths: Sequence[str] = ()


@dataclass
class WorkspaceSandbox:
    """A fenced workspace that never points at the target repository root."""

    root: Path
    source_root: Optional[Path] = None
    git_worktree: bool = False
    temporary: bool = True

    @classmethod
    async def create(
        cls,
        source_root: Optional[str] = None,
        workspace_dir: Optional[str] = None,
    ) -> "WorkspaceSandbox":
        source = Path(source_root).resolve() if source_root else None

        if workspace_dir:
            root = Path(workspace_dir).expanduser().resolve()
            root.mkdir(parents=True, exist_ok=True)
            if source and _is_same_or_inside(root, source):
                raise SandboxError("L3W workspace must not be the target repository root or a child of it.")
            return cls(root=root, source_root=source, temporary=False)

        root = Path(tempfile.mkdtemp(prefix="omniroute-l3w-"))

        if source is None:
            return cls(root=root, temporary=True)

        git_root = await _git_toplevel(source)
        if git_root:
            await _run_checked(
                ["git", "-C", str(git_root), "worktree", "add", "--detach", str(root), "HEAD"]
            )
            return cls(root=root, source_root=git_root, git_worktree=True, temporary=True)

        shutil.copytree(source, root, dirs_exist_ok=True)
        return cls(root=root, source_root=source, git_worktree=False, temporary=True)

    def assert_inside(self, candidate: str) -> Path:
        path = Path(candidate).expanduser().resolve()
        if not _is_same_or_inside(path, self.root):
            raise SandboxError(f"Worker path escapes the sandbox: {path}")
        return path

    async def diff(self) -> str:
        if not self.git_worktree:
            return ""
        return await _run_capture(["git", "-C", str(self.root), "diff", "--binary"])

    async def changed_files(self) -> List[str]:
        if not self.git_worktree:
            return []
        output = await _run_capture(
            ["git", "-C", str(self.root), "status", "--short", "--untracked-files=all"]
        )
        return [line[3:] if len(line) >= 3 else line for line in output.splitlines() if line.strip()]

    async def cleanup(self) -> None:
        if not self.temporary:
            return
        if self.git_worktree and self.source_root:
            await _run_capture(
                [
                    "git",
                    "-C",
                    str(self.source_root),
                    "worktree",
                    "remove",
                    "--force",
                    str(self.root),
                ]
            )
            shutil.rmtree(self.root, ignore_errors=True)
            return
        shutil.rmtree(self.root, ignore_errors=True)


@dataclass
class WorkerRunResult:
    worker_id: str
    execution_state: str
    return_code: int
    output: str
    workspace_dir: str
    changed_files: List[str] = field(default_factory=list)
    timed_out: bool = False


def _watchdog_preexec() -> None:
    if os.name != "posix":
        return
    try:
        libc = ctypes.CDLL(None)
        libc.prctl(1, 15, 0, 0, 0)
    except Exception:
        return


class WorkerManager:
    """Launches and supervises L3W workers through a parent-death-aware watchdog."""

    def __init__(
        self,
        python_executable: Optional[str] = None,
        watchdog_module: str = "omniroute_delegation.worker_watchdog",
    ) -> None:
        self._python = python_executable or sys.executable
        self._watchdog_module = watchdog_module
        self._active: Dict[str, asyncio.subprocess.Process] = {}

    @property
    def active_worker_ids(self) -> List[str]:
        return list(self._active)

    async def run(
        self,
        command: Sequence[str],
        workspace: WorkspaceSandbox,
        timeout: float,
        environment: Mapping[str, str],
        policy: SandboxPolicy,
    ) -> WorkerRunResult:
        if timeout <= 0:
            raise ValueError("Worker timeout must be positive.")

        worker_id = uuid.uuid4().hex[:12]
        workspace.root.joinpath(".l3w").mkdir(parents=True, exist_ok=True)

        sandboxed_command = self._build_sandbox_command(
            list(command),
            workspace,
            policy,
        )

        manifest_fd, manifest_name = tempfile.mkstemp(
            prefix=f"omniroute-l3w-{worker_id}-", suffix=".json"
        )
        os.close(manifest_fd)
        manifest = Path(manifest_name)
        config = {
            "command": sandboxed_command,
            "cwd": str(workspace.root),
            "env": dict(environment),
            "timeout": timeout,
        }
        manifest.write_text(json.dumps(config), encoding="utf-8")

        watchdog_command = [
            self._python,
            "-m",
            self._watchdog_module,
            "--manifest",
            str(manifest),
        ]

        process = await asyncio.create_subprocess_exec(
            *watchdog_command,
            cwd=str(workspace.root),
            env=dict(environment),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
            preexec_fn=_watchdog_preexec if os.name == "posix" else None,
        )
        self._active[worker_id] = process

        try:
            output_bytes, _ = await process.communicate()
            output = output_bytes.decode("utf-8", errors="replace")
        except asyncio.CancelledError:
            await self.terminate(worker_id, graceful=True)
            raise
        finally:
            self._active.pop(worker_id, None)
            try:
                manifest.unlink()
            except FileNotFoundError:
                pass

        return_code = process.returncode if process.returncode is not None else 1
        timed_out = return_code == 124
        if return_code == 0:
            state = ExecutionState.SUCCESS.value
        elif timed_out:
            state = ExecutionState.TIMED_OUT.value
        elif return_code in (130, 143):
            state = ExecutionState.CANCELLED.value
        else:
            state = ExecutionState.FAILED.value

        return WorkerRunResult(
            worker_id=worker_id,
            execution_state=state,
            return_code=return_code,
            output=output,
            workspace_dir=str(workspace.root),
            changed_files=await workspace.changed_files(),
            timed_out=timed_out,
        )

    async def terminate(self, worker_id: str, graceful: bool = True) -> None:
        process = self._active.get(worker_id)
        if process is None or process.returncode is not None:
            return
        if graceful:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
                return
            except asyncio.TimeoutError:
                pass
        process.kill()
        await process.wait()

    async def shutdown_all(self) -> None:
        for worker_id in list(self._active):
            await self.terminate(worker_id, graceful=True)

    @staticmethod
    def _build_sandbox_command(
        command: List[str],
        workspace: WorkspaceSandbox,
        policy: SandboxPolicy,
    ) -> List[str]:
        if not policy.use_bwrap:
            if policy.require_os_sandbox:
                raise SandboxUnavailableError("Strict L3W execution requires an OS-level sandbox.")
            return command

        bwrap = shutil.which("bwrap")
        if not bwrap:
            if policy.require_os_sandbox:
                raise SandboxUnavailableError(
                    "bubblewrap is required for strict L3W execution but was not found."
                )
            return command

        wrapped: List[str] = [
            bwrap,
            "--die-with-parent",
            "--new-session",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
        ]

        for path in policy.read_only_paths:
            if os.path.exists(path):
                wrapped.extend(["--ro-bind", path, path])

        for path in policy.additional_read_only_paths:
            if os.path.exists(path):
                wrapped.extend(["--ro-bind", path, path])

        for path in policy.writable_paths:
            if os.path.exists(path):
                wrapped.extend(["--bind", path, path])

        wrapped.extend(
            [
                "--bind",
                str(workspace.root),
                "/workspace",
                "--chdir",
                "/workspace",
            ]
        )
        wrapped.extend(command)
        return wrapped


def _is_same_or_inside(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([str(path), str(root)]) == str(root)
    except ValueError:
        return False


async def _git_toplevel(path: Path) -> Optional[Path]:
    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(path),
        "rev-parse",
        "--show-toplevel",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    if process.returncode != 0:
        return None
    return Path(stdout.decode().strip()).resolve()


async def _run_checked(command: Sequence[str]) -> None:
    process = await asyncio.create_subprocess_exec(*command)
    code = await process.wait()
    if code != 0:
        raise WorkerManagerError(f"Command failed with exit code {code}: {' '.join(command)}")


async def _run_capture(command: Sequence[str]) -> str:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        error = stderr.decode("utf-8", errors="replace").strip()
        raise WorkerManagerError(error or f"Command failed: {' '.join(command)}")
    return stdout.decode("utf-8", errors="replace")

"""Compatibility adapter for the stateful L3W service."""

from __future__ import annotations

import json
from typing import Dict

from .l3w_delegate import L3WConfig, L3WDelegate
from .worker_manager import MemoryMode

_ACTIVE_SESSIONS: Dict[str, object] = {}


async def dispatch_opencode_worker(
    task: str,
    target_file: str = "",
    workspace_dir: str = "",
    isolated_memory: bool = True,
    timeout_seconds: float = 1800.0,
) -> str:
    """Run one supervised OpenCode L3W order and return a JSON receipt."""
    delegate = L3WDelegate()
    config = L3WConfig(
        workspace_dir=workspace_dir or None,
        memory_mode=MemoryMode.BUBBLE if isolated_memory else MemoryMode.GLOBAL,
        timeout_seconds=timeout_seconds,
        strict_sandbox=True,
        use_bwrap=True,
    )
    session = await delegate.start(config)
    _ACTIVE_SESSIONS[session.session_id] = (delegate, session)

    result = await session.execute_order(
        task,
        target_file=target_file or None,
    )
    return json.dumps(
        {
            "session_id": session.session_id,
            "state": result.state.value,
            "worker_id": result.worker_id,
            "workspace_dir": result.workspace_dir,
            "changed_files": result.changed_files,
            "output": result.leaf.raw_output if result.leaf else None,
        },
        ensure_ascii=False,
    )


async def manage_workers(action: str, worker_id: str = "") -> str:
    """List or stop L3W sessions."""
    if action == "list":
        if not _ACTIVE_SESSIONS:
            return "No active L3W sessions."
        return "\n".join(
            f"Session {session_id} | Stateful L3W session"
            for session_id in _ACTIVE_SESSIONS
        )

    if action in {"kill", "stop"}:
        entry = _ACTIVE_SESSIONS.pop(worker_id, None)
        if entry is None:
            return f"L3W session {worker_id} not found."
        delegate, session = entry
        await delegate.stop(session.session_id, success=False)
        return f"L3W session {worker_id} stopped."

    return f"Unknown worker action: {action}"

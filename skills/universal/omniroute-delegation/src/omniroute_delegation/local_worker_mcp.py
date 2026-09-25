#!/usr/bin/env python3
import asyncio
import os
import subprocess
import uuid
import json


# In-memory registry of workers
active_workers = {}


async def dispatch_opencode_worker(
    task: str,
    target_file: str = "",
    workspace_dir: str = "",
    isolated_memory: bool = False
) -> str:
    """
    Instantiates an OpenCode subagent locally to perform a task directly on the file system.
    This saves your context by delegating file read/write operations to the OpenCode harness
    which is powered by OmniRouter (infinite tokens).
    
    Args:
        task: The instruction for OpenCode (e.g., "Refactor the authentication logic in UserDAO").
        target_file: Optional. A specific file to edit.
        workspace_dir: Optional. The directory where OpenCode should run. Defaults to current.
        isolated_memory: If True, creates an isolated ai-memory scope for this worker.
    """
    worker_id = str(uuid.uuid4())[:8]
    work_dir = workspace_dir if workspace_dir else os.getcwd()
    
    env = os.environ.copy()
    if isolated_memory:
        # Override project so ai-memory resolves a blank slate for this worker
        env["AI_MEMORY_PROJECT"] = f"worker_bubble_{worker_id}"
    
    cmd = ["opencode", "--task", task]
    if target_file:
        cmd.extend(["--target", target_file])
        
    try:
        # Launch asynchronously
        process = subprocess.Popen(
            cmd,
            cwd=work_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        active_workers[worker_id] = {
            "process": process,
            "task": task,
            "dir": work_dir
        }
        return f"OpenCode worker {worker_id} dispatched successfully. Running in background."
    except Exception as e:
        return f"Failed to dispatch worker: {str(e)}"


async def manage_workers(action: str, worker_id: str = "") -> str:
    """
    List, status, or kill active OpenCode workers.
    Actions: 'list', 'kill'.
    """
    if action == "list":
        if not active_workers:
            return "No active workers."
        lines = []
        for wid, w in active_workers.items():
            status = "Running" if w["process"].poll() is None else f"Exited ({w['process'].returncode})"
            lines.append(f"Worker {wid} | Status: {status} | Task: {w['task'][:50]}")
        return "\n".join(lines)
    
    elif action == "kill":
        if worker_id in active_workers:
            proc = active_workers[worker_id]["process"]
            if proc.poll() is None:
                proc.terminate()
                return f"Worker {worker_id} terminated."
            return f"Worker {worker_id} was already finished."
        return f"Worker {worker_id} not found."
    
    return f"Unknown action: {action}"

if __name__ == "__main__":
    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    
    asyncio.run(main())

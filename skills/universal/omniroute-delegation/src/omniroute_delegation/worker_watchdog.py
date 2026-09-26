"""Process watchdog for stateful L3W harness execution.

The watchdog is a direct child of the orchestrator. It supervises the actual
harness process, enforces an independent timeout, and kills the harness process
group when the watchdog receives a shutdown signal. On Linux, PR_SET_PDEATHSIG
also terminates the watchdog when its orchestrator parent dies.
"""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import os
import signal
from typing import Dict, List


def _set_parent_death_signal(signum: int) -> None:
    if os.name != "posix":
        return
    try:
        libc = ctypes.CDLL(None)
        libc.prctl(1, signum, 0, 0, 0)
    except Exception:
        return


def _preexec_watchdog() -> None:
    if hasattr(os, "setsid"):
        os.setsid()
    _set_parent_death_signal(signal.SIGTERM)


def _preexec_worker() -> None:
    _set_parent_death_signal(signal.SIGKILL)


def _kill_process_group(pid: int, sig: signal.Signals) -> None:
    if os.name == "posix":
        try:
            os.killpg(pid, sig)
            return
        except ProcessLookupError:
            return
        except PermissionError:
            pass

    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        pass


async def _run(config: Dict[str, Any]) -> int:
    command: List[str] = list(config["command"])
    cwd = str(config["cwd"])
    env = dict(config["env"])
    timeout = float(config["timeout"])

    stop_event = asyncio.Event()

    def request_stop() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, request_stop)
        except (NotImplementedError, RuntimeError):
            pass

    child = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
        preexec_fn=_preexec_worker if os.name == "posix" else None,
    )

    communication = asyncio.create_task(child.communicate())
    stop_wait = asyncio.create_task(stop_event.wait())

    done, _ = await asyncio.wait(
        {communication, stop_wait},
        timeout=timeout,
        return_when=asyncio.FIRST_COMPLETED,
    )

    if communication in done:
        stop_wait.cancel()
        output, _ = communication.result()
        if output:
            os.write(1, output)
        return child.returncode if child.returncode is not None else 1

    stop_wait.cancel()

    if stop_event.is_set():
        _kill_process_group(child.pid, signal.SIGTERM)
        try:
            output, _ = await asyncio.wait_for(communication, timeout=5.0)
        except asyncio.TimeoutError:
            _kill_process_group(child.pid, signal.SIGKILL)
            output, _ = await communication
        if output:
            os.write(1, output)
        return 143

    _kill_process_group(child.pid, signal.SIGTERM)
    try:
        output, _ = await asyncio.wait_for(communication, timeout=5.0)
    except asyncio.TimeoutError:
        _kill_process_group(child.pid, signal.SIGKILL)
        output, _ = await communication

    if output:
        os.write(1, output)
    return 124


def main() -> int:
    parser = argparse.ArgumentParser(description="Supervise an L3W harness process.")
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    with open(args.manifest, "r", encoding="utf-8") as handle:
        config = json.load(handle)

    return asyncio.run(_run(config))


if __name__ == "__main__":
    raise SystemExit(main())

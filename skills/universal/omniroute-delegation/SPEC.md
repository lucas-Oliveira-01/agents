# OmniRoute Delegation Specification

## 1. Scope

This skill owns the OmniRoute delegation boundary and the supervised L3W worker service. External orchestration skills remain outside the modification boundary.

## 2. L3W invariants

The implementation MUST provide:

- one stateful `L3WDelegate` service;
- one `WorkerManager` lifecycle authority;
- one isolated `WorkspaceSandbox` per configured worker session;
- an explicit `MemoryScope` selected by the L2;
- a parent-death-aware watchdog;
- strict timeout and cleanup semantics;
- typed execution states and typed worker receipts.

## 3. Worker lifecycle

```text
START
  ↓
WORKSPACE_READY
  ↓
MEMORY_READY
  ↓
WATCHDOG_RUNNING
  ↓
HARNESS_RUNNING
  ├── SUCCESS
  ├── TIMED_OUT
  ├── CANCELLED
  └── FAILED
  ↓
FINALIZE
  ↓
CONSOLIDATE or CLEANUP
```

A worker session may execute multiple orders. Each order reuses the same workspace and memory scope, preserving state without requiring a permanently running process.

## 4. Process supervision

The L2 creates only the watchdog process directly.

On normal shutdown, the watchdog terminates the harness process group, waits for graceful exit, and escalates to SIGKILL after the grace period.

On orchestrator parent death, the watchdog receives `PR_SET_PDEATHSIG`.

The sandboxed harness additionally uses `PR_SET_PDEATHSIG=SIGKILL` and bubblewrap `--die-with-parent` when strict sandboxing is enabled.

## 5. Sandbox policy

The default L3W policy is fail-closed.

If strict isolation is requested and the configured OS sandbox is unavailable, the worker MUST NOT execute.

A repository target is never used directly as the worker current directory.

Git repositories use detached worktrees where possible so the worker receives a mutable tree without mutating the source working tree.

## 6. Memory policy

The L2 selects one of:

- `GLOBAL`: reuse configured system memory;
- `BUBBLE`: create an isolated memory identity per selected bubble.

Multiple bubbles may coexist simultaneously.

Orders can be appended to the bubble without changing the worker source code or global memory namespace.

Bubble finalization can clean transient state or preserve a controlled handoff for later consolidation.

## 7. Public service API

The primary operations are `L3WDelegate.start()`, `issue_order()`, `add_order()`, `stop()`, and `execute()`.

The legacy `local_worker_mcp` module is an adapter over this service and MUST NOT create raw subprocesses.

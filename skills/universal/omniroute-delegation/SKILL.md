---
name: omniroute-delegation
description: Universal stateless L3T delegation and supervised stateful L3W worker execution.
---

# OmniRoute Delegation Skill

This skill defines secure L3T and L3W delegation services for agents interacting with the OmniRoute ecosystem.

## Execution boundaries

All stateless delegations MUST pass through `DelegationGateway`.

All stateful workers MUST pass through `L3WDelegate` and `WorkerManager`.

The L3W runtime MUST NOT launch a raw child process directly from an orchestration path.

## L3W architecture

```text
L2
 │
 ▼
L3WDelegate
 │
 ├── MemoryScope
 │    ├── GLOBAL
 │    └── BUBBLE
 │
 ├── WorkspaceSandbox
 │    ├── isolated temporary workspace
 │    └── detached Git worktree when a repository is supplied
 │
 └── WorkerManager
      │
      ▼
   Watchdog
      │
      ▼
   Harness / OpenCode
```

## Stateful behavior

State is preserved across orders through the isolated workspace, selected memory scope, worker session identifier, and append-only memory order stream.

An L2 can create multiple independent memory bubbles and inject additional orders into each session.

## Memory policy

`MemoryMode.GLOBAL` preserves the caller's configured memory environment.

`MemoryMode.BUBBLE` creates an isolated task-scoped memory identity using `AI_MEMORY_SCOPE`, `AI_MEMORY_BUBBLE_ID`, `AI_MEMORY_PROJECT`, `AI_MEMORY_ROOT`, and `AI_MEMORY_ORDERS_FILE`.

Bubble cleanup is explicit. Successful consolidation can preserve the bubble for later controlled consumption.

## Workspace isolation

The worker MUST NOT execute in the target repository root.

When a repository root is provided and no explicit workspace is supplied, the skill creates a detached Git worktree when possible or a temporary filesystem copy otherwise.

Every target file is validated to remain inside the worker workspace.

For strict OS-level isolation, the runtime uses bubblewrap with `--die-with-parent`. If strict sandboxing is requested and bubblewrap is unavailable, execution fails closed.

## Process lifecycle

The worker process is supervised by a dedicated watchdog.

The watchdog provides strict execution timeout, graceful termination, forced termination after the grace period, process-group cleanup, and parent-death signalling.

No raw `subprocess.Popen` worker launcher is permitted.

## Contracts and state

L3W results use the same Pydantic execution model as L3T and include `DelegateKind.L3W`, `ExecutionState`, `LeafContract`, worker identifier, sandbox workspace, and changed files.

The execution state distinguishes `RUNNING`, `SUCCESS`, `PARTIAL_COVERAGE`, `SCHEMA_VIOLATION`, `FAILED`, `TIMED_OUT`, and `CANCELLED`.

## Security invariants

- Never run an L3W worker in the target repository root.
- Never launch an unmanaged child process.
- Never inherit arbitrary environment variables by default.
- Never expose the memory root unless explicitly mounted by policy.
- Never silently fall back from strict sandboxing to unsandboxed execution.
- Treat worker output as untrusted evidence.
- Preserve valid workspace changes as explicit artifacts before cleanup.

# Sources and Provenance

## Origin

This skill standardizes interactions with the OmniRoute MCP gateway and supervised local worker execution.

## L3W Architecture Decision

The previous worker implementation used an unmanaged `subprocess.Popen` registry. That design did not guarantee timeout enforcement, cleanup, workspace isolation, or parent-death handling.

The L3W implementation replaces it with:

- `WorkerManager` for lifecycle ownership;
- `worker_watchdog` for parent-death supervision and process-group cleanup;
- `WorkspaceSandbox` for isolated Git worktrees or temporary copies;
- `MemoryScope` for GLOBAL or BUBBLE memory routing;
- `L3WDelegate` as the stateful service boundary.

## Operational Contract

The Level 2 orchestrator selects the harness executable and arguments, worker timeout, repository/workspace, memory mode and bubble identifier, memory mount paths, strict sandbox policy, and workspace persistence policy.

The skill does not modify external orchestrators in this change.

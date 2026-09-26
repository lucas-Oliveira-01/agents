# ADR 08: Snapshot Drift Resolution Strategy

## Status

Accepted — Phase 7 canonicalizes global target drift and node dependency drift as distinct semantics.

## Decision

The runtime uses two drift levels:

1. **Global Target Drift**: the root target identity no longer matches the run's immutable `TargetSnapshot`. The run cannot complete or publish against that snapshot. Recovery requires a new snapshot.
2. **Node Dependency Drift**: a subset of nodes referenced by an active WorkItem/Evidence changes during execution. Dependent evidence is marked `STALE`, the affected WorkItem terminates with `SNAPSHOT_DRIFT`, and independent WorkItems may continue.

The current semantic pipeline uses node-level reconciliation. The older global-stop-only description is retired and must not be treated as an alternative implementation contract.

## Evidence rules

Evidence affected by node drift is never silently promoted back to `VALID`. It must be revalidated or regenerated under a stable snapshot before reuse.

## Consequences

The architecture preserves unaffected work while maintaining a hard publication/completion boundary for global snapshot identity.

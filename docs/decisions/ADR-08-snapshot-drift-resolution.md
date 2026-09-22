# ADR 08: Snapshot Drift Resolution Strategy

## Context
During the forensic review, it was identified that snapshot drift detection was partially implemented without a fully defined architectural contract. Specifically, the injection of a `current_snapshot_provider` lacked formal architectural authority. We must define when the drift is checked, who provides the snapshot, and how to handle it.

## Decision
We decide to **REMOVE** the `current_snapshot_provider` injection at the function level. Instead, the drift detection relies explicitly on comparing the `TargetSnapshot.snapshot_fingerprint` already persisted for the run against a point-in-time snapshot fingerprint obtained before/during critical execution boundaries.

1. **Who produces the initial snapshot?** The `TargetSnapshot` is generated upfront during context building and its fingerprint is securely stored as part of the run.
2. **When is the current state captured?** The Orchestrator checks for drift explicitly by comparing the `run.target_snapshot_ref` to the current state (provided by a system-level hashing/snapshot mechanism) during the pre-execution phase of a work item.
3. **What happens on drift?** Execution is STOPPED immediately. The run is marked with `DRIFT_DETECTED`, preventing `COMPLETE` state and publication.
4. **How does recovery work?** A run that suffered snapshot drift can be recovered, but it cannot be marked `COMPLETE` without a new snapshot.
5. **How is Evidence affected?** Any `Evidence` collected after drift is detected is marked `SUSPECT`.

## Consequences
- **Positive:** Restores architectural integrity by removing unauthorized `current_snapshot_provider` residue. Clarifies the invalidation graph.
- **Negative:** Checking for drift requires explicit mechanisms which might slightly increase execution time overhead.

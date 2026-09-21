# Architecture Decision Record: Reproducibility & Audit Target Snapshot (ADR-06)

**Status:** accepted

## Context
In an incremental auditing system, relying solely on a Git commit hash to identify the "audit target" is insufficient. A single commit can be audited under drastically different conditions depending on the working tree (dirty files), the active submodules, the generated artifacts (e.g., compiled binaries, schemas), the active methodology (auditor versions), and environment constraints. 

If the system attempts to determine whether a piece of evidence is still valid (`REUSE` vs `INVALIDATE`) without an exact ontological reference of *what* was audited, it will suffer from false positives (reusing stale evidence because the commit didn't change, but the methodology did) and false negatives (discarding valid evidence because a superficial variable changed).

## Decision
We establish the **`TargetSnapshot`** as the fundamental, immutable ontological reference for every audit execution (`AuditRun`) and every unit of work (`AuditWorkItem`). 

1. **Identity Over Commit:** The `TargetSnapshot` is a persisted structural schema that captures the exact identity of the target, including:
   - Primary Repository Identity and Commit Hash.
   - Working Tree State (is it dirty? which files are uncommitted?).
   - Submodule states (if applicable).
   - Generated or build-time artifact hashes (e.g., generated GraphQL schemas, compiled ASTs).
2. **Methodology Snapshot:** The `TargetSnapshot` must also freeze the versions of the tools performing the audit:
   - `policy_version`: the version of the planning rules.
   - `auditor_version`: the specific version of the specialized skill (e.g., `security-audit v1.2`).
   - `schema_version`: the data contract version.
3. **Reproducibility Invariant:** An `AuditRun` is inextricably linked to one `TargetSnapshot`. If any element within the `TargetSnapshot` definition changes, the target is considered logically distinct, triggering the downstream incremental engine (ADR-04) to re-evaluate evidence validity based on dependency matching.

## Consequences
- **Positive:** Provides a rock-solid foundation for the incremental engine (ADR-04). Evidence validity can now be calculated mathematically against a precise snapshot rather than vague "project state".
- **Positive:** Guarantees reproducibility. An auditor can inspect an old `TargetSnapshot` and know exactly which versions of rules and uncommitted files were present.
- **Negative:** Requires an upfront "Context Builder" step to deterministically calculate hashes and assemble the `TargetSnapshot` before any planning or auditing can begin, slightly increasing initial latency.

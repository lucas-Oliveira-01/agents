# Architecture Decision Record: Incremental State & Evidence Validity (ADR-04)

**Status:** accepted

## Context
A naively implemented incremental audit system typically relies on a direct mapping between a changed file (e.g., `git diff`) and the invalidation of a finding. This approach is flawed: a finding's underlying logic may survive textual refactoring, and conversely, an unchanged file may contain a vulnerability that is newly exploitable due to a change in a configuration file or a methodology update.

To drastically reduce token costs while preserving epistemic integrity, the system needs a rigorous semantic model that separates the identity of a problem from its historical lifecycle, and the material evidence from its validity under the current `TargetSnapshot` (ADR-06).

## Decision

We establish a formal ontological separation of identities, lifecycles, and validities, governed by a deterministic incremental matrix.

### 1. Separation of Identities
Do not collapse identity, status, and lifecycle into a single field.
- **Evidence Identity:** "What observation is this?" (e.g., the presence of a specific insecure SQL string).
- **Evidence Validity:** "Does this observation still accurately represent the current `TargetSnapshot`?" (`VALID`, `STALE`, `INVALID`, `UNKNOWN`).
- **Finding Identity:** "What is the logical problem?" (e.g., SQL Injection in User Login). This identity must survive line-number shifts or file renames if the logical defect remains.
- **Finding Status:** "What is the current epistemic certainty?" (e.g., `CANDIDATE`, `PROBABLE`, `CONFIRMED`, `REJECTED`, `NOT_DETERMINABLE`).
- **Finding Lifecycle:** "How has this problem evolved across `AuditRuns`?" (e.g., `NEW`, `PERSISTING`, `MODIFIED`, `FIXED`, `REGRESSED`, `INVALIDATED`).

*Invariant: `INVALIDATED` ≠ `FIXED`. If a file is deleted, the old evidence is invalidated, and the finding's lifecycle may become `INVALIDATED` or status `NOT_DETERMINABLE`, but the system cannot claim the bug was "fixed" without proof of remediation.*

### 2. Semantic Dependencies
Evidence does not exist in a vacuum. The validity of `Evidence E` depends on a set of semantic relationships:
- `source_inputs` (the specific files/lines observed)
- `configuration_inputs` (associated configs, e.g., `application.yml`)
- `build/environment` (e.g., dependency manifests)
- `methodology` (the toolchain, auditor version, policy version used)

When a dependency changes in a new `TargetSnapshot`, the validity of the evidence must be re-evaluated. *(Note: The exact algorithmic implementation of this dependency graph—e.g., hashing vs AST mapping—is deferred, but the semantic requirement is frozen).*

### 3. Fact vs Methodology (Compatibility)
A change in the `TargetSnapshot` does **not** automatically invalidate previous evidence.
- If `Target` changes but the specific dependencies of `Evidence E` are untouched, `E` remains `VALID`.
- If `Target` is identical, `Evidence` is identical, but `auditor_version` changes from v1 to v2, the `Evidence` remains `VALID`, but the *Assessment* (the conclusion drawn from it) may become `STALE`.

### 4. The Incremental Action Matrix
Based on the validity of evidence and methodology, the Orchestrator assigns one of four incremental actions to an `AuditWorkItem` (evaluated with the precedence: `INVALIDATE` > `REAUDIT` > `REVALIDATE` > `REUSE`):

| Action | Condition | Meaning |
| :--- | :--- | :--- |
| **`INVALIDATE`** | Evidence is factually contradicted by the new snapshot, or dependencies are missing/deleted. | The previous result cannot be used. The finding/evidence is dropped or marked as historical. |
| **`REAUDIT`** | Evidence is fundamentally broken by a dependency change, or the auditor methodology has a breaking update. | A substantive re-analysis must be performed from scratch by the Strong Auditor. |
| **`REVALIDATE`** | Evidence is intact, but a loosely-coupled dependency or context changed, OR the assessment might be stale. | A cheap verification (e.g., quick deterministic check or cheap LLM prompt) is needed to confirm the conclusion holds. |
| **`REUSE`** | Evidence, dependencies, and methodology are fully intact and compatible under the new TargetSnapshot. | The previous conclusion is adopted directly without re-evaluating the audit logic. Epistemic integrity is preserved safely. |

If validity is **indeterminable**, the system must fail-safe to `REAUDIT`.

### 5. Binding to WorkItems
The incremental decision (`REUSE`, `REVALIDATE`, `REAUDIT`, `INVALIDATE`) is calculated during the Planning phase and bound explicitly to an `AuditWorkItem` before execution.

## Consequences
- **Positive:** Massive reduction in LLM token costs through safe `REUSE`.
- **Positive:** Eliminates false "Fixes" caused by files moving or being deleted.
- **Negative:** The Orchestrator's planning phase becomes highly complex, as it must compute dependency intersections across `TargetSnapshots`.

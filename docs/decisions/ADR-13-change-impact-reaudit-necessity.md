# ADR 13: Change Impact and Reaudit Necessity

**Status:** Accepted — implemented by Phase 11

## Context

Phase 9 established an explicit deterministic classification boundary and Phase 10 made the existing incremental decision matrix executable across regenerated WorkItems.

The remaining architectural gap is the causal link between a project change and the incremental decision that follows. The current runtime can determine Evidence dependency validity and can bind `REUSE`, `REVALIDATE`, or `REAUDIT`, but the architecture does not yet define a first-class, deterministic explanation of:

```text
change
  ↓
affected surface
  ↓
affected dependency
  ↓
affected Evidence / Finding / WorkItem
  ↓
incremental action
```

The repository's classifier architecture already identifies Change Impact and Reaudit Necessity as deterministic responsibilities. This ADR defines their semantics without introducing a second router, an LLM classifier, or a new Layer 3 contract.

## Decision

### 1. Change Impact is a deterministic planning analysis

Change Impact is computed from immutable TargetSnapshots and the deterministic difference between their input fingerprints and methodology state.

The analysis operates on canonical input identity, not narrative text and not generated WorkItem UUIDs.

A change event is classified as one or more of:

- `ADDED`
- `MODIFIED`
- `DELETED`
- `RENAMED`
- `DEPENDENCY_CHANGE`
- `CONFIG_CHANGE`
- `METHODOLOGY_CHANGE`

The implementation must preserve stable path normalization and must treat renames as an identity-preserving event when the dependency model can prove continuity.

### 2. Impact propagation follows existing dependency semantics

Impact is propagated through existing deterministic relationships:

```text
changed input
    ↓
Evidence Dependency Graph node
    ↓
historical Evidence
    ↓
FindingFingerprint
    ↓
logical WorkItem (auditor + target_surface)
```

The classifier does not invent hidden dependencies. Where dependency propagation cannot be proven, the result is indeterminate and the existing fail-safe rules apply.

A source dependency change is stronger than a semantic dependency change.

### 3. Reaudit Necessity is a decision over evidence and impact

The Reaudit Necessity decision does not replace ADR-04/ADR-12. It supplies a deterministic impact explanation that feeds the existing incremental matrix.

The precedence remains:

```text
INVALIDATE > REAUDIT > REVALIDATE > REUSE
```

Operationally:

- unchanged relevant inputs + intact dependencies + compatible methodology → `REUSE`;
- changed loosely-coupled context/dependency while factual Evidence remains intact → `REVALIDATE`;
- changed source/factual dependency, broken compatibility, or insufficient dependency knowledge → `REAUDIT`;
- evidence-level invalidation remains `INVALIDATE`, bound to executable `REAUDIT` at the WorkItem boundary.

No new `RECHECK` WorkItem action is introduced. The existing canonical actions remain `REUSE`, `REVALIDATE`, and `REAUDIT`.

### 4. Classification changes are impact events

A deterministic classification result is part of the planning context. If a future implementation proves that a classification decision relevant to an existing WorkItem has changed, dependent planning must be reconsidered.

The system must not silently retain an old WorkItem solely because source-file hashes are unchanged when a materially relevant upstream classification input has changed.

A classification change that cannot be shown to affect a WorkItem must not broaden the audit scope merely by association.

### 5. Findings are not invalidated by filename change alone

Finding identity remains based on `FindingFingerprint`, not physical line numbers or path strings.

Therefore:

- a rename does not automatically mean `FIXED`;
- a path relocation does not automatically create `NEW`;
- deletion of a dependency invalidates the factual basis of historical Evidence, but does not prove remediation;
- `INVALIDATED` remains distinct from `FIXED`.

The existing durable FindingLifecycle remains the authority for historical lifecycle.

### 6. Provenance and explainability use existing contracts

Phase 11 does not add a new canonical persisted entity merely to hold impact output.

The decision explanation must remain recoverable from existing auditable state, principally:

- `AuditWorkItem.decision_basis`;
- `ClassificationResult` provenance where classification participated in the decision;
- Evidence source/dependency references;
- TargetSnapshot references;
- existing execution receipts where applicable.

A future implementation may introduce an internal immutable value object for computation, but it must not expand the canonical JSON schemas unless a later ADR explicitly establishes a new persisted ontology.

### 7. Snapshot Drift remains a separate boundary

Change Impact is evaluated between completed/immutable snapshots for incremental planning.

Runtime Snapshot Drift during an active execution remains governed by ADR-08. Change Impact must never be used to silently continue an execution against a mutated live target.

Therefore:

```text
incremental change between snapshots
    → analyze impact

live mutation during execution
    → Snapshot Drift handling
```

These are different events and must not be conflated.

### 8. OmniRoute is outside this decision

Change Impact and Reaudit Necessity are Core/Orchestrator planning decisions.

OmniRoute does not:

- decide which surfaces are affected;
- decide whether a finding requires REUSE/REVALIDATE/REAUDIT;
- override dependency validity;
- determine audit applicability.

If semantic escalation is ultimately required, the Core produces the task and policy boundary; OmniRoute only resolves the concrete model/provider execution path.

### 9. Deterministic-first constraint

Phase 11 is deterministic.

Inputs may include:

- TargetSnapshot input fingerprints;
- Git diff metadata where available;
- file classification;
- ProjectProfile / ClassificationResult;
- Evidence source references;
- Evidence semantic dependencies;
- methodology versions;
- existing logical WorkItem identity.

No LLM is required to establish basic change impact where these facts are sufficient.

Semantic reasoning may still be required downstream for audit interpretation. It cannot be used as a substitute for deterministic change accounting.

## Decision table

| Situation | Impact interpretation | Existing action |
|---|---|---|
| No relevant input changed | No proven impact | `REUSE` |
| Source input changed | Factual basis changed | `REAUDIT` |
| Semantic/config dependency changed | Context may affect conclusion | `REVALIDATE` |
| Required dependency deleted | Old factual basis unavailable | `INVALIDATE` → executable `REAUDIT` |
| Methodology contract/policy changed incompatibly | Prior assessment incompatible | `REAUDIT` |
| Auditor implementation version changed | Observation may remain, assessment may stale | `REVALIDATE` |
| Historical Evidence missing/ambiguous | Identity/evidence cannot be proven | `REAUDIT` |
| Classification materially changed for dependent work | Plan context changed | Reconsider affected WorkItems using the same matrix |
| Live target mutates during execution | Active snapshot no longer authoritative | ADR-08 Snapshot Drift path |

## Schema impact

None authorized by this ADR.

No new canonical field is introduced into:

- TargetSnapshot;
- AuditPlan;
- AuditWorkItem;
- Evidence;
- AuditRun;
- FindingRecord.

Existing `decision_basis`, `ClassificationResult`, dependency references, and snapshot references are sufficient for the Phase 11 implementation boundary.

## Acceptance criteria for implementation

A later implementation phase must prove, without LLM calls:

1. the same pair of snapshots produces the same change-impact result;
2. path normalization does not create false impact;
3. source changes and semantic dependency changes produce their defined actions;
4. deleted dependencies fail closed;
5. rename continuity is preserved only when deterministically provable;
6. classification changes reconsider only demonstrably dependent work;
7. finding lifecycle never converts invalidation into FIXED;
8. WorkItem identity remains logical across regenerated UUIDs;
9. decision explanations remain reconstructable from persisted state;
10. Snapshot Drift handling remains separate from inter-snapshot incremental analysis.

## Non-goals

- no Tier 2 / SLM classifier;
- no LLM-based change-impact classifier;
- no new model/provider routing;
- no new WorkItem action;
- no automatic FIXED inference;
- no modification of audit-normalize;
- no canonical schema expansion;
- no replacement of the existing Evidence Dependency Graph;
- no replacement of ADR-12 runtime reuse.

## Consequences

Positive:

- The reason for an incremental action becomes explicit and deterministic.
- Phase 9 classification and Phase 10 reuse become causally connected.
- Incremental behavior can be measured by affected surfaces and avoided work rather than only by final action counts.
- The architecture gains a precise boundary for future impact analysis without introducing another routing system.

Negative:

- Dependency metadata must become sufficiently precise for impact propagation to be useful.
- Ambiguous relationships intentionally increase REAUDIT rather than allowing optimistic cache reuse.

## Implementation record

Implemented in `project-audit` Phase 11. The change-impact computation is deterministic and feeds the existing incremental matrix without adding canonical schema fields. See `docs/architecture/phase11-change-impact-reaudit.md` and `test_phase11_change_impact.py` for the executable acceptance boundary.

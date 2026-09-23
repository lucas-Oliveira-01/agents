# Project-Audit Single-Agent Runtime — Phase 1

**Status:** PHASE 2 IMPLEMENTED — SEMANTIC/FINDING PHASE PENDING

## Scope

This phase materializes the first executable path for the `project-audit` product without changing the canonical ontology or introducing a multi-agent audit runtime.

The product remains a single-agent auditor. Codex, Antigravity, and OpenCode are development environments, not runtime actors in this audit flow.

## Runtime boundary

```text
Target Repository
      |
      v
Deterministic Discovery
      |
      v
File / Stack / Applicability Classification
      |
      v
AuditPlan + AuditWorkItems
      |
      +---- deterministic analysis
      |
      +---- semantic analysis (future milestone)
      |
      v
Evidence / AuditRun
      |
      v
Markdown Output Set
      |
      v
audit-normalize
```

## Decisions preserved

- `TargetSnapshot`, `AuditPlan`, `AuditWorkItem`, `Attempt`, `ExecutionReceipt`, `Evidence`, and `AuditRun` remain the existing Layer 2 contracts.
- `audit-normalize` remains downstream and unchanged by this phase.
- Deterministic-first is a routing rule: do not invoke an LLM when repository metadata, parsers, static rules, hashes, or other deterministic mechanisms can resolve the task.
- Applicability uncertainty does not silently exclude scope.
- The single-agent MVP does not introduce `ExecutionProvider`, agent federation, or multi-agent audit coordination.

## Phase 1 implementation

Implemented in this branch:

- deterministic filesystem inventory;
- read-only Git metadata discovery;
- deterministic file classification;
- deterministic stack signal classification;
- deterministic audit applicability classification;
- deterministic Engineering PASS 1 inspection;
- deterministic Security PASS 2 inspection;
- explicit task classification with an LLM-necessity signal;
- creation of a real `TargetSnapshot`;
- generation of a real `AuditPlan` and atomic `AuditWorkItem`s.

Not implemented yet:

- semantic audit execution;
- full engineering/security Markdown generation;
- Evidence Dependency Graph;
- advanced incremental reuse/cache;
- independent verifier;
- multi-agent audit runtime.

## Validation boundary

The implementation was syntax-checked in isolation. Full repository tests were not executed in the development container because outbound DNS/network access was unavailable. No successful test run is claimed by this document.


## Current implementation boundary

The executable single-agent path now reaches:

1. deterministic discovery;
2. deterministic classification;
3. applicability and planning;
4. Engineering PASS 1;
5. Security PASS 2;
6. four Markdown audit artifacts;
7. optional downstream `audit-normalize` invocation over exactly those four artifacts.

The remaining product gap is semantic audit interpretation: confirming observations, formalizing findings/controls, and producing the final audit semantics required by the canonical Markdown contract.

No multi-agent runtime was introduced.

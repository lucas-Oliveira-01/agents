# project-audit — Core Engine V1

Core orchestration engine for the `project-audit` skill system.

The current product runtime is **single-agent**. Development may use Codex, Antigravity, and OpenCode, but those are not runtime auditors.

## Scope

This package contains:

- Domain types (`TargetSnapshot`, `AuditPlan`, `AuditWorkItem`, `Evidence`, `AuditRun`, `Attempt`, `ExecutionReceipt`)
- Deterministic discovery and classification
- Single-agent Engineering PASS 1 executor
- Semantic validators (pure, deterministic, no LLM)
- State store (local durable persistence with atomic writes)
- Core orchestration primitives
- FakeAuditor for engine validation

## Current execution boundary

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
AuditPlan + WorkItems
      |
      v
PASS 1 — Engineering
      |
      +--> deterministic observations + Evidence
      |
      v
PASS 2 — Security
```

`audit-normalize` remains downstream and is not invoked by the core engine during this phase.

## Phase status

Implemented:

- repository filesystem discovery;
- read-only Git metadata discovery;
- deterministic file and stack classification;
- applicability decisions with explicit uncertainty;
- `TargetSnapshot` creation;
- `AuditPlan`/`AuditWorkItem` preparation;
- real deterministic Engineering PASS 1 execution;
- execution receipts and Evidence persistence for completed engineering work.

Not implemented yet:

- semantic Engineering escalation;
- independent Security PASS 2 execution;
- final four-file Markdown audit output writer;
- correlation between PASS 1 and PASS 2;
- optional `audit-normalize` downstream handoff from the CLI; the normalizer remains a separate skill;
- advanced incremental reuse/cache;
- Evidence Dependency Graph;
- multi-agent audit runtime.

## Safety boundary

Engineering PASS 1 is read-only and uses deterministic inspection. Security work items are intentionally left for PASS 2.

The engine must not claim full audit publication merely because PASS 1 completed.

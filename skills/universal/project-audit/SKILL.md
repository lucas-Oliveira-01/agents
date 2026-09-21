# project-audit — Core Engine V1

Core orchestration engine for the project-audit skill system.

Implements the Canonical Data Model (Layer 2) as defined in `docs/references/canonical-data-model.md`.

## Scope

This package contains:
- Domain types (TargetSnapshot, AuditPlan, AuditWorkItem, Evidence, AuditRun, Attempt, ExecutionReceipt)
- Semantic Validators (pure, deterministic, no LLM)
- State Store (local durable persistence with atomic writes)
- Core orchestration primitives
- FakeAuditor for engine validation

## Architecture

See `docs/references/` for the frozen architectural baseline.

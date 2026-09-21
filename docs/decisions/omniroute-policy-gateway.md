# Architecture Decision Record: OmniRoute as Task Policy Gateway

**Status:** accepted

## Context
Initial prototypes treated the OmniRoute MCP integration simply as a "model selector" (e.g., routing `coding` tasks to model A and `security` tasks to model B). However, duplicating logic like fallback, retry, quotas, and health checks in the Orchestrator agent was redundant and complex.
Furthermore, delegating raw, unfiltered project context to a gateway risks violating Trust Boundaries and blowing up token budgets.

## Decision
We establish a strict separation of concerns between the Orchestrator Agent and OmniRoute:

1. **OmniRoute's Responsibility (Infrastructure):** OmniRoute is responsible for execution mechanics. It handles model/provider resolution, fallbacks, retries, health checks, rate limiting, and cache affinity.
2. **Orchestrator's Responsibility (Domain Logic):** The Orchestrator remains fully responsible for context slicing (progressive disclosure), trust boundaries (never executing untrusted data), budget allocation, provenance tracking, and data validation.
3. **The Delegation Contract:** The Orchestrator does NOT ask OmniRoute for a specific model. It asks for a **Task Policy** (e.g., `cheap`, `fast`, `quality`, `context-optimized`). OmniRoute resolves that policy to a concrete model.
4. **No Recursive Delegation:** The architecture is strictly `Agent -> OmniRoute -> Leaf Model`. Leaf models cannot recurse back into OmniRoute.

## Consequences
- **Positive:** Decouples the audit logic from the volatile landscape of LLM providers.
- **Positive:** Protects the system from unbounded recursive loops and context explosion.
- **Negative:** Requires rigorous schema validation on the `delegar_tarefa` MCP tool to ensure policies are correctly typed and budgets are respected.

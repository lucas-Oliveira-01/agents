# Docs as the Canonical Source of Truth

The `docs/` directory is the immutable source of truth for the project's architecture, rules, decisions, and procedures.

## Core Principles

1. **Agent Behavior**: Before proposing structural changes, defining new skills, or altering workflows, agents MUST consult the relevant documentation in `docs/` (such as `rules/`, `decisions/`, and `procedures/`) and `ai-memory`.
2. **Synchronization**: Whenever a new project-wide rule, architectural decision (ADR), or canonical procedure is created, it MUST be persisted as a Markdown file in the appropriate subdirectory of `docs/` AND synced to the `ai-memory` module (e.g., using `memory_write_page` with `pinned: true` for rules and decisions).
3. **Immutability of Decisions**: Files in `docs/decisions/` are historical records (ADRs). Do not edit the substance of an accepted decision. If a decision changes, create a new ADR and mark the old one as `superseded`.
4. **Structure Compliance**: The `docs/` folder strictly follows this layout:
   - `assets/` (reusable static artifacts)
   - `decisions/` (architectural decisions and proposals)
   - `gotchas/` (traps and lessons learned)
   - `procedures/` (checklists and step-by-steps)
   - `references/` (runtime knowledge)
   - `references/evidence/` (execution logs and persistent examples)
   - `rules/` (unbreakable rules)
   - `scripts/` (deterministic helpers)
   - `sources/` (provenance and gaps)
   
Agents must never place random files at the root of `docs/`. Every file must be categorized correctly.

# Architecture Decision Record: Isolated Audit Repository (.audit)

**Status:** accepted

## Context
The user is writing software for academic purposes. Generating automated AI code or AI artifacts inside the main project repository violates academic integrity rules and pollutes the primary Git history.
At the same time, the audit system requires persistent state (history, cache, provenance, coverage) to support Incremental Auditing (e.g., deciding whether a finding should be `REUSE`, `REVALIDATE`, or `REAUDIT` based on a git diff).

## Decision
1. **Isolated State Directory:** All audit state, history, runs, and artifacts must be stored in an `.audit/` directory at the root of the target project.
2. **Git Ignore Boundary:** The `.audit/` directory MUST be added to the primary project's `.gitignore`.
3. **Independent Audit VCS:** The `.audit/` directory will initialize its own isolated Git repository (`.audit/.git/`). This creates a strict boundary: `project.git != audit.git`.
4. **Incremental Auditing:** By persisting previous Audit Output Sets in this isolated repository, the Orchestrator can perform delta analyses (Change Impact Classification) against the target project's commit history, drastically reducing token waste by reusing previous evidence where files and contexts remain unchanged.

## Consequences
- **Positive:** Total compliance with academic integrity constraints; AI artifacts never bleed into the main codebase.
- **Positive:** Enables true stateful, continuous, and incremental security auditing.
- **Negative:** Agents must be specifically programmed to manage two distinct Git working trees simultaneously.

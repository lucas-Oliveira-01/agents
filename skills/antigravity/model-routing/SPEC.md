# Model Routing Maintenance Specification

## 1. Intent and Scope
This skill provides the cognitive framework and policies for selecting the appropriate model tier (`flash_lite`, `flash`, `pro`, `inherit`) and orchestration fallback mechanisms within the Antigravity ecosystem. It is intended to be globally applicable to any software project.

## 2. Maintenance Boundaries
*   **SKILL.md:** Must remain abstract and agnostic of specific model slugs (e.g., avoid hardcoding "Claude Opus 4.6"). It only governs the strategy (tiering, escalation, role-based assignment).
*   **references/:** This is the volatile data layer. As new models are released or benchmarked, `model-inventory.md` and `routing-matrix.md` should be updated here, NOT in `SKILL.md`.

## 3. Anti-Patterns
*   Do not turn `SKILL.md` into a benchmark ranking table.
*   Do not inject project-specific routing rules (e.g., "Use model X for React files") into this global skill.

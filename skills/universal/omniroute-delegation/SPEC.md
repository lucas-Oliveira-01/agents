# OmniRoute Delegation Specification

## 1. Intent and Scope
This skill defines the universal contract for delegating tasks via the OmniRoute MCP gateway. It ensures that agents properly structure their delegation payloads, verify health status, and handle OmniRoute responses.

## 2. Maintenance Boundaries
*   **SKILL.md:** Defines the cognitive protocol for the orchestrator agent (when to delegate, how to structure the task).
*   **src/ & tests/:** Contains the OmniRoute MCP client and task builder validation logic.
*   **references/:** Can contain templates for optimal task structures.

## 3. Anti-Patterns
*   Do not hardcode specific model slugs into the delegation payload; OmniRoute should handle routing, or the agent should refer to the `model-routing` skill.
*   Do not bypass the MCP contract validation. All tasks must adhere to the schema required by the OmniRoute server.

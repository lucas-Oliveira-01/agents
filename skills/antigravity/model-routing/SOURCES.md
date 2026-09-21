# Sources and Provenance

## Origin
This skill was proposed and structured based on an architectural analysis of model benchmarking and efficiency theory, originally synthesized from a dialogue involving GPT-5.6 Luna, Claude Sonnet 5, and the project's Principal Agent.

## Key Decisions
*   **Antigravity Namespace:** Placed in `skills/antigravity/` because it is specifically designed to interoperate with Antigravity's native `invoke_subagent` tool and internal tiering mechanics. It cannot be used directly by generic agents.
*   **Decoupled Intelligence:** It was decided to separate the conceptual routing policy (`SKILL.md`) from volatile model rankings (`references/`) to ensure the skill does not decay rapidly as new frontier models are released.
*   **Role-Based Focus:** We adopted the convention that subagents must represent *Roles* (e.g., `debugger`, `implementer`) rather than tying agents directly to specific model names.
*   **Escalation Logic:** Implemented an "escalate-on-failure" paradigm rather than defaulting to maximum intelligence.

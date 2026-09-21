# Sources and Provenance

## Origin
This skill was proposed and structured based on an architectural analysis of model benchmarking and efficiency theory, originally synthesized from a dialogue involving GPT-5.6 Luna, Claude Sonnet 5, and the project's Principal Agent.

## Key Decisions
*   **Decoupled Intelligence:** It was decided to separate the conceptual routing policy (`SKILL.md`) from volatile model rankings (`references/`) to ensure the skill does not decay rapidly as new frontier models are released.
*   **Role-Based Focus:** We adopted the convention that subagents must represent *Roles* (e.g., `debugger`, `implementer`) rather than tying agents directly to specific model names.
*   **Escalation Logic:** Implemented an "escalate-on-failure" paradigm rather than defaulting to maximum intelligence, aligning with Antigravity's resource optimization axioms.

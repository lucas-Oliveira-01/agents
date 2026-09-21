# Architecture Decision Record: Fail-Closed Agent Orchestration

**Status:** accepted

## Context
Analysis of the SmartServ audit retrospective revealed a systemic failure mode labeled as the "Execution Bias". The agent consistently bypassed mandatory metacognitive planning steps (checking `ai-memory`, reading `SKILL.md`, evaluating handoffs) in favor of immediate execution (`view_file`, `run_command`).
Previously, this was mitigated by adding longer instructions to the System Prompt. However, architectural analysis (Luna 5.6 / Opus 5) demonstrated that instructions in a prompt cannot reliably gate tool usage. When task output goals compete with procedural rules in a single LLM context window, the model optimizes for output and ignores the rules. This caused catastrophic continuity and coverage failures.

## Decision
We are adopting a **Fail-Closed Agent Architecture** featuring strict Two-Phase Tool Gating:
1. **Pre-flight Phase (PLAN mode):** At session start or upon context truncation, execution tools (`view_file`, `write_to_file`, `run_command`, etc.) are *mechanically blocked* by the Tool Gateway. The agent only has access to planning tools (`memory_briefing`, `skill_read`, `plan_submit`).
2. **Tool-Call Plan:** To unlock execution, the agent must submit a structured plan detailing which skills it read, its memory state, and its delegation strategy.
3. **Execution Phase:** Only after `plan_submit` passes validation does the Tool Gateway expose execution tools.
4. **Completion Validation:** The emission of `GOAL_COMPLETE` is no longer a self-asserted agent action. It is intercepted by an `exit_validator()` that verifies required post-conditions (e.g., findings persisted, coverage attested, handoff generated) before accepting completion.

## Consequences
- **Positive:** Systemic eradication of Execution Bias and "Meta-Forgetting". Agents can no longer silently skip memory rehydration or handoffs because the runtime physically prevents them from taking any other action.
- **Positive:** Prevents "Completion Fraud" where an agent declares a goal finished despite having skipped critical coverage areas.
- **Negative/Trade-off:** Increases integration complexity. The Antigravity orchestrator must implement stateful tool toggling (whitelisting) and formal completion validators, rather than treating the LLM as a purely trusted actor.

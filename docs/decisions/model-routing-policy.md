# Model Routing Policy Implementation

**Status:** accepted

## Context
As the agent swarm scales (Level 1 Principal, Level 2 Subagents, Level 3 OmniRoute), defaulting to highest-tier models (`pro` or `inherit`) for all subagent invocations creates severe latency and cost bottlenecks. The system needed a formalized mechanism to decouple task complexity from model selection, ensuring that lightweight models (`flash`) handle mechanical tasks while heavy models (`pro`) handle deep reasoning.

## Decision
1. We adopted a **Role-Based Model Escalation Strategy**. The model is no longer fixed statically but selected dynamically based on task requirements (Reasoning Depth, Context Size, Tool Complexity, Cost of Failure).
2. We implemented this strategy through a new global skill: `model-routing`.
3. The logic governing escalation (try `flash` first, validate, escalate to `pro` if failed) resides in the `SKILL.md` of `model-routing`.
4. Volatile benchmarks and mappings of specific tasks to model tiers reside in the `references/` directory of the skill (`model-inventory.md` and `routing-matrix.md`).

## Consequences
- **Easier maintenance:** As new frontier models are released, only the `references/model-inventory.md` file needs to be updated. The core orchestration logic remains untouched.
- **Resource efficiency:** The orchestrator agent is now cognitively bound to attempt cheaper/faster delegation before defaulting to expensive deep reasoning.
- **Consistency:** By deploying this skill globally via a symlink (as dictated by the Skill Installation rule), all projects initialized by the user will benefit from this financial and latency intelligence.

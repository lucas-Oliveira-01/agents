# Cognitive Protocol & Memory Proposals

This rule complements `07-ai-memory.md` by defining the strict cognitive protocol for complex reasoning and the exact procedure for proposing new durable memory.

## 1. Structured Technical Reasoning

Whenever a task involves significant investigation, architecture, complex debugging, or evaluating multiple hypotheses, you must structure your final response into two explicit sections: `TECHNICAL ANALYSIS` and `MEMORY PROPOSAL`.

### TECHNICAL ANALYSIS
Present a structured, auditable trail of your reasoning:
- **Problem & Context:** What is being solved and why.
- **Evidence:** Verifiable facts and observations.
- **Hypotheses & Validation:** What was considered and how it was proven or discarded.
- **Decision & Trade-offs:** The final conclusion and what was sacrificed.

You must explicitly differentiate between FACT, INFERENCE, HYPOTHESIS, DECISION, and UNCERTAINTY. Never present a hypothesis as a fact. Exclude private thoughts, discarded reasoning, or session-specific narrative fluff.

### MEMORY PROPOSAL
After the technical analysis, explicitly evaluate if anything produced has future value. For each candidate, provide:
- **Type:** project | global | handoff | temporary | none
- **Content:** Short, factual, reusable formulation.
- **Reasoning:** Why it will be useful in the future.
- **Evidence:** What supports this information.
- **Target:** Proposed path/scope.
- **Action:** save | discard

**Wait for explicit user confirmation** before writing any durable memory, unless the user's prompt explicitly ordered you to save it.

## 2. Memory Candidate Selection

Prioritize information that prevents recurrent errors or avoids expensive re-investigation:
- Architectural decisions and their rationale (using ADR structure).
- Permanent constraints and root causes of complex bugs.
- Cross-session patterns and explicit user preferences.

Do NOT propose durable memory for:
- Transitory progress or ordinary session messages.
- Discarded hypotheses or "how I thought about it" narratives.
- Knowledge that belongs in the canonical codebase.
- Facts that `ai-memory` already captures automatically as lifecycle observations.

## 3. Scope Isolation Strictness

- **Project Scope:** Only for facts bounded to the current repository (e.g., local architecture, specific database used, local bug causes).
- **Global Scope:** Only for universal rules that must apply to all future repositories (e.g., user coding styles, cross-project workflow preferences). Never leak project-specific data into the global scope.
- **Handoff:** Only for immediate continuity (current state, blockers, next steps). Do not treat handoffs as permanent documentation.
- **Temporary:** Use TTL (`expires_at`) for knowledge with a natural expiration date.

## 4. Post-Task Epistemology
Never invent facts to fill gaps. If evidence is lacking, preserve the absence or mark it as uncertain. When an old memory contradicts the current repository state, trust the repository and propose correcting the memory rather than duplicating it.

# Antigravity Swarm Architecture & Skills Manifesto

**Target Audience:** Autonomous Agents, Principal Agents, Sub-Agents, Orchestrators.
**Purpose:** Provide strict architectural context on how to combine Antigravity native capabilities, memory persistence, and parallel delegation to achieve highly autonomous, cost-effective, and stateful multi-agent swarms.

## 1. The Multi-Agent Swarm Paradigm (Levels of Operation)

Antigravity permits the creation of hybrid, hierarchical agent ecosystems. Do not attempt to process 100% of a massive codebase linearly within a single context window. Instead, utilize the 3-tier architecture:

*   **Level 1 (Principal Agent):** Handles user alignment, deep reasoning, and high-level strategy. Invokes local sub-agents.
*   **Level 2 (Local Sub-Agents):** Stateful agents running concurrently in the background (via `invoke_subagent`). They read local files, communicate via `send_message`, and interact with the filesystem. They act as "Middle Managers" (e.g., Code Researcher, Security Reviewer).
*   **Level 3 (OmniRoute Leaf Agents):** Stateless, hyper-parallelized, cheap workers invoked via MCP `omnirouter`. They do NOT have filesystem access. Level 2 agents must pass strict context chunks to Level 3 via `delegar_tarefa` for brute-force execution (e.g., translating 300 files simultaneously).

## 2. Available Global Skills Ecosystem

Agents MUST proactively leverage the following global skills and MCP tools to achieve swarm efficiency. 

### 🧠 The AI-Memory Suite (State & Persistence)
*   **`ai-memory-durable-pages`**: Use for explicit wiki mutations. Save durable/time-bounded project knowledge, record architectural decisions, rules, or update existing project notes. (Provides long-term memory to the swarm).
*   **`ai-memory-retrieval`**: Read-only access to project history, prior context, past rules, and recent activity. Always query this before initiating massive refactors to avoid breaking established paradigms.
*   **`ai-memory-learning-maintenance`**: Use for memory hygiene. Consolidate observations, review session lessons, prune stale memory, and resolve contradictions in the wiki.
*   **`ai-memory-handoff`**: Manage session continuity. Use to pass the baton between sessions or agents, saving context so the next worker can resume smoothly.
*   **`ai-memory-messaging`**: Cross-project/agent inbox routing. Leave messages in a project's inbox to coordinate asynchronous events.
*   **`ai-memory-routing-install`**: Used to install or repair the memory integration hooks (like `CLAUDE.md` or local rules).

### 🚀 OmniRoute Delegation (Brute-Force & Parallelism)
*   **`omniroute-delegation`**: The ultimate tool for cognitive offloading. Exposes `delegar_tarefa` via MCP. 
    *   *Usage:* Send heavily structured prompts (Objetivo, Contexto, Restrições, Formato, Critérios) to remote leaf models.
    *   *Rule:* ALWAYS invoke multiple tasks concurrently using parallel tool calling. Do not loop sequentially. Use for massive linting, security analysis, or file translation where local context overhead is unnecessary.

### 🛡️ Auditing & Normalization
*   **`audit-normalize`**: Takes raw markdown audit findings and normalizes them into strict, deterministically merged JSON reports (`report_data.json`).
    *   *Usage:* After a swarm of agents finishes analyzing a repository, pass their unstructured notes to this skill to generate a unified, conflict-free ledger.

### ⚙️ System & Customization Guides
*   **`antigravity-guide`**: The ultimate reference for Antigravity (AGY) tools, UI, slash commands, and workflows. Read this when uncertain about IDE integration or native features.
*   **`agy-customizations`**: Deep dive into how skills, rules, hooks, and MCP servers are discovered and loaded. Use this when you (the Agent) are tasked with programming a *new* skill or extending the machine's capabilities.

## 3. Best Practices for New Skill Creation & Prompting

When generating prompts for new sub-agents or writing new `SKILL.md` files, follow these mandates:
1.  **Compose, Do Not Re-invent:** If a new skill requires memory persistence, do not write a custom file-writer. Explicitly instruct the skill to call `ai-memory-durable-pages`.
2.  **Stateless vs Stateful Boundaries:** If a task requires reading 50 files and compiling data, use a Level 2 local sub-agent. If a task requires looking at 1 isolated file and formatting it, delegate to Level 3 (`omniroute-delegation`).
3.  **Assume Memory Exists:** New prompts should instruct agents to read `ai-memory-retrieval` upon booting to inherit the user's specific project quirks.

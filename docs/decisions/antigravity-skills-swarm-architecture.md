# Antigravity Swarm Architecture & Skills Manifesto

**Document Type:** Architectural Reference & Operational Specification  
**Target Audience:** Autonomous Agents, Principal Orchestrators, Local Subagents, Skill Developers  
**Status:** Active / Canonical  

---

## 1. Executive Summary & Core Principles

This specification defines the multi-tier agent architecture, memory persistence model, and delegation standards within the Antigravity ecosystem. The primary objective is to maximize execution quality, traceability, and autonomy while strictly minimizing token consumption and context degradation.

### Core Architectural Axioms
1. **Hierarchical Task Decomposition:** Monolithic context processing across large codebases is prohibited. Workloads must be decomposed across specialized, hierarchical agent tiers.
2. **Stateless vs. Stateful Segregation:** Stateful operations requiring local filesystem access and iterative reasoning are decoupled from stateless, hyper-parallel cognitive offloading.
3. **Deterministic Superiority:** Automated transformations, schema validations, and state consolidations must rely on deterministic scripts and schemas rather than unstructured LLM evaluation.
4. **Continuous Persistence:** Durable knowledge, architectural decisions, and operational handoffs must be systematically committed to the persistent memory layer (`ai-memory`).
5. **Progressive Disclosure:** Runtime agents must only ingest context relevant to the active decision branch, loading extended references and domain guides strictly on demand.

---

## 2. Multi-Tier Agent Swarm Topology

The swarm operates across three discrete execution tiers with rigid privilege boundaries.

```mermaid
flowchart TD
    User([User / System Trigger]) --> L1[Level 1: Principal Agent]
    
    subgraph L1_Scope [Strategic Layer]
        L1
    end

    subgraph L2_Scope [Tactical Layer - Stateful Subagents]
        L2A["Level 2 Agent: Code Researcher"]
        L2B["Level 2 Agent: Domain Auditor"]
        L2C["Level 2 Agent: Security Reviewer"]
    end

    subgraph L3_Scope [Execution Layer - Stateless Workers]
        L3A["Level 3 Leaf: Syntax Transformer"]
        L3B["Level 3 Leaf: Chunk Classifier"]
        L3C["Level 3 Leaf: Pattern Extractor"]
    end

    subgraph Persistence [Durable Storage & Memory]
        AIMem[(ai-memory Knowledge Graph)]
        GitRepo[(Git Repository & Docs)]
    end

    L1 -->|invoke_subagent| L2A
    L1 -->|invoke_subagent| L2B
    L1 -->|invoke_subagent| L2C
    
    L2A <-->|send_message| L1
    L2B <-->|send_message| L1
    L2C <-->|send_message| L1

    L2B -->|delegar_tarefa (batch/parallel)| L3A
    L2B -->|delegar_tarefa (batch/parallel)| L3B
    L2B -->|delegar_tarefa (batch/parallel)| L3C

    L1 <-->|read/write| AIMem
    L2A <-->|read/write| AIMem
    L1 <-->|commit/edit| GitRepo
```

### 2.1 Level 1: Principal Agent (Strategic Orchestration)
- **Role:** Central orchestrator responsible for user alignment, high-level planning, strategic reasoning, and task decomposition.
- **Capabilities:** Direct user communication, subagent invocation (`invoke_subagent`), skill discovery, global memory management (`ai-memory`), and Git revision control.
- **Execution Mandates:**
  - Never execute repetitive, file-by-file linear tasks directly within the primary context window.
  - Formulate unambiguous execution plans, assign scoped workloads to Level 2 agents, and synthesize final deliverables.

### 2.2 Level 2: Local Subagents (Tactical Stateful Managers)
- **Role:** Domain-specific autonomous workers operating concurrently in isolated execution contexts (e.g., Code Researcher, Security Auditor, Test Engine).
- **Capabilities:** Direct local filesystem access (`view_file`, `replace_file_content`, `run_command`), asynchronous message-based communication (`send_message`), and Level 3 task dispatching.
- **Execution Mandates:**
  - Execute background analysis or file mutations within bounded task definitions.
  - Coordinate with the Principal Agent via structured message responses.
  - Offload high-volume, isolated sub-tasks to Level 3 workers instead of consuming local execution steps.

### 2.3 Level 3: OmniRoute Leaf Agents (Stateless Execution Workers)
- **Role:** High-throughput, cost-optimized leaf workers executing pure transformations, classifications, extraction, and chunk analysis.
- **Capabilities:** Invoked via the MCP OmniRoute tool `delegar_tarefa`. Strictly sandboxed with **zero filesystem access**.
- **Execution Mandates:**
  - Must receive self-contained context and explicit operational contracts (Objective, Context, Constraints, Format, Criteria).
  - Must be invoked in parallel batches (`call_mcp_tool` concurrency) rather than sequential iterations.
  - Level 2 callers must perform deterministic validation on Level 3 outputs before ingestion.

---

## 3. Global Skills Ecosystem

Swarm components must proactively leverage the following canonical skills and MCP tools:

### 3.1 AI-Memory Suite (Persistence & State Management)
The `ai-memory` subsystem serves as the immutable long-term memory across sessions and agents:

| Skill | Category | Operational Purpose |
| :--- | :--- | :--- |
| `ai-memory-durable-pages` | Write / Mutation | Records canonical decisions (ADRs), permanent project constraints, domain models, and pinned operational rules. |
| `ai-memory-retrieval` | Read-Only | Queries historical decisions, conventions, resolved gotchas, and architectural guidelines prior to modifying code. |
| `ai-memory-learning-maintenance` | Hygiene / Audit | Audits wiki consistency, consolidates transient observations, resolves contradictions, and runs memory forget sweeps. |
| `ai-memory-handoff` | Session Continuity | Serializes pending tasks, blockers, and contextual artifacts during agent handoffs or session transitions. |
| `ai-memory-messaging` | Asynchronous I/O | Manages inter-project or inter-agent inboxes for asynchronous coordination across isolated repositories. |
| `ai-memory-routing-install` | Infrastructure | Configures agent routing tables, manages instruction snippets, and repairs local/global skill bindings. |

### 3.2 OmniRoute Delegation Engine (Cognitive Offloading)
Exposed through the `omniroute-delegation` skill and the MCP `omnirouter` server:

- **Core Functionality:** Exposes `delegar_tarefa(prompt, modelo_ou_rota)` to route workloads dynamically through local or remote model endpoints based on policy configurations (e.g., `auto/coding`, `auto/fast`, `auto/cheap`).
- **Standardized Prompt Contract:**
  Every delegation payload to Level 3 must conform to the 5-field schema:
  1. **Objective (`Objetivo`):** Concrete, single-purpose outcome required.
  2. **Context (`Contexto`):** Complete, self-contained textual data (code snippet, AST segment, diff chunk).
  3. **Constraints (`Restrições`):** Strict operational boundaries (e.g., no markdown wrapping, strict schema adherence).
  4. **Format (`Formato`):** Exact expected response format (JSON schema, CSV, or raw code block).
  5. **Criteria (`Critérios`):** Explicit validation standards for output acceptance.
- **Concurrency Directive:** Sequential loops calling `delegar_tarefa` one by one are prohibited when chunks are mutually independent. Schedulers must dispatch requests concurrently via parallel tool calls.

### 3.3 Auditing & Normalization Engine
Exposed through the `audit-normalize` skill:

- **Core Functionality:** Ingests raw, unstructured Markdown findings emitted by heterogeneous audit agents and transforms them into a canonical, schema-compliant `report_data.json` dataset.
- **Operating Guarantees:** 
  - Strictly deterministic and non-destructive.
  - Tracks full provenance and detects conflicting findings without executing secondary LLM hallucinations.
  - Serves as the authoritative source for subsequent report publishing and issue creation.

### 3.4 System & Customization Guides
- **`antigravity-guide`:** Canonical reference for Antigravity native tools, slash commands, background tasks, and environment lifecycle mechanics.
- **`agy-customizations`:** Complete architectural guide for extending the agent runtime (authoring skills, defining custom rules, implementing MCP sidecars, and managing loading priorities).

---

## 4. Communication & Delegation Protocols

### 4.1 Tier Boundary Matrix

| Characteristic | Level 1 (Principal) | Level 2 (Subagent) | Level 3 (OmniRoute Leaf) |
| :--- | :--- | :--- | :--- |
| **Statefulness** | Stateful | Stateful | Stateless |
| **Filesystem Access** | Full Read/Write | Full Read/Write | None (Payload only) |
| **Tool Group** | Full CLI / Subagents / MCP | Subagent Tools / MCP | No tools |
| **Execution Medium** | Native Session | `invoke_subagent` Process | HTTP / MCP Gateway |
| **Invocation Pattern** | Event-driven (User) | Asynchronous Task | Massively Parallel Batch |
| **Recursion Policy** | May invoke Level 2 | May invoke Level 3 | Recursive invocation prohibited |

### 4.2 Error Handling & Quality Escalation
When deploying lower-tier models through OmniRoute:
1. **Validation First:** All Level 3 outputs must pass deterministic schema or regex validation upon return to Level 2.
2. **Escalation Trigger:** If a leaf task fails schema validation or returns an uncertainty flag, the Level 2 agent must escalate the task to a high-capacity model rather than re-querying the failing leaf.
3. **No Blind Trust:** Untrusted model outputs must never be written directly to the codebase without syntactical and logical verification.

---

## 5. Directives for Skill Creation & Prompt Authoring

When defining new subagents or authoring `SKILL.md` specifications, agents must adhere to the following rules:

### Rule 1: Composition Over Duplication
Never reimplement capabilities provided by the global ecosystem.
- For persistence, invoke `ai-memory-durable-pages` instead of creating ad-hoc local files.
- For report synthesis, feed raw findings into `audit-normalize` instead of crafting custom JSON mergers.
- For multi-file inspection, delegate parallel slices to `omniroute-delegation`.

### Rule 2: Strict Boundary Enforcement
- If a task requires scanning multiple directory hierarchies or modifying codebases, encapsulate it in a **Level 2 Subagent**.
- If a task involves transforming, extracting, or categorizing an isolated data slice, route it to a **Level 3 OmniRoute Worker**.

### Rule 3: Memory Assumption
All new subagent definitions and runtime prompts must incorporate initialization logic that queries `ai-memory-retrieval` at boot time. Swarm agents must inherit project-specific idioms, conventions, and architectural gotchas before generating solutions.

### Rule 4: Progressive Disclosure in Skills
Skill definitions (`SKILL.md`) must act as **runtime routers**, remaining compact (target < 500 lines):
- Do not overload `SKILL.md` with exhaustive background documentation.
- Maintain separate directories: `references/` for on-demand domain knowledge, `scripts/` for deterministic utilities, and `assets/` for templates and schemas.
- Reference documentation must only be read by an agent when a specific conditional branch mandates it.

### Rule 5: Non-Contamination of User Codebases
Auxiliary operational states, raw audit artifacts, and internal LLM traces must never pollute the primary project repository. Machine-generated states and audit records must be isolated within independent sub-repositories or designated directory trees (e.g., `.audit/`).

---

## 6. Skill Lifecycle, Directory Anatomy & Deployment Architecture

### 6.1 Canonical Skill Directory Anatomy
Every skill packaged within the swarm architecture follows a strict layout separating runtime instructions, maintenance specifications, deterministic scripts, and verification schemas:

```text
skills/<category>/<skill-name>/
├── SKILL.md                 # Runtime router and entry point (< 500 lines)
├── SPEC.md                  # Maintenance contract, behavioral invariants, and evaluation targets
├── SOURCES.md               # Provenance, architectural decisions, and upstream citations
├── pyproject.toml           # Deterministic dependencies and packaging configuration
├── src/                     # Core deterministic engine (zero LLM hallucination risk)
├── schemas/                 # Canonical JSON schemas for work items, plans, and output artifacts
├── references/              # On-demand reference documentation loaded via progressive disclosure
├── scripts/                 # Deterministic CLI utilities and automation scripts
└── tests/                   # Verification suite (unit, integration, and invariant tests)
```

### 6.2 Deployment & Symlink Standard
The repository `projects/skills` serves as the sole authoritative source of truth for skill development. Agent runtimes must consume skills via symbolic links rather than divergent copies:

```text
projects/skills/<skill-name>
         ↓ (symbolic link)
~/.gemini/config/skills/<skill-name>
```

- **Zero Duplication:** Skills must never be cloned or copied into agent configuration roots.
- **Snapshot Isolation:** In production environments requiring release isolation, symlinks point to validated release snapshots rather than active worktrees.

## 7. Centralized Agent Configuration Management

To ensure uniformity across the swarm of local agents (Antigravity, Claude, OpenCode, Kimi, etc.), all underlying configurations, behavioral rules, and persistent context connectors have been migrated directly into this repository.

### Directory Structure

```text
SKILLS/
├── configs/
│   ├── universal/
│   │   └── rules/       # Global cognitive rules (e.g., 07-ai-memory.md, 08-cognitive-protocol.md)
│   └── antigravity/     
│       ├── rules/       # Antigravity-specific overrides (Terminal UI, Diagrams)
│       ├── mcp/         # Antigravity MCP Server configs
│       └── hooks/       # Pre/Post Invocation lifecycle hooks
├── skills/
│   ├── universal/       # Shared skills (ai-memory suite, audit-normalize, etc.)
│   └── antigravity/     # Antigravity-specific tools (model-routing)
```

### Symlink Mechanism
All agents must create symlinks from their local home-directory configuration paths pointing to this repository. For example:
- `~/.gemini/config/rules/` -> `SKILLS/configs/universal/rules/`
- `~/.gemini/config/skills/` -> `SKILLS/skills/universal/`

This guarantees that any architectural decision or cognitive shift committed to this repository propagates instantly to every active agent in the swarm without requiring manual `ai-memory` updates for structural agent behaviors.

### Installation & Snapshot Isolation

To prevent active development from breaking running agents (Snapshot Isolation principle), a dynamic provisioning script is provided at `scripts/setup-agent-configs.sh`.

**Live Development Mode (Tracks HEAD):**
```bash
./scripts/setup-agent-configs.sh --target ~/.gemini/config
```

**Production Snapshot Mode (Immutable):**
Extracts a specific tag/commit into a `.snapshots/` directory and points symlinks there. This guarantees the agent's cognitive boundary remains completely stable regardless of active edits in the working tree.
```bash
./scripts/setup-agent-configs.sh --target ~/.claude/config --snapshot v1.0.0
```

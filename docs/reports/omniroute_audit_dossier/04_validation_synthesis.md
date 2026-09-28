# OmniRoute Delegation - Validated Synthesis

## 1. Overview and Synthesis
The `omniroute-delegation` skill functions as an MCP-based routing gateway decoupling domain orchestration logic from model execution. The Orchestrator (Agent) handles domain logic, context scoping, and schema validation, while OmniRoute resolves the execution infrastructure (model selection, latency, budgets, retries, and dual-layer caching). The package is version-frozen at `v1.0.0-frozen` and verified with 196 passing tests, but flagged as `READY_WITH_WARNINGS` due to missing concurrency tests.

## 2. Handling of L3 Agents (Leaf Models)
- **Role-Based Escalation:** Tasks escalate based on the policy required. Mechanical tasks run on lightweight models; schema failures escalate to smarter models; critical tasks use a `fusion` consensus mechanism.
- **Security & Trust Boundary:** L3 agents are heavily isolated. There is no recursive delegation allowed (agents cannot call MCP tools back). All inputs and outputs are treated as **untrusted data**, meaning output code or commands are not blindly executed.
- **Task Construction:** The `TaskBuilder` component ensures proper scoping by enforcing a strict 5-part prompt structure (Objective, Constraints, Context, Expected format, Success criteria).
- **Delegation Execution:** Communication is managed via the `delegar_tarefa` tool, dynamically discovered over an HTTP JSON-RPC 2.0 transport that maintains separate network (`mcp-session-id`) and logical (`session_id`) states.

## 3. Handling of SCHEMA_VIOLATION
- **Historical Issue:** During Engine V2 benchmarks, strict validations rejected LLM outputs, causing `SCHEMA_VIOLATION` errors. These failures masked actual vulnerabilities (like IDOR) by erroneously reporting "0 findings".
- **Engine V3 Resolution (Fail-Closed):**
  - Errors like `SCHEMA_VIOLATION` or `TIMEOUT` no longer return 0 findings. Instead, they force a `SEMANTIC_COVERAGE_FAILED` and `INCOMPLETE` state.
  - The parsing layer now uses **tolerant normalization**, capable of coercing slight structural deviations (e.g., lists instead of objects) using explicit conversion rules.
  - Completely malformed outputs fallback to a loud `VALIDATION_ERROR`.

## 4. Identified Contradictions and Gaps
- **CRITICAL Contradiction (Validation Bypass Bug C-007):** While the Code Audit dictates that `TaskBuilder` enforces a strict credential scanner (`scan_for_credentials`) and `jsonschema` verification before delegation, the Memory Audit reveals a confirmed architectural bug (`MCPOmniRouteBackend` bypasses normal `MCPClient` validations). It calls `delegar_tarefa` directly, completely circumventing the credential firewall and schema checks.
- **Testing Gaps:** Although functional testing is robust (196 tests), the implementation lacks exhaustive concurrency tests and an explicit V2 regression baseline.

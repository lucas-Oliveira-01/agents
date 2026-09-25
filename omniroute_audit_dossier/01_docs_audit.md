# OmniRoute & Task Delegation - Architectural Audit

## 1. Architectural Intent
OmniRoute acts as a local model routing gateway designed to decouple the orchestration logic of the agent from specific LLM providers. 
- **Separation of Concerns:** The Orchestrator (Agent) handles domain logic: defining context slices, managing budgets, enforcing trust boundaries, and schema validation. OmniRoute handles execution infrastructure: model/provider resolution, fallback, retries, rate limiting, and cache affinity.
- **Abstract Task Policies:** The Orchestrator requests execution based on an abstract policy (e.g., `cheap`, `fast`, `coding`, `quality-first`) rather than a concrete model. OmniRoute resolves this policy to the best matching model according to latency, cost, and availability.

## 2. Delegation Strategies
- **Role-Based Model Escalation:** Mechanical tasks start on lightweight models (`auto/cheap` or `auto/fast`). If deterministic validation (like schema checks) fails, the system escalates the task to deeper reasoning models (`auto/coding`, `auto/smart`).
- **Fusion Mode:** For critical vulnerability verification, a `fusion` policy dispatches concurrent requests to multiple distinct models and consolidates them through a judge model.

## 3. Trust Boundary & Execution Safety
- **Strict Capability Firewall:** The MCP exposes only safe task execution methods (`delegar_tarefa`, `consultar_status_delegacao`, `invalidar_cache_local`). OmniRoute’s administrative controls (like managing quotas or provider keys) are completely blocked from the agent.
- **No Recursive Delegation:** Delegation strictly flows downwards (`Agent -> OmniRoute -> Leaf Model`). The leaf model has no access to MCP tools or credentials and cannot delegate tasks back into the system.
- **Untrusted Context:** All project files, code, and LLM outputs are treated as **untrusted data**. Deterministic layers govern execution capability and sanitize code blocks to mitigate indirect prompt injections.

## 4. Context Use and Cost Optimization
- **Dual Caching Layer:**
  1. **Deterministic Application Cache:** Maintained by the Orchestrator, it generates a SHA-256 key from task type, prompt, normalized context, and schema. Stored in `.audit/cache/tasks/`, resolving hits without ever calling OmniRoute.
  2. **Infrastructure Cache:** Managed by OmniRoute to leverage prompt-caching APIs from upstream providers (e.g., Anthropic, OpenAI).
- **Progressive Disclosure:** Instead of dumping the entire repository, context is fed in escalating tiers (Level 0: Metadata -> Level 5: Full Source) depending on the task's cognitive requirements.
- **Hierarchical Budget Governance:** Token and monetary limits are cascaded (Global -> Run -> Task -> Request). Over-budget conditions result in explicitly marked failed/partial states, never silent degradation.

## 5. Traceability and Independence
- **Semantic Provenance:** Every OmniRoute interaction produces a canonical record in `run_manifest.json`, storing the context hash, token consumption, requested policy, resolved provider, and validation status.
- **Git Isolation:** The Orchestrator maintains its history inside a separate `.audit/.git/` tree. This ensures the primary project codebase isn’t contaminated with AI artifacts or caches.

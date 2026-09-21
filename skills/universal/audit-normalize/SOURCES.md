# Sources and Provenance

## Origin
This skill was developed to solve the "Typed JSON Handoff" requirement in multi-agent security pipelines. Since free-text Markdown handoffs lead to context loss and hallucinations between agents, this script was created to deterministically parse and merge those documents.

## Key Decisions
*   **Python Implementation:** Chosen over bash or pure LLM reasoning to guarantee deterministic, reproducible, and schema-valid output.
*   **Idempotency:** Designed to safely merge updates without losing prior findings, supporting continuous audit lifecycles.
*   **Universal Namespace:** Placed in `skills/universal/` because it does not rely on any platform-specific MCP or native tools.

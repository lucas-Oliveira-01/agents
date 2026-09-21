# Sources and Provenance

## Origin
This skill was created to standardize interactions with the OmniRoute MCP gateway within the Antigravity ecosystem. OmniRoute abstracts away model routing and concurrent sub-task execution.

## Key Decisions
*   **Antigravity Namespace:** Placed in `skills/antigravity/` because it is specifically designed to interoperate with Antigravity's MCP implementation and OmniRoute server.
*   **Contract Enforcement:** The Python suite validates task structures locally before they are sent to the MCP gateway, ensuring the orchestrator agent does not waste time sending malformed requests.

# Sources and Provenance

## Origin
This skill was created to standardize interactions with the OmniRoute MCP gateway. OmniRoute abstracts away model routing and concurrent sub-task execution.

## Key Decisions
*   **Universal Namespace:** Placed in `skills/universal/` because the user intends to connect all their agents (across different platforms) to the OmniRoute MCP gateway, making this delegation contract universally applicable.
*   **Contract Enforcement:** The Python suite validates task structures locally before they are sent to the MCP gateway, ensuring the orchestrator agent does not waste time sending malformed requests.

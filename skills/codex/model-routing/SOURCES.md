# Sources and Provenance

## Origin

This skill is a semantic adaptation of
`skills/antigravity/model-routing`. The original intent was accepted in
`docs/decisions/model-routing-policy.md`: model choice should be driven by task
complexity, validation needs, latency, and cost instead of always using the
highest tier.

## Adaptation evidence

- The Antigravity implementation is platform-specific because it relies on
  `invoke_subagent`, Antigravity model tiers, and `/boost`.
- The Codex runtime exposes model and reasoning selection on subagent
  invocation through `model` and `reasoning_effort`.
- Current higher-priority Codex instructions restrict when subagents may be
  spawned, so this skill only applies after delegation or model selection is
  otherwise authorized.

## Non-portable elements

- Antigravity `invoke_subagent` API.
- Antigravity `flash_lite`, `flash`, `pro`, and `inherit` tier names.
- Antigravity `/boost` verification mechanism.

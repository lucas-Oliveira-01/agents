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
- The OpenCode runtime exposes model selection on agents and subagent
  invocation through `model` in `provider/model#variant` form (see
  `https://opencode.ai/v2/docs/agents`), with built-in subagents `general`
  and `explore`.
- Current higher-priority instructions restrict when subagents may be spawned,
  so this skill only applies after delegation or model selection is otherwise
  authorized.

## Non-portable elements

- Antigravity `invoke_subagent` API.
- Antigravity `flash_lite`, `flash`, `pro`, and `inherit` tier names.
- Antigravity `/boost` verification mechanism.

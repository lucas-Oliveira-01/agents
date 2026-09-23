# Codex Model Routing Maintenance Specification

## Intent and scope

This skill adapts the Antigravity `model-routing` policy to Codex. It governs
how to choose Codex model and reasoning profiles when model selection or
subagent delegation is already authorized by higher-priority instructions.

## Compatibility boundary

The Antigravity source uses `invoke_subagent`, `flash_lite`, `flash`, `pro`,
`inherit`, and `/boost`. Those mechanisms are not installed directly in Codex.
The Codex adaptation uses only Codex concepts that are visible in the runtime
tooling: subagent `model` and `reasoning_effort` selection.

The skill must never be edited to bypass active Codex policies about when
subagents may be spawned.

## Maintenance boundaries

- `SKILL.md` stays abstract and describes the routing strategy.
- `references/model-inventory.md` may contain current observed model slugs and
  must be refreshed when Codex exposes a different model set.
- `references/routing-matrix.md` maps task envelopes to Codex profiles without
  importing Antigravity-only tiers.

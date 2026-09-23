# OpenCode Model Routing Maintenance Specification

## Intent and scope

This skill adapts the Antigravity `model-routing` policy to OpenCode. It governs
how to choose OpenCode model, variant, and subagent profiles when model
selection or subagent delegation is already authorized by higher-priority
instructions.

## Compatibility boundary

The Antigravity source uses `invoke_subagent`, `flash_lite`, `flash`, `pro`,
`inherit`, and `/boost`. Those mechanisms are not installed directly in
OpenCode. The OpenCode adaptation uses only OpenCode concepts that are visible
in the runtime tooling: agent `model` (`provider/model#variant`) selection and
subagent choice (`general`, `explore`, custom subagents).

The skill must never be edited to bypass active OpenCode policies about when
subagents may be spawned.

## Maintenance boundaries

- `SKILL.md` stays abstract and describes the routing strategy.
- `references/model-inventory.md` may contain current observed model slugs and
  must be refreshed when OpenCode exposes a different model set.
- `references/routing-matrix.md` maps task envelopes to OpenCode profiles without
  importing Antigravity-only tiers.

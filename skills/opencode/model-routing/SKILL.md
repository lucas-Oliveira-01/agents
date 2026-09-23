---
name: model-routing
description: >
  Use this skill when an OpenCode task already has authorization to delegate work
  or select a model/agent profile, and the agent must choose a fitting
  OpenCode model, variant, or subagent based on task complexity, cost, latency,
  verification needs, and failure risk.
---

# OpenCode Model Routing Policy

This skill preserves the Antigravity `model-routing` intent for OpenCode: choose
execution capacity from task characteristics rather than defaulting to the
largest available model.

This skill does not authorize delegation by itself. First follow the active
OpenCode, developer, repository, and user instructions that decide whether a
subagent may be spawned or a non-default model may be selected. When delegation
or model selection is already in scope, use this policy to choose the smallest
reliable profile.

## OpenCode routing dimensions

When using OpenCode subagent tooling or agent definitions that expose `model`
(`provider/model#variant`) and agent selection (`general`, `explore`, custom
subagents), choose them from the task envelope:

- Use a fast profile for bounded mechanical implementation, straightforward
  refactors, short searches, and low-risk extraction.
- Use a workhorse profile for everyday engineering, routine debugging, and
  standard reviews.
- Use a reasoning profile (strong model, high variant, or reasoning router)
  for architecture, complex debugging, security review, broad synthesis, high
  ambiguity, or high cost of failure.
- Increase the model variant (for example `#high`, `#xhigh` where supported)
  only when the task requires deeper reasoning, longer planning, or careful
  verification.
- Prefer inheritance or the default session model when the current task does
  not need a different model choice.

## Escalation protocol

1. Classify complexity before selecting a profile.
2. Start with the lowest profile that can reliably satisfy the task.
3. Validate the result with deterministic checks or reviewer judgment.
4. Escalate only when evidence shows the selected profile was insufficient.

## Role-based guidance

- Data extractor, simple implementer, bulk refactorer: fast profile, explore
  subagent for read-only work, low variant.
- Test fixer, ordinary debugger, routine reviewer: workhorse profile, general
  subagent, medium variant as needed.
- Architect, security auditor, complex debugger, release-risk reviewer:
  reasoning profile, high or stronger variant.

## References

Read `references/routing-matrix.md` when mapping a task profile to an OpenCode
profile. Read `references/model-inventory.md` before relying on a specific
model slug, because available OpenCode models may change over time.

---
name: model-routing
description: >
  Use this skill when a Codex task already has authorization to delegate work
  or select a model/reasoning profile, and the agent must choose a fitting
  Codex model or reasoning effort based on task complexity, cost, latency,
  verification needs, and failure risk.
---

# Codex Model Routing Policy

This skill preserves the Antigravity `model-routing` intent for Codex: choose
execution capacity from task characteristics rather than defaulting to the
largest available model.

This skill does not authorize delegation by itself. First follow the active
Codex, developer, repository, and user instructions that decide whether a
subagent may be spawned. When delegation or model selection is already in
scope, use this policy to choose the smallest reliable profile.

## Codex routing dimensions

When using Codex subagent tooling that exposes `model` and `reasoning_effort`,
choose them from the task envelope:

- Use a fast/workhorse profile for bounded mechanical implementation,
  straightforward refactors, short searches, and low-risk extraction.
- Use a frontier profile for architecture, complex debugging, security review,
  broad synthesis, high ambiguity, or high cost of failure.
- Increase `reasoning_effort` only when the task requires deeper reasoning,
  longer planning, or careful verification.
- Prefer inheritance or the default profile when the current task does not need
  a different model choice.

## Escalation protocol

1. Classify complexity before selecting a profile.
2. Start with the lowest profile that can reliably satisfy the task.
3. Validate the result with deterministic checks or reviewer judgment.
4. Escalate only when evidence shows the selected profile was insufficient.

## Role-based guidance

- Data extractor, simple implementer, bulk refactorer: fast/workhorse profile,
  low or medium reasoning.
- Test fixer, ordinary debugger, routine reviewer: workhorse profile, medium or
  high reasoning as needed.
- Architect, security auditor, complex debugger, release-risk reviewer:
  frontier profile, high or stronger reasoning.

## References

Read `references/routing-matrix.md` when mapping a task profile to a Codex
profile. Read `references/model-inventory.md` before relying on a specific
model slug, because available Codex models may change over time.

# OpenCode Model Inventory

This inventory reflects the OpenCode model options visible in this runtime on
2026-09-23 (via `opencode models`). Treat it as volatile operational data, not
a permanent ranking.

## Reasoning profile

- `opencode/muse-spark-1.3-contributor-free`: supports variants `minimal`,
  `low`, `medium`, `high`, `xhigh`. Highest-capacity option for demanding
  reasoning, architecture, complex debugging, security review, and high-risk
  verification (use `#high` / `#xhigh`).
- `omniroute/auto-reasoning`, `omniroute/auto-smart`: router profiles that
  select a capable backend automatically.

## Workhorse profile

- `opencode/muse-spark-1.3-contributor-free` (default variant): default strong
  coding and everyday engineering profile.
- `omniroute/auto-coding`: router profile for coding work.

## Fast profile

- `opencode/mimo-v2.6-flash-free`: fast profile for easier bounded tasks and
  auxiliary work.
- `opencode/ling-3.0-flash-fin-free`: fast profile.
- `opencode/nemotron-3.5-lightning-free`: fast profile.
- `omniroute/auto-fast`, `omniroute/auto-cheap`: router profiles for
  latency- or cost-sensitive work.

## Other observed models

- `opencode/big-pickle`
- `opencode/muse-spark-1.2-contributor-free`
- `opencode/nemotron-3-ultra-free`

Use these only when compatibility, cost, or explicit user/runtime requirements
justify them. Refresh this file when `opencode models` exposes a different set.

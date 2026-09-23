# OpenCode Routing Matrix

Use this matrix after delegation or explicit model selection is already allowed
by current instructions.

| Task profile | Primary need | OpenCode profile |
|---|---|---|
| Simple rename or bounded refactor | Throughput and latency | Fast model, explore subagent for read-only work |
| Routine CRUD implementation | Productivity | Workhorse model, general subagent |
| Mechanical changes across many files | Throughput with local verification | Workhorse model, general subagent |
| Cost-sensitive auxiliary analysis | Cost and latency | Fast profile, low variant |
| Broad synthesis or architecture | Context processing and judgment | Reasoning model, high variant |
| Complex bug investigation | Hypothesis and verification | Reasoning or workhorse model, high variant |
| Security auditing and release-risk review | Precision and failure avoidance | Reasoning model, high or stronger variant |
| Long-horizon autonomous work | Persistence and verification | Reasoning model, high or stronger variant |

Decision heuristic:

```text
profile = f(reasoning depth, context size, tool complexity, cost of failure, latency/cost sensitivity)
```

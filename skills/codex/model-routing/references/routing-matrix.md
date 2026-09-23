# Codex Routing Matrix

Use this matrix after delegation or explicit model selection is already allowed
by current instructions.

| Task profile | Primary need | Codex profile |
|---|---|---|
| Simple rename or bounded refactor | Throughput and latency | Fast/workhorse model, low or medium reasoning |
| Routine CRUD implementation | Productivity | Workhorse model, medium reasoning |
| Mechanical changes across many files | Throughput with local verification | Workhorse model, low or medium reasoning |
| Cost-sensitive auxiliary analysis | Cost and latency | Fast profile, low reasoning |
| Broad synthesis or architecture | Context processing and judgment | Frontier model, high reasoning |
| Complex bug investigation | Hypothesis and verification | Frontier or workhorse model, high reasoning |
| Security auditing and release-risk review | Precision and failure avoidance | Frontier model, high or stronger reasoning |
| Long-horizon autonomous work | Persistence and verification | Frontier model, high or stronger reasoning |

Decision heuristic:

```text
profile = f(reasoning depth, context size, tool complexity, cost of failure, latency/cost sensitivity)
```

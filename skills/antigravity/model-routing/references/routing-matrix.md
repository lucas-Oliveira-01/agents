# Routing Matrix

Use this matrix to determine the optimal subagent model tier based on the task envelope.

| Task Profile                              | Primary Need               | Tier Needed |
| ----------------------------------------- | -------------------------- | ----------: |
| Simple rename/refactor                    | Throughput & Latency       | `flash`     |
| Routine CRUD implementation               | Productivity               | `flash`     |
| Mechanical changes across 50+ files       | High Throughput            | `flash`     |
| Cost-sensitive / experimental auxiliary   | Cost efficiency            | `flash_lite`|
| Broad synthesis / literature review       | Context processing         | `pro`       |
| Complex bug investigation                 | Hypothesis & Verification  | `pro`       |
| Core architecture design                  | Deep Reasoning             | `pro`       |
| Security auditing & verification          | Precision                  | `pro`       |
| Long-horizon / autonomous agents          | Persistence & Verification | `pro`       |

**Decision Function Heuristic:**
`Tier = f(Reasoning Depth, Context Size, Tool Complexity, Cost of Failure, Cost Sensitivity)`

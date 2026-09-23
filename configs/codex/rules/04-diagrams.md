# Codex Diagrams

Use Mermaid only when a diagram explains architecture, flow, sequence, or state more clearly than prose or a table.

## Mermaid Compatibility

Prefer simple diagrams that render predictably in plain Markdown viewers and terminal contexts.

Allowed patterns:

- `flowchart`
- `sequenceDiagram`
- `stateDiagram-v2`
- simple rectangular nodes
- diamond decisions
- plain edge labels

Avoid renderer-specific styling such as:

- `style`
- `classDef`
- `class`
- inline colors or fills
- complex decorative node shapes

When a table or plain text structure is clearer, use that instead.

# OpenCode Configuration Installation

## Purpose

This procedure records how repository-owned universal and OpenCode-specific configuration is adapted and installed for OpenCode without creating divergent runtime copies.

## Source Classification

| Source | Purpose | Classification | OpenCode result |
|---|---|---|---|
| `configs/universal/rules/*.md` | Cross-agent behavioral rules | `UNIVERSAL` | Referenced by `configs/opencode/AGENTS.md`; preserved without conceptual adaptation |
| `configs/antigravity/rules/02-terminal-ui.md` | Terminal presentation guidance (Kitty, Nerd Font) | `REQUIRES_ADAPTATION` | Copied as `configs/opencode/rules/02-terminal-ui.md` (plain trees, no font glyphs) |
| `configs/antigravity/rules/04-diagrams.md` | Mermaid rendering constraints | `PORTABLE_TO_OPENCODE` with retitling | Copied as `configs/opencode/rules/04-diagrams.md` |
| Antigravity `ai-memory` hooks (`hooks.example.json`) | ai-memory lifecycle hooks | `NOT_PORTABLE` (already satisfied) | Not installed: `~/.config/opencode/plugins/ai-memory.ts` already exists with divergent local state; left untouched |
| `configs/antigravity/mcp/mcp_config.example.json` | Antigravity MCP server example | `REQUIRES_ADAPTATION` / `ALREADY_CONNECTED` | Nothing installed: global `opencode.json` already has `ai-memory` and `omniroute` connected |
| `configs/antigravity/mcp` entry `stitch` | Google Stitch MCP example with placeholder API key | `NOT_PORTABLE` | Not installed for OpenCode |
| `invoke_subagent` swarm model | Stateful work delegation to Antigravity subagents | `NOT_PORTABLE` | No direct config translation installed |

## Antigravity to OpenCode Adaptation Matrix

| Antigravity | Intent | OpenCode equivalent | Result | Evidence |
|---|---|---|---|---|
| `PreInvocation` hook | Capture session start in ai-memory | ai-memory TypeScript plugin (`open-code` / `opencode2` shape) | `PRESERVED_AS_IS` | `~/.config/opencode/plugins/ai-memory.ts` pre-exists; diverged from its `.bak`, so migration to a repo symlink was refused to preserve local state |
| `PreToolUse` / `PostToolUse` hooks | Capture tool observations | Same plugin | `PRESERVED_AS_IS` | Same file as above |
| Antigravity `ai-memory` MCP JSON | Configure ai-memory MCP | `mcp` entry in global `opencode.json` | `PRESERVED` | `opencode mcp list` reports `ai-memory` connected |
| Antigravity `omnirouter` MCP JSON | Configure OmniRoute MCP | `mcp` entry in global `opencode.json` | `PRESERVED` / `CONNECTED` | `opencode mcp list` reports `omniroute` connected |
| Antigravity `stitch` MCP JSON | Configure Google Stitch MCP | None installed | `NOT_PORTABLE` | Contains placeholder `YOUR_GCP_API_KEY_HERE`; no credential source established |
| Nerd Font icons / tree glyphs | Rich terminal scanning | Plain readable trees | `ADAPTED` | `configs/opencode/rules/02-terminal-ui.md` is a copy of the Codex adaptation, retitled |
| Mermaid ASCII renderer constraints | Avoid broken diagrams | Renderer-agnostic simple Mermaid | `ADAPTED` | `configs/opencode/rules/04-diagrams.md` is a copy of the Codex adaptation, retitled |

## Installation Manifest

| Source | Destination | Type | Action | Status |
|---|---|---|---|---|
| `configs/opencode/AGENTS.md` | `~/.config/opencode/AGENTS.md` | symlink | install global OpenCode entry point | `CORRECT` |
| `configs/universal/rules/` | `configs/opencode/rules/universal` | symlink | expose universal rules from OpenCode config tree (shared source, not another agent's folder) | `CORRECT` |
| `configs/opencode/rules/02-terminal-ui.md` | n/a (repo canonical) | copy of Codex adaptation | copy, never symlink to another agent's folder | `CORRECT` |
| `configs/opencode/rules/04-diagrams.md` | n/a (repo canonical) | copy of Codex adaptation | copy, never symlink to another agent's folder | `CORRECT` |
| `~/.config/opencode/opencode.json` | unchanged | regular file | preserve user-local OpenCode config (MCP already connected) | `PRESERVED` |
| `~/.config/opencode/plugins/ai-memory.ts` | unchanged | regular file | preserve user-local plugin with divergent state | `PRESERVED` |
| Repo root `AGENTS.md` | unchanged | Codex-owned symlink | OpenCode loads it as project instructions; not modified | `PRESERVED` |

## Validation

Observed on 2026-09-23:

| Target | Evidence | Level |
|---|---|---|
| `~/.config/opencode/AGENTS.md` | `readlink` resolves to `/home/oliveira/Projects/SKILLS/configs/opencode/AGENTS.md` | `SYMLINK_RESOLVES` |
| `configs/opencode/rules/universal` | `readlink` resolves to `../../universal/rules`; 8 rule files readable | `SYMLINK_RESOLVES` |
| `02-terminal-ui.md` | `diff` against Codex source shows only title lines changed | `COPY_VERIFIED` |
| `04-diagrams.md` | `diff` against Codex source shows only the title line changed | `COPY_VERIFIED` |
| MCP | `opencode mcp list` reports `ai-memory` and `omniroute` connected | `RUNTIME_AVAILABLE` |

The `instructions` field in `opencode.json` is not loaded by OpenCode V2, so `AGENTS.md` is the only instruction channel; no `instructions` entries were added.

## Known Limitations

The repo root `AGENTS.md` remains Codex-owned. OpenCode loads it as project-level instructions alongside the new global file. Changing it would touch Codex-owned state and was explicitly out of scope.

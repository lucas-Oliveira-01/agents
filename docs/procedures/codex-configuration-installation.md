# Codex Configuration Installation

## Purpose

This procedure records how repository-owned universal and Codex-specific configuration is adapted and installed for Codex without creating divergent runtime copies.

## Source Classification

| Source | Purpose | Classification | Codex result |
|---|---|---|---|
| `configs/universal/rules/*.md` | Cross-agent behavioral rules | `UNIVERSAL` | Referenced by `configs/codex/AGENTS.md`; preserved without conceptual adaptation |
| `configs/antigravity/rules/02-terminal-ui.md` | Terminal presentation guidance | `REQUIRES_ADAPTATION` | Adapted as `configs/codex/rules/02-terminal-ui.md` |
| `configs/antigravity/rules/04-diagrams.md` | Mermaid rendering constraints | `PORTABLE_TO_CODEX` with minor wording adaptation | Adapted as `configs/codex/rules/04-diagrams.md` |
| `configs/antigravity/hooks/hooks.example.json` | ai-memory lifecycle hooks | `REQUIRES_ADAPTATION` | Adapted as `configs/codex/hooks/hooks.json` using Codex hook event names |
| `configs/antigravity/mcp/mcp_config.example.json` | Antigravity MCP server example | `REQUIRES_ADAPTATION` / `PARTIALLY_BLOCKED` | Codex MCP config is in `~/.codex/config.toml`; `omnirouter` is configured there as a streamable HTTP server |
| `configs/antigravity/mcp` entry `stitch` | Google Stitch MCP example with placeholder API key | `NOT_PORTABLE` | Not installed for Codex |

## Antigravity to Codex Adaptation Matrix

| Antigravity | Intent | Codex equivalent | Result | Evidence |
|---|---|---|---|---|
| `PreInvocation` hook | Capture session start in ai-memory | `SessionStart` in `~/.codex/hooks.json` | `ADAPTED` | Current Codex runtime uses `SessionStart` in `/home/oliveira/.codex/hooks.json` |
| `PreToolUse` hook | Capture pre-tool observations | `PreToolUse` in `~/.codex/hooks.json` | `ADAPTED` | Current Codex runtime has trusted hash entries for this hook in `/home/oliveira/.codex/config.toml` |
| `PostToolUse` hook | Capture post-tool observations | `PostToolUse` in `~/.codex/hooks.json` | `ADAPTED` | Current Codex runtime has trusted hash entries for this hook in `/home/oliveira/.codex/config.toml` |
| `Stop` hook | Capture stop event | `Stop` in `~/.codex/hooks.json` | `ADAPTED` | Current Codex runtime uses `Stop` |
| Antigravity `ai-memory` MCP JSON | Configure ai-memory MCP | `[mcp_servers.ai-memory]` in `~/.codex/config.toml` | `PRESERVED` | `codex mcp list` reports `ai-memory` enabled |
| Antigravity `omnirouter` MCP JSON | Configure OmniRoute MCP | `[mcp_servers.omnirouter]` in `~/.codex/config.toml` | `ADAPTED` / `CONNECTED` | `codex mcp list` reports `omnirouter` enabled at `http://127.0.0.1:20130/mcp`; Docker Compose stack in `/home/oliveira/Desktop/routers/omnirouter` exposes the MCP gateway on `127.0.0.1:20130` |
| Antigravity `stitch` MCP JSON | Configure Google Stitch MCP | None installed | `NOT_PORTABLE` | Contains placeholder `YOUR_GCP_API_KEY_HERE`; no Codex credential source was established |
| `invoke_subagent` swarm model | Delegate stateful work to Antigravity subagents | No direct config translation installed | `NOT_PORTABLE` | Current Codex agent delegation is governed by runtime tools/instructions, not Antigravity config files |

## Installation Manifest

| Source | Destination | Type | Action | Status |
|---|---|---|---|---|
| `configs/codex/AGENTS.md` | `AGENTS.md` | symlink | install project Codex entry point | `CORRECT` |
| `configs/universal/rules/` | `configs/codex/rules/universal` | symlink | expose universal rules from Codex config tree | `CORRECT` |
| `configs/codex/hooks/hooks.json` | `/home/oliveira/.codex/hooks.json` | symlink | migrate equivalent existing Codex hooks to repository canonical file | `CORRECT` |
| `/home/oliveira/.codex/config.toml` | unchanged | regular file | preserve user-local Codex config | `PRESERVED` |
| Codex MCP `omnirouter` | `/home/oliveira/.codex/config.toml` | regular file entry | install OmniRoute MCP endpoint | `CONNECTED` |

## Validation

Minimum validation steps:

1. `git status --short --branch`
2. `readlink AGENTS.md`
3. `readlink configs/codex/rules/universal`
4. `readlink /home/oliveira/.codex/hooks.json`
5. `codex doctor`
6. `codex mcp list`
7. `codex debug prompt-input` when the environment allows Codex debug startup
8. `git diff --check`

Validation levels must be reported separately:

- `FILE_EXISTS`
- `SYMLINK_RESOLVES`
- `CODEX_DISCOVERS_FILE`
- `CODEX_LOADS_FILE`

## Validation Results

Observed on 2026-09-22:

| Target | Evidence | Level |
|---|---|---|
| `AGENTS.md` | `readlink AGENTS.md` resolves to `configs/codex/AGENTS.md`; `codex debug prompt-input` includes `# AGENTS.md instructions for /home/oliveira/Projects/SKILLS` and the content of `configs/codex/AGENTS.md` | `CODEX_LOADS_FILE` |
| `configs/codex/rules/universal` | `readlink configs/codex/rules/universal` resolves to `../../universal/rules`; `configs/codex/rules/universal/07-ai-memory.md` is readable | `SYMLINK_RESOLVES` |
| `/home/oliveira/.codex/hooks.json` | `readlink /home/oliveira/.codex/hooks.json` resolves to `/home/oliveira/Projects/SKILLS/configs/codex/hooks/hooks.json`; `codex doctor --json` reports `config.load` as `ok` with hooks feature enabled | `SYMLINK_RESOLVES` / `CODEX_DISCOVERS_FILE` |
| Codex MCP config | `codex mcp list` reports `ai-memory` enabled from `~/.codex/config.toml` | `CODEX_DISCOVERS_FILE` |
| Codex OmniRoute MCP config | `codex mcp get omnirouter` reports `omnirouter` enabled as `streamable_http` at `http://127.0.0.1:20130/mcp` | `CODEX_DISCOVERS_FILE` |
| OmniRoute Docker gateway | `docker compose up -d` in `/home/oliveira/Desktop/routers/omnirouter` reports `omniroute`, `omniroute-redis`, and `omniroute-gateway` running; `docker compose ps` reports all three healthy | `RUNTIME_AVAILABLE` |
| OmniRoute MCP protocol | Direct MCP `initialize` and `tools/list` POSTs to `http://127.0.0.1:20130/mcp` return server `OmniRoute Task Gateway` and expose `delegar_tarefa` | `MCP_TOOLS_DISCOVERED` |

`codex doctor --json` also reported pre-existing environment issues unrelated to this installation: provider DNS/reachability failure, optional ai-memory MCP reachability failure from the doctor process, and `~/.codex/memories_1.sqlite` integrity/open failure. These were not remediated by this procedure.

On 2026-09-22, OmniRoute CLI `v3.8.50` was present and `codex mcp add omnirouter --url http://127.0.0.1:20130/mcp` succeeded. The standalone CLI daemon path (`omniroute serve`) was not the active deployment and was not used as the final runtime because this machine has the production-like Docker Compose deployment at `/home/oliveira/Desktop/routers/omnirouter`. That compose stack provides the app, Redis cache, and MCP gateway. The gateway health endpoint returns `{"status":"ok"}` and the MCP endpoint exposes `delegar_tarefa`.

The currently running Codex session may not expose newly-added MCP tools until the session/tool registry is refreshed or a new session starts.

## Known Limitations

`~/.codex/config.toml` is a user-local regular file that contains model settings, trusted project entries, MCP configuration, and trusted hook hashes. This procedure does not replace it with a symlink because that would risk losing user-local state and Codex hook trust records.

If Codex later supports a documented config include directory or a profile that is automatically loaded, repository-owned TOML snippets can be added without replacing the user-local file.

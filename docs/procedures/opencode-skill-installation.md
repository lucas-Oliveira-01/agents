# OpenCode Skill Installation

## Purpose

This procedure records how repository-owned skills are installed for OpenCode
without creating divergent runtime copies.

The repository remains the canonical source. The OpenCode-visible global skill
directory uses symlinks that point back to `skills/universal/` or
`skills/opencode/`.

## Runtime target

OpenCode V2 discovers skills in (precedence low to high): built-ins,
`.claude/skills`, `.agents/skills` (global compatibility), then
`~/.config/opencode/skills`, project `.opencode/skills`, and explicit `skills`
config entries.

Repository-managed global skills are installed into
`~/.config/opencode/skills`, which takes precedence over the
`~/.agents/skills` compatibility source where the Codex installation already
exposes the same skills.

## Source Classification

| Source | Purpose | Classification | OpenCode result |
|---|---|---|---|
| `skills/universal/ai-memory-durable-pages` | ai-memory durable wiki mutation routing | `UNIVERSAL` | Installed by symlink |
| `skills/universal/ai-memory-handoff` | ai-memory handoff routing | `UNIVERSAL` | Installed by symlink |
| `skills/universal/ai-memory-learning-maintenance` | ai-memory maintenance routing | `UNIVERSAL` | Installed by symlink |
| `skills/universal/ai-memory-messaging` | ai-memory cross-project messaging routing | `UNIVERSAL` | Installed by symlink |
| `skills/universal/ai-memory-retrieval` | ai-memory read-only retrieval routing | `UNIVERSAL` | Installed by symlink |
| `skills/universal/ai-memory-routing-install` | ai-memory routing install routing | `UNIVERSAL` | Installed by symlink |
| `skills/universal/audit-normalize` | Deterministic audit report normalization | `UNIVERSAL` | Installed by symlink |
| `skills/universal/omniroute-delegation` | OmniRoute MCP delegation contract | `UNIVERSAL` | Installed by symlink |
| `skills/universal/project-audit` | Project audit orchestration engine | `UNKNOWN` / not finalized | Not installed |
| `skills/antigravity/model-routing` | Antigravity model-tier routing for subagents | `REQUIRES_ADAPTATION` | Adapted as `skills/opencode/model-routing` and installed by symlink |

## Antigravity to OpenCode Adaptation Matrix

| Antigravity | Intent | OpenCode equivalent | Result | Evidence |
|---|---|---|---|---|
| `skills/antigravity/model-routing/SKILL.md` | Choose model capacity from task envelope instead of defaulting to the largest model | OpenCode agent `model` (`provider/model#variant`) and subagent selection (`general`, `explore`, custom) when delegation/model choice is already authorized | `ADAPTED` as `skills/opencode/model-routing/SKILL.md` | OpenCode V2 agents guide documents `model` with `#variant` and `mode: subagent`; the adaptation states that it does not itself authorize spawning |
| Antigravity `invoke_subagent` API | Stateful subagent invocation | OpenCode `subagent` tool / agent definitions | `REMOVED_WITH_REASON` | Subagent launch is controlled by current OpenCode runtime tools and higher-priority instructions |
| Antigravity tiers `flash_lite`, `flash`, `pro`, `inherit` | Coarse capacity routing | OpenCode fast/workhorse/reasoning profiles with volatile model inventory | `ADAPTED` | `skills/opencode/model-routing/references/model-inventory.md` maps the currently visible OpenCode model set (`opencode models`, 2026-09-23) |
| Antigravity `/boost` | Parallel verification/escalation mechanism | Deterministic validation and explicit escalation | `REMOVED_WITH_REASON` | No OpenCode `/boost` mechanism was established for this runtime |

## Installation Manifest

| Source | Destination | Type | Action | Status |
|---|---|---|---|---|
| `skills/universal/ai-memory-durable-pages` | `~/.config/opencode/skills/ai-memory-durable-pages` | symlink | fresh install (target absent) | `CORRECT` |
| `skills/universal/ai-memory-handoff` | `~/.config/opencode/skills/ai-memory-handoff` | symlink | fresh install (target absent) | `CORRECT` |
| `skills/universal/ai-memory-learning-maintenance` | `~/.config/opencode/skills/ai-memory-learning-maintenance` | symlink | fresh install (target absent) | `CORRECT` |
| `skills/universal/ai-memory-messaging` | `~/.config/opencode/skills/ai-memory-messaging` | symlink | fresh install (target absent) | `CORRECT` |
| `skills/universal/ai-memory-retrieval` | `~/.config/opencode/skills/ai-memory-retrieval` | symlink | fresh install (target absent) | `CORRECT` |
| `skills/universal/ai-memory-routing-install` | `~/.config/opencode/skills/ai-memory-routing-install` | symlink | fresh install (target absent) | `CORRECT` |
| `skills/universal/audit-normalize` | `~/.config/opencode/skills/audit-normalize` | symlink | fresh install (target absent) | `CORRECT` |
| `skills/universal/omniroute-delegation` | `~/.config/opencode/skills/omniroute-delegation` | symlink | fresh install (target absent) | `CORRECT` |
| `skills/opencode/model-routing` | `~/.config/opencode/skills/model-routing` | symlink | install OpenCode adaptation | `CORRECT` |
| `skills/universal/project-audit` | `~/.config/opencode/skills/project-audit` | none | exclude because not finalized | `NOT_APPLICABLE` |

No pre-existing runtime state was replaced: `~/.config/opencode/skills/` did not exist before installation, and `/home/oliveira/.agents/skills/` was left untouched.

## Validation

Observed on 2026-09-23:

| Target | Evidence | Level |
|---|---|---|
| 8 universal skills | Each `~/.config/opencode/skills/<name>` entry is a symlink resolving to `/home/oliveira/Projects/SKILLS/skills/universal/<name>` and each linked `SKILL.md` is readable | `SYMLINK_RESOLVES` |
| `model-routing` | Symlink resolves to `/home/oliveira/Projects/SKILLS/skills/opencode/model-routing` and `SKILL.md` is readable | `SYMLINK_RESOLVES` |
| `project-audit` | `~/.config/opencode/skills/project-audit` is absent | `NOT_APPLICABLE` |

The structural update property is satisfied because each runtime symlink points
at a stable repository path. A later edit to a canonical skill file in the
repository will be visible through the same symlink without reinstalling it.

## Known Limitations

The `skills/opencode/model-routing/references/model-inventory.md` file records the
OpenCode model options visible in this runtime on 2026-09-23. Treat that reference
as volatile operational data.

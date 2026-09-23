# Codex Skill Installation

## Purpose

This procedure records how repository-owned skills are installed for Codex
without creating divergent runtime copies.

The repository remains the canonical source. The Codex-visible skill directory
uses symlinks that point back to `skills/universal/` or `skills/codex/`.

## Runtime target

Observed Codex skill roots on 2026-09-22 include:

- `/home/oliveira/.agents/skills`
- `/home/oliveira/.codex/skills/.system`

Repository-managed user skills are installed into
`/home/oliveira/.agents/skills`. System skills under
`/home/oliveira/.codex/skills/.system` are not modified by this procedure.

## Source Classification

| Source | Purpose | Classification | Codex result |
|---|---|---|---|
| `skills/universal/ai-memory-durable-pages` | ai-memory durable wiki mutation routing | `UNIVERSAL` | Installed by symlink |
| `skills/universal/ai-memory-handoff` | ai-memory handoff routing | `UNIVERSAL` | Installed by symlink |
| `skills/universal/ai-memory-learning-maintenance` | ai-memory maintenance routing | `UNIVERSAL` | Installed by symlink after reconciling the newer runtime-managed instruction into the repository source |
| `skills/universal/ai-memory-messaging` | ai-memory cross-project messaging routing | `UNIVERSAL` | Installed by symlink |
| `skills/universal/ai-memory-retrieval` | ai-memory read-only retrieval routing | `UNIVERSAL` | Installed by symlink after reconciling the newer runtime-managed instruction into the repository source |
| `skills/universal/audit-normalize` | Deterministic audit report normalization | `UNIVERSAL` | Existing correct symlink preserved |
| `skills/universal/omniroute-delegation` | OmniRoute MCP delegation contract | `UNIVERSAL` | Existing correct symlink preserved |
| `skills/universal/project-audit` | Project audit orchestration engine | `UNKNOWN` / not finalized | Not installed |
| `skills/antigravity/model-routing` | Antigravity model-tier routing for subagents | `REQUIRES_ADAPTATION` | Adapted as `skills/codex/model-routing` and installed by symlink |

## Antigravity to Codex Adaptation Matrix

| Antigravity | Intent | Codex equivalent | Result | Evidence |
|---|---|---|---|---|
| `skills/antigravity/model-routing/SKILL.md` | Choose model capacity from task envelope instead of defaulting to the largest model | Codex subagent `model` and `reasoning_effort` selection when delegation/model choice is already authorized | `ADAPTED` as `skills/codex/model-routing/SKILL.md` | Current Codex subagent tooling exposes `model` and `reasoning_effort`; the Codex adaptation states that it does not itself authorize spawning |
| Antigravity `invoke_subagent` API | Stateful subagent invocation | No direct portable API installed from Antigravity | `REMOVED_WITH_REASON` | Codex delegation is controlled by current Codex runtime tools and higher-priority instructions |
| Antigravity tiers `flash_lite`, `flash`, `pro`, `inherit` | Coarse capacity routing | Codex fast/workhorse/frontier profiles with volatile model inventory | `ADAPTED` | `skills/codex/model-routing/references/model-inventory.md` maps the currently visible Codex model set |
| Antigravity `/boost` | Parallel verification/escalation mechanism | Deterministic validation and explicit escalation | `REMOVED_WITH_REASON` | No Codex `/boost` mechanism was established for this runtime |

## Installation Manifest

| Source | Destination | Type | Action | Status |
|---|---|---|---|---|
| `skills/universal/ai-memory-durable-pages` | `/home/oliveira/.agents/skills/ai-memory-durable-pages` | symlink | migrate existing runtime directory | `CORRECT` |
| `skills/universal/ai-memory-handoff` | `/home/oliveira/.agents/skills/ai-memory-handoff` | symlink | migrate existing runtime directory | `CORRECT` |
| `skills/universal/ai-memory-learning-maintenance` | `/home/oliveira/.agents/skills/ai-memory-learning-maintenance` | symlink | reconcile and migrate existing runtime directory | `CORRECT` |
| `skills/universal/ai-memory-messaging` | `/home/oliveira/.agents/skills/ai-memory-messaging` | symlink | migrate existing runtime directory | `CORRECT` |
| `skills/universal/ai-memory-retrieval` | `/home/oliveira/.agents/skills/ai-memory-retrieval` | symlink | reconcile and migrate existing runtime directory | `CORRECT` |
| `skills/universal/ai-memory-routing-install` | `/home/oliveira/.agents/skills/ai-memory-routing-install` | symlink | migrate existing runtime directory | `CORRECT` |
| `skills/universal/audit-normalize` | `/home/oliveira/.agents/skills/audit-normalize` | symlink | preserve existing correct symlink | `CORRECT` |
| `skills/universal/omniroute-delegation` | `/home/oliveira/.agents/skills/omniroute-delegation` | symlink | preserve existing correct symlink | `CORRECT` |
| `skills/codex/model-routing` | `/home/oliveira/.agents/skills/model-routing` | symlink | install Codex adaptation | `CORRECT` |
| `skills/universal/project-audit` | `/home/oliveira/.agents/skills/project-audit` | none | exclude because not finalized | `NOT_APPLICABLE` |

Existing runtime directories replaced by symlinks were preserved at
`/home/oliveira/.agents/skills/.pre-symlink-20260922T000000` because two
runtime directories contained `.bak-*` files and the installation must not
discard local state.

## Validation

Observed on 2026-09-22:

| Target | Evidence | Level |
|---|---|---|
| Universal ai-memory skills | Each `/home/oliveira/.agents/skills/ai-memory-*` entry is a symlink resolving to `/home/oliveira/Projects/SKILLS/skills/universal/<name>` and each linked `SKILL.md` is readable | `SYMLINK_RESOLVES` |
| `audit-normalize` | Existing symlink resolves to `/home/oliveira/Projects/SKILLS/skills/universal/audit-normalize` and `SKILL.md` is readable | `SYMLINK_RESOLVES` |
| `omniroute-delegation` | Existing symlink resolves to `/home/oliveira/Projects/SKILLS/skills/universal/omniroute-delegation` and `SKILL.md` is readable | `SYMLINK_RESOLVES` |
| `model-routing` | Symlink resolves to `/home/oliveira/Projects/SKILLS/skills/codex/model-routing` and `SKILL.md` is readable | `SYMLINK_RESOLVES` |
| `project-audit` | `/home/oliveira/.agents/skills/project-audit` is absent | `NOT_APPLICABLE` |

The structural update property is satisfied because each runtime symlink points
at a stable repository path. A later edit to a canonical skill file in the
repository will be visible through the same symlink without reinstalling it.

Codex skill discovery was validated separately with `codex debug prompt-input`
after installation. The generated prompt input listed the installed user skills
from `/home/oliveira/.agents/skills`, including `model-routing`, and did not
list `project-audit`.

## Known Limitations

The current Codex session already loaded its skill catalog before this
procedure completed, so newly installed skills may require a new Codex session
or registry refresh before they appear in this conversation's available-skills
block.

The `skills/codex/model-routing/references/model-inventory.md` file records the
Codex model options visible in this runtime on 2026-09-22. Treat that reference
as volatile operational data.

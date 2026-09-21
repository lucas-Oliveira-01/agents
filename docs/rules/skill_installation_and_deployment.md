# Skill Installation and Deployment

The skills repository located at `projects/skills` is the canonical development source for agent skills.

## Installation model

Skills must NOT be installed by cloning their repositories into the agent's skill directories.

The installation mechanism is a symbolic link from the agent's skill directory to the corresponding skill directory inside `projects/skills`.

When installing a new skill:

1. Verify whether the skill already exists in `projects/skills`.
2. If it exists, use that local copy as the source.
3. Create a symbolic link from the agent's skill directory to the canonical skill directory in `projects/skills`.
4. Never duplicate or clone the skill into the agent's runtime directory unless explicitly requested.

The expected relationship is:

```text
projects/skills/<skill>
        ↓
    symbolic link
        ↓
<agent>/skills/<skill>
```

## Existing skills

The currently installed skills may be outdated. Migrate existing installations to the canonical skills in `projects/skills` by replacing the old installed copies with symbolic links to the corresponding local skills.

Do not blindly overwrite a skill. Before replacing an existing installation, verify whether it contains local modifications or files that are not present in the canonical repository.

## Development vs runtime

`projects/skills` is the development workspace and may change during skill development.

Agent runtime directories must therefore reference a specific validated skill state rather than being treated as independent copies.

When a skill is being actively modified, avoid exposing partially edited or broken states to production agents.

Prefer the following model when release stability matters:

```text
projects/skills/
    └── development source

validated skill state
    └── immutable/release snapshot

agent runtime
    └── symlink → validated snapshot
```

If the environment does not yet implement release snapshots, use the canonical local skill directory directly, but do not create duplicate copies.

## Future installations

This rule applies to all future skill installations.

Whenever the user asks to "install", "add", "update", "enable", or otherwise make a skill available to an agent, assume the intended mechanism is:

```text
symbolic link → projects/skills/<skill>
```

Do not clone the skill into the agent's directory unless the user explicitly requests a standalone copy.

## Source of truth

`projects/skills` is the source of truth for locally managed skills.

Agent skill directories are deployment/consumption locations, not independent repositories.

Do not create divergent copies of locally managed skills.

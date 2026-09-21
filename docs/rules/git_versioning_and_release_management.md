# Git Versioning and Release Management

The `projects/skills` repository is the canonical source of truth for locally managed agent skills.

Git is the authoritative mechanism for tracking changes, history, provenance, releases, rollback and reproducibility.

## Core principles

### 1. Never modify history to hide mistakes

The Git history must remain an accurate representation of the development process.

Do not rewrite shared history with:

```text
git push --force
git push --force-with-lease
git rebase
git reset --hard
```

when doing so would alter commits already consumed by other agents, collaborators or releases.

History rewriting is acceptable only on private, unpublished branches.

### 2. Every meaningful skill change must be versioned

Changes to any of the following are considered versioned changes:

```text
SKILL.md
SPEC.md
SOURCES.md
references/
scripts/
assets/
evals/
schemas
validators
agent definitions
repository-level rules
```

A change must have a corresponding Git commit.

Do not accumulate unrelated modifications and later commit them as an opaque batch.

## Commit discipline

Commits should represent one coherent change.

A commit should answer:

```text
What changed?
Why was it necessary?
What behavior does it affect?
```

Prefer small, atomic commits over large mixed commits.

Avoid commits such as:

```text
update skills
fix stuff
misc
changes
final
```

Prefer descriptive conventional-style subjects:

```text
feat(skill): add security-audit workflow
fix(skill): correct evidence validation
refactor(skill): simplify routing logic
docs(skill): document execution profile
test(skill): add regression scenarios
chore(repo): update skill tooling
```

Use the scope to identify the affected skill or repository subsystem.

## Change classification

Use these categories consistently:

```text
feat      new capability or behavior
fix       correction of existing behavior
refactor  structural change without intended behavior change
docs      documentation-only change
test      evals, fixtures or validation changes
chore     maintenance/tooling/configuration
perf      performance improvement
security  security-specific hardening
```

Do not use `feat` merely because a file was modified. Classify the semantic effect of the change.

## Branching

The default branch represents the stable repository state.

Development work should occur on short-lived branches when the change is sufficiently large, risky or experimental.

Recommended naming:

```text
feat/<skill>-<description>
fix/<skill>-<description>
refactor/<skill>-<description>
test/<skill>-<description>
chore/<description>
```

Examples:

```text
feat/security-audit-independent-verification
fix/project-context-routing
refactor/skill-scanner-permissions
test/security-audit-regressions
```

Do not create long-lived branches without a concrete maintenance reason.

## Before committing

Before a skill change is considered complete:

```text
1. inspect the diff
2. validate repository structure
3. validate SKILL.md
4. run relevant scripts/validators
5. run relevant evals
6. inspect generated artifacts
7. verify that unrelated files were not changed
8. review the final diff
```

A change that has not been validated must not be presented as a validated release.

The repository's quality system should distinguish development state from validated state.

## Skill-specific change discipline

When modifying a skill, first determine:

```text
What behavior changes?
What existing rule becomes obsolete?
What can be removed?
Why is the new file/reference/script necessary?
```

Avoid adding instructions, references or scripts without a concrete runtime purpose.

`SKILL.md` is runtime behavior and routing.

`SPEC.md` is the maintenance contract.

`SOURCES.md` records provenance, decisions and evidence.

`references/` contains supporting knowledge.

`scripts/` contains deterministic operations.

`evals/` contains quality and regression checks.

Do not move historical reasoning, source analysis or maintenance notes into `SKILL.md` merely because they are relevant to the skill.

## Documentation synchronization

Changes to behavior must be reflected in the appropriate maintenance documentation.

Examples:

```text
behavior change       → SKILL.md
architecture change   → SPEC.md
source/provenance     → SOURCES.md
new regression        → evals/
new deterministic op  → scripts/
```

Do not duplicate the same rule across several files when a single canonical location is sufficient.

## Versioning

Use Git commit identity as the immutable source identity of a skill state.

A validated release should be traceable to:

```text
repository
commit SHA
skill version
validation state
```

Prefer release identifiers that can be mapped directly to a Git commit.

Example:

```text
skill: security-audit
version: 1.4.0
commit: a83f91d5
status: validated
```

Semantic versioning may be used for externally meaningful skill versions:

```text
MAJOR.MINOR.PATCH
```

Interpretation:

```text
MAJOR
    incompatible workflow, contract or behavior changes

MINOR
    backward-compatible capability or behavior additions

PATCH
    backward-compatible corrections and maintenance changes
```

A version change must correspond to an actual semantic change. Do not increment versions merely because a commit exists.

## Tags and releases

Stable releases should be represented by Git tags.

Use annotated tags for release points:

```text
v1.0.0
v1.1.0
v1.1.1
```

A release tag must identify a commit that has already passed the required validation.

Do not tag an unvalidated working state.

The release process is:

```text
development
    ↓
commit
    ↓
validation
    ↓
release candidate
    ↓
evaluation
    ↓
Git tag
    ↓
validated release
```

## Runtime deployment

The development working tree is not automatically a production release.

Agent runtime locations must consume a validated state.

Preferred architecture:

```text
projects/skills/
    development working tree
            │
            ▼
       validation
            │
            ▼
   immutable release snapshot
            │
            ▼
    symbolic link from agent
```

This prevents an unfinished edit from immediately changing production agent behavior.

The deployment pointer may be represented by a symbolic link such as:

```text
prod -> releases/a83f91d5
```

The target release must not be modified after promotion.

## Promotion

Promotion must be explicit.

A validated release should be promoted only after:

```text
Git state is clean
required validation passes
required evals pass
release identity is recorded
runtime installation is verified
```

Changing the runtime pointer must not modify the release itself.

Promotion should be an atomic pointer operation whenever possible.

## Rollback

Rollback must never require reconstructing files manually.

Previous validated releases must remain available so that runtime can switch back to a known-good commit.

Example:

```text
prod -> releases/a83f91d5
previous -> releases/41ab92e0
```

Rollback consists of repointing the runtime symlink to a previously validated release.

Do not "fix" a broken release directly inside its deployed directory.

Create a new commit and a new validated release instead.

## Reproducibility

Every deployed skill state must be reproducible from Git.

Given:

```text
repository
+
commit SHA
```

it must be possible to reconstruct the exact source state used by the release.

Avoid depending on:

```text
uncommitted local files
local-only patches
manual edits
unknown generated files
mutable external directories
```

unless their provenance is explicitly documented.

## Git state checks

Before release or deployment, verify:

```text
git status
git diff
git diff --cached
git rev-parse HEAD
```

The release source must correspond exactly to the intended commit.

Uncommitted modifications must never silently enter a release.

## Regression awareness

A change that fixes one behavior can break another.

Therefore, changes to skills should be evaluated against:

```text
existing evals
affected workflows
routing behavior
references
scripts
schemas
runtime contracts
```

When a regression is discovered, add or improve an evaluation that would detect it in the future.

The goal is not merely:

```text
"the current version works"
```

but:

```text
"future modifications are less likely to silently break this behavior"
```

## Installation rule

Installing a skill means making a validated skill state available to an agent through a symbolic link.

Do not clone independent copies of locally managed skills into agent directories.

The canonical relationship is:

```text
Git repository
    ↓
validated release
    ↓
symbolic link
    ↓
agent runtime
```

This preserves a single source of truth while allowing runtime versions to remain isolated from ongoing development.

## Historical traceability

Never delete or overwrite the historical identity of a release merely because a newer version exists.

A release should remain traceable through:

```text
version
commit
tag
validation result
deployment state
```

This makes it possible to answer:

```text
Which version is deployed?
Which commit produced it?
What changed between releases?
Which release was deployed previously?
Can the previous state be restored?
```

## Rule of thumb

Treat skill development like software development:

```text
edit
  ↓
inspect diff
  ↓
validate
  ↓
commit
  ↓
evaluate
  ↓
tag/release
  ↓
promote
  ↓
deploy through symlink
```

A skill is not considered a release merely because its files exist in `projects/skills`.

A release is a **validated, identifiable and reproducible Git state**.

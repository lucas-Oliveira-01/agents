# Skill Namespacing and Platform Grouping

**Rule:** Agent skills must be explicitly namespaced by their target execution platform to prevent cross-agent execution failures.

## Context
As the `SKILLS` repository scales, it will contain skills designed for various different agentic platforms (e.g., Google Antigravity, Cursor, Claude Code, custom CLI tools). Some skills rely on platform-specific native tools (such as Antigravity's `invoke_subagent`, `ai-memory`, or `omniroute`). A generic agent attempting to run a platform-specific skill will crash or fail silently.

## Enforcement
1. **Directory Structure:** All skills inside the `skills/` directory MUST be placed in a platform namespace subdirectory.
   - `skills/antigravity/`: Skills requiring Antigravity native tools (e.g., `model-routing`).
   - `skills/cursor/`: Skills specific to Cursor's agent.
   - `skills/universal/`: Skills that only use standard bash commands or pure LLM reasoning, usable by any capable agent.

2. **Symlinking:** When deploying a skill locally (e.g., via `~/.gemini/config/skills/`), the symlink must point to the namespaced path (e.g., `/home/oliveira/Projects/SKILLS/skills/antigravity/model-routing`).

#!/bin/bash
# Script to symlink centralized agent configurations and skills to a local environment.
# Features "snapshot" mode to guarantee other agents don't break when we edit files.

REPO_ROOT=$(pwd)

function usage() {
    echo "Usage: $0 --target <agent_config_dir> [--snapshot <git_tag_or_commit>]"
    echo "Example: $0 --target ~/.gemini/config --snapshot v1.0.0"
    exit 1
}

TARGET_DIR=""
SNAPSHOT=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --target) TARGET_DIR="$2"; shift ;;
        --snapshot) SNAPSHOT="$2"; shift ;;
        *) usage ;;
    esac
    shift
done

if [ -z "$TARGET_DIR" ]; then
    usage
fi

SOURCE_DIR="$REPO_ROOT"

if [ -n "$SNAPSHOT" ]; then
    echo "Snapshot mode enabled. Resolving snapshot $SNAPSHOT..."
    SNAPSHOT_DIR="$REPO_ROOT/.snapshots/$SNAPSHOT"
    
    if [ ! -d "$SNAPSHOT_DIR" ]; then
        echo "Creating immutable snapshot at $SNAPSHOT_DIR"
        mkdir -p "$SNAPSHOT_DIR"
        git --git-dir="$REPO_ROOT/.git" --work-tree="$SNAPSHOT_DIR" checkout "$SNAPSHOT" -- .
    fi
    SOURCE_DIR="$SNAPSHOT_DIR"
    echo "Using source directory: $SOURCE_DIR (Isolated from active development)"
else
    echo "Live mode enabled. Using active working tree: $SOURCE_DIR (Warning: active edits will propagate to this agent)"
fi

echo "Setting up agent configuration symlinks in: $TARGET_DIR"

mkdir -p "$TARGET_DIR/rules"
mkdir -p "$TARGET_DIR/skills"
mkdir -p "$TARGET_DIR/mcp"
mkdir -p "$TARGET_DIR/hooks"

# 2. Symlink Universal Rules
for rule in "$SOURCE_DIR/configs/universal/rules/"*.md; do
    [ -e "$rule" ] || continue
    ln -sf "$rule" "$TARGET_DIR/rules/$(basename "$rule")"
done

# 3. Symlink Antigravity-Specific Rules
for rule in "$SOURCE_DIR/configs/antigravity/rules/"*.md; do
    [ -e "$rule" ] || continue
    ln -sf "$rule" "$TARGET_DIR/rules/$(basename "$rule")"
done

# 4. Handle Infrastructure Configs (Templates)
if [ ! -f "$TARGET_DIR/hooks.json" ] && [ -f "$SOURCE_DIR/configs/antigravity/hooks/hooks.example.json" ]; then
    cp "$SOURCE_DIR/configs/antigravity/hooks/hooks.example.json" "$TARGET_DIR/hooks.json"
    echo "Copied hooks.example.json -> hooks.json (Requires manual configuration)"
fi

if [ ! -f "$TARGET_DIR/mcp_config.json" ] && [ -f "$SOURCE_DIR/configs/antigravity/mcp/mcp_config.example.json" ]; then
    cp "$SOURCE_DIR/configs/antigravity/mcp/mcp_config.example.json" "$TARGET_DIR/mcp_config.json"
    echo "Copied mcp_config.example.json -> mcp_config.json (Requires secret injection)"
fi

# 5. Symlink Skills
for skill_dir in "$SOURCE_DIR/skills/universal/"*; do
    if [ -d "$skill_dir" ]; then
        ln -sf "$skill_dir" "$TARGET_DIR/skills/$(basename "$skill_dir")"
    fi
done

for skill_dir in "$SOURCE_DIR/skills/antigravity/"*; do
    if [ -d "$skill_dir" ]; then
        ln -sf "$skill_dir" "$TARGET_DIR/skills/$(basename "$skill_dir")"
    fi
done

echo "Agent configuration setup complete in $TARGET_DIR!"

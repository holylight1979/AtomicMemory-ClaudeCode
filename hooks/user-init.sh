#!/bin/bash
# user-init.sh — SessionStart hook
# Generates USER.md and IDENTITY.md from template + per-user overrides.

CLAUDE_DIR="$HOME/.claude"
USERNAME="$(whoami | sed 's/.*\\/\//; s/.*\\\\//')"

# === USER.md ===
USER_FILE="$CLAUDE_DIR/USER-${USERNAME}.md"
USER_TEMPLATE="$CLAUDE_DIR/templates/USER.template.md"
USER_TARGET="$CLAUDE_DIR/USER.md"

if [ ! -f "$USER_FILE" ] && [ -f "$USER_TEMPLATE" ]; then
  cp "$USER_TEMPLATE" "$USER_FILE"
fi
if [ -f "$USER_FILE" ]; then
  cp "$USER_FILE" "$USER_TARGET"
fi

# === IDENTITY.md ===
# IDENTITY.md 為直接維護的單一真相（行為契約必載檔）；IDENTITY-{user}.md 是選配的
# 個人擴充槽（啟用時由 CLAUDE.md @import，本腳本不經手）。
# 這裡只做災難復原：IDENTITY.md 不存在時從 template 還原（與 SessionStart 完整性哨兵互補）。
ID_TEMPLATE="$CLAUDE_DIR/templates/IDENTITY.template.md"
ID_TARGET="$CLAUDE_DIR/IDENTITY.md"

if [ ! -f "$ID_TARGET" ] && [ -f "$ID_TEMPLATE" ]; then
  cp "$ID_TEMPLATE" "$ID_TARGET"
fi

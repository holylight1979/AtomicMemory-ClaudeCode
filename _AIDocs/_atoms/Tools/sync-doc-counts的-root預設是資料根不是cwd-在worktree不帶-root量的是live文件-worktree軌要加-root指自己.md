# sync-doc-counts的--root預設是資料根不是cwd-在worktree不帶--root量的是live文件-worktree軌要加--root指自己

- Scope: global
- Author: holylight
- Source: track-tech-refresh 001 代寫 2026-10-22
- Confidence: [臨]
- Trigger: sync_doc_counts, DOC_COUNTS_CHECK, --root, worktree 文件計數
- Created-at: 2026-10-22

## 知識

- [臨] tools/sync_doc_counts.py --check 的 --root 預設是資料根（WG_CLAUDE_DIR 沒設＝live ~/.claude），不是 cwd；在 worktree 裡不帶 --root 量到的是 live 的 TECH，worktree 軌要加 `--root <worktree>`。

## 行動

- （依知識內容判斷）

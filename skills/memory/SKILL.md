---
name: memory
description: 原子記憶系統綜合工具 — health/peek/undo/review/score 五合一。用於檢查記憶健康、檢視自動萃取、撤銷誤寫、自我迭代、Session 評分。
---

# /memory — 記憶系統綜合工具

> V5 P1：合併原 `/memory-health`、`/memory-peek`、`/memory-undo`、`/memory-review`、`/memory-session-score` 五個 commands 為單一 skill。
> 全域 Skill，適用任何專案。

---

## 使用方式

```
/memory health [--json]
/memory peek [--since=24h]
/memory undo [last | --since=24h | --all-from-today]
/memory review
/memory score [--last | --since=24h | --top-n=10]
```

第一個 token 為 subcommand。從 `$ARGUMENTS` 解析。
若無 subcommand → 預設 `health`。

---

## Subcommand 分派

### health → 記憶品質診斷

合併執行 `tools/memory-audit.py` + `tools/atom-health-check.py`：

1. **偵測專案記憶目錄**（Bash）：
   ```bash
   python -c "
   import sys, os
   sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
   try:
       from wg_core import get_project_memory_dir
       d = get_project_memory_dir(os.getcwd())
       print(d or '')
   except Exception:
       print('')
   "
   ```
   非空 → 記為 `$PROJECT_MEM_DIR`，後續工具加 `--project-dir`。

2. **memory-audit**（並行 2 個工具）：
   ```bash
   python ~/.claude/tools/memory-audit.py [--project-dir $PROJECT_MEM_DIR] [--json]
   ```

3. **atom-health-check**（並行 2 個工具）：
   ```bash
   python ~/.claude/tools/atom-health-check.py --report [--json] [--memory-root $PROJECT_MEM_DIR]
   # 若有專案層，再跑全域層
   python ~/.claude/tools/atom-health-check.py --report [--json]
   ```

4. **綜合報告**：格式驗證 / 過期 / 參照完整性 / 晉升降級 / 重複偵測 / 索引一致性，每個區塊有問題列出、無問題 ✓。末尾總結 N 個問題 / 全健康。

5. **互動**：發現問題詢問是否修正。**禁止手動 mv atom 跨層** — 用 `atom-move.py move` 或 MCP `atom_move`。

### peek → V4.1 自動萃取檢視

```bash
python ~/.claude/tools/memory-peek.py $ARGS
```

`$ARGS` 為 `--since=...` 等使用者傳入參數。列最近 24h（或自訂時段）自動萃取的 atom + pending candidates + trigger 原因。

### undo → V4.1 撤銷自動萃取

```bash
python ~/.claude/tools/memory-undo.py $ARGS
```

支援 `last` / `--since=24h` / `--all-from-today`。撤銷 `auto-extracted-v4.1` 寫入的 atom，搬到 `_rejected/` 並記錄原因。

### review → 自我迭代檢閱

手動觸發記憶系統自我迭代：衰減掃描、晉升候選、震盪偵測、覆轍偵測、episodic 回顧。

1. 偵測專案記憶目錄（同 health Step 1）。
2. 跑 `python ~/.claude/tools/memory-audit.py --self-iterate [--project-dir $PROJECT_MEM_DIR]`（若工具支援；否則改跑 health 全套）。
3. 列出晉升候選 / 衰減候選 / 震盪 atom / 覆轍模式。

### score → Session 評分檢視

```bash
python ~/.claude/tools/memory-session-score.py $ARGS
```

支援 `--last` / `--since=24h` / `--top-n=10`。列出最近 session 的 5 維度評分：density / precision / novelty / cost / trust → weighted_total。

---

## 預設行為

`$ARGUMENTS` 為空時：
- 列出 5 個 subcommand 摘要
- 詢問使用者要跑哪個（推薦 `health`）

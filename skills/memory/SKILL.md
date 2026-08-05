---
name: memory
description: 原子記憶系統綜合工具 — health/review/score 三主力 + peek/undo（僅查自動萃取歷史殘留）。用於檢查記憶健康、自我迭代、Session 評分。
---

# /memory — 記憶系統綜合工具

> 單一 skill 統整 health / peek / undo / review / score 五個 subcommand
> （peek/undo 僅查自動萃取歷史殘留）。全域 Skill，適用任何專案。

---

## 使用方式

```
/memory health [--json]
/memory peek [--since=24h]        # 僅查歷史殘留（自動萃取管線已裁撤）
/memory undo [last | --since=24h | --all-from-today]   # 同上
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

4. **效果報表**（結構面之外的效果面——注入的記憶有沒有被用上）：
   ```bash
   python ~/.claude/tools/memory-effect-report.py
   ```
   三清單直接轉述：A top 有用（α/β Wilson 下界 + rescue 命中）、B 高曝光零使用
   （token 稅，附 trigger 收斂建議）、C 零曝光死重候選；末尾 30 天週趨勢表。
   B/C 有項目時點出，但**不自動改 trigger / 不自動刪 atom**（裁決權在使用者）。

5. **綜合報告**：格式驗證 / 過期 / 參照完整性 / 晉升降級 / 重複偵測 / 索引一致性，每個區塊有問題列出、無問題 ✓。末尾總結 N 個問題 / 全健康。

6. **互動**：發現問題詢問是否修正。**禁止手動 mv atom 跨層** — 用 `atom-move.py move` 或 MCP `atom_move`。

7. **broken_refs → OFFER L2 自癒（純手動觸發，零每-session 常駐成本）**：
   報告出現 **Broken References（死連結）** 時，**詢問**使用者是否跑 L2 LLM 修復（絕不自動跑；Native-first：不長常駐枝葉）。
   同意 → 對報告中每個含死連結的 atom（`broken_refs[].atom` 去重），逐個 CLI 直呼：
   ```bash
   python ~/.claude/tools/atom-heal.py --atom <name> --apply --backend ollama --json
   ```
   CLI 直呼為**預設路徑**：headless、無伺服器依賴、不受 :3848 孤兒舊碼影響。逐個判讀 JSON：
   - `fixed:true` → 已修好（repoint 錯字 / remove 無效連結），回報改了什麼。
   - `needs_human:true` → 自動修不好，`atom-heal.py` 已落診斷卡 `memory/_heal_review/<atom>.json` → 提示使用者走 `/heal-review` 人工裁決。

   **可選快路徑**（僅當 dashboard :3848 已開且確認跑新碼）：`POST http://127.0.0.1:3848/api/heal-all` 一次背景批修全部 broken_refs（走 server `healRunner` 併發、回 202 `{started,count,pending}`）。⚠️ live :3848 可能是**孤兒舊碼**（`/api/heal-all` 路由非新增、舊碼不會 404 而是靜默跑舊行為）→ 用前先確認新碼上線（見 atom [[guardian-dashboard-孤兒佔埠與新碼重啟]]）；不確定就用上面 CLI。

   L1 反向連結**不在此處理** — SessionEnd `atom-health-check --fix-refs` 已全庫機械補齊，此處只治 L2 死連結，別重覆跑。

### peek → 自動萃取檢視（僅歷史殘留）

> ⚠️ auto-capture 自動萃取管線已裁撤（`per_turn` 與 `session_end_flush` 停用；
> 裁決見 atom [[自動萃取層淨值審查-調整式拔除-2026-07]]），不再產生新草稿。
> 回報 `{"written":0,"pending":0}` 為預期現況、非故障。本命令僅供查詢舊殘留。

```bash
python ~/.claude/tools/memory-peek.py $ARGS
```

`$ARGS` 為 `--since=...` 等使用者傳入參數。列指定時段內自動萃取的 atom + pending candidates + trigger 原因（現況只有歷史殘留會出現）。

### undo → 撤銷自動萃取（僅歷史殘留）

> ⚠️ 同 peek：管線已裁撤，無新寫入可撤。`memory-undo.py` 對舊殘留仍可運作。

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

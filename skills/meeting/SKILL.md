---
name: meeting
description: 會議錄音整理：音檔 → 逐字稿 → 決議／待辦／未決三段摘要 → 決議寫進專案記憶（shared）。使用者說「整理這場會議」「會議錄音」「轉錄」「做會議摘要」時用。
user-invocable: true
triggers: 整理這場會議, 會議錄音, 會議摘要, 轉錄, 逐字稿, 會議記錄, meeting
pattern: tool-wrapper
---

# /meeting — 會議錄音整理

> 後端 `~/.claude/tools/meeting-transcribe.py`：ffmpeg 轉檔與靜音切段 → Ollama 音訊模型逐字稿
> → 同一組 backend 的文字模型做摘要 → 每條決議一顆 `[臨]` atom。參數以 `--help` 為準；
> 機制與限制見 `~/.claude/TECH.md` §6.6。

## 使用方式

```
/meeting <音檔>                         # 專案根＝目前 cwd 所屬專案；標題＝檔名、日期＝檔案修改日
/meeting <音檔> 標題 專案週會 日期 2026-10-06
/meeting <音檔> 人名 小明,阿華 術語 HybridCLR,OAuth   # 提高辨識準確度
/meeting check                          # 只檢查 ffmpeg 與音訊 backend
```

## 意圖 → 動作

| 使用者說 | 做什麼 |
|---|---|
| 整理這場會議 `<檔>`／幫我轉錄 | `python ~/.claude/tools/meeting-transcribe.py <檔> --project <專案根> [--title] [--date] [--glossary a,b] --json` |
| 只要逐字稿／先不要寫進記憶 | 同上加 `--no-ingest` |
| 先看會寫哪些 atom | 同上加 `--dry-run` |
| 能不能跑／為什麼失敗 | `python ~/.claude/tools/meeting-transcribe.py --check` |

- **專案根**：`--project` 給「含 `.claude/` 的專案根」。cwd 在某專案內就用該專案根；cwd 是 `~/.claude` 或找不到 → 問使用者「這場會議屬於哪個專案（路徑）」，只問這一件。
- **人名術語**：使用者提到會議裡會出現的人名、產品名、技術詞，一律放 `--glossary`（逗號分隔），辨識與摘要都會用它校正同音錯字。
- 音檔格式不限（m4a／mp3／wav／mp4…），路徑有空白要加引號。

## 完成判定與回報

- exit 0 且 stdout 是 JSON：回報三段——**決議**（每條附 atom 落點：寫入 `shared/<範疇>/`、待審 `shared/_pending_review/`、或失敗原因）、**待辦**（負責人、期限）、**未決問題**；最後一行給逐字稿與摘要檔路徑（`<專案>/.claude/memory/_staging/meetings/<日期-標題>/`）。
- 待審的決議：告訴使用者「分不出範疇，放在待審區；說『審待審』或 `/conflict pending` 核可」。
- exit 1：把 stderr 的 `[meeting] 失敗：…` 原樣回報。常見：沒有 backend 能跑音訊模型（要在有顯卡的 Ollama 主機 `ollama pull gemma4:e4b`）、找不到 ffmpeg（`winget install Gyan.FFmpeg`）、音檔路徑錯。不繞道、不改用別的辨識方式。
- 辨識結果有明顯錯字（人名、術語）：建議使用者補 `--glossary` 重跑，不要手改逐字稿。

## 鐵則

1. 逐字稿只放 `_staging/`（不進索引、不注入、不進版控）；atom 只寫決議，逐字稿路徑記在 atom 的 Source 行。
2. 不自動 commit；專案記憶層由背景 vcs-sync 同步。
3. 音檔不離開內網：只打 `workflow/config.json` 登記的 Ollama backend。

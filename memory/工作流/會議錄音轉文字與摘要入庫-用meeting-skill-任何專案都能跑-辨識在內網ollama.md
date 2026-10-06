# 會議錄音轉文字與摘要入庫-用meeting-skill-任何專案都能跑-辨識在內網ollama

- Scope: global
- Author: holylight
- Source: tools/meeting-transcribe.py；TECH.md §6.6；使用者 2026-10-06 指定觸發詞
- Confidence: [臨]
- Trigger: 會議, 會議錄音, 會議音檔, 錄音轉文字, 語音轉文字, 逐字稿, 會議摘要, 會議記錄, 整理這場會議, meeting, transcribe, /meeting
- Created-at: 2026-10-06
- Depends: path:C:/Users/holylight/.claude/tools/meeting-transcribe.py, path:C:/Users/holylight/.claude/skills/meeting/SKILL.md
- Related: ollama-gemma4-e4b-音訊輸入走images欄位-單次可吃5分鐘-會議轉錄實測
- Quote: 「atoms 起來.. 索引應該要有 會議、錄音轉文字、會議錄音、會議音檔 這些.. 吧?? 另外我也想知道在專案層也能進行嗎? 能不能做成全域都能使用的 skill ??」

## 知識

- [臨] 會議錄音整理走 `/meeting`（根層 skill，所有專案都能用）：對 Claude 說「整理這場會議 <音檔> 人名 小明,阿華」→ 跑 `python ~/.claude/tools/meeting-transcribe.py <音檔> --project <專案根> --glossary … --json`。音檔 m4a／mp3／wav／mp4 皆可；辨識在內網 Ollama（gemma4:e4b audio，現況 192.168.199.130），音檔不出門，本機不需顯卡。
- [臨] 產出：`<專案>/.claude/memory/_staging/meetings/<日期-標題>/transcript.md`（含時間戳）與 `summary.md`（決議／待辦／未決三段）；每條決議一顆 [臨] atom 進該專案 `shared/<範疇>/`，分不出範疇進 `shared/_pending_review/`（`/conflict pending` 核可）。逐字稿不進 atom、不進版控。
- [臨] 常用旗標：`--check`（先驗 ffmpeg 與音訊 backend）、`--dry-run`（atom 只預覽）、`--no-ingest`（只要逐字稿與摘要）。同音錯字靠 `--glossary` 人名術語清單校正。機制見 TECH.md §6.6；Ollama 音訊 API 細節見 local atom [[ollama-gemma4-e4b-音訊輸入走images欄位-單次可吃5分鐘-會議轉錄實測]]。

## 行動

- 使用者提到會議錄音／錄音轉文字／會議摘要 → 直接用 /meeting，不要另寫轉錄流程
- cwd 不在專案內時只問一件事：這場會議屬於哪個專案根

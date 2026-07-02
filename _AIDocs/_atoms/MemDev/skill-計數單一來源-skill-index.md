# skill-計數單一來源-skill-index

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: skill 計數, skill count, skill-index, _skill_index.json, skill-count marker, 出文件 skill 數, 增刪 skill, skill 漂移, skill drift
- Created-at: 2026-06-18
- Related: realm-範疇分區機制-v5, feedback-memory-system-doc-sync, windows-python-write-text-缺-newline-把-lf-翻-crlf-整檔假-diff

## 知識

- [臨] skill 計數單一真相（SoT）= `skills/*/SKILL.md` 檔案系統（Claude Code 自動發現 skill 的來源）。工具 `tools/skill-index.py` 掛它 → 產機器鏡像 `skills/_skill_index.json`（count + name/desc 清單，勿手改）+ 重寫人讀文件中的 `<!-- skill-count -->N<!-- /skill-count -->` marker。鎏 `_atom_index.json` + `sync-memory-index.py` 既有慈例。
- [臨] 模式：`--check`（json count 或任一 doc marker ≠ 實檔數 → stderr 列差異、exit 1）/ `--write`（重生 json + 重寫所有 marker，冪等）/ dry-run（預設）。
- [臨] 防 drift 串接（「增刪調 skill / 出文件都同步」）：① PostToolUse hook 偵測 Edit/Write 到 `skills/*/SKILL.md` → detached 自動跑 `--write`（`handlers/post_tool_use.py._maybe_sync_skill_index`，鎏 changelog auto-roll）；② SessionStart 跑輕量 --check（實檔 `skills/*/SKILL.md` 數 ≠ `_skill_index.json` count → advisory，抓 Bash 刪除等 hook 漏接）；③ config `skill_index.enabled=false` 一鍵關。
- [臨] MARKED_DOCS = TECH.md / Install-forAI.md / _AIDocs/Architecture.md / _AIDocs/_INDEX.md（marker 只包純數字；「19 遷移…」「含外部 karpathy」等策展文字人工維護、工具不動）。新增散落計數位置 → 加進 MARKED_DOCS + 插 marker。SPEC_ATOM_V5 §4.2 為遷移歷史快照、不挂 marker（加了指標轉 SoT）。
- [臨] 緣起：2026-06-18 doc-sync 發現 skill 計數跨檔不一致（Install-forAI 內 22 vs 23、changelog 史載 24）。實數 = 23（22 記憶系統 skill + 1 外部 karpathy-guidelines；unity-mcp 已搬專案層不計）。verify：`tools/verify/verify_skill_index.py`（含「真庫無 drift」防 commit 進 drift）。

## 行動

- 增刪改 skill → PostToolUse 自動同步；手動可跑 `python tools/skill-index.py --write`
- 出文件要寫 skill 數 → 用 `<!-- skill-count -->N<!-- /skill-count -->` marker、勿硬編；新位置加進 MARKED_DOCS
- 看到 [Guardian:SkillIndex] advisory → 跑 --write 同步
- 判 skill drift 先信 `_skill_index.json`/實檔，非文件硬編數

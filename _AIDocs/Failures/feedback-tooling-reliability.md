# feedback-tooling-reliability

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: codex, codex companion, codex CLI, gpt-5, bg subprocess, DEVNULL, ready flag, subprocess Popen, MCP, 安裝 MCP, 安裝 skill, silent failure, probe burst, 規則唯一來源
- Created-at: 2026-05-26
- Related: feedback-completion-gates, feedback-memory-structure, feedback-workflow-discipline, atom-table-support, cc-能力查證反編譯實跑-binary, codex-log-bloat-analytics

## 知識

- [臨] MCP / skill 全域裝到 ~/.claude/，避專案層重複
- [臨] bg subprocess stderr 必導檔（不 DEVNULL），ready flag 自寫；code review 見 DEVNULL 退件
- [臨] codex brief 5 要件：背景 / 問題 / 期望輸出 / 限制 / 驗證；三紅線禁贅字
- [臨] codex_companion.model 忝空，CLI 預設專手控版本
- [臨] silent-failure 調查前先 log 採樣 + probe burst (3 位點)，避推測
- [臨] 規則 / 驗證集中到唯一模組（如 lib/atom_spec.py），caller 端禁 patch 豁免
- [臨] **atom_write 兩個防護缺口（2026-06-01 稽核 client_il/client-il 重複案發現並修復）**：① `mode=replace` 是無閘 silent upsert——目標檔不存在照樣寫（existsSync 只用於保留舊 metadata），繞過 create 的 [臨] 閘，一次呼叫就生出 [固] 新 atom。② 無「分隔符正規化碰撞」偵測——slugify 把 `_→-`（CJK 保留），所以 legacy 底線檔（如 client_il.md）對 append/replace/flatLegacyFallback 全部路徑不可達；append 報 not found → 提示『use create』→ 反而 fork 出近似重複檔。兩者疊加：`replace title=client_il [固]` → slug 變 client-il → 生出分歧的 [固] 片段 stray，且可能落錯 scope。
- [臨] **修復**：server.js 新增 `findSeparatorVariant(memDir, slug)`；create 命中變體即擋（提示改 append/replace 或先改名）；replace 目標不存在即拒寫並導向 create。改全域 MCP server 需重啟生效。**教訓**：atom 檔名必須遵 hyphen slug 規範，底線命名 atom 是 non-conforming、工具天生碰不到 → 應正規化為 hyphen，而非讓工具長期特例兼容。關聯 [[workflow-rules]]、[[feedback-atom-write-initial-confidence]]。
- [臨] **atom_write 第三缺口「reformat blast radius」（2026-06-01 修復）**：append 2 行卻整檔 48 行 diff。根因不在 buildAtomContent（產純 LF、無辜），而在 funnel `lib/atom_io.py:_atomic_write` 用 `Path.write_text(newline=None)`——Windows 把每個 \n 翻成 os.linesep；server.js append 用 Node `fs.readFileSync` 原樣讀既有 CRLF 再拼 \n → 混合 EOL → 既有 \r\n 被二次翻成 \r\r\n（double-CR），整檔行尾全變 → git 視為全行更動。修：`_atomic_write` 先正規化純 LF → `_detect_eol` 偵測既有檔行尾原樣套回 → `open(newline='')` 關平台轉譯；既有 CRLF byte-stable、僅新增行進 diff。Python 端改、下次 CLI 呼叫即生效（免重啟 MCP）。未動 atom_index_json.py 兩處 write_text（Windows os.linesep=CRLF 符 repo、不 blast；跨平台 EOL 為 pre-existing 待辦）。關聯 [[feedback-memory-system-doc-sync]]。

## 行動

- MCP/skill 全域裝
- bg stderr 導檔 + ready flag
- codex brief 5 要件
- silent-failure 先錄 probe burst
- 規則唯一來源集中

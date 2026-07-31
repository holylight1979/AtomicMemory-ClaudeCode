# Session Coordination Bus — 多大師計畫紀錄（2026-07-31）

> 需求原話：「多開 session 併行執行同一核心…彼此之間有沒有什麼樣的溝通管道…避開衝突、甚至是透過溝通來達成分工合作？如果沒有，可不可以增加？」
> 流程：官方現況調查 → 5 大師計劃（CC 架構師/考古 + Codex 極簡/保守/激進，gpt-5.6-sol）→ CC 雙預測 → 使用者裁決方案 A → dry-run + CC/Codex 雙稽核 → probe → 實作 → 1170 tests + e2e smoke + Codex 紅隊。

## 官方現況（CC 2.1.219/220，2026-07 查證）
無原生跨 session 管道。SendMessage 限本 session/同 team；Agent Teams 實驗性（單 team 信箱 `~/.claude/teams/`）；hooks 全 session 內；worktree 策略=隔離非協調；同檔互寫零偵測。Open FR：#37213/#36181/#33788。

## 七席關鍵發現與仲裁
- **全席共識**：協調資料不進 `state-*.json`（Node writeState 無鎖吞錯 + Python `_shared._cleanup_old_states` / Node `listAllSessions`（讀取即刪）/ DELETE API 三條 GC 互不相認 → last-writer-wins + 資料必被吃）；warn-only；訊息=不可信 peer 輸入。
- **仲裁改道**：原「擴充 3848 daemon 三階段」→ 純檔案方案（查詢直讀 state、零新 HTTP API）。理由：PreToolUse 熱路徑不打 HTTP（交棒 15s 空窗）；daemon CORS `Access-Control-Allow-Origin: *` 未解前不加 mutation API（激進/保守獨到發現）。
- **Codex 獨到（已親驗）**：MCP transport 拿不到呼叫者 session_id（模型自報可偽造）→ 發訊須仿 `anti_evasion_report` one-writer（MCP chip → PostToolUse 蓋章）。
- **效益席打臉**：真痛點 `git add -A`/`reset --hard` 走 Bash，原 Write|Edit matcher 攔不到 → 補 Bash git 收尾預警（本計畫價值最高的一刀）。
- **CC 稽核救命**：advisory 帶 `permissionDecision:"allow"` = 自動核准繞過權限系統——警告危險指令的同時替使用者按允許。裸 additionalContext 定案。
- **Probe 實測（headless 2.1.220）**：PreToolUse additionalContext 有效且模型可見，但 `WHEN=after-write`——隨工具結果進下一輪，非寫前攔截（寫前僅 deny/ask）。語意如實降級為「寫入當下告知、據以停手協調」。

## 落地（Stage 0+1，方案 A）
`hooks/wg_coordination.py`（衝突掃描/Bash 偵測/warn-cache/per-session NDJSON log）+ `pre_tool_use.py`（warn 接點、deny 優先）+ `post_tool_use.py`（write_state 後 60s late-collision）+ `_shared.py`（cache 7d / log 30d GC）+ config `coordination.*`。settings.json/daemon 零改動。verify 16 測項（含 warn/deny 互斥矩陣、60s 窗邊界、Bash 誤報反例）；e2e smoke 延遲 5.5ms。

## Defer（重啟條件）
Stage 2 收件匣（每週預估 0-2 次使用；設計已完備：MCP `session_message` chip → one-writer → `workflow/coord/messages/<sid>/<msg>.pending.json` → UPS 注入 ≤2 則/turn 獨立 cap → TTL tombstone）與 Phase 3 認領制。重啟條件：observation log 顯示 P1 警告後仍互踩頻發、或 first-write 衝突常態化。日落：log 連續 4 週零命中 → 提降級（2026-08-28 後檢視）。
daemon CORS wildcard 債另記：未加 auth 前不得對 3848 加任何 mutation API。

## 七席報告原始檔
計畫工作檔（briefing/outputs transcripts）已依協議於收尾清除；本檔為濃縮存證。

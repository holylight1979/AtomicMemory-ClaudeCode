# 跨session協調-衝突預警機制與CC原生現況

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 跨 session 溝通, session 協調, 衝突預警, CoordWarn, wg_coordination, session_message, 收件匣, coordination, 多 session 併行, session 互踩, add -A 預警, late-collision, Agent Teams
- Status: Stage 0+1 已上線；Stage 2/3 defer 待數據
- Created-at: 2026-07-31
- Related: 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, 跨session資訊失真機制與對策, guardian-dashboard-孤兒佔埠與新碼重啟, guardian-警告訊息辨識度-emoji-前綴分流

## 知識

- [臨] CC 原生（2.1.220）**無跨 session 溝通管道**：SendMessage 只達本 session subagent/同 team；Agent Teams 實驗性（env CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1）僅限單 team 內；hooks 全 session 內事件。相關 open feature request：anthropics/claude-code #37213/#36181/#33788
- [臨] **PreToolUse hook 輸出語意**（官方文檔+headless probe 2.1.220 實測）：hookSpecificOutput 支援裸 additionalContext（模型可見）但送達時點=隨工具結果進下一輪（after-write，**非寫前**；寫前生效僅 deny/ask）；頂層 systemMessage=使用者可見；`permissionDecision:"allow"` 會自動核准繞過權限系統——advisory 絕不可帶
- [臨] 本環境已建**衝突預警**（hooks/wg_coordination.py，多大師計畫 7 席共議定案）：純檔案方案（不依賴 3848 daemon）——PreToolUse 掃其他活 session state 的 modified_files（entry 級 session_id 歸屬）warn 同檔互寫；Bash git add -A/reset --hard 且同 cwd 有他人未收改動 → 警告；PostToolUse 60s late-collision 補償。log 落 Logs/session-coordination/<sid>.jsonl；config coordination.enabled 一鍵關
- [臨] 定案原則：協調資料**絕不寫入 state-*.json**（Node writeState 無鎖吞錯 + Python/Node 三條 GC 互不相認 last-writer-wins 必吃資料）；Stage 2 收件匣（MCP chip→PostToolUse one-writer 蓋真實 sender→一訊息一檔 sidecar）與 Phase 3 認領制 **defer**——重啟條件=observation log 顯示 P1 警告後仍互踩頻發或 first-write 衝突常態化
- [臨] 計畫全程紀錄濃縮於 _AIDocs/DevHistory/session-coordination-bus.md（七席意見/仲裁/probe 數據）

## 行動

- 多 session 互踩議題 → 先看 Logs/session-coordination/*.jsonl 實際命中數據再論擴建（Stage 2/3 defer 有據）
- 改 wg_coordination.py 前跑 hooks/verify/verify_session_coordination.py（16 測項含 warn/deny 互斥矩陣）
- 日落檢視：log 連續 4 週 conflict_warn 零命中 → 主動提降級評估（約 2026-08-28 後）
- 任何 PreToolUse advisory 輸出禁帶 permissionDecision（allow=自動核准）

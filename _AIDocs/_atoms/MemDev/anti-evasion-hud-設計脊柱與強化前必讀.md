# anti-evasion-hud-設計脊柱與強化前必讀

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: anti-evasion, AEC, AEC HUD, 收尾檢核 HUD, anti_evasion_report, one-writer, sibling 隔離, aec_severity, autospawn, 彈窗, 強化 AEC, 改 AEC HUD, 記憶系統開發
- Created-at: 2026-07-06
- Related: guardian-dashboard-孤兒佔埠與新碼重啟, feedback-memory-system-doc-sync

## 知識

- [臨] **SoT 指標(先讀再改)**:設計/行為權威在 `_AIDocs/Architecture.md`(ScanReport Gate 列)+ `tools/workflow-guardian-mcp/lib/_MAP.md`(模組+one-writer+C7)+ `_CHANGELOG.md`(AEC HUD 系列條目)。本 atom 只收「改/強化前必知的脊柱與踩坑」,細節看 SoT、勿在此複製本體。
- [臨] **one-writer 脊柱(不可違)**:MCP 進程無 session 身份 + Node writeState 無鎖 race → state/落 per-turn 檔/HUD spawn 一律由 Python `hooks/handlers/post_tool_use.py`(帶原始 session_id+turn_seq)獨佔;MCP tool(`lib/anti-evasion.js`)只回 chip、**全程不碰 state**。改 AEC 時別讓 Node 端寫 state。
- [臨] **sibling 隔離必雙鍵**:Stop 閘判 emit 滿足用 turn_seq **且** session_id(`bool(turn_seq)` 護欄防 0==0 假滿足);共用工作樹/merged state 下隔壁 session 的 emit 不可誤放行本 session。改閘門別退回單鍵、別只看 turn_seq。
- [臨] **severity blank-detection gotcha**:`_aec_blank`(py, wg_evasion)/`aecBlank`(js, anti-evasion)為 **py↔js MIRROR**,必 strip 尾標點再比對「無」(模型慣寫「無。」);太嚴會把 routine 報告誤升 real-evasion 洗 chat。改一邊必同步另一邊。
- [臨] **WORKFLOW_DIR 全域**:報告落 `~/.claude/workflow/aec-report/<sid>-t<turn>.json`(CLAUDE_DIR-based、**非 per-project**);專案層 session 報告亦集中此,HUD 是**跨 session/專案的全域視圖**,靠檔名 session_id 區分。`.gitignore` 收 `workflow/aec-report/`。
- [臨] **上線/除錯 gotcha**:Node 面(anti-evasion.js/aec-hud-html.js/server.js 路由)改動**需重啟 guardian 才 live**(佔 3848 舊碼問題見 [[guardian-dashboard-孤兒佔埠與新碼重啟]]);Python hook 即時生效;Edge `--app` 窗 Ctrl+F5 常**不 hard-reload** → 改 HUD 頁後要**關窗重開**才看到新內容。
- [臨] **UX 張力(設計取捨,非 bug)**:「報告不進 chat」與「看完就關窗」不可兼得——窗關著時 notable/real 只能 fallback 落 chat(routine 恆靜默入 disk)。**彈窗觸發策略(autospawn 開關 / 哪些 severity 才彈 / 觸發窗雙顯)屬 config+`_maybe_spawn_hud` spawn-gate、以最新碼為準查證**(此區可能有併發修正,勿照本 atom 舊述斷言)。
- [臨] **v2 backlog**:SyncReminder/一般 block 的 session-filter(比照 ScanReport 已做的 own_mod_files)、(d) 暫存檔互動保留/刪除鈕(複用 guardian world command bus + hook 注入 pending 決策、deferred 執行)、SSE、消觸發窗雙顯。

## 行動

- 改/強化 AEC 前先讀本 atom + Architecture.md(ScanReport 列)+ lib/_MAP.md
- 守 one-writer(MCP 不碰 state)+ Stop 閘雙鍵 + py↔js MIRROR(aecBlank/aecSeverity 改一邊同步另一邊)
- Node 面改動後重啟 guardian 才 live;改 HUD 頁要關窗重開(--app Ctrl+F5 不 reload)
- 彈窗/spawn 行為以最新碼(config + _maybe_spawn_hud)為準查證,勿照記憶舊述

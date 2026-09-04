# anti-evasion-hud-設計脊柱與強化前必讀

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: anti-evasion, AEC, AEC HUD, 收尾檢核 HUD, anti_evasion_report, one-writer, sibling 隔離, aec_severity, autospawn, 彈窗, 強化 AEC, 改 AEC HUD, 記憶系統開發, d_pending, AEC-Pending, 尚未寫, 見下一動
- Created-at: 2026-07-06

- Related: feedback-memory-system-doc-sync, guardian-dashboard-孤兒佔埠與新碼重啟

## 知識

- [臨] **SoT 指標(先讀再改)**：設計/行為權威在 `_AIDocs/Architecture.md`(ScanReport Gate 列)+ `tools/workflow-guardian-mcp/lib/_MAP.md`(模組+one-writer+C7)+ `_CHANGELOG.md`(AEC 系列條目)。本 atom 只收「改/強化前必知的脊柱與踩坑」。
- [臨] **one-writer 脊柱(不可違)**：MCP 進程無 session 身份 + Node writeState 無鎖 race → state/落 per-turn 檔/HUD spawn 一律由 Python `hooks/handlers/post_tool_use.py`(帶原始 session_id+turn_seq)獨佔；MCP tool(`lib/anti-evasion.js`)只回 chip、**全程不碰 state**。
- [臨] **sibling 隔離必雙鍵**：Stop 閘判 emit 滿足用 turn_seq **且** session_id(`bool(turn_seq)` 護欄防 0==0)；共用工作樹下隔壁 session 的 emit 不可誤放行本 session。
- [臨] **py↔js MIRROR 三組，改一邊必同步另一邊**：`_aec_blank`↔`aecBlank`(必 strip 尾標點再比「無」，太嚴會把 routine 誤升 real-evasion 洗 chat)；`aec_severity`↔`aecSeverity`；`aec_pending_items`↔`aecPendingItems`((d)/(h) 把記憶寫入推到之後：看每行「→」後結論段，已寫／不寫定論放過；parity test 在 verify_aec_emission_gate)。
- [臨] **報告是收尾檢核不是待辦清單**：模型自己當下能做的(寫 atom／補測試／commit)不得以「下一動」出現。post_tool_use 落 `report.d_pending`、Stop `AEC-Pending` 每 turn 擋一次逼 atom_write 後重 emit。再強化其他欄位的推後偵測沿用「結論段＋定論放過」、別整行掃(項目段常含「未記錄的踩坑」等誤中字)。
- [臨] **WORKFLOW_DIR 全域**：報告落 `~/.claude/workflow/aec-report/<sid>-t<turn>.json`(非 per-project)，HUD 是跨 session/專案全域視圖，靠檔名 session_id 區分；`.gitignore` 收。
- [臨] **上線 gotcha**：Node 面(anti-evasion.js/aec-hud-html.js/mcp.js schema)改動需新 node 進程才 live(見 [[guardian-dashboard-孤兒佔埠與新碼重啟]])；Python hook 即時生效；Edge `--app` 窗 Ctrl+F5 不 hard-reload → 改 HUD 頁要關窗重開。
- [臨] **UX 張力(設計取捨)**：「報告不進 chat」與「看完就關窗」不可兼得；窗關著時 notable/real fallback 落 chat。彈窗策略(autospawn/哪些 severity 才彈)屬 config+`_maybe_spawn_hud`，以最新碼為準。
- [臨] **v2 backlog**：SyncReminder/一般 block 的 session-filter、SSE、消觸發窗雙顯。

## 行動

- 改/強化 AEC 前先讀本 atom + Architecture.md(ScanReport 列)+ lib/_MAP.md
- 守 one-writer(MCP 不碰 state)+ Stop 閘雙鍵 + py↔js MIRROR 三組(aecBlank/aecSeverity/aecPendingItems 改一邊同步另一邊)
- Node 面改動後需新 node 進程才 live；改 HUD 頁要關窗重開
- 彈窗/spawn 行為以最新碼(config + _maybe_spawn_hud)為準

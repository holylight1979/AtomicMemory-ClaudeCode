# codegraph與agent-retro評估結論-codegraph只當專案local-MCP不進記憶-agent-retro只拆量測

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: codegraph, agent-retro, code graph, session retro, retrospective, 外部工具評估, 拆入記憶系統, tool_result_sizes, friction, MCP 外掛, prompt hook 疊加
- Created-at: 2026-09-18
- Related: codex-exec-手動派工三旗標-skip-git-repo-check-stdin關閉-unelevated, feedback-原子記憶核心理念-知識經驗全積累分門別類-高精準零token浪費, 糾正與失敗偵測把sub-agent完成通知當使用者輸入-task-notification整則進ups-引用的糾正詞誤觸deeppostmortem

## 知識

- [臨] colbymchenry/codegraph（v1.6.0，tree-sitter AST → SQLite 圖，MCP 只曝 `codegraph_explore`）與原子記憶是互補：它答「現在程式碼怎麼呼叫」，記憶答「以前為何這樣決定」。程式碼位置是可再生索引，**不進 atom／不向量化**；要用就在專案內 `codegraph install --location=local`，因為全域安裝會改 ~/.claude 版控中的 CLAUDE.md（CODEGRAPH_START 區塊）與 settings.json（MCP + 預設開啟的 UserPromptSubmit hook）；那個 hook 每則結構性 prompt 最多再注入 9,000 字元原始碼，與記憶注入預算疊加不共用，且出錯靜默退出；`--yes` 會被解讀成開 hook；telemetry 預設開（`codegraph telemetry off` 或 `DO_NOT_TRACK=1` 同時關更新檢查）。
- [臨] giannimassi/agent-retro（v0.1.0 skill + 600 行 extract.py）在本機直接炸：`open(path)` 不給 encoding → 繁中 transcript `cp950 UnicodeDecodeError`，加 `python -X utf8` 才能跑；成本公式寫死 Opus 舊價 15/75（高 3 倍）；「完整對話」實際 user 截 2000／assistant 截 1000 字；子代理靠 60 秒鄰近配對。與本系統重疊七成（失敗萃取／DPM／episodic／journal），唯一增量是「工具結果體積」與「使用者糾正訊號」兩種量測，已拆成 `hooks/wg_friction.py`；其餘（retro 報告檔、美元 handoff 門檻）不值得收。
- [臨] 評估外部 agent 工具是否拆入的判準：先 grep 本系統有沒有同一量測（本次實證：全 repo 零工具結果體積量測、DPM 只認 failing_tests/evasion），再問效果是否第一個 session 就看得到；只拆「量測」不拆「功能」，功能用 MCP 外掛接。

## 行動

- 要在專案用 codegraph：`--location=local`、telemetry off、Front-load hook 選 No；不在 ~/.claude 全域裝
- agent-retro 只借方法：session 統計抽取要自寫（UTF-8、不算美元），餵 /memory score 的空轉指標是第二階段
- 評估其他外部 agent 工具：先 grep 本系統同一量測是否存在，再決定拆量測或接 MCP

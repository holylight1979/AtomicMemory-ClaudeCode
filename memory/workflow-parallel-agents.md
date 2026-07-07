# workflow-parallel-agents

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 多 agent, 平行 agent, sub-agent, 並行, 並行加速, 拆 agent, 多開 agent, 分頭, 多檔調查, 批量重構, 全面審視, 跨檔比較, parallel agents
- Created-at: 2026-05-28
- Related: workflow-rules, decisions, feedback-workflow-discipline, 模型行為移植-fable行為契約必載檔

## 知識

- ### 為什麼預設要評估並行
- [臨] 序列調查/實作會耗光主對話 context，且時間是 user 等待
- [臨] Sub-agent 各跑獨立 context，回傳精簡摘要 → 主 context 不被 raw 結果污染
- [臨] 同 message 一次 dispatch ≥2 個 Agent → 並行執行，wall-clock 接近單 agent 時長
- 
- ### 拆分判準（≥1 成立就值得拆）
- [臨] 多個獨立目標：「調查 A 也順便看 B」「重構 X 與 Y」
- [臨] 不重疊的檔案集：A 動 frontend、B 動 backend
- [臨] 跨檔比較／審計：「全部 hook 看一遍」「比較這幾個 atom」
- [臨] 批量同形：N 個檔案套同一規則修改（每個檔可獨立 agent）
- [臨] 混合性質：一個 research / 一個 code edit / 一個 doc 撰寫
- 
- ### 不該拆的情況
- [臨] 強依賴序列：B 必須先看 A 的結果才知道怎麼做
- [臨] 共寫同一個檔：多 agent 同寫會衝突
- [臨] prompt 本身很小（單檔小改）：拆 agent overhead 反而拖慢
- [臨] user 明確要逐步：例如「先做 A 給我看結果再決定 B」
- 
- ### Agent type 怎麼挑
- [臨] 找檔案 / 找 symbol / 找引用 → `Explore`（快速 read-only）
- [臨] 設計實作策略 / 跨檔分析架構 → `Plan`（不寫 code，回實作計畫）
- [臨] 跑命令 / 改檔 / 開放式調查 → `general-purpose`（最通用、有 write 權）
- [臨] 不確定 → `general-purpose`
- [臨] code review / security 等專項 → 對應 specialized agent（看當下可用清單）
- 
- ### 同 message 多 dispatch 寫法
- [臨] 必須在單一 assistant message 內放多個 Agent tool_use block → 才會 parallel
- [臨] 拆到不同 message → 變成 sequential，失去並行意義
- [臨] 每個 agent prompt 自包含（不能引用「前面 agent 的結果」，因 agent 互不見對方）
- 
- ### Context 隔離注意
- [臨] 主對話拿到的是 agent 「最終回報」，不是過程
- [臨] 要求 agent 回報控字數（如 "report in under 200 words" / punch list）
- [臨] 大量 raw 結果讓 agent 消化後給結論，不要讓 agent 全部丟回主對話
- 
- ### Hook 推播訊號
- [臨] `wg_parallel.py` 掃 prompt 連接詞/批量詞/多檔提及，達門檻時注入 `[Parallel:Suggest]`
- [臨] 看到提示不要無腦拆 — 仍要套上述判準，不適合就在回應裡說明為何不拆
- 
- ### Pre-dispatch 自檢清單（拆前必走）
- [臨] dispatch 前必列每 agent 預計 touch 的檔案集；任一交集 → 拒拆改序列
- [臨] 「各改同一檔的不同段」也禁拆 — agent 各自讀整檔、寫整檔回去，後寫覆蓋前寫
- [臨] Stale-read 風險：A 讀完 X 開始想 → B 同期改 X → A 寫回時用的是過期心智模型
- [臨] 索引/計數類合併點（如 _atom_index.json、_CHANGELOG.md、MEMORY.md）不該由多 agent 同期寫，走 funnel 也要避免競寫
- 
- ### 進階：Worktree 物理隔離（選性採用）
- [臨] Agent tool 支援 `isolation: "worktree"` — 每 agent 拿到專屬 git worktree，物理隔離檔寫
- [臨] 適用：專案 src 下有 git 且拆出去的是 code edit 類
- [臨] 不適用：練寫 ~/.claude 本身（不走 git worktree）、寫共享代表性資源（設定檔/atom/index）
- [臨] Worktree 不必讀：如拆出去的都是 read-only 調查（Explore agent），並行本身安全，不需隔離
- 
- ### Hook 不推播的 same-file 個案
- [臨] `wg_parallel.py` 已內建：prompt 只提到 1 個唯一檔 → score 扊 -2（初步屏蔽「重構 X 的 N 個函式」此類單檔多段）
- [臨] 然而 hook 只認明示檔名，描述型 prompt（「那個函式」）取得不到 → 仍依賴上面的 pre-dispatch 自檢

## 行動

- 開工前先掃 prompt 切面數：≥2 不衝突獨立目標 → 候選並行
- 候選並行時，先想清楚每個 agent 的「自包含 prompt」+「回報格式」再 dispatch
- 同一 assistant message 內一次發 ≥2 個 Agent tool 呼叫
- 看到 `[Parallel:Suggest]` 注入：套判準確認後決定拆或不拆，不拆要說原因
- 拆完彙整時，主對話只做「綜合判斷」，不重做 agent 已做的事

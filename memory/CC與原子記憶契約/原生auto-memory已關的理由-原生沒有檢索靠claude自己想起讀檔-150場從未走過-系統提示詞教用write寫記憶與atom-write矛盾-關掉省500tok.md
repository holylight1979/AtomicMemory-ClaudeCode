# 原生auto-memory已關的理由-原生沒有檢索靠claude自己想起讀檔-150場從未走過-系統提示詞教用write寫記憶與atom-write矛盾-關掉省500tok

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: auto memory, autoMemoryEnabled, 原生記憶, 自動記憶, MEMORY.md 原生, projects memory 目錄, 橋接檔, native-memory-bridge, 要不要開 auto memory, 併行原生記憶
- Created-at: 2026-11-04
- Source: session:ad474d11#6b975fab 2026-11-04
- Quote: 「沒有要收割的知識經驗的話，我要關session囉」

## 知識

- [臨] 現況：`settings.json` 設 `autoMemoryEnabled: false`，橋接檔與 `native-memory-bridge.py` 已退役。理由（實測 150 場）：原生 auto memory 沒有檢索，啟動只載 MEMORY.md 前 200 行，其他主題檔靠 Claude 自己想起去 Read；Claude 從未讀過我們放的目錄檔（0 次）、從未寫原生目錄（0 次，13 次被閘擋回 atom_write）。留著的代價是每場約 500 tok 的系統提示詞教 Claude「用 Write 寫記憶」，與「寫入一律走 atom_write」正面矛盾。
- [臨] 原子記憶不靠原生那條路：索引走根層 CLAUDE.md `@memory/MEMORY.md` 常駐，每回合由 UserPromptSubmit 依觸發詞推送（150 場 13,146 次），主動查走 `memory_search`（224 次）。關掉原生後一張卡都不少。
- [臨] 若要「併行」原生寫入：只能把 autoMemoryDirectory 指到收件匣再收割，但會重新引入提示詞矛盾且與 SessionEnd 全量萃取重複；先拿「Claude 自發寫原生目錄的次數」數字再談。

## 行動

- 有人提議開回 auto memory：先看 `wg_core` MemoryPathBlock 的擋下次數與系統提示詞有沒有 # Memory 段，再談
- 驗關閉是否生效：新 session 的指令集不含 projects/<slug>/memory/MEMORY.md

# Failures — 踩坑記錄與失敗模式

> 跨專案累積的環境陷阱、假設錯誤、靜默失敗、認知偏差、誤診案例
> 最近更新：2026-05-28（feedback-* atoms 遷入 + cognitive-patterns 升 atom）

> **本目錄含兩類**：
> - **atom（受原子記憶體系管轄）**：`cognitive-patterns.md` + `feedback-*.md`（14 檔）+ `memory-pipeline-silent-failure-2026-05.md` — 印象在 [MEMORY.md](../../memory/MEMORY.md)，認知本體在此
> - **參考文件（非 atom）**：其餘 7 檔失敗模式（env-traps / wrong-assumptions / silent-failures / misdiagnosis-* / codex-* / vectordb-*）

---

## 文件清單

| # | 文件 | 類別 | 說明 | keywords |
|---|------|------|------|----------|
| 1 | env-traps.md | 參考 | Windows/MSYS2/Node.js/Ollama/MCP/VSCode 環境踩坑 | Win環境陷阱, Windows, MSYS2, Node.js, npx, Ollama, port, MCP啟動, VSCode |
| 2 | wrong-assumptions.md | 參考 | 假設錯誤案例（直覺偏差、空目錄、metrics 異常） | 假設錯誤, 直覺偏差, 為何沒生效, 空目錄, metrics異常, 功能沒反應 |
| 3 | silent-failures.md | 參考 | 靜默失敗案例（看似正常實際沒生效） | 靜默, silent, 看似正常, setdefault, knowledge_queue為空, 吞掉錯誤 |
| 4 | cognitive-patterns.md | **atom** [固] | 認知偏差案例（過度工程、代理指標、自我合理化編造） | 過度工程, 代理指標, proxy metric, AI看不懂, AI在打轉, 品質回饋, 自我合理化, 編造規則, 籠統話術, 訂規保留, 設計慣例, plan 檔誤留 |
| 4a | feedback-workflow-discipline.md | **atom** [臨] | handoff 自足 / drift 修補門檻 / 裁決推薦 / commit 中文 | handoff, 續接, 下 session, next-phase, 順手修補, drift 修補, 重複失敗, fix-escalation, 裁決, 決策推薦, plan 路徑, commit message, 上 GIT |
| 4b | feedback-completion-gates.md | **atom** [臨] | pytest 必跑 / smoke / 收尾 4 項檢核 / 衍生暫存清單 / plans 屬衍生 | 完成宣告, 收尾, pytest, smoke test, 研究先行, 清理, 先清後建, 基線, 衍生暫存, 暫存檔, 清暫存, 收尾檢核, plans 目錄, plan 檔 |
| 4c | feedback-tooling-reliability.md | **atom** [臨] | codex brief / bg subprocess / MCP 全域 / silent failure | codex, codex companion, codex CLI, gpt-5, bg subprocess, DEVNULL, ready flag, MCP, silent failure, probe burst, 規則唯一來源 |
| 4e | feedback-rigor-standards.md | **atom** [臨] | high thinking 紀律 / 規範先讀 / 技術我決 | 縝密, 漏掉, 沒看到, max thinking, high thinking, 外包思考, 規範, rigor, 前例, precedent, 既有 drift |
| 4e2 | feedback-atom-write-initial-confidence.md | **atom** [臨] | atom_write 初次寫入必 [臨]、不能直接 [固]；晉升 ≥4→[觀] ≥10→[固] | atom_write, 初次寫, 信心度, confidence, knowledge 行, 隨手寫 [固] |
| 4e3 | feedback-memory-system-doc-sync.md | **atom** [臨] | 記憶系統修改後必逐項同步相關文件（標準檢視清單） | 記憶系統修正, 改 hook, 改 wg_, server.js, 文件同步, doc sync |
| 4f | memory-pipeline-silent-failure-2026-05.md | **atom** [臨] | 原子記憶管線 2026-05-22 靜默失效（confirmations 恆 0 / episodic 停擺 / _ATOM_INDEX parser 空行 break） | memory-review, memory-health, confirmations, episodic, 晉升, 自我迭代, 衰減掃描, 覆轍偵測 |
| 5 | misdiagnosis-verify-first.md | 誤診案例 + 驗證優先原則 | 誤診, 驗證優先, verify first, 診斷失敗, 先射箭再畫靶, 假設錯誤就規劃, 過度規劃, 沒驗證就動手 |
| 6 | vectordb-silent-failure-2026-04.md | VectorDB 12 天假陽性 — 路徑寫死 + flag 無 gate；Wave 3a 修補 + Wave 3b REVIVE 決策 | vector, lance, silent failure, vector_ready, flag, 假陽性, bg subprocess, DEVNULL, probe burst |
| 7 | codex-windows-sandbox-1385.md | Codex `-s read-only` 在 Windows 因 `[windows] sandbox = "elevated"` 觸發 `CreateProcessWithLogonW failed: 1385`；修補 = `-c 'windows.sandbox="unelevated"'` | codex, sandbox, 1385, CreateProcessWithLogonW, windows, elevated, unelevated, logon type |
| 8 | codex-cli-version-mismatch-2026-04.md | model 升 (`gpt-5.5`) 但 codex CLI 沒升 → 400「needs newer Codex」；對策：升 model 同時 `npm i -g @openai/codex` + assessor.py 偵測 400 訊息獨立分類 | codex, CLI 版本, gpt-5.5, model 升級, npm i codex, 400 needs newer, version mismatch |

# 共同認知簡報：原子記憶系統全面檢視（2026-09-21）

你是這次「全面檢視」的其中一位審查者。多位 Claude 與 Codex 審查者各持一個角度並行工作，最後由主持者彙整。本檔是所有審查者共享的認知基底，請完整讀完再開工。

## 任務原文（使用者）

> 針對最新版 Claude Code（含上網蒐集官方發布與非官方各種討論），以及目前多人推薦、或設計理念非常特別的 skill，找出目前原子記憶系統（含子系統）可以**補強、或新增、或精簡**的，先出一份報告、若確實存在則推進計畫到執行；原則是**可以不用硬找或硬加，過於雞肋的也不用考慮，若有很 hack 的「演算法」或特定設計，可以多研究**。

## 審查原則

1. 不硬找、不硬加。找不到就說找不到，這也是合格答案。
2. 雞肋不收：判準是「第一個 session 就看得到效果」且「本系統沒有同一量測／機制」。先 grep 本系統有沒有同一量測，再說可新增。
3. 很 hack 的演算法／特定設計要挖到機制層級（公式、觸發條件、資料流），不是功能名。
4. 「精簡」與「補強」同等重要：本系統已相當龐大（見下），砍掉沒效果的機制也是成果。
5. 每個主張附證據：URL、檔案路徑:行號、實測數字。查不到就寫「未查到」，不腦補。
6. 已除役／已評估過的東西（見末兩節）不要再提，除非有新證據推翻。

## 系統現況（原子記憶系統 V5.1，Workflow Guardian 5.1.0，發布 2026-07-25）

位置：`C:/Users/holylight/.claude/`（git repo，多機共享）。詳盡文件：`TECH.md`（15 章，74KB，最完整）、`_AIDocs/Architecture.md`（索引型）、`README.md`（人讀）。

### 一句話
讓 Claude Code 擁有跨 session、跨專案的長期記憶：知識寫成「記憶卡片（atom）」markdown 檔，每個 prompt 由 hook 自動檢索最相關的幾張注入給 AI；寫入走品質閘門；用過有效才晉升，沒用的淡出；回合收尾檢查 AI 有沒有敷衍。

### 資料層
- atom = markdown 卡片，欄位：Trigger（關鍵詞）、Confidence 三級（[臨]→[觀]→[固]）、Scope 四層（global / shared / personal / project）、Related、Supersedes、Depends、Evidence（實證 3 > 引述 2 > 推測 1）。
- 索引：`memory/_atom_index.json` 單一真相；`MEMORY.md` / `_ATOM_INDEX.md` / 各層 `_INDEX.md` 為鏡像。多機 git 合併有語意合併驅動。
- Realm：跨專案通用 → `memory/<範疇>/`；只在 ~/.claude 內有用 → `_AIDocs/_atoms/`（local realm，外部專案零負擔）。專案層 → `{專案}/.claude/memory/`。
- 目前規模：global 193 顆、local 約 78 顆。

### 每 prompt 檢索注入（UserPromptSubmit hook，四段：gates → context → search → inject）
L0 意圖偵測 → Trigger 匹配（ASCII 整詞／CJK 子字串）→ BM25（僅 trigger 命中 ≤2 時；min_score 7.0、top 3）→ Vector（LanceDB + Ollama，只補專案層）→ Supersedes 過濾 → RRF 融合 × ACT-R activation（使用頻率 + 時間衰減）→ hot/cold 分級 → 同題去冗 → per-turn atom 段硬頂 1200 tok、整包 additionalContext 依 prompt 長度 1000/2000/3000。無 cross-encoder rerank。

### 寫入與積累
- 顯式：MCP `atom_write`（write gate 評分、去重、write-time 衝突偵測 → pending 待審）。新 atom 一律 [臨]。
- 自動萃取（在跑）：失敗關鍵字萃取（UPS 偵測 → detached worker → `Failures/`）；SessionEnd 全量萃取（本地 gemma4:e4b，transcript ≤20000 chars、max 5）；episodic 摘要（TTL 24 天）；使用者決策萃取（L1 qwen3 yes/no → L2 gemma4 結構化，conf ≥0.92 直寫／0.70–0.92 pending）。
- 晉升：Stop 時做效用歸因（本輪注入的 atom 有沒有被用到，lexical overlap ≥0.18 或稀有 token ≥2）→ Wilson 下界 ≥0.6 且 n≥3 升 [觀]；≤0.35 且 n≥5 降級候選；decay λ=0.97 每日一次。ReadHits 只是曝光計數，不助晉升。
- 遺忘：selective forget（score = 0.5·recency + 0.5·usage < 門檻 → 隔離到 `_distant/`，可逆）。
- 衝突裁決：證據等級 → recency；新側實證 vs 舊側 [固] 直接 fast-refute。

### 守門與收尾（Stop / PreToolUse 等）
反退避（Anti-Evasion）檢查、測試失敗閘、動手前預告（PAN）閘、「上GIT」口令閘、AEC-Pending 閘（記憶寫入不得推給下回合）、Codex 驗收裁判（subprocess，第二意見）、auto-handoff 四層交接、跨層 Bash 閘、lang guard。

### 可觀測
Dashboard（http://127.0.0.1:3848/）、Anti-Evasion HUD、腦內世界（world.html 視覺化）、statusline、週健檢、召回失念偵測（recall-miss）、回歸評估集、注入效果報表（top 有用 / token 稅 / 零曝光候選）、工具結果體積提醒、使用者糾正訊號量測（`hooks/wg_friction.py`，2026-09 新增）。

### Hooks（settings.json 九事件）
SessionStart / UserPromptSubmit / PreToolUse / PostToolUse / PreCompact / PostCompact / PostToolBatch / Stop / SessionEnd。`hooks/dispatcher.py` 純路由 → `hooks/handlers/{event}.py`；主模組 `hooks/wg_*.py`（atoms / coordination / core / docdrift / episodic / evasion / extraction / friction / handoff / parallel / recall_miss / rescue / research / roles）。官方硬牆：UPS 30s（實設 8s）；SessionEnd 全部 hook 共 1.5s → LLM 萃取走 detached worker。

### Skills（21 個 active）
atom-debug, browse-sprites, changelog-debug, codex-companion, conflict, consciousness-stream（識流）, continue, extract, fix-escalation, generate-episodic, handoff, harvest, heal-review, journal, karpathy-guidelines, memory（health/review/score/classify）, read-project, refile, skill-creator, synced, upgrade, vector。

### MCP server（`tools/workflow-guardian-mcp/server.js`）
5 tool：atom_write / atom_promote / atom_move / atom_edit_meta / anti_evasion_report；同進程提供 Dashboard。

### Token 成本
always-load 約 1,500–2,000 tok（IDENTITY + USER + rules + MEMORY.md）；每輪注入 atom 段 ≤1200；典型 session overhead 2,500–3,500 tok。

### 目前健檢已知問題（2026-09-21 週報）
- broken_refs 5 筆；episodic 生成停擺（最後 2026-09-04，疑管線靜默失效）；memory-audit issues 41 / duplicates 7；注入效果：top 有用 10 / token 稅 0 / 零曝光候選 35。

### 系統自評的已知弱點（TECH.md §2.2）
- 無 cross-encoder rerank。
- 萃取物無 provenance（指不回原文 transcript 位置）。
- 注入段每輪變動、不進 prompt cache。

## 已除役機制（不要再提議）
per-turn 逐輪萃取（write-only 死路、0 下游消費）；SessionEnd 草稿 flush；quick-extract 快篩 + Hot Cache；跨 session Confirmations 晉升軌；Codex 常駐 daemon（改 subprocess）；init-roles / conflict-review skill（單人環境）；UPS 週期 Reminder 注入（改 statusline 零 token）；MCP 內部 IPC 4 tool；commands/*.md（併入 skills）；PAN deny 模式（漏偵 14–33%）；Realm LLM fallback 分類（保確定性）；ReadHits 助晉升（曝光≠有用）。

## 已評估過的外部工具（2026-09-18 結論）
- codegraph（tree-sitter AST 圖 MCP）：與記憶互補，程式碼位置是可再生索引，不進 atom；只在專案 local 裝。
- agent-retro：與本系統重疊七成；唯一增量「工具結果體積」「使用者糾正訊號」兩量測已拆入 `wg_friction.py`。
- 判準：只拆「量測」不拆「功能」，功能用 MCP 外掛接；先 grep 本系統有沒有同一量測。

## 回報格式（統一，方便彙整）

```
## 候選清單
| # | 名稱 | 來源（URL / 檔案:行） | 機制（3–6 句白話，有公式寫公式） | 類型（補強/新增/精簡/無關） | 對本系統的意義（差在哪） | 第一個 session 看得到的效果 | 成本（人日／風險） | 證據等級（實測數字/引述/推測） |

## 最值得做的 5 件（排序 + 理由）
## 明確不建議做的（+ 為什麼）
## 未查到／不確定的
```

語言：繁體中文，術語首次出現附一句白話。務實、懷疑、不湊數。

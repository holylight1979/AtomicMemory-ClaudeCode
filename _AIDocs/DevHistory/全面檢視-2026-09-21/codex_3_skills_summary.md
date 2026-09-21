# Codex #3（gpt-6-astra）社群 skill — 摘要（全文 reply_3.md，280K tokens）

結論：優先修現有 skill 的失效指令、寫入契約與評估方法；不整套導入外部框架。最值得借：「有／無 skill 對照評估」與「只留無法從程式碼再生的經驗」。

## 本機實證
- 現有 audit-skill.py 稽核 21 個 skill：**19 個失敗，全因缺自訂 `triggers` 欄位**（本機契約與平台不一致，非載入失敗）；只 2 個有 evals/triggers.json 且稽核只查檔案存在。
- `userInvocable` 拼法 vs 官方 `user-invocable`（預設可呼叫，未失效但模板未對齊）；frontmatter 單行 regex 不能解析多行 description。
- **`/extract` 失效路徑**：SKILL.md:54 傳 JSON 只有 mode/max_chars/max_items；extract-worker.py:320 需 session_id/cwd；wg_core.py:422 缺值回 None → 空結果；頂層 8000/5 也不是該段用的設定。
- read-project:78/132 建 doc-index atom 並要手動補 MEMORY.md；consciousness-stream:119 依風險字詞引導寫 pitfalls/decisions 並更新 MEMORY.md；upgrade:276 舊遷移配方直接複製 atom/改 metadata/手動索引。
- memory skill:24 vs :151「無參數直接 health」與「先列選單」矛盾；`memory review --self-iterate` 選項在 memory-audit.py argparse 不存在。
- fix-escalation 實際 2+3+3+1=9 次代理呼叫；skill-creator 強制四題訪談無省略規則。
- karpathy-guidelines 與 rules/coding-style.md 高度相近 → 候選縮減自動載入（先有/無對照）。
- 工具輸出統計：3 session、65 次呼叫、67,631 字元、達 20K 門檻 0 筆 → 不急裝輸出壓縮器。
- 9/21 skill 已 disable-model-invocation。

## 前五
1. 修 `/extract` 失效路徑（不復活 per-turn）；移除「新建可直接 [觀]/[固]」舊描述。
2. 統一 active skill 寫入契約：可再生索引不進 atom、統一走 MCP；品質閘補 Compound 反事實判準「能否從程式碼/測試/文件再生」（不做 LLM 分類器）。
3. 修 skill-creator 規格：audit 分官方錯誤/本機建議；triggers/pattern 非必填；500 行為建議；修 frontmatter 解析；refile 同步。
4. trigger fixtures 升級為真正成效測試（觸發準確度與任務成效分開計分）；先 extract / read-project / skill-creator。
5. 精簡固定儀式：fix-escalation 改「根因調查＋獨立驗證」再視證據擴大；skill-creator 訪談先填已知只問缺口。

## 不採用
ECC instinct 聚類/跨專案晉升（已有、英文 token 規則不適 CJK）；cc-sessions/disler 硬閘（PAN deny 已退役）；beads/CCPM；planning-with-files/GSD（已有 handoff/continue）；ralph loop；context-mode/RTK 暫緩（樣本不支持）；HumanLayer 舊套件（維護者明示棄用）；每次失敗自動改 CLAUDE.md 或自動生 skill；全面強制 plan-first/TDD/多代理會議。

## 共識
description 寫「適用情境＋產出」；500 行是建議；`context: fork` 不繼承當前對話（不能套 handoff/extract）；skill 表程序、hook 表保證；評估先無 skill 基準。

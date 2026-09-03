# MyClaudeCode (.claude) — AI 分析文件索引

> 本資料夾記錄 `~/.claude` 自訂擴充系統的架構與演進。
> 最近更新：2026-08-31（對外四文件全面改寫：README 人讀化、TECH 按現況重排、Install-forAI 前置需求＋降級邏輯、version.json 加網頁位置欄）
> 前次：2026-07-25（V5.1：RRF 三路融合 + memory-eval 回歸集 + 失念/壞滅緣/證據等級）

---

## 文件清單

| # | 文件名稱 | 說明 | keywords |
|---|---------|------|----------|
| 1 | Architecture.md | 系統架構索引：hooks 9 事件與模組表 + Skills + Evasion Guard + atom 寫入 funnel + Realm 分區 + MCP 5 tool + 可觀測層 + 腦內世界（子系統索引型；現況細節以 TECH.md 為準） | 架構, hooks, skill, rules, 事件驅動, wisdom engine, 規則模組, guardian, 覆轍偵測, 自我迭代自動化, 專案自治, funnel, realm, MCP, BM25 |
| 2 | Project_File_Tree.md | 頂層目錄角色說明（30 行；詳細請跑 `tree -L 3`） | 目錄角色, 頂層結構說明 |
| 3 | _CHANGELOG.md | 變更記錄（最近 ~8 筆） | 變更記錄, 最近更新, 改了什麼 |
| 4 | _CHANGELOG_ARCHIVE.md | 變更記錄封存 | 歷史變更, 舊版記錄 |
| 5 | ../README.md | 人讀入口：是什麼 / 平常在做什麼 / 核心理念 + 與原生 CC 差異表（零技術名詞；安裝與用法指到 Install.md） | 安裝, 入門, 使用方式, 快速開始, 設計理念 |
| 5d | ../Install.md | 人讀安裝指南：版控庫網址 + 在 ~/.claude 貼 prompt 由 AI 代跑 + 驗證 + 專案 3 步 + 啟動檔維護 | 安裝, 人讀, prompt, 專案初始化, 啟動檔 |
| 5c | ../Install-forAI.md | AI 代跑安裝指南：前置需求逐項附替代方案與降級邏輯、合併安裝步驟、驗證 checklist、升級、FAQ、網頁介面位置 | 安裝, 前置需求, 降級, fail-open, 升級, FAQ, Ollama, codex, Node |
| 5b | ../TECH.md | 技術深度文件（按現況排章）：設計理念 / 與原生・業界差異 / 一回合流程 / 記憶資料層 / 檢索與注入 / 寫入與積累 / 守門與收尾 / 可觀測 / 背景服務與網頁 / 目錄樹 / 設定總表 / 版本歷史（以代碼為真源） | 設計哲學, 流程圖, ACT-R, RRF, BM25, Write Gate, scope, realm, 注入預算, 核心子系統, 版本歷史 |
| 6 | DocIndex-System.md | 全檔系統索引（啟動鏈 + Hook 模組 + <!-- skill-count -->21<!-- /skill-count --> Skills + Tools + Memory <!-- atom-breakdown -->159 atoms：core 71 + feedback 21 + 失敗模式 2 + local 65〔Tools9/MemDev52/OS2/CC與原子記憶契約1/Vision1〕<!-- /atom-breakdown -->） | 啟動鏈, lifecycle, 全檔索引, 檔案清單, 系統索引, realm, local atom |
| 7 | ClaudeCodeInternals/_INDEX.md | Claude Code 原生架構深度分析（14 章：Harness Engineering 全書） | claude code 架構, harness engineering, tool system, hook system, agent, permission, prompt, MCP, skill, plugin, feature flag, query loop, context, state |
| 8 | Tools/_INDEX.md | 工具與領域知識（Excel 操作、Unity YAML/Prefab、記憶系統檔案索引、BM25 全域檢索層） | Excel, xlsx, openpyxl, Unity YAML, fileID, GUID, prefab, WndForm, 記憶系統架構, BM25 |
| 9 | ../memory/Failures/_reference/_INDEX.md | 踩坑記錄與失敗模式參考文件（環境陷阱、假設錯誤、靜默失敗、誤診、codex/vector 案例）；失敗家族 atom（feedback-* + cognitive-patterns）住 `memory/Failures/<主題>/`，索引 `memory/Failures/_INDEX.md`（生成器產） | 環境陷阱, Windows, MSYS2, npx, Ollama, 假設錯誤, 靜默, 過度工程, 誤診, 驗證優先, feedback atoms, cognitive-patterns |
| 10 | DevHistory/_INDEX.md | 開發紀錄（版本演進、遷移紀錄、A/B 實測數據、atom 演化日誌；含 V5 升版完整紀錄 [DevHistory/v5-overhaul-2026-05/](DevHistory/v5-overhaul-2026-05/README.md)） | 演化, 版本, changelog, 遷移, migration, V2.18, V2.20, V2.21, V5 升版, A/B, 實測, benchmark |
| 11 | SPEC_ATOM_V5.md | 原子記憶 V5 規格 — skills 取代 commands / hook 6+2 模組 / BM25 全域層 + RRF 融合（§14）/ optional Depends·Evidence 欄（§13）/ Codex subprocess / MCP 砍 4 內部 tool / 禁語 JSON 單一來源 | V5, GA, skills, BM25, RRF, 檢索融合, Depends, Evidence, 壞滅緣, 證據等級, Codex subprocess, MCP, 禁語, hook 整併 |
| 12 | SPEC_ATOM_V4.md | 原子記憶 V4 規格（V5 詳情依靠的對照證物）— 多職務團隊共享（personal / shared / role 三層 scope、衝突三時段偵測、管理職雙向認證、JIT 角色 filter） | V4, scope 三層, role-shared, personal-in-project, 多職務, 團隊協作, 衝突偵測, 管理職, audience, 角色 filter |
| 14 | Research/_INDEX.md | 外部調查與業界比對（論文／廠商／社群專案查證整理，附來源 URL）；LLM agent 長期記憶業界調查 2025–2026；寫碼風格出處（rules/coding-style.md 依據） | research, 業界調查, agent memory, Mem0, Letta, Zep, LongMemEval, context rot, 社群專案 |
| 13 | Vision/_INDEX.md | 發想與前瞻設計（尚未開工、「說不定某天做成成品」的平台設計與現有應用比對）；首個主題：JARVIS 式企業 AI 開發協作平台（README + 9 子檔，記憶服務化/編排核心/模型路由/工具註冊/攝取/多模態/作業紀錄/安全治理/演進路線）。read-on-demand、非 atom、零注入成本 | 發想, 願景, vision, 前瞻設計, jarvis, 企業平台, 編排, 多模型路由, 工具註冊, 演進路線圖 |
| 15 | MultiMachineMemorySync.md | 多機記憶同步（AI 讀）：索引三檔三層防線（全 repo LF → 合併驅動 hook 自動裝 → `--resolve` 備案自動觸發）、config、CLI 契約（exit code／JSON 欄位）、stage 方向矩陣、支援的 shell 語法、Windows 約束、失敗模式 SOP、手動最後手段、不在保證範圍、設計取捨、驗證方法 | 多機, 多人, 合併, merge driver, atomindex, --resolve, 索引三檔, 索引衝突, LF, CRLF, gitattributes, rebase 衝突, stage, ours theirs, IndexConflict, MergeDriver |

---

## 架構一句話摘要

基於 Claude Code hooks 事件驅動的工作流監督系統，搭配雙 LLM（Claude + Ollama gemma4:e4b / qwen3:1.7b）原子記憶管理跨 session 知識。全域 BM25 / 專案層 Vector + RRF 融合 + `_atom_index.json` JSON SoT（<!-- atom-total -->159<!-- /atom-total --> atoms：core <!-- atom-core -->71<!-- /atom-core --> 住 `memory/<範疇>/`（Lv1 閉合清單 `memory/_meta/taxonomy.json`）+ <!-- atom-feedback -->21<!-- /atom-feedback --> feedback-* + 失敗模式 atom 住 `memory/Failures/<主題>/` + <!-- atom-local -->65<!-- /atom-local --> local 範疇 atom 物理在 `_AIDocs/_atoms/<domain>/`、realm 由 path 推導、只在 ~/.claude 注入；`CROSS_PROJECT_LOCAL_DOMAINS` 空集合、機制保留）+ Codex Companion subprocess（無 daemon @ 3850）+ Hook 6 主模組 + 1 shim + 9 event handler + <!-- skill-count -->21<!-- /skill-count --> Skills + MCP 5 tool + `lib/atom_io.locate_atom` atom 落點單一裁決。

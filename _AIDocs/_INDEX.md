# MyClaudeCode (.claude) — AI 分析文件索引

> 本資料夾記錄 `~/.claude` 自訂擴充系統的架構與演進。
> 最近更新：2026-07-25（**V5.1 Ultra-Optimization**：RRF 三路融合 + memory-eval 回歸集 + 失念/壞滅緣/證據等級工程化 — SPEC_V5 §13/§14 新章 + TECH §5.11/5.12 + Architecture/DocIndex/governance §4.5 全同步）
> 前次：2026-06-03（**Realm 維度 S3**：core vs local 範疇分區文件全同步 — SPEC_V5 §2.2 Realm 章 + Architecture/rules/DocIndex + MEMORY.md「本地範疇」段 + Project_File_Tree V5 校準）

---

## 文件清單

| # | 文件名稱 | 說明 | keywords |
|---|---------|------|----------|
| 1 | Architecture.md | 系統架構總覽：原子記憶 V5 GA + Workflow Guardian + Wisdom Engine + 三層即時管線 + Hot Cache + 全域 BM25 + 專案自治層 | 架構, hooks, skill, rules, 事件驅動, wisdom engine, 規則模組, guardian, 覆轍偵測, 自我迭代自動化, 專案自治, hot cache, quick extract, 即時管線, BM25 |
| 2 | Project_File_Tree.md | 頂層目錄角色說明（30 行；詳細請跑 `tree -L 3`） | 目錄角色, 頂層結構說明 |
| 3 | _CHANGELOG.md | 變更記錄（最近 ~8 筆） | 變更記錄, 最近更新, 改了什麼 |
| 4 | _CHANGELOG_ARCHIVE.md | 變更記錄封存 | 歷史變更, 舊版記錄 |
| 5 | ../README.md | 安裝 + 3 步上手（人類入門，80 行） | 安裝, 入門, 使用方式, 快速開始 |
| 5b | ../TECH.md | V5 GA 技術深度文件：架構 / 流程圖 / 子系統 / BM25 + JSON SoT + Codex subprocess / V4 scope + V4.1 決策萃取（以代碼為真源） | 設計哲學, 流程圖, ACT-R, Write Gate, Hot Cache, BM25, V4 scope, V4.1 使用者決策, V5 GA, 核心子系統 |
| 6 | DocIndex-System.md | 全檔系統索引（啟動鏈 + Hook 模組 + <!-- skill-count -->21<!-- /skill-count --> Skills + Tools + Memory <!-- atom-breakdown -->79 atoms：core 15 + feedback 12 + 失敗模式 2 + local 50〔Tools9/MemDev34/OS4/Continuity2/Vision1〕<!-- /atom-breakdown -->） | 啟動鏈, lifecycle, 全檔索引, 檔案清單, 系統索引, realm, local atom |
| 7 | ClaudeCodeInternals/_INDEX.md | Claude Code 原生架構深度分析（14 章：Harness Engineering 全書） | claude code 架構, harness engineering, tool system, hook system, agent, permission, prompt, MCP, skill, plugin, feature flag, query loop, context, state |
| 8 | Tools/_INDEX.md | 工具與領域知識（Excel 操作、Unity YAML/Prefab、記憶系統檔案索引、BM25 全域檢索層） | Excel, xlsx, openpyxl, Unity YAML, fileID, GUID, prefab, WndForm, 記憶系統架構, BM25 |
| 9 | Failures/_INDEX.md | 踩坑記錄與失敗模式（環境陷阱、假設錯誤、靜默失敗、認知偏差、誤診）+ V5+ Session α 起為 5 個 feedback-* atoms + cognitive-patterns + memory-pipeline-silent-failure-2026-05 的物理位置（索引仍在 memory/_atom_index.json 單一來源） | 環境陷阱, Windows, MSYS2, npx, Ollama, 假設錯誤, 靜默, 過度工程, 誤診, 驗證優先, feedback atoms, cognitive-patterns |
| 10 | DevHistory/_INDEX.md | 開發紀錄（版本演進、遷移紀錄、A/B 實測數據、atom 演化日誌；含 V5 升版完整紀錄 [DevHistory/v5-overhaul-2026-05/](DevHistory/v5-overhaul-2026-05/README.md)） | 演化, 版本, changelog, 遷移, migration, V2.18, V2.20, V2.21, V5 升版, A/B, 實測, benchmark |
| 11 | SPEC_ATOM_V5.md | 原子記憶 V5 規格 — skills 取代 commands / hook 6+2 模組 / BM25 全域層 + RRF 融合（§14）/ optional Depends·Evidence 欄（§13）/ Codex subprocess / MCP 砍 4 內部 tool / 禁語 JSON 單一來源 | V5, GA, skills, BM25, RRF, 檢索融合, Depends, Evidence, 壞滅緣, 證據等級, Codex subprocess, MCP, 禁語, hook 整併 |
| 12 | SPEC_ATOM_V4.md | 原子記憶 V4 規格（V5 詳情依靠的對照證物）— 多職務團隊共享（personal / shared / role 三層 scope、衝突三時段偵測、管理職雙向認證、JIT 角色 filter） | V4, scope 三層, role-shared, personal-in-project, 多職務, 團隊協作, 衝突偵測, 管理職, audience, 角色 filter |
| 13 | Vision/_INDEX.md | 發想與前瞻設計（尚未開工、「說不定某天做成成品」的平台設計與現有應用比對）；首個主題：JARVIS 式企業 AI 開發協作平台（README + 9 子檔，記憶服務化/編排核心/模型路由/工具註冊/攝取/多模態/作業紀錄/安全治理/演進路線）。read-on-demand、非 atom、零注入成本 | 發想, 願景, vision, 前瞻設計, jarvis, 企業平台, 編排, 多模型路由, 工具註冊, 演進路線圖 |

---

## 架構一句話摘要

基於 Claude Code hooks 事件驅動的工作流監督系統，搭配雙 LLM（Claude + Ollama gemma4:e4b / qwen3:1.7b）原子記憶管理跨 session 知識。**V5 GA + Session α/β**：三層即時管線 + Hot Cache + 全域 BM25 / 專案層 Vector + `_atom_index.json` JSON SoT（<!-- atom-total -->79<!-- /atom-total --> atoms：core <!-- atom-core -->15<!-- /atom-core --> + <!-- atom-feedback -->12<!-- /atom-feedback --> feedback-* + cognitive-patterns + memory-pipeline-* 物理在 `_AIDocs/Failures/` + <!-- atom-local -->50<!-- /atom-local --> local 範疇 atom 物理在 `_AIDocs/_atoms/<domain>/`、realm 由 path 推導、預設只在 ~/.claude 注入；CROSS_PROJECT_LOCAL_DOMAINS 例外如 Continuity 跨專案注入）+ Codex Companion subprocess（無 daemon @ 3850）+ Hook 6 主模組 + 2 shim + 8 event handler + <!-- skill-count -->21<!-- /skill-count --> Skills + MCP 4 tool + `lib/atom_locations.py` atom 位置單一規則來源。

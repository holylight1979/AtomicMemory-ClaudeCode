# JARVIS 企業 AI 平台發想文件指標

- Scope: global
- Author: holylight
- Confidence: [固]
- Trigger: JARVIS, 企業平台, AI 協作平台, 編排核心, 願景, 前瞻設計, vision-doc, 平台發想, 記憶系統當核心缺什麼
- Created-at: 2026-06-26

## 知識

- [固] 「原子記憶系統還缺什麼才能當 JARVIS 式企業 AI 開發協作平台核心」的 gap 分析 + 多 agent 研究補充，收於 `_AIDocs/Vision/jarvis-enterprise-ai-platform/`（README + 01-09 共 10 檔；read-on-demand、零注入成本）
- [固] 定調：原子記憶系統＝海馬迴，JARVIS＝大腦；真正核心是「編排者(Orchestrator)」，記憶是它最關鍵的器官但非本身。缺口分 A(記憶硬骨頭：服務化/真權限/規模化檢索) + B(其他器官：編排/模型路由/工具註冊/攝取/多模態/治理/跨裝置)
- [固] 子檔對照：01 記憶共享皮層 / 02 編排核心 / 03 模型路由 / 04 工具註冊協定(MCP+A2A+AGNTCY 三層棧) / 05 知識攝取(GitLab) / 06 多模態(STT/翻譯/出圖) / 07 作業紀錄 / 08 安全治理(EU AI Act) / 09 演進路線圖(落地切入點總整合)
- [臨] 2026-10-01 與公司主管討論的「公司共用後台核心（中台）」是 JARVIS 願景的窄化版，只含三要件：共用後台＋中台主機、新專案直接接不重做、各職能工具與知識丟上去由 AI 自動分類註冊全公司共用；對應願景 #1 #3 #5 #10（＋#8 一半），不含編排／路由／多模態。缺口評估結論：多機 git/svn 同步已可當第一代中台主機；真正缺的是工具註冊中心（0%）、跨職能 taxonomy、非 Claude Code 使用者的查詢介面、多人能力啟用實測；真權限（RLS）延後到有跨團隊敏感知識才做。
- [臨] 中台記憶地基 2026-10-01 已落地（計畫檔 `plans/prancy-marinating-kay.md`，審查鏈 Codex→缺漏獵手→身份嚴審→地基辩方→反駁）：讀取端 `memory_search`（MCP＋cli）、公司層 org（`open-data-prog/companyatomsmem`，本機 `C:\\CompanyAtomsMem`）、AD 身份／職能／裁決設定鍵、Source／Depends 欄、編碼硬化、工具卡掃描器（`org-memory.py --scan-tools`）。未做：HTTP `GET /api/memory/search` 選配；真正對外服務屬 Vision P0。

## 行動

- 規劃此類企業 AI 平台功能、或回答「記憶系統當核心還缺什麼」→ 先讀 `_AIDocs/Vision/jarvis-enterprise-ai-platform/README.md`
- 某子系統「在現有原子記憶系統上怎麼接」→ 看對應子檔 01-09 的『現有原子記憶系統落地切入點』一節
- 此為發想文件指標（指標型 atom），內容本體在 docs，勿往此 atom 堆細節

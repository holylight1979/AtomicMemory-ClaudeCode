# realm-範疇分區機制-v5

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: realm, 範疇分區, 核心非核心, local atom, _AIDocs/_atoms, 注入閘門, atom 物理位置, promote fallback, wg_core bootstrap, 記憶系統
- Created-at: 2026-06-03
- Related: decisions-architecture, memory-index-caption-regen, feedback-workflow-discipline, 專案等級-mcpskillhookslog-不放全域根層, harness原生memory與atom索引marker撞名辨識, dashboard-apiatoms-專案-shared-範疇被-frontmatter-scope-覆寫誤歸核心房, feedback-complexity-origin-trace, auto-capture碎片sweep污染詞庫-defer根治, 跨session資訊失真機制與對策, scope-shared-無主題子夾路由-專案靠-project-hooks-sweep-分層, atom-edit-meta與atom-heal對專案層atom的缺口與繞法, 路徑解析函式的根層分支是遷移盲點-cwd在claude根時專案分支會長出舊址, atom-write-global必須省略project-cwd, feedback-atom-write-initial-confidence, 向量庫stale清理失效根因-layer標籤含冒號拆鍵錯位-刪0列仍回報成功, 記憶索引分類讀寫鏈總審計結論-驗無誤清單與一條龍中斷點

## 知識

- [觀] **機制本體不在本顆**：realm 由 index path 前綴推導、注入閘、分類器與保護清單、V6 多段 domain／深度閘／LLM 四態／詞庫自學與污染護欄、catalog 拆分、`/refile`、搬遷工具、守門測試——完整規格見 `_AIDocs/SPEC_ATOM_V5.md` §2.2（realm）與 §2.3（寫入閘）；核心層範疇資料夾與 Failures 家族見 §2.1；決策脈絡見 `_AIDocs/DevHistory/核心記憶分類階層化-2026-08.md`。本顆只留判準與文件沒寫的坑。
- [觀] **核心判定三問**（rules/core.md 記憶段指向此）：① 可重用 ≥2 個專案？ ② 系統規則 vs 特定 app／工具／環境範疇？ ③ 月級 vs 週級有效期？——三題偏前者 → core（`memory/<範疇>/`）；偏後者 → local（`_AIDocs/_atoms/<domain>/`）。分類階層化後再加一問：**使用面**（任何專案的 AI 會碰到）留 core，**開發面**（改記憶系統本身、本機特定）去 local `MemDev`。分類器安全預設 core，只高信心判 local。
- [觀] 坑：`hooks/wg_core.py` 的 `CLAUDE_DIR` 必須**本地定義**（它用來 `sys.path.insert` 定位 `lib/atom_locations` 本身），不可改成 `from atom_locations import CLAUDE_DIR`（雞與蛋）；MEMORY_DIR 同源同值，改 import 只增脆弱性、零實益。
- [觀] 坑：查 realm 守門測試要掃三處（`lib/verify` ∥ `tools/verify` ∥ `hooks/verify`），只看一處會漏 sweep／LLM 分類器那兩支。
- [觀] 儲存位置與注入範圍是兩個維度：`CROSS_PROJECT_LOCAL_DOMAINS` 例外機制（storage 在 `_atoms/` 仍跨專案注入）現為空集合、機制保留——起因是使用者心智模型「memory/＝索引、_atoms＝知識儲存」與「路徑前綴綁死注入範圍」的矛盾（見 [[feedback-complexity-origin-trace]]）；分類階層化後跨專案知識一律直接住 `memory/<範疇>/`，不再靠例外。
- [觀] 本顆住 `MemDev`（開發面）：記憶系統機制對外部專案是噪音；使用面契約由 rules/core.md 記憶段與 MCP `atom_write` schema 承載。

## 行動

- 新 local 知識：atom_write 帶 realm=local + domain；server.js 改動需重啟 MCP 生效
- 改任何 atom 物理位置：走 atom-set-realm／atom-move／atom-categorize（連 .access.json 搬、寫 index），不手動 mv
- 機制細節先查 SPEC §2.1–2.3，不在本顆重抄

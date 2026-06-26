# scope-shared-無主題子夾路由-專案靠-project_hooks-sweep-分層

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: scope=shared, 主題子夾, 專案 atom 分層, _resolve_target, project_hooks, classify-project-atoms, _unclassified, shared 扁平落根, project delegate hook, 專案記憶分類
- Created-at: 2026-06-26
- Related: realm-範疇分區機制-v5, auto-capture碎片sweep污染詞庫-defer根治, 專案等級-mcpskillhookslog-不放全域根層

## 知識

- [臨] 核心 lib/atom_io.py `_resolve_target` 只對 realm=local（→ `_AIDocs/_atoms/<domain>/`）與 feedback-（→ `_AIDocs/Failures/`）做物理子夾路由；scope=shared/role/personal 一律**扁平**寫 `<project>/.claude/memory/{shared | roles/<r> | personal/<u>}/<slug>.md`，**無主題子夾分類**（atom_io.py:239-264）。故 curated 專案 atom 會堆在 shared/ 根。auto-capture 草稿另由 extract-worker._flush_route 隔離到 `shared/_drafts/auto-capture/`（不入索引、不注入），那條沒問題——漏點是 curated（有 .access.json / 已索引）的 shared atom。
- [臨] 專案要把 curated shared atom 分層 → **自建 taxonomy classifier 接 core 的 project delegate hook**（`hooks/handlers/_shared.py:_call_project_hook`：subprocess / 5s timeout / never-raises），core **目前只在 session_start 呼叫** `<project>/.claude/hooks/project_hooks.py`（session_start.py:442）。不該把專案分類器硬接進 core wg_atoms.py（會耦合單一專案 taxonomy + 打全專案最熱寫入路徑，違反 realm 分區）。
- [臨] C:/Projects 實作（2026-06-26）：project_hooks.handle_session_start → `_auto_classify_shared_atoms` → importlib in-process 載 `tools/classify-project-atoms.apply_classification`（taxonomy 計分 name×10>trigger×1；無命中 → `shared/_unclassified/`，每次重掃 _unclassified → 補詞庫後自動畢業到主題夾）。搬移後當 session 不靜默、注入提示行——仿核心 `_sweep_realm_auto_migrate` + `REALM_AUTOMOVE_MARKER` 的 1-session-lag 慣例。
- [臨] `_unclassified` 命名安全關鍵：`_` 前綴**不在** sync-atom-index `EXCLUDED_DIR_PARTS`（=_drafts/_archived/_pending_review/_staging/templates/wisdom/episodic/_reference）內 → 落此夾的 atom **仍入索引/注入**（curated 知識不轉暗），`_` 只作視覺「待補詞庫」標記。若改用排除清單內名稱會讓 atom 靜默消失。

## 行動

- 專案要 shared atom 分層：寫 taxonomy classifier + 接 project_hooks session_start，勿動 core
- 判斷 atom 是否該分類：有 .access.json/已索引=curated 該分；_drafts/auto-capture 下=草稿不動
- 新增待分類夾務必確認名稱不在 sync-atom-index EXCLUDED_DIR_PARTS，否則 atom 會脫索引

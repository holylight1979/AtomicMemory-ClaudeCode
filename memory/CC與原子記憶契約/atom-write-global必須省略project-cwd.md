# atom-write-global必須省略project-cwd

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: atom_write, scope=global, project_cwd, force_global, global 寫入被拒
- Created-at: 2026-08-13
- Related: feedback-tooling-reliability, toolchain, memory-index-caption-regen, realm-範疇分區機制-v5

## 知識

- [臨]（2026-08-13 實證）atom_write `scope=global` 必須**省略 project_cwd 參數**：帶了必被「cwd inside project root」檢查拒寫。錯誤提示的 `force_global=true` 在 MCP schema 中不存在（參數被驗證層剝除）＝不可達 bypass，別重試。
- **How to apply:** 從專案 cwd 寫全域知識 → scope=global、不帶 project_cwd；直接 Write atom 檔會被 funnel 拒，不要繞。[[feedback-tooling-reliability]]
- [固] `mode=create` 另必給 `domain="<Lv1>[/<Lv2>]"`（Lv1 閉合清單見 `memory/_meta/taxonomy.json`；`vcs/git` 這類英文別名自動 snap 成 `版控/Git`）；feedback-* 標題的 domain＝失敗主題（落 `memory/Failures/<主題>/`）；scope=shared 同規則落 `shared/<Lv1>/`。缺 domain 直接拒並列全部 Lv1；不確定落點先 `dry_run=true`（跑完整條閘鏈、回預計路徑、不落檔）。append/replace 不需 domain（既有檔靠 index 定位）。

## 行動

- （依知識內容判斷）

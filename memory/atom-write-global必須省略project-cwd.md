# atom-write-global必須省略project-cwd

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: atom_write, scope=global, project_cwd, force_global, global 寫入被拒
- Created-at: 2026-08-13
- Related: feedback-tooling-reliability, toolchain

## 知識

- [臨]（2026-08-13 實證）atom_write `scope=global` 必須**省略 project_cwd 參數**：帶了必被「cwd inside project root」檢查拒寫。錯誤提示的 `force_global=true` 在 MCP schema 中不存在（參數被驗證層剝除）＝不可達 bypass，別重試。
- **How to apply:** 從專案 cwd 寫全域知識 → scope=global、不帶 project_cwd；直接 Write atom 檔會被 funnel 拒，不要繞。[[feedback-tooling-reliability]]

## 行動

- （依知識內容判斷）

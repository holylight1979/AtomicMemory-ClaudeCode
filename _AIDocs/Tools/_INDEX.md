# Tools — 工具與領域知識索引

> 跨專案工具操作知識、領域特定知識
> 最近更新：2026-05-28（V5 GA + Session α/β：feedback-* atoms 遷移到 `_AIDocs/Failures/` + `lib/atom_locations.py` 為 atom 物理位置單一規則來源）

---

## 文件清單

| # | 文件 | 說明 | keywords |
|---|------|------|----------|
| 1 | doc-index-system.md | 原子記憶系統全檔案索引（啟動鏈 + Hook 模組 + Skills + Tools + Memory + lib） | 記憶系統架構, 檔案結構, hook, skill, tool, lib, 記憶升級, 記憶迭代, 目錄結構 |
| 2 | excel-tools.md | Excel 讀取工具操作配方（openpyxl/xlrd） | Excel, xls, xlsx, 試算表, spreadsheet, openpyxl, xlrd |
| 3 | unity-yaml.md | Unity YAML Asset 序列化知識（fileID, GUID, PrefabInstance） | Unity YAML, fileID, GUID, PrefabInstance, .prefab, .meta, 型別ID, 序列化, Missing Script |
| 4 | unity-prefab-component-guids.md | SGI Client UI Component Script GUIDs 對照表 | prefab GUID, component GUID, m_Script, ILUIWnd GUID, UIButtonCustom GUID, EnhancedScroller GUID, UI component registry |
| 5 | unity-wndform-yaml-template.md | WndForm Prefab YAML 模板（RefDb, AutoGenUICode, Scroller stack） | WndForm template, prefab YAML, RefDb, AutoGenUICode, Scroller stack, Canvas template, prefab 建立 |
| 6 | unity-prefab-workflow.md | Prefab 程式化建立 SOP（generate-ui-prefab 流程） | prefab SOP, 程式化建立 prefab, generate-ui-prefab, WndForm 建立, 元件 stack, Console 警告 |
| 7 | bm25-global-layer.md | V5 全域 atom BM25 檢索層（取代 Vector daemon 殺雞用牛刀） | BM25, 全域檢索, atom 注入, char-bigram, k1, b, vector global_layer, V5 P5a |
| 8 | （補完候選） | atom-locations 設計（FAILURES_DIR + iter_atom_files_multi + failures_write_target，commit `89ccb2d`/Session β）— 暫由 [lib/atom_locations.py](../../lib/atom_locations.py) docstring + [SPEC_ATOM_V5 §2.1](../SPEC_ATOM_V5.md) 替代，未獨立文件化 | atom 位置, 路由, FAILURES_DIR, 多根掃描, single source of truth |
| 9 | hook-injection-probe.md | 用真 hook 進程驗 atom 注入效果的探針 SOP（SessionStart→UPS 順序、標記統計、判讀規則、最小腳本、清理與陷阱、injection-turns.jsonl 欄位、effect-report／followup-check 配套） | hook 探針, 實機驗證, workflow-guardian.py, UserPromptSubmit, SessionStart, additionalContext, Context budget, trim dropped, budget fallback, same-topic, injection-turns.jsonl, memory-effect-report, followup-check, 兄弟 state, _ensure_state |

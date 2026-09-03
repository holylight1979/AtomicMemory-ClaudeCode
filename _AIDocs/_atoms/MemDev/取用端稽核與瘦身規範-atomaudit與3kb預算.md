# 取用端稽核與瘦身規範-AtomAudit與3KB預算

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: AtomAudit, 取用端稽核, injection_log, 瘦身, knowledge budget, 大小預算, Status 行, cold 注入, budget skip, 一行路標
- Created-at: 2026-07-29
- Related: decisions-architecture, atom-edit-meta與atom-heal對專案層atom的缺口與繞法, feedback-原子記憶核心理念-知識經驗全積累分門別類-高精準零token浪費, 注入預算三教訓-裁切要回填-分級看token不看字元-橋接檔須隨索引重產

## 知識

- [臨] 肥大因果鏈實證：hot/cold 判定與大小無關（trigger 命中→恒 hot）；降一行的真兇是 per-turn 預算三態（TURN_BUDGET_LIMIT → ok/fallback/skip；值見 wg_core.py，須容得下約 3 顆中位數 atom 全文）——肥 atom 撞預算被 skip 成一行、沒人讀
- [臨] 取用端閉環：ups_inject 落 state.injection_log（name/path/source/form/turn_seq，cap 100）；Stop AtomAudit 閘只稽 source=trigger 且 form∈{skip,cold} 且非本 turn；consumed 用既有 accessed_files 回收線（不加 per-Read hook）；trigger 詞面全管線不留存，source=trigger 即「任務域吻合」等價訊號
- [臨] 防噪三件套：per-atom 每 session 一次（atom_audit_prompted）、同 turn 注入不催、沿用 stop_gate_max_blocks 第 3 次強制放行；config atom_audit.enabled 可關
- [臨] 瘦身：KNOWLEDGE_BUDGET_BYTES=3KB（lib/atom_spec，依據註於常數）；write-gate 排最前硬拒（explicit_user/pitfall 不豁免）＋落檔 floor（build/create_atom/append，skip_gate 繞不過）；append 以拼接後總量計；write_raw（episodic/failures）豁免、validate 不檢＝存量讀取不受影響
- [臨] Status 行：atom 選填 `- Status:` 現況（只寫現況、禁版本敘事）；cold/budget-skip 一行路標自帶 [Status: …]，hot/fallback 經 _FRONTMATTER_KEEP_RE 保留

## 行動

- 動 AtomAudit/瘦身閘前先讀 _AIDocs/Architecture.md Stop 列 + atom_write 節；verify 見 hooks/verify/verify_atom_consumption_audit.py + lib/verify/verify_knowledge_budget.py
- 改 mcp.js/atom-tools.js 後需重啟 MCP server 才生效

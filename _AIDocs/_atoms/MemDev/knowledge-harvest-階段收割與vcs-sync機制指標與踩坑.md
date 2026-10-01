# knowledge-harvest-階段收割與vcs-sync機制指標與踩坑

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: knowledge_harvest_report, KnowledgeHarvest, 收割, Harvest-Pending, atom_retire, supersedes, receipt, vcs-sync, vcs_sync, wg_harvest, wg_vcs_sync, push 守門, 記憶自動 commit, 退役 atom
- Created-at: 2026-10-01
- Related: anti-evasion-hud-設計脊柱與強化前必讀, 團隊產出上傳前先問人-記憶庫自動做滿, 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, 自動萃取層淨值審查-調整式拔除-2026-07, vcs-sync拉取側機制指標與踩坑-隔離worktree-recover持久化-新編輯保護-冷卻

## 知識

- [臨] **SoT 指標（先讀再改）**：閘與核對 `hooks/wg_harvest.py` + `hooks/handlers/stop.py`（KnowledgeHarvest／Harvest-Pending 插在 ScanReport 前）+ `hooks/handlers/post_tool_use.py`（receipt 入帳、items 核對、validated 後 spawn）；worker `hooks/wg_vcs_sync.py` + `hooks/vcs-sync-worker.py`；MCP `tools/workflow-guardian-mcp/lib/harvest.js`（knowledge_harvest_report 只回 chip）與 `atom-tools.js`（atom_retire、supersedes 三態、receipt 尾行）；py funnel `lib/atom_io.check_supersedes`、`lib/atom_io_cli` action retire／check_supersedes、`tools/memory-audit.delete_atom`。行為權威在 TECH.md §6.3／§6.4／§7.1／§12。
- [臨] **收割核對只信 receipt**：`resolve_atom_path` 只掃全域層、`exists()` 驗不出 append 與索引失敗（`atom_io_cli` 索引失敗仍 ok=True）；所以 atom_write／atom_retire 結果最後一行 `receipt: {json}` 由 PostToolUse 記進 `state.atom_ops[sid]`，收割 items 逐項對 receipt（op、path、index_ok；superseded 看 receipt.supersedes；retired 看 old_path），窗口是 `seq > last_valid_op_seq`。
- [臨] **worker 兩條硬規則的由來**：① 不用 GIT_INDEX_FILE 暫存 index 動目前分支——commit 後真 index 相對新 HEAD 會出現反向 staged（新 atom 變 staged deletion），別的 session 一般 commit 會把記憶撤回；改成 `git add -A -- <記憶 pathspec>` + `git commit -- <pathspec>`。② push 守門——`rev-list @{u}..HEAD` 任一 commit 碰到記憶路徑以外的檔就不推（否則會把未上 GIT 的程式碼一起發布）。
- [臨] **退役順序固定**：①護欄（找不到／[固]／核心保護含 import 失敗／被 Related+Supersedes 引用含 personal 層）②向量③Related 清理④索引與 MEMORY.md⑤最後才搬 `_distant/`；①–④ 冪等，任一失敗停在原位、回 ok=False 帶 steps，重跑從頭即可。svn 的舊路徑 delete 只依 retire receipt 的 old_path，其他 `!` 不動。
- [臨] **坑**：Python hook 即時生效，但 Node 面（新 tool、receipt 尾行）要 Reload Window 後才存在——改完當 session 會看到 KnowledgeHarvest 閘要求呼叫一個尚不存在的 tool，屬預期；閘的觸發沿用 claims_completion 詞表，對「待補做／收尾」類中途訊息也會命中，一 turn 只擋一次、不吃共用預算。
- [臨] **Supersedes 三態**：atom_write 未給＝replace 保留原行（js 讀舊檔回填，不重驗）；`[]`＝清除；非空＝替換並經 py `check_supersedes`（可解析／非自指／沿鏈無循環／非核心保護名）。缺省時 py↔js buildAtomContent 輸出 byte 不變（parity test_28）。

## 行動

- 改收割閘或 worker 前先讀本顆 + TECH.md §6.3／§7.1 + wg_harvest.py／wg_vcs_sync.py 檔頭
- 改 MCP js 後要 Reload Window 才能 dogfood；本 session 只能跑 `tools/workflow-guardian-mcp/verify/smoke_mcp_stdio.js`（隔離埠）
- worker 行為異常先看 `Logs/vcs-sync.log` 與 `workflow/vcs-sync/<hash>.unpushed`，再看 `roots.json`

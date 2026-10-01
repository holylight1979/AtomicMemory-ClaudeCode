# org-memory-init-必種一顆工具卡-sync-memory-index對空索引exit1

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: org-memory, 公司層記憶, org_memory, scope=org, 空索引 exit 1, sync-memory-index --check
- Created-at: 2026-10-01

## 知識

- [臨] tools/sync-memory-index.py 對 `_atom_index.json` 空或缺一律 exit 1（在專案模式分流之前就 return 1），所以 org-memory.py --init 必須先種一顆 atom（shared/工具/org-memory.md 工具卡）再呼叫 --write，否則 --check 永遠紅。
- [臨] 公司層（org）＝config org_memory.roots[0] 那個專案根的 shared 層：py 寫入端零改，js atom_write/atom_retire 把 scope=org 改寫成 scope=shared + project_cwd=org_root；候選池 org 組由 wg_core.org_memory_root() 單一來源讀 config（roots >1、缺鍵、空 → None 且 stderr 一行）。
- [臨] org 根要寫 .claude/project-tree.json {"standalone": true}，否則底下子專案往上尋根會把 org 根當候選祖先。

## 行動

- 改 sync-memory-index 空索引行為前先看 org-memory.py --init 的種子邏輯，兩邊同步
- org 落點實測一律用 tmp 目錄 git init 跑 --init，測完把 config org_memory 回 enabled=false、registry 刪 tmp 條目

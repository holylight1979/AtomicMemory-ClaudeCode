# Realm 範疇分區機制 (V5+)

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: realm, 範疇分區, 核心非核心, local atom, _AIDocs/_atoms, 注入閘門, atom 物理位置, promote fallback, wg_core bootstrap, 記憶系統
- Created-at: 2026-06-03
- Related: decisions-architecture, feedback-workflow-discipline, 腦內世界-環境演化-放置式架構

## 知識

- [臨] Realm（核心 vs 非核心）由 index path 前綴 `_AIDocs/_atoms/` **推導**，不存欄位/不寫 frontmatter/免 heal；與 Scope 正交，local atom 仍 `Scope=global`。核心住 memory/、全專案注入；local 住 `_AIDocs/_atoms/<domain>/`（World/Tools/MemDev），只在 cwd∈~/.claude 注入。
- [臨] 沿用 feedback-* 既有機制：物理檔在 `_AIDocs/` 下、靠 `_atom_index.json` 的 path（base_dir=CLAUDE_DIR join）被讀出注入；`_AIDocs/_atoms/` 與 feedback 的 `_AIDocs/Failures/` 不同前綴、零衝突。零新管線。
- [臨] 注入閘門（範疇限定）落在 SessionStart 建候選快取處依 cwd 過濾 path 前綴，**非** user_prompt_submit 注入迴圈（候選只在 SessionStart 建一次，迴圈只讀快取）。
- [臨] 坑（S1 已踩中並修）：物理在 memory/ 外的 atom（Failures / _atoms）必須在 server.js promote/edit_meta/find 加 `findAtomFileRecursive(LOCAL_ATOMS_DIR, ...)` find-fallback（鏡像 feedback fallback），否則 scope=global 的 local atom 會 `Atom not found`。
- [臨] 坑：wg_core 的 `CLAUDE_DIR` 必須**本地定義**（它用來 `sys.path.insert` 定位 lib/atom_locations 本身），不可改成 `from atom_locations import CLAUDE_DIR`（雞與蛋）。MEMORY_DIR 同源同值、改 import 只增 fallback 脆弱性、零實益。
- [臨] 坑：搬遷工具 atom-set-realm（Phase 3）必須連 `.access.json` sidecar 一起原子性搬，否則 confirmations/usefulness 計數歸零、[固] 可能掉回 [臨]。
- [臨] 分類器硬規則：核心保護清單（decisions*/workflow-*/toolchain*/preferences/feedback-*/atom-*）強制 core；**絕不靠 `_AIDocs/` 路徑前綴判 local**（feedback-* 就在 _AIDocs 卻是 core）。py↔js 常數對拍見 lib/verify test_14。

## 行動

- 新 local 知識：atom_write 帶 realm=local + domain（需 MCP server 重啟生效）
- 改任何 atom 物理位置：同步 server.js promote/edit_meta/find 的 fallback + 連 .access.json 搬
- 完整機制/文件同步在 Phase 4；本顆為 S1 種子 [臨]，Phase 4 擴充並決定是否歸 MemDev-local

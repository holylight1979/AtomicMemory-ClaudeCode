# 子專案cwd歸核心根層-project-tree雙向宣告-無宣告零行為變化-hook只讀不寫

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 專案根, 子專案, project-tree, project_root, find_project_root, 尋根, subs, root_abs, standalone, ProjectRoot, 宣告檔, claim, pick, 認領, 根層記憶, 分叉
- Status: 已上線 2026-09-05；本機 C:\TSLG 首例落地中
- Created-at: 2026-09-05
- Related: 路徑解析函式的根層分支是遷移盲點-cwd在claude根時專案分支會長出舊址, realm-範疇分區機制-v5, atom-scope-讀取端可見性-候選池一次收窄-他專案不進池-personal只給本人

## 知識

- [臨] 「記憶要歸哪個根」單一來源 `lib/project_root.py::resolve_project_root(cwd)`；`wg_core.find_project_root`（找不到回 Path(cwd)）與 `atom_io._find_project_root`（回 None、先 resolve cwd）都只是委派。四份 has_marker 複本已集中 `has_project_marker`（四標記 ∪ 有效宣告檔）。
- [臨] 宣告檔 `{X}/.claude/project-tree.json`：根層 `subs`（相對前綴，`*` 全部）、子層 `root`（只准指祖先）、`root_abs`（本機絕對，目錄存在才優先、不存在忽略）、`standalone`（停止向上、不提問）。優先序：standalone → 本層 root → 本層即根(self) → 祖先 subs → 舊規則 nearest。**沒有任何宣告時行為與舊碼逐案等值**（回歸鎖 `test_T_no_declaration_equals_legacy`）。
- [臨] 路徑規則一條：沿字面路徑（absolute+normpath）往上走、比對時才 resolve、回傳保持字面（junction／8.3／大小寫靠 resolve 後 Path 元件比對）。排除集合 {家目錄, ~/.claude, 磁碟根} 套在 walk 層、root 候選、fallback 三處——家目錄的 `.claude/memory/MEMORY.md` 也符合標記，不排除會把 ~/Downloads 的 session 判成家目錄專案、shared 寫進全域 memory/shared。
- [臨] 三個曾被 Codex 抓到的設計坑：①`cwd == 宣告層` 若先判 self 會吞掉本層 root（開在 `C:\TSLG\Server` 被判成自己）→ 本層 root 先於 self；②壞 JSON 若算標記就不等於「無檔」→ 三態（無／有效／無效只警告）；③宣告認領但根層 memory 尚未 pull 時 `get_project_memory_dir` 回 None → failures/staging 落全域 → 宣告認領一律回 `root/.claude/memory`（可不存在，寫者 mkdir parents）。
- [臨] resume/compact 沿用舊 state 的前提是 `atom_index.project_root_fingerprint`（cwd＋沿途宣告檔 mtime＋根）相同；不符走重建分支並照搬 modified_files／knowledge_queue 等脈絡。只重印宣告行不重建 = 提示說歸 TSLG、注入仍走舊根。
- [臨] 鐵律：hook 只讀宣告檔（`test_hooks_never_write_declaration` 餵三事件比 mtime）；增刪改只在 `tools/project-tree.py`；推斷出的候選根只用來 ❓ 提問（AskUserQuestion 四選一），不自動認領。視窗（tkinter askdirectory）只由 `pick` 子命令彈，不放 hook 裡（20 秒逾時、headless、每 session 干擾）。
- [臨] 實地事實：`C:\TSLG` 是 SVN WC、`svn:ignore` 含 Client Server Tools（各自獨立 WC）；`C:\TSLG\Server\.gitignore` 把整個 `.claude/` 排除在本地 git overlay 外——宣告檔要靠 SVN 帶到同事機器。

## 行動

- 改任何依 cwd 解析目錄的函式：測外部專案／非專案目錄／~/.claude 本身與子目錄／家目錄直下 四種 cwd，並跑 hooks/verify/verify_project_root_claim.py
- 同事開在子專案看不到根層記憶：先 `python ~/.claude/tools/project-tree.py explain <cwd>` 看 claimed_by 與 warnings，再決定 claim / add-sub
- 看到 ⚠️ 分叉 N 顆：inventory → atom_move dry_run → 搬 → 其餘進 quarantine，不直接刪

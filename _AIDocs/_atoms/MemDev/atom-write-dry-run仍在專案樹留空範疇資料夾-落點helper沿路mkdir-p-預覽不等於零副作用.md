# atom-write-dry-run仍在專案樹留空範疇資料夾-落點helper沿路mkdir-p-預覽不等於零副作用

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: dry_run, dry-run, 空目錄, 空資料夾, mkdir, _resolve_target, 落點預覽, 副作用, svn status 多了資料夾, 預覽不落檔
- Status: 已修（lib/atom_io._resolve_target create_dirs）＋回歸測試；待上 GIT
- Created-at: 2026-09-07
- Related: 子專案cwd歸核心根層-project-tree雙向宣告-無宣告零行為變化-hook只讀不寫, 驗證腳本判準要錨結果句不能錨系統有反應-catch-all關鍵字等於自動通過

## 知識

- [臨] 始末：2026-09-05 在 C:\TSLG\Server\scripts 用 `atom_write dry_run=true` 驗證 shared 落點，回報「nothing written」，但兩天後 svn status 在 `C:\TSLG\.claude\memory\shared\` 多了一個空的 `工作流` 資料夾（mtime 正是 dry_run 那刻）。正解：`_resolve_target(create_dirs=False)` 在 dry_run 時算完落點，把途中新建的空目錄收回；空殼已手動 rmdir。
- [臨] 根因：`write_atom` 的 dry_run 判斷在落點解析**之後**（先 `_resolve_target` 再 `if dry_run: return`），而落點解析沿路呼叫的 `project_category_target`／`project_subdir_target`／`failures_write_target`／`core_write_target`／`local_write_target` 五個 helper 都 `mkdir(parents=True)`——「算路徑」和「建目錄」綑在同一步，預覽自然有副作用。我在做落點驗證時只看回報訊息，沒去看檔案系統。
- [臨] 設計原理：helper 們 mkdir-p 是為了讓真正寫入時 `write_text` 不用再管父目錄存在與否（一路 mkdir 到底、寫入端零判斷）；`_resolve_target` docstring 也自述「唯讀；只 mkdir 落點」，把 mkdir 當成無害。dry_run 是後來加的預覽功能，沒回頭檢視這個假設。
- [臨] 運作邏輯：`write_atom(dry_run=True)` → `_resolve_target` → helper mkdir-p 建出 `<root>/.claude/memory/shared/<Lv1>/`（此時目錄已落地）→ 回 `dir` → `if dry_run: return WriteResult(ok, path=預計路徑)`。斷點在第二步：目錄已建、回報卻說 nothing written。在專案樹（進版控）上尤其明顯——svn/git 立刻多一個未版控資料夾。
- [臨] 修法取捨：沒把 create_dirs 一路傳進五個 helper（改動面大、每個都要加參數），改在 `_resolve_target` 外包一層：dry_run 時先快照 GLOBAL_MEMORY_DIR／`_AIDocs/_atoms`／專案 `.claude` 底下的目錄集合，跑完把新增的目錄由深到淺 `rmdir`（只刪空的，非空 rmdir 失敗即略過）。回歸測試 `verify_project_root_claim.py::test_dry_run_from_sub_lands_at_root_without_creating_dirs`。
- [臨] 防再犯：任何「預覽／dry_run／--check」路徑驗收時，判準要加一條「檔案系統前後 diff 為空」（tmp 樹上 `rglob` 前後比對），不能只錨回報文字；在版控樹上跑預覽後順手 `svn status`／`git status` 看一眼。設計上凡「算路徑」的函式若順手 mkdir，要在 docstring 標明是副作用、不是唯讀。

## 行動

- 驗 dry_run／預覽功能：tmp 樹上 rglob 前後 diff 必為空，並在版控樹上跑一次 status 看有無新目錄
- 新增會 mkdir 的路徑 helper 時：docstring 標「有副作用」，並確認所有 dry_run 呼叫端有 create_dirs=False 或事後收回

# 多機記憶同步：索引三檔的合併防線（AI 讀）

> 讀者：在任一 repo／工作副本（根層 `~/.claude`、專案 `{proj}/.claude/memory`，git 或 SVN）遇到合併、衝突、行尾問題的 CC session。人讀版在 `README.md`「多台電腦／多人同時寫記憶」。
> 程式真源：`tools/merge-atom-index.py`、`tools/normalize-eol.py`（`auto_project_eol`）、`tools/sync-memory-index.py::_auto_project_eol`、`hooks/handlers/pre_tool_use.py::check_merge_driver`、`hooks/handlers/session_start.py::_index_conflict_advisory`、`hooks/wg_core.py::find_vcs_root／memory_dir_candidates`、`lib/atom_io.py::write_text_lf`。本檔只講契約與 SOP，實作以碼為準。

## 名詞速查

| 名詞 | 白話 |
|---|---|
| 索引三檔 | `MEMORY.md`（範疇計數表）、`_ATOM_INDEX.md`（表列 mirror）、`_atom_index.json`（機器源）。一列一 atom 的集合，不是文章 |
| 根層衍生索引檔 | 只有 `~/.claude` 有：各層 `_INDEX.md`（`memory/<範疇>/**`、`_AIDocs/_atoms/**`；`\| Atom \| 說明 \|` 列表＋可選 `\| 子層 \| atom 數 \|` 計數表）與 `memory/_local_catalog.md`（`\| 範疇根 \| atom 數 \|` 計數表），都由 `sync-memory-index --write` 產生。兩人同範疇各加一顆就在同區塊各多一列——同一驅動以「表格文件」語意合（列表以第 0 欄為鍵聯集、計數表 o＋t−b、骨架文字逐行三方），根層 `.gitattributes` 綁定 |
| merge driver（驅動） | git 合併某類檔案時改叫的外部程式。註冊名 `atomindex`，在 git 的 **global config**（機器級），靠 `.gitattributes`／全域 attributes 的 `merge=atomindex` 綁到檔案 |
| stage | git index 在衝突時對同一路徑保留的三份版本：`:1` base（共同祖先）、`:2` HEAD 側、`:3` 對方側。`git ls-files -u` 列出仍未合併的 stage；**衝突是否解除看 index 有無 unmerged stage，不看工作樹有無 `<<<<<<<`** |
| ours／theirs | git 術語：ours＝`:2`＝目前 HEAD；theirs＝`:3`。rebase 時方向反直覺，見「stage 方向矩陣」 |
| resolve（備案） | `merge-atom-index.py --resolve`：git 已停在衝突後，把同一套語意驅動套在三檔的 stage 上，寫回工作樹並 `git add` |
| 語意三方 | 不是逐行比對，而是把索引當集合：JSON 以 `path` 為 key 逐條合、triggers 聯集、一側刪一側改留改的；`_ATOM_INDEX.md` 表列同鍵；`MEMORY.md` 範疇計數 = ours + theirs − base；表外手寫文字仍走 `git merge-file` 逐行三方 |
| SVN 衝突來源檔 | `svn update` 停在文字衝突時留下的 `X.mine`（更新前自己的工作版＝ours）、`X.r舊`（base）、`X.r新`（theirs）；三個絕對路徑由 `svn info --xml` 的 `<conflict type="text">` 給出（`prev-wc-file`／`prev-base-file`／`cur-base-file`），不猜檔名；`svn resolve --accept working` 後自動刪除 |
| memory dir 候選 | SVN 分支只掃這些目錄、不掃整個工作副本（大 WC 的 `svn status` 要 3～6 秒）：cwd 往上到 WC 根每層的 `.claude/memory`、WC 根的根層佈局 `memory/`（須有 `_atom_index.json`）、登記專案中位於 WC 根之下者（`wg_core.memory_dir_candidates`） |

## 目的與問題

- 兩台機器各自新增 atom 後 `git pull --rebase`／merge：atom 本體是各自的新檔，不衝突；索引三檔在同一區塊各加一列，git 逐行三方必衝突。
- 第二型：某一側索引檔被寫成 CRLF，每行都算改過 → 整檔衝突（2800 行）。來源是寫檔工具沿用平台預設換行、或 CC session 手寫 JSON 解衝突。
- 目標：團隊每個人只要 checkout 含本版，索引三檔的合併全自動（git 與 SVN 專案都是）；人與 CC 只在「手寫段兩側同改」時介入。專案記憶樹的行尾也全自動，不靠任何人到專案 session 貼 prompt。

## 三層防線

| 層 | 在哪 | 何時觸發 | 怎麼驗 |
|---|---|---|---|
| 1. 行尾全 LF | 根層 `.gitattributes`（`* text=auto eol=lf` + `*.md *.py *.js *.json *.jsonl *.sh *.ps1 *.txt *.ini *.toml *.yaml *.yml text eol=lf`）、`.editorconfig`（`end_of_line=lf`）；寫檔漏斗 `lib.atom_io.write_text_lf()`／`normalize_lf()`，其餘寫檔點 `newline="\n"`。**專案記憶樹**：`tools/sync-memory-index.py` 專案模式 `--write` 成功（含 up to date）後呼叫 `normalize-eol.auto_project_eol(mem)`——樹內轉 LF，git 專案在 `.gitattributes` 寫入標記區塊（`.claude/memory/** text eol=lf`＋索引三檔 `merge=atomindex`），svn 專案對已版控文字檔 `svn propset svn:eol-style LF`（已 LF 略過，冪等）；config `eol.auto_normalize_project`（預設 true）、`--no-eol` | 每次 git add／checkout（porcelain）；每次工具寫檔；專案樹＝每次 atom 寫入（`funnel.js syncMemoryIndex` 背景觸發 `--write`）之後，第一次動整棵樹、之後為零，改動跟著下一次記憶提交走 | 來源 lint：`hooks/verify/verify_lf_writes.py`（AST 掃文字模式寫檔無 `newline=""`／`"\n"` 且無 `# lf-exempt:` 即 FAIL；`**kwargs` 不通行）。結果守衛：`python tools/normalize-eol.py --root --check`（index blob 與工作樹殘留 CRLF／mixed 即 exit 1，含 dirty／untracked 列報）；health-weekly 併入黃燈 |
| 2. 合併驅動 | `tools/merge-atom-index.py` 註冊為 git merge driver `atomindex`：global git config `merge.atomindex.driver` + `~/.config/git/attributes`（`**/.claude/memory/{三檔} merge=atomindex text eol=lf`）；根層 repo 另有自帶 `.gitattributes`：三檔＋根層衍生索引檔（`memory/**/_INDEX.md`、`_AIDocs/_atoms/**/_INDEX.md`、`memory/_local_catalog.md`） | git 合併三檔時由 git 自己呼叫（merge／rebase／cherry-pick／stash pop 都走）。**自動安裝**：PreToolUse `check_merge_driver` 在 CC 的 Bash/PowerShell 段含 `git pull|merge|rebase|cherry-pick|stash pop|stash apply` 前呼叫 `is_installed()`，任一項不成立 → `--install --quiet` → `[Guardian:MergeDriver] 已自動安裝索引三檔合併驅動` | `python tools/merge-atom-index.py --status` 末行「已安裝」；`tools/verify/verify_merge_atom_index.py`（純函式＋真 git merge/rebase 零衝突＋無驅動對照組必衝突＋`--install` 冪等＋`--resolve` e2e） |
| 3. resolve 備案 | 同一支 `merge-atom-index.py --resolve` | git 已停在衝突（驅動沒裝、或衝突發生在裝好之前）。**自動觸發**：PreToolUse 段含 `git rebase --continue|merge --continue|cherry-pick --continue|commit|stash pop|stash apply` 且 `git ls-files -u` 有索引三檔 → `--resolve --cwd <repo> --quiet` → `[Guardian:IndexConflict] 已自動合併並 add 索引檔：…`／`已 stage 你解好的版本：…`／`⚠ <error 或 remaining> → 手動 python ~/.claude/tools/merge-atom-index.py --resolve`。SessionStart `_index_conflict_advisory`：repo 卡在 rebase/merge/cherry-pick 且三檔未合併 → 一行提示。**SVN**（沒有驅動可裝，只有這條備案）：段含 `svn commit|ci|resolve|resolved`（`--accept mine-full/theirs-full/base/…` 明確選邊除外）→ 純檔案系統往上找 `.svn`（不是 svn WC → 零子行程）→ 只對 memory dir 候選跑 `svn status --xml`，有 conflicted 索引三檔 → 同一支 `--resolve --cwd <cwd> --quiet`（拿 `.mine`／`.r舊`／`.r新` 跑同一套驅動、寫回、`svn resolve --accept working`）→ `[Guardian:IndexConflict] 已自動合併並 標記 resolved 索引檔：…`。`svn update` 不觸發；SessionStart 對 svn WC 看 memory dir 有無 `<檔>.mine`（零子行程） | `hooks/verify/verify_merge_driver_gate.py`（拆段分類、真 git 題、svn 拆段／觸發詞／非 svn WC 零子行程／svnadmin 本地倉 e2e／預算、`auto_*:false` 不動作、子行程卡死仍 fail-open 且總耗時 ≤2.5s）；`verify_merge_atom_index.py` e2e：無驅動 rebase 卡住 → `--resolve` → `GIT_EDITOR=true git rebase --continue` 成功；svn：兩個 wc 各加 atom → `svn up --accept postpone` 三檔 C → `--resolve` → `svn ci` 成功、另一 wc update 拿到合併結果 |

`is_installed(repo_cwd)` 四項全成立才算已裝：driver command 存在；command 引號內的直譯器與腳本路徑都存在；attributes 檔含 marker 行；目標 repo 對三檔 `git check-attr merge` 回 `atomindex`。任一不成立即重裝（`install()` 先寫 attributes 再寫 config，原子替換、保留既有內容；`pythonw.exe` 換成同目錄 `python.exe`）。

## config

`workflow/config.json` 頂層：

```json
"merge_driver": {
  "_doc": "索引三檔合併：合併類 git 指令前自動 --install；續行類指令前對未合併三檔自動 --resolve。hook 內 fail-open、總預算 2.5s。",
  "auto_install": true,
  "auto_resolve": true
}
```

- 缺鍵視為 true。兩旗標只影響 PreToolUse hook（git 與 svn 觸發都受 `auto_resolve` 管；`auto_install` 只對 git 有意義）；git 自己呼叫驅動、手動 CLI 不受影響。
- 關掉後仍可手動 `--install`／`--resolve`。

```json
"eol": {
  "_doc": "專案記憶樹換行自動統一 LF：sync-memory-index 專案模式 --write 後呼叫 normalize-eol.auto_project_eol。",
  "auto_normalize_project": true
}
```

- 缺鍵視為 true；`sync-memory-index.py --no-eol` 單次關閉。只影響專案模式（`<proj>/.claude/memory`）；根層 repo 由 `.gitattributes` 保證，不走這條。

## CLI 契約（`tools/merge-atom-index.py`）

| 形式 | 用途 | exit |
|---|---|---|
| `<base> <ours> <theirs> [<path>]` | git 呼叫的驅動本體；結果寫回 `<ours>`。依 `<path>` basename 分派：三檔各自語意；`_INDEX.md`／`_local_catalog.md` 走 `merge_table_doc`；其他逐行 | 0 乾淨；1 仍有衝突（含標記） |
| `--install [--quiet]` | 寫 attributes + global config | 0 成功；1 失敗（訊息含具體原因：非 UTF-8、不可寫…） |
| `--status` | 人讀自檢，末行「已安裝」／「未安裝」 | 0 已裝；1 未裝或失效 |
| `--resolve [--cwd <dir>] [--quiet]` | 依 cwd 最近的 VCS 根分流（`wg_core.find_vcs_root`，svn WC 住在 git repo 裡時取 svn）：git → 把驅動套在索引三檔的 unmerged stage 上；svn → 套在 `.mine`／`.r舊`／`.r新` 上並 `svn resolve --accept working` | 0＝三檔已無 unmerged stage／conflicted；1＝仍有殘留或錯誤（含「不在 git repo 或 svn 工作副本內」） |

`--quiet` 只抑制人讀 stderr；stdout／stderr 為 `None`（pythonw）時不崩。

`--resolve` stdout 單行 JSON：

```json
{"resolved": ["memory/_atom_index.json"], "staged_user_version": [], "skipped": [{"path": "...", "reason": "missing stage 3"}], "remaining": ["memory/MEMORY.md"], "installed": true, "error": null}
```

| 欄位 | 意思 |
|---|---|
| `resolved` | 語意驅動合成功、已寫回工作樹並 `git add`（svn：`svn resolve --accept working`） |
| `staged_user_version` | 工作樹已無標記且格式合法（JSON 可 parse／表頭與 key 唯一／MEMORY 目錄表在）→ 直接 `git add` 使用者版本（svn：直接標記 resolved） |
| `skipped` | 不處理並附原因：缺 `:2` 或 `:3`（一側刪檔，delete/modify）、路徑不在 `memory/` 或 `.claude/memory/`、`check-attr merge` 不是 `atomindex`；svn：非文字衝突或 `.mine/.rN` 已不在 |
| `remaining` | 仍是 unmerged：驅動殘留衝突（已寫回含標記結果、**不 add／不 resolve**）、工作樹有標記但不等於 git 原始衝突輸出（人解到一半，不碰；svn 無此判定，見下）、無標記但格式不合法 |
| `installed` | 順手跑 `install()` 的結果（svn 分支只回報 git 端現況，不嘗試安裝） |
| `error` | 非預期錯誤字串；否則 `null` |

`--resolve` 演算法（git）：`rev-parse --show-toplevel` 定根 → `git ls-files -u -z` 取 unmerged 路徑與實際存在的 stage → 篩三檔（basename ∈ 三檔、路徑白名單、check-attr）→ 三 stage 齊或 add/add（無 `:1` → base 空）→ 在 tmp 以 stage 重建 git 標準衝突輸出（`git merge-file -p`，標籤正規化）與工作樹 byte-compare → **相等**才以驅動結果覆蓋＋`git add`；不等的分流見上表。

`--resolve` 演算法（svn）：最近的 `.svn` 目錄為 WC 根 → memory dir 候選的 `svn status --xml`（`item="conflicted"` 且 basename ∈ 三檔、路徑白名單）→ 一次 `svn info --xml` 取每檔的 `.mine`／`.r舊`／`.r新` 絕對路徑（缺任一或非 text conflict → skipped）→ 同一套 `_driver_on_texts(base=.r舊, ours=.mine, theirs=.r新)` → 工作檔仍含 `<<<<<<<`（svn 原始輸出或驅動上一輪殘留）視為未動過：寫回，0 衝突進 resolved、否則 remaining；無標記：格式合法 → staged_user_version，否則 remaining → 最後一次 `svn resolve --accept working -- <resolved+staged>`。svn 只用 `--xml` 輸出（UTF-8；純文字輸出走 locale，非 ASCII 路徑會壞）。

## stage 方向矩陣（必看）

| 操作 | `:2`（HEAD／ours） | `:3`（theirs） | 白話 |
|---|---|---|---|
| `git merge` / `git pull`（merge 模式） | 自己的分支 | 被合進來的對方 | 直覺方向 |
| `git rebase` / `git pull --rebase` | **upstream／新基底（同事那邊）** | **正在重放的自己的 commit** | 反直覺：rebase 先站到對方基底上，再逐顆重放自己的 |
| `git cherry-pick` | 目前所在分支 | 被 pick 進來的那顆 commit | 同 rebase |
| `git stash pop` | 目前工作樹的 HEAD | stash 內容 | 沒有 `MERGE_HEAD`；只能靠 `ls-files -u` 判定 |

對語意三方本身方向不重要（計數 = ours + theirs − base 對稱、集合合併對稱）；只在看 `<<<<<<<` 標記決定手寫段留哪側時要用這張表。add/add 沒有 `:1`，base 視為空。

## 支援的 shell 語法（PreToolUse 拆段器 `_vcs_segments`；`_git_segments`／`_svn_segments` 為薄包裝）

- 認得：`git <sub> …`、`git.exe <sub>`（大小寫不拘）、`git -C <path> <sub>`（含引號路徑 `-C "C:\My Repo"`；相對路徑以 tool cwd 解析）、前置 `cd X && git …`／`cd X; git …`（決定 run_cwd）、`;`／`&&`／`||`／`|` 切段。svn 同法：`svn <sub>`、`svn.exe`、路徑尾綴，`--username/--password/--config-dir/--config-option` 帶值旗標跳過；觸發子命令 `commit|ci|resolve|resolved`。
- 不認得（hook 不動作、git 仍照 attributes 走驅動）：shell alias、shell function、PowerShell call operator（`& git …`）、包在 script 檔或 `bash -c` 字串裡的 git、`git` 不在段首的複合命令。
- 命中才起子行程：無合併類子命令的 Bash 呼叫零 git 子行程。

## Windows 約束

- hook 在 `pythonw.exe` 下跑：`sys.stdout`／`sys.stderr` 可能是 `None`，所有輸出走 `_out()` 類 helper；子行程一律 `capture_output`、UTF-8、`errors="replace"`、`creationflags=CREATE_NO_WINDOW`（否則閃 console 窗，守衛 `hooks/verify/verify_no_window_spawn.py`）。
- 時限：settings.json PreToolUse hook 預算 5 秒（整鏈共用）；`check_merge_driver` 總預算 2.5 秒，內部 `ls-files -u` 1s、`is_installed` 每次 git 呼叫 0.5s、`--install` 1.5s、`--resolve` 2.5s，帶絕對 deadline；逾時＝fail-open（放行、不出訊息、落 log）。
- 驅動 command 內的直譯器記絕對路徑；`pythonw.exe` 換成 `python.exe`（驅動要 stdout）。venv 內安裝取底層真 Python。
- `git check-attr` 與 attributes 路徑：`~/.config/git/attributes`（`core.attributesFile` 有設則依 git 規則對 home 解析）。

## 失敗模式與 SOP

| 症狀 | 原因 | 動作 |
|---|---|---|
| pull 後 git 停在索引三檔衝突，沒看到任何 `[Guardian:…]` 訊息 | 這台驅動未裝且這次 pull 不是在 CC 跑（Fork／裸終端），或 checkout 還是舊 hook | `python ~/.claude/tools/merge-atom-index.py --resolve --cwd <repo>` → `git rebase --continue`（或 `merge --continue`）。之後 `--status` 確認已裝 |
| 停在衝突，CC 下 `git rebase --continue` 看到 `[Guardian:IndexConflict] 已自動合併並 add 索引檔` 但 git 仍報衝突 | 還有**非索引檔**的衝突 | 照常處理其他檔；resolver 只碰三檔 |
| `⚠ … remaining: MEMORY.md` | 表外手寫段兩側同改；驅動已寫回含 `<<<<<<<` 的結果、沒 add | 開 `MEMORY.md` 看標記，依 stage 方向矩陣判斷留哪側或合寫；存檔後 `git add`，再 `--continue`。不做 `--prefer-head` 之類選邊 |
| `remaining` 且工作樹有標記、但內容不是 git 原始輸出 | 人（或上一輪 CC）解到一半 | resolver 不覆蓋。解完存檔 → 若已無標記，再跑一次 `--resolve` 會走 `staged_user_version`；或直接 `git add` |
| `skipped: missing stage 2/3` | 一側刪了索引檔（delete/modify） | 人判：通常留存在的那側 `git checkout --ours|--theirs -- <path>` 後 `git add`；再跑 `sync-atom-index`／`sync-memory-index` 重生（見手動最後手段） |
| `--status` 說「未安裝」但之前裝過 | 直譯器搬家／升級、attributes 檔被覆寫、`core.attributesFile` 改指別處 | `--install` 重跑（hook 下次合併類指令前也會自動重裝） |
| `normalize-eol.py --root --check` exit 1 | 某工具寫出 CRLF、或外部編輯器存成 CRLF | 看列報路徑：工具寫的 → 找該寫檔點補 `newline="\n"`／改走 `write_text_lf`，並跑 `verify_lf_writes`；手動存的 → `python tools/normalize-eol.py --root`（乾淨檔）或 `--include-dirty` |
| 專案 repo 索引三檔仍整檔衝突 | 專案記憶樹尚未釘 LF（該機 checkout 還沒在本版下寫過任何 atom，`.gitattributes` 區塊／`svn:eol-style` 尚未落下） | 正常路徑：下一次 atom 寫入後自動（`sync-memory-index` 專案模式）。想立刻做：`python ~/.claude/tools/normalize-eol.py --memory-dir <proj>/.claude/memory --auto` 後隨記憶一起提交 |
| TortoiseSVN／`svn update` 停在索引三檔衝突（狀態 C、留下 `.mine`／`.rN`） | 正常：SVN 沒有驅動可裝 | 回 CC 下 `svn commit`（hook 自動解並標記 resolved）；或手動 `python ~/.claude/tools/merge-atom-index.py --resolve --cwd <wc>` 再 `svn commit` |
| svn `--resolve` 回 `remaining` 且檔案仍含標記 | 表外手寫段兩側同改（驅動已寫回含標記結果、未 resolve、`.mine/.rN` 還在） | 開檔判斷後存檔（拿掉標記）→ 再跑 `--resolve`（無標記且格式合法會直接標記 resolved）或 `svn resolve --accept working <檔>` |
| `[sync-memory-index] eol normalize failed: …`（funnel crash log） | svn propset 被拒（混行尾檔：先轉再設，理論上不會；明列 unversioned：已先用 `svn status -v` 過濾）、`.gitattributes` 不可寫、check-attr 驗證失敗 | 看訊息尾巴；手動 `normalize-eol.py --memory-dir <mem> --auto` 重現 |
| `[Guardian:IndexConflict]` 在 SessionStart 出現 | 上個 session 留下未完成的 rebase/merge | 同第一列：`--resolve` → `--continue`；或 `git rebase --abort` 重來（驅動已裝就不會再停） |
| hook 沒動作、也沒訊息 | `merge_driver.auto_*` 為 false；或命令語法不在支援清單；或逾時 fail-open | `--status`／手動 `--resolve`；查 `Logs/` 對應 hook log |

## 手動最後手段（從磁碟重生索引）

驅動與 `--resolve` 都用不上（例如三檔全被人手改壞）時，接受工作樹當下的 atom 檔為真相重生索引——**只在 `rebase --continue` 之前、且工作樹已含兩側 atom** 時做，否則會丟另一側：

```bash
python ~/.claude/tools/sync-atom-index.py --memory-dir <dir> --add-from-frontmatter --fix-scope-from-path
python ~/.claude/tools/sync-memory-index.py --memory-dir <dir> --write
git add <三檔>
```

根層 `<dir>`＝`~/.claude/memory`（local 範疇另在 `_AIDocs/_atoms/`，`sync-memory-index.py --write` 不帶 `--memory-dir` 即兩根都重生）；專案 `<dir>`＝`{proj}/.claude/memory`。

## 自動拉取（vcs-sync worker 拉段）

程式：`hooks/wg_vcs_sync.py`（`_git_pull`／`_git_isolated_rebase`／`svn_update_targets`，檔頭「拉」段有設計理由）；觸發：SessionStart `handlers/session_start.py::_spawn_pull_sync`（讀索引前 spawn，`reason=pull`，不等）＋ worker 每輪 git 順序 commit → 拉 → push；開關 `workflow/config.json` `vcs_sync.pull.{enabled, fetch_timeout_s}`，與 `vcs_sync.push` 獨立。

流程（git）：
1. `fetch`（`fetch_timeout_s`）；失敗只落 `.behind`（理由 fetch 失敗），push 段照跑。
2. 一次固定 H（本地分支）／U（FETCH_HEAD），`behind`／`ahead` 用 rev-list 算；behind=0 → 清 `.behind` 結束。
3. incoming 逐 commit 分類：全部路徑在記憶 pathspec 內且不被 `vcs_sync.exclude` 才是「純記憶」（merge commit 一律非純）。
4. 三條路：
   - **ahead=0 ∧ 純記憶** → 「ref＋pathspec 同步」：記憶路徑乾淨才 `update-ref`（CAS）＋ `restore --source=U --staged --worktree -- <pathspecs>`；主工作樹只有記憶路徑的 index／工作樹被對齊，程式碼路徑零觸碰（用 restore 而非 `checkout U -- <pathspecs>`：checkout 不會刪上游已刪的檔）。
   - **ahead=0 ∧ 含程式碼** → 整樹乾淨（`status --porcelain -uno` 空）才 `merge --ff-only`（顯式關 `merge.autoStash`）。
   - **ahead>0（分叉）** → 本地 ahead 純記憶 ∧ incoming 純記憶 ∧ 記憶路徑乾淨才在**隔離暫時 worktree** `rebase U`（主工作樹不 rebase：鎖只互斥 worker、擋不住他 session 同時寫檔，autostash 也不是完整交易）；衝突迴圈有界（≤ ahead 次）、只接受 `check-attr merge=atomindex` 的索引檔並交 `merge-atom-index.py --resolve`（檢查返回碼／`error`／`remaining`／`ls-files -u`），任何其他衝突或 resolver 失敗 → `rebase --abort` + `worktree remove`。成功後主 repo 只 `update-ref`（CAS）＋記憶 pathspec restore。
5. 拉成功：向量增量索引（fail-open）＋ `sync-atom-index --check`（漂移只記 log）；roots.json `last_pull`／`pulled_commits`、`pull_error=None`；清 `.behind`。push 段**重新**取 H 再守門。

主工作樹寫入的三道保險：① `update-ref` 之前重驗 symbolic HEAD 仍在該分支且 HEAD==H（`_git_on_branch`），整合期間別人切了分支就放棄本輪；② `update-ref` 之前先落 `workflow/vcs-sync/<hash>.recover.json`（branch／from／to／pathspecs），restore 成功才刪——restore 中途失敗（index.lock 等）時下一輪 `_git_recover` 先重做 restore，做不成就本輪**不 commit、不 push**（否則會把「相對新 HEAD 缺的上游新檔」當本地刪除提交出去）；②-b restore 之前逐檔比對工作樹／index 與 from 樹及目標樹（`_git_new_edits`）：兩者皆不符＝有人在恢復或整合期間編輯了記憶檔 → 不覆蓋、保留 recover、`.behind` 留人；HEAD 已是目標的後代（別人又在同分支 commit）→ 改以 HEAD 為 restore 來源；③ 隔離 worktree 的建立與清理都在 try/finally，remove 重試、prune、驗證無殘留，殘留即 `.behind`。純 pull 請求有冷卻（`vcs_sync.pull.cooldown_s`，預設 600 秒）：記憶路徑無本地變更且上次拉取在冷卻內就跳過拉段；advisory 的「拉入 N 筆」靠 roots.json `pull_reported_at` 只報一次。

什麼情況留 `.behind`（`workflow/vcs-sync/<root-hash>.behind`，JSON `reason/at`；roots.json `pull_error` 同值；下個 SessionStart `_pull_advisory_lines` 浮出一行）→ 人手 `git pull --rebase`（三層防線接手索引三檔）：fetch 失敗／逾時；incoming 含程式碼 commit 且本地有未提交改動；分叉但本地 ahead 含程式碼 commit、或 incoming 含程式碼、或記憶路徑不乾淨；隔離 rebase 遇到索引檔以外的衝突（atom 本文兩側同改）或 resolver 解不開；CAS 失敗（整合期間分支被別人動了，本輪放棄）。`.behind` 與 push 側的 `.unpushed`／`last_error` 分欄、互不清除；請求 ack 只看 commit＋push 段。

svn（`svn_update_targets`，取代舊 out-of-date 重試）：先把 validated 退役且 `missing` 的檔 `svn delete`（schedule），其他 `missing` 存在 → 本輪不 update、`.behind`（理由列路徑；update 會把檔補回）；`svn update --accept postpone -- <memory paths>` 後 `status --xml` 看 text／property（`props`）／tree 衝突：只有索引三檔 text 衝突 → `--resolve --cwd`；其餘衝突 → `.behind` 並停止本輪（不 commit）。**mixed-revision 工作副本可接受**（只 update 記憶 pathspec）。

既定策略與限制：
- **索引 scalar 兩側異改取 ours**（`merge_scalar`：兩側同→取、單側改→取改的、異改→ours）；隔離 rebase 裡 ours＝上游（見「stage 方向矩陣」），所以 `MEMORY.md`／`_atom_index.json` 單值欄（caption、Confidence 等）兩機同改會無聲取上游值且 rebase 報成功——不改策略，撞到時以上游為準再補寫。
- **拉入的 atom 下一個 session 才進候選池**：候選池 SessionStart 建一次，advisory 只報「上次拉入 N 筆、候選池以本次載入快照為準」，不宣稱本 session 已載入；不做啟動時同步等待的快速路徑。
- 主工作樹的不可逆面只有 `update-ref`（CAS，reflog 可回）與記憶 pathspec restore；rebase 全在暫時 worktree，失敗即丟棄。
- `hooks/post-git-pull.sh`（post-merge 樣板）根層不裝：worker 已負責拉；它是專案 `shared/` 的 pull-audit，`/status` 讀 `index_job.running`，缺 `index_job`／服務不可達／`index_job.error` 各自提早結束。
- 驗證：`hooks/verify/verify_vcs_sync_worker.py`（純記憶 ff 在髒程式碼樹成功且程式碼檔未動、含程式碼 incoming 髒樹 → 標記、分叉純記憶隔離 rebase 且主樹其他 staged 檔原封不動、索引三檔衝突自動解、atom 本文衝突 → abort＋標記＋tmp worktree 清掉、fetch timeout → 標記且 push 段仍跑、svn retired missing 先 delete 再 update、其他 missing 不 update、property conflict 判定）。

## 不在保證範圍

- **尚未 pull 到含本版 hook 的 checkout**：帶來新 hook 的那次 pull 跑的還是舊 hook。上線一次性步驟：`cd ~/.claude && git pull` 後跑一次 `python tools/merge-atom-index.py --install`；那次 pull 若本身卡在三檔，`--resolve` 可解。
- **CC 以外的 pull**（Fork、裸終端）：驅動裝好前會停一次；裝好後 Fork 也受益（驅動在 git 本身的 global config）。不為 Fork 另補自動安裝。vcs-sync worker 的隔離 rebase 不依賴驅動是否已裝（直接呼叫 resolver）。
- **git plumbing 寫入**（`hash-object`／`update-index` 直寫 blob）繞過 `.gitattributes` 正規化。
- **他機 repo-local attributes 覆寫**：`.git/info/attributes` 或更靠近檔案的 `.gitattributes` 可以蓋掉 `merge=atomindex`／`eol=lf`；只能靠 `--status`／`normalize-eol --check` 事後發現。
- **第三方程式寫檔**、**沒有 CI／伺服器端檢查**：LF 保證是本機層（守衛＋巡檢），不是遠端強制。
- **只處理索引三檔與根層衍生索引檔**的 unmerged stage／conflicted；atom 本體或其他檔的衝突仍由人／CC 處理。已知仍會逐行衝突的兩型：**同一顆 atom 兩機各 append**（知識行都加在檔尾）、`memory/_meta/*-learned.json` 自動學習檔兩機同時更新——目前頻率低，撞到再做。
- **SVN 的 `svn update` 本身不自動解**：client 端只有全域 `diff3-cmd` 外掛，會套到所有檔且 TortoiseSVN 未必吃，風險大；只在 CC 下 `svn commit|ci|resolve` 前解。update 停在衝突屬正常。
- **SVN 只掃 memory dir 候選**（walk-up `.claude/memory`、WC 根的 `memory/`、登記專案）：記憶樹放在候選之外的位置不會被看到（手動 `--resolve --cwd <該 memory dir>` 可解）。
- **SVN 沒有 stage 可重建原始衝突輸出**：工作檔仍含 `<<<<<<<` 就視為未動過並覆蓋——人解到一半又留著標記的版本會被驅動結果蓋掉（git 分支會辨識、svn 不會）。解到一半請先把標記清乾淨再下 `svn commit`。
- **SVN tree／property conflict** 不處理（只認 `<conflict type="text">`）。
- **TortoiseSVN 留下的衝突檔命名未實測**（CLI 為 `.mine/.rN`）；實作路徑取自 `svn info --xml`，不依賴檔名，理論上同樣可解。
- **`svn:eol-style` 只設在已版控檔上**：剛寫入、尚未 `svn add` 的 atom 在下一次記憶寫入時補上（樹內轉 LF 不受此限）。
- 專案樹 LF 自動化只在**專案模式 `--write` 走到**時發生：第一次啟用本版後要有一次 atom 寫入（或手動 `--auto`）才會落 `.gitattributes`／屬性。

## 設計取捨

- **為何不在 driver 內從磁碟重掃**：driver 執行當下工作樹只有 HEAD 那側的 atom 檔（merge 缺對方新檔、rebase 缺自己的新檔；`verify_merge_atom_index.py` 有時機實測），重掃會把另一側 atom 從索引弄丟。三份 blob 已含全部資訊，零磁碟副作用、根層專案層通用。
- **為何 B 用 stage 而非「取 HEAD 版＋重生」**：stage 三份就是驅動的輸入，同一套語意合併、不丟另一側索引級編輯（例如 triggers 改動）、不在 hook 內跑 sync 工具（時限與副作用都省）；重生留作手動最後手段。
- **為何不選邊**（無 `--prefer-head`）：殘留只會是手寫段兩側同改，量少且需要看內容；自動選邊等於無聲丟一側文字。留標記、不 add、fail-visible，交正在 pull 的 CC session 判斷。
- **為何自動安裝放合併類指令前而不放 SessionStart**：只在會用到的時刻付成本（2 個 git 呼叫＋stat），無合併的 session 零子行程；且解衝突時同一 hook 順手裝，不必兩處維護。
- **為何 hook 只 warn 不 deny**：resolver 失敗的正確反應是讓 git 自己報衝突、人來看，不是擋住命令；閘排在隱私閘之前，讓隱私檢查看到 resolver 之後的 staged 集合。
- **為何 `git add` 不觸發 resolve**：使用者自己 `git add` 索引檔＝告訴 git 已解，此時 B 多餘。
- **為何全 repo LF 而非只釘三檔**：混合行尾的來源是寫檔工具的平台預設，只釘三檔擋不住下一個被寫成 CRLF 的檔；統一規則後 `--check` 一條命令就能巡完。
- **為何專案樹 LF 掛在 atom 寫入漏斗尾端而不是 pull 前或 SessionStart**：pull 前製造未提交變更會讓 `git pull --rebase` 拒絕（unstaged changes）；SessionStart 每次都付成本且與「合併時才需要」無關；掛在寫入後，第一次動整棵樹、之後為零，改動跟著本來就要提交的記憶批次走，使用者零動作。
- **為何 SVN 用 `svn info --xml` 取三份輸入而不猜 `.rN` 檔名**：版號不需解析、TortoiseSVN 或未來 svn 版本改命名也不受影響；一次呼叫可帶多個 target，仍在 hook 預算內（實測 memory dir 的 status 0.2s＋info 0.2s＋resolve 0.1s）。
- **為何 SVN 只掃 memory dir 候選**：`svn status` 對整個工作副本是 O(檔數)，本機 d:\MyDev 要 5.6 秒、c:\Projects\Tools 2.9 秒，直接爆掉 2.5 秒預算；索引三檔只會在記憶樹裡。

## 驗證方法

- 自動：`python run_verify.py` 收集 `tools/verify/verify_merge_atom_index.py`（驅動純函式、真 git merge/rebase/cherry-pick、add/add、delete/modify skipped、其他 U 檔保留、人解一半不覆蓋、無標記合法版本被 stage、根層佈局、同名非記憶檔不碰、`--install` 冪等）、`tools/verify/verify_normalize_eol.py`（CRLF／mixed／BOM／NUL／孤立 `\r`；dirty 跳過但 `--check` 列報；`--write-gitattributes` 重跑 byte-identical）、`hooks/verify/verify_lf_writes.py`、`hooks/verify/verify_merge_driver_gate.py`（quoted `-C`、`cd x; git pull`、`git.exe rebase --continue`、`git status` 不觸發、PowerShell 觸發、`auto_*:false`、子行程卡死 fail-open ≤2.5s、resolver stage 後隱私閘仍能 deny）。
- 實機探針（隔離 `GIT_CONFIG_GLOBAL`／`XDG_CONFIG_HOME` 指到 tmp）：
  1. tmp repo 兩個 clone 各加一顆 atom 並改索引三檔 → 一側 push、另一側 `git pull --rebase` 停在衝突（對照組，證明無驅動必衝突）。
  2. 用真 hook 進程餵 PreToolUse JSON（`tool_name=Bash`，`command="git pull --rebase"`）→ 期待 `[Guardian:MergeDriver]` 且 tmp global config 出現 `merge.atomindex`。
  3. 餵 `command="git rebase --continue"` → 期待 `[Guardian:IndexConflict] 已自動合併並 add`，`git ls-files -u` 為空，`GIT_EDITOR=true git rebase --continue` 成功、`git status` 乾淨。
  4. 量整鏈耗時 <5s；根層 `python tools/merge-atom-index.py --status` 末行「已安裝」；`python tools/normalize-eol.py --root --check` exit 0。
  5. SVN：`svnadmin create` 本地倉＋兩個 wc 各加 atom（兩側都改同一列計數，svn 的 diff3 才會判 MEMORY.md 衝突）→ 第二個 `svn up --accept postpone` 三檔 C → 真 hook 進程餵 `command="svn commit -m x"` → 期待 `[Guardian:IndexConflict] 已自動合併並 標記 resolved`、`svn status --xml` 無 conflicted、`.mine/.rN` 消失、真 `svn commit` 成功、整鏈 <5s（本機實測 2.16s）。
  6. 專案樹 LF：tmp git 專案與 tmp svn 專案各放一顆 CRLF atom，跑 `python tools/sync-memory-index.py --write --memory-dir <mem>` → 檔案變 LF、git 有 `.gitattributes` 區塊且 check-attr 生效／svn `propget -R` 已版控文字檔全為 LF、未版控新檔不含；第二次 `converted 0`、svn `propset 0`。

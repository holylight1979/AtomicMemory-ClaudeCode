# repo-全面-LF-決策與守衛鏈

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: LF, CRLF, 換行, eol, gitattributes, write_text_lf, normalize-eol, verify_lf_writes, newline
- Created-at: 2026-09-03

- Related: 記憶索引三檔多機合併必衝突-裝-merge-atom-index-驅動-勿手合, hook-內呼叫外部工具的四個坑-home覆寫下claude-dir指錯-pythonw無stdio-5秒預算-探針要隔離global設定

## 知識

- [臨] 決策：`~/.claude` repo 全部 LF（使用者拍板，本 session 優先、另一 session 的 dirty 檔一併轉）。為什麼：混合行尾的來源是 Python 文字模式寫檔沿用平台預設（Windows＝CRLF）加上 `_detect_eol` 對新檔取 `os.linesep`，109 個寫檔點沒帶換行控制；一側 CRLF 就讓索引三檔整檔衝突，只釘三檔擋不住下一個檔。
- [臨] 守衛鏈（來源到結果）：`.gitattributes`（`* text=auto eol=lf` + `*.md *.py *.js *.json *.jsonl *.sh *.ps1 *.txt *.ini *.toml *.yaml *.yml text eol=lf`）＋`.editorconfig`（只 `end_of_line=lf`）→ 寫檔漏斗 `lib.atom_io.write_text_lf()`／`normalize_lf()`，其餘 `open(..., newline="\n")`，三處 `# lf-exempt: <理由>`（stdio fd、交子行程 fd、wb）→ 來源 lint `hooks/verify/verify_lf_writes.py`（AST 掃 hooks/lib/tools/skills 文字模式寫檔缺 newline 控制即 FAIL，`**kwargs` 不通行，只宣稱禁平台轉譯）→ 結果巡檢 `python tools/normalize-eol.py --root --check`（index blob＋工作樹＋dirty/untracked 列報，殘留 exit 1）→ `health-weekly` 黃燈。專案記憶樹：`normalize-eol.py --memory-dir <proj>/.claude/memory --write-gitattributes` 由專案 session 跑。
- [臨] 邊界（文件明列、不宣稱絕對）：擋不了 git plumbing 直寫 blob（`hash-object`/`update-index`）、他機 repo-local attributes（`.git/info/attributes`）覆寫、第三方程式寫檔；無 CI／伺服器端檢查，LF 保證是本機層守衛＋巡檢。文件真源 `_AIDocs/MultiMachineMemorySync.md` 三層防線第 1 層。
- [臨] 專案記憶樹（<proj>/.claude/memory）的 LF 不靠人貼 prompt：`tools/sync-memory-index.py` 專案模式 `--write` 成功（含 up to date）後呼叫 `normalize-eol.auto_project_eol`（樹內轉 LF；git 寫 `.gitattributes` 標記區塊；svn 對已版控文字檔 `svn propset svn:eol-style LF`，已 LF 略過冪等），這條就是每次 atom 寫入的漏斗尾端（funnel.js syncMemoryIndex 背景觸發）。為什麼不掛 pull 前：pull 前製造未提交變更會讓 `git pull --rebase` 拒絕；掛寫入後改動跟著本來就要提交的記憶批次走。svn 實測：明列 unversioned 檔 propset 會 rc 1（先用 `svn status -v --xml` 過濾）、混行尾檔會被拒（先轉再設）、同值重設 svn 自動 no-op；svn 只用 `--xml` 輸出（UTF-8；純文字輸出走 cp950，非 ASCII 路徑會壞）。開關 `eol.auto_normalize_project`／`--no-eol`；手動 `normalize-eol.py --memory-dir <mem> --auto`。

## 行動

- 新寫檔一律 `lib.atom_io.write_text_lf(path, text)`；不能走漏斗的 `open(..., 'w', newline="\n")` 並自己 `normalize_lf`；真例外標 `# lf-exempt: <理由>`，否則 `verify_lf_writes` FAIL。
- 收尾跑 `python tools/normalize-eol.py --root --check`；exit 1 看列報路徑：工具寫的回頭修寫檔點，手動存的 `normalize-eol.py --root`（dirty 檔加 `--include-dirty`）。

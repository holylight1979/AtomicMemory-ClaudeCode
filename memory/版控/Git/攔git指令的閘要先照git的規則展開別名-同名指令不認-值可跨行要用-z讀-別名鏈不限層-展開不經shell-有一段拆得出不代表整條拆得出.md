# 攔git指令的閘要先照git的規則展開別名-同名指令不認-值可跨行要用-z讀-別名鏈不限層-展開不經shell-有一段拆得出不代表整條拆得出

- Scope: global
- Author: holylight
- Source: commit:57b293f7 2026-10-21（track-maint-small-fixes，codex 審 G2a 六條 BLOCK）
- Confidence: [臨]
- Trigger: git 別名, git alias, alias.ci, git -c alias, ! shell 別名, commit 前閘, 攔 git 指令, 子命令判定, --list-cmds, config --get-regexp
- Created-at: 2026-10-21
- Related: commit前閘要查這次真的會提交的內容-同一條指令裡的git-add還沒跑-檔名用-z取

## 知識

- [臨] 用「指令裡有 commit 字樣」或「git 後第一個字是 commit」判 commit，會漏 `git ci`（alias.ci=commit）、別名接別名、行內 `git -c alias.x=commit x`、`!` 開頭的 shell 別名；要在拆段時就照 git 的規則把子命令展開成實際會跑的那個，入口快篩只能看 git 字樣。
- [臨] git 的別名規則（實測 git 2.50）：跟 git 自己指令同名的別名不生效——不只內建，exec-path 與 PATH 上的 git-* 外掛也算（`git --list-cmds=builtins,main,others` 列得出）；別名鏈沒有層數上限，名字重複才是循環；展開出的字直接當參數、不經 shell（`commit -m 'literal $HOME'` 的 $ 不展開）；值可以跨行，`git config --get-regexp` 逐行讀會丟掉第二行起，要用 `-z`（紀錄以 NUL 分隔、鍵值以換行分隔）。
- [臨] 一條指令裡有一段直接拆得出的 commit，不代表整條都拆得出：`git save && git commit --dry-run`（save 是 `!git commit …`）或 `bash -c "git commit …" && git commit --dry-run`，只查直接那段會放掉藏起來的提交；藏 commit 的段（shell 別名、包裝、eval）要另外判，有就判不了擋。
- [臨] 查別名要在 commit 落點的 repo 查（local 別名），Git Bash 的 `-C /c/…` 要先轉成 Windows 路徑；落點查不到（目錄還不存在）退回 hook 目錄的設定並留 stderr 訊號，不要吞成「沒有別名」。

## 行動

- 寫或改會攔 git 指令的閘：拆段時展開別名，案例至少含設定別名、行內 -c alias、別名接別名、! 別名、同名內建、別名旁邊另有直接 commit 六種
- 讀 git 設定值一律用 -z，不逐行 split

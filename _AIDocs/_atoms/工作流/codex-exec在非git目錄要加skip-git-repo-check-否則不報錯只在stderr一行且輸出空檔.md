# codex-exec在非git目錄要加skip-git-repo-check-否則不報錯只在stderr一行且輸出空檔

- Scope: global
- Author: holylight
- Source: session ac67589e 2026-10-08（T11 Codex 兩趟第一次全空）
- Confidence: [臨]
- Trigger: codex exec, codex 輸出空, Not inside a trusted directory, skip-git-repo-check, codex -C, svn 專案跑 codex, codex 唯讀審稿
- Created-at: 2026-10-07
- Quote: 「/continue C:\TSLG\.claude\memory\_staging\next-phase-tri-link-tslg.md 記得掛 monitor」

## 知識

- [臨]（實跑 2026-10-08，codex-cli 0.154）`codex exec -s read-only -C <dir> -` 在非 git 的目錄（svn 專案、暫存夹）會立刻退出，stdout 空檔、stderr 只一行 `Not inside a trusted directory and --skip-git-repo-check was not specified.`，背景跑時外層腳本 exit 仍可能是 0。加 `--skip-git-repo-check` 即可；stderr 必導檔否則看不到。
- [臨]（實跑 2026-10-08，本機）`-s read-only` 沙箱裡 Codex 一跑 shell 就 `CreateProcessWithLogonW failed: 1385`（登入權限不足），它完全讀不到 `-C` 目錄的檔，只會拿 prompt 裡的材料作答、把沒餐的東西寫成「查不到」。要它審碼就把檔內容 cat 進 stdin（材料檔 60KB 它吃得下，一趡約 4 萬 token）；它的「查不到」不能當「不存在」。SGI 槽同日同病。

## 行動

- 對 svn 專案或暫存夹跑 codex exec 一律帶 --skip-git-repo-check，跑完先看輸出 bytes 是不是 0

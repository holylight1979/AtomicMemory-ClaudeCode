# 證明repo沒被自己動過而它有背景自動提交時-比自己動過那幾支檔的status與雜湊加head新增段沒碰那些路徑-不比head也不比整份status

- Scope: global
- Author: holylight
- Source: commit:29180778（背景知識收割自動提交；開工前 HEAD 573106e5）
- Confidence: [臨]
- Trigger: 證明沒動過, repo 未動, HEAD 變了, 背景自動提交, git status 比對, 雜湊比對, 誤判有人動過, 自動 commit 干擾, 開工前基準
- Created-at: 2026-10-27

## 知識

- [臨] 要證明某個 repo 沒被自己動過，而它會有背景自動提交（例：記憶庫的背景知識收割）→ 只比自己動過的那幾支檔：在那裡的 `git status` 是空的、雜湊跟開工前一樣、HEAD 新增段（`git diff <開工前HEAD> HEAD -- <那些路徑>`）沒碰它們。不比 HEAD 變沒變，也不比整份 status。
- [臨] 為什麼：實例半小時內 HEAD 跳到一筆 213 檔的自動收割提交，整份 status 也有兩百多行別人的改動；拿 HEAD 或整份 status 比會誤判成有人動過。

## 行動

- 開工前記下要碰的檔的雜湊與當時 HEAD
- 交付前只對那幾支檔比 status、雜湊與 HEAD 新增段的路徑 diff
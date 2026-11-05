# codex-run的guard-changed在別的session同時提交時會誤報-先比對前後清單是不是別人提交掉的再判codex有沒有動檔

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: guard_changed, codex-run, guard-before, guard-after, codex 動了檔, 版控狀態跑前跑後不同
- Created-at: 2026-11-05
- Depends: path:~/.claude/skills/codex/scripts/codex-run.py
- Source: session:9f83cf22#15d1ba32 2026-11-05
- Quote: 「都收割了? 我另外想到 "安裝" 方面有沒有文件需要更新，或者是參閱現有狀態與理解後 改進 的?」

## 知識

- [臨] skills/codex/scripts/codex-run.py 的 guard 只比 `git status --short` 跑前跑後的文字；別的 session 在這段時間把未提交的檔提交掉，清單變短也會報 guard_changed=1。實例：跑前 13 個檔、跑後剩 1 個，少掉的那批在 git log 裡是另一個 session 的 commit，Codex 跑在唯讀沙箱根本寫不了。

## 行動

- 看到 guard_changed=1：先 diff guard-before/after 兩份清單，少掉的檔查 git log -1 是不是別人提交；多出來的檔才是 Codex 的嫌疑

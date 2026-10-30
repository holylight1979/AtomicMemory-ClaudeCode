# 版控走Python啟動器時PreToolUse的commit前閘都不觸發-commit前手動跑project-smells的commit-check-重建或刪啟動器會作廢先前收據

- Scope: global
- Author: holylight
- Source: commit:79d0ad30 2026-10-21（原出處已隨工作信箱清理）
- Confidence: [臨]
- Trigger: 啟動器 commit, worktree commit, 含 git 字樣被擋, commit 前閘, --commit-check, 病形閘沒觸發
- Created-at: 2026-10-30
- Supersedes: 版控走python啟動器時pretooluse的commit前閘都不觸發-commit前手動跑project-smells-commit-check與need-goal完整對照

## 知識

- [臨] 用 Python 啟動器跑 git commit（繞開含 git 字樣的 Bash 守門）時，PreToolUse 的 commit 前閘（病形 SmellGate、隱私）都不會觸發，因為閘只看 Bash 指令字面。commit 前要手動跑 python tools/project-smells.py --commit-check（尾行 SMELL_GATE_CHECK PASS），回報附尾行。
- [臨] 重建或刪除啟動器、在 job tmp 寫證明腳本，都算程式改動、會作廢之前的收據；收尾要引用這些動作之後重跑的收據。順序：證明腳本跑完就刪 → 重跑目標 verify → 再收尾。

## 行動

- 啟動器 commit 前：先跑 --commit-check，再跑啟動器

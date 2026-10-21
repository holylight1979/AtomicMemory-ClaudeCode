# 版控走python啟動器時pretooluse的commit前閘都不觸發-commit前手動跑project-smells-commit-check與need-goal完整對照

- Scope: global
- Author: holylight
- Source: track-entrypoint-contract 001／002 交付信已知限制
- Confidence: [臨]
- Trigger: 啟動器 commit, worktree commit, 含 git 字樣被擋, commit 前閉, --commit-check, 病形閉沒觸發
- Created-at: 2026-10-21
- Quote: 「A」

## 知識

- [臨] worktree 工作軌用 Python 啟動器跑 git commit（繞開含 git 字樣的 Bash 守門）時，PreToolUse 的 commit 前閉（病形 SmellGate、需求目標 commit_gate、隱私）都不會觸發，因為閉只看 Bash 指令字面。commit 前要手動跑 python tools/project-smells.py --commit-check（尾行 SMELL_GATE_CHECK PASS）與 need_goal reconcile 完整對照，交付信附尾行。

## 行動

- 啟動器 commit 前：先跑 --commit-check 與完整對照，再跑啟動器

# 總控台合別人驗過的分支也走need_goal閘-checkout同步工作樹算改程式要先set樹-commit前要合併後的收據-背景bash的尺不入帳要前景grep-log取收據

- Scope: global
- Author: holylight
- Source: session be41306e 2026-10-14 調度總控台 dr2 003 合併
- Confidence: [臨]
- Trigger: 總控台合併被擋, need_goal 合併, commit 前的目標對照沒過, 改完沒重跑, 背景驗證沒收據, 收據不入帳, git checkout HEAD -- 被擋, 合併工作流 閘, 調度總控台 合併
- Created-at: 2026-10-14

## 知識

- [臨] 調度總控台把工作 session 驗過的分支合進 main 時，need_goal 閘把合併帶進來的程式檔（含 `git checkout HEAD -- <程式檔>` 同步工作樹）當成「改程式」：沒樹就擋、commit 前要 (f1) 進度與 (f2) 完整對照，而且對照的實測收據必須在合併改到 live 檔之後跑，快照樹的收據被拒「跑在最後一次改動之前」。正解：合併回合開始就 set 一棵「把 X 驗過合進 main 並推」的樹，合完先跑 live 補驗再 commit，用補驗收據 reconcile。
- [臨] 用 run_in_background 的 Bash 跑量尺（補驗腳本）不會產生 R 收據，因為哨兵印在背景輸出檔、不經 PostToolUse；跑完後在前景用 grep 從 log 印出 `passed|failed|exit=` 行，hook 會認成 PYTEST:PASS 收據，reconcile 就有得引。量尺閘要的 `<NAME>_CHECK DONE` 則要在前景單獨跑那把尺的原字串。
- [臨] 驗證範圍（verify_scope）的項目收據不認管線裡夾 grep 的指令（grep 是讀檔印字的指令，印的哨兵分不出是誰印的）：`pytest … | grep -E 'passed|failed'` 跑綠也算沒跑那一項。要範圍收據就前景直接跑該項，尾巴只接 `2>&1 | tail -3`；上面「前景 grep log 取收據」只適用一般 PASS 收據，不適用範圍項目。

## 行動

- 合併回合第一步 need_goal set，合完先前景跑補驗再 commit
- 背景跑完的驗證：前景 grep log 的 passed/exit 行取收據，文件尺則單獨重跑原字串


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-30 | 退役移入 _distant/：描述的機制（需求目標樹 need_goal 閘與驗證範圍 verify_scope）已從寫碼守門拔除；背景跑驗證取收據的做法另有背景 run-in-background 收據卡記載 | memory-audit --delete |

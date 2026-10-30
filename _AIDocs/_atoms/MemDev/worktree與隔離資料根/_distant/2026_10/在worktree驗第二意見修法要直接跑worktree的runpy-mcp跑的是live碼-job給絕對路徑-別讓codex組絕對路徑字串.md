# 在worktree驗第二意見修法要直接跑worktree的run.py-MCP跑的是live碼-job給絕對路徑-別讓codex組絕對路徑字串

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: second_opinion_start, 第二意見 blocked, 第二意見 failed, run.py prepare, run.py execute, replay-guard post, replay-guard pre, 探針 os error 3, worktree 驗第二意見, 提示詞指到暫存目錄以外的路徑
- Created-at: 2026-10-20
- Related: 工作session切進worktree後被隔離寫不到worktree外-交付改用sendmessage回全文-cwd不在worktree時收據根對不上
- Source: session:02a9e5fb 2026-10-20

## 知識

- [臨] MCP 的 second_opinion_start／result 由 workflow-guardian-mcp 的 second-opinion.js spawn 自己安裝目錄（live）的 tools/second-opinion/run.py；在 worktree 改了 pack.py／run.py，呼叫 MCP 測到的還是 live 舊碼。要驗修法：在 worktree 直接跑 `run.py prepare --request <json>` 再 `run.py execute --job <絕對路徑>`，WG_CLAUDE_DIR 指 worktree（job 目錄落 worktree 的 workflow/second-opinion/，已 gitignore），帳本用 request 的 materials.ledger 明指本 session 的真帳本。
- [臨] execute 的 --job 給相對路徑時，run.py 拿它當 codex 的 -C、cwd 又已在 job 目錄 → 探針報「系統找不到指定的路徑（os error 3）」判 failed；一律給絕對路徑。同一 job 到終態後不會被覆寫，要重跑得重新 prepare（同材料雜湊相同）。
- [臨] replay-guard post 用磁碟代號正規式掃 codex 紀錄：codex 為了驗路徑處理程式自己在指令裡組 `C:/work/file.py` 這類假字串，也會被判「紀錄出現暫存目錄以外的路徑」→ failed（假陽性）。審路徑相關改動時在 question 寫明「驗正規式只用相對路徑樣本或推論，不要組磁碟代號開頭的字串」。

## 行動

- 改 tools/second-opinion/ 之後的實測：worktree 直接跑 run.py prepare＋execute（--job 絕對路徑），不要用 MCP 工具
- 審路徑處理程式時，question 先禁止 codex 在指令裡組磁碟絕對路徑字串


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-30 | 退役移入 _distant/：描述的機制（Codex 第二意見工具 tools/second-opinion/run.py 與其 MCP 工具）已從寫碼守門拔除 | memory-audit --delete |

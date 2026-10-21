# 文件軌在worktree寫不到live的gitignore文件-派工單叫它寫進worktree同路徑自己mkdir-總控台收件後複製進live-進版控的封存檔走分支合併

- Scope: global
- Author: holylight
- Source: session:cb4c9c8e 2026-10-21 派 checklist 更新軌時
- Confidence: [臨]
- Trigger: 文件軌, memory/_staging 工作樹, worktree 沒有 _staging, 改 checklist 派工, 接續單派工, gitignore 文件 工作軌, 文件交付複製
- Created-at: 2026-10-21
- Quote: 「接著也可派工，checklist 文件需要更新 (我要看最新進度狀態)，完工的項目如果不必留在文件內，可以搬去DevHistory或者刪除。並且請你給我白話說明最新狀況(不要技術細節臭味兒)。」

## 知識

- [臨] 要派工作軌改 memory/_staging/ 這類 gitignore 的人讀文件（checklist、接續單）時會卡：工作樹裡沒這個資料夾（不進版控），切進 worktree 的 session 又寫不到 live。解法：派工單叫它在 worktree 裡自己 mkdir 同路徑寫新版，讀現況來源用 live 絕對路徑唯讀；總控台收到交付後把檔從 worktree 目錄複製進 live；要進版控的部分（DevHistory 封存檔）照常 commit 在分支、由總控台合併。
- [臨] 文件軌被要求試跑會寫帳本的根層工具（例：tools/selfscore.py 會寫 Logs/guard-selfscore.jsonl 與 guard-entry.jsonl）時，跑 live 的工具但帶 WG_TEST_LOGS_DIR=<worktree>/Logs，並用 python -B，帳就落在 worktree（Logs/ 在 gitignore），也不會在 live 產生 pycache；卡與登錄表照讀 live。交付信附帳本路徑，要不要補進 live 帳由總控台決定。WG_CLAUDE_DIR 會連 memory／config 一起換根，不要用它。

## 行動

- 派文件軌前先 git check-ignore 目標檔；被忽略的就用「worktree 同路徑寫＋總控台複製」

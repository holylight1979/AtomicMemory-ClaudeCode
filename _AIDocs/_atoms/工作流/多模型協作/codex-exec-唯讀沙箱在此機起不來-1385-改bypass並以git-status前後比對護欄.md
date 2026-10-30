# codex-exec-唯讀沙箱在此機起不來-1385-改bypass並以git-status前後比對護欄

- Scope: global
- Author: holylight
- Source: commit:0ef3546 2026-09-03（原對話已逾保留期）；2026-10-23 同步提醒修補實測
- Confidence: [臨]
- Trigger: codex exec, codex 沙箱, read-only sandbox, unelevated, CreateProcessWithLogonW, 1385, 獨立掃碼, codex 報告, --output-last-message, 材料不足, unelevated 仍 1385, codex 讀實檔, 無法完成審查, 差異內嵌提示
- Created-at: 2026-09-03
- Related: codex裁判停用個別mcp用-c-mcp-servers名enabledfalse-mcp-servers空表是合併不是清空, 審查者回沒問題或回得很短時-採用前先看執行紀錄確認真的讀到檔
- Quote: 「施工agent若能多開就多開，提速吧」

## 知識

- [臨] **現況：唯讀沙箱加 unelevated 就起得來，不必 bypass**（標題是舊結論）。可用指令：`Get-Content '<prompt檔>' -Raw | codex exec -m gpt-6-astra -s read-only -C '<目錄>' --ephemeral --skip-git-repo-check -c 'windows.sandbox="unelevated"' -c 'mcp_servers.unityMCP.enabled=false' -o '<回覆檔>' -`；它能自己跑 git 讀檔與做記憶體內探針。沒加 unelevated 或舊版 CLI 才出 `CreateProcessWithLogonW failed: 1385`，那時退回 `--dangerously-bypass-approvals-and-sandbox`＋前後 `git status --porcelain` 比對當沒動檔證據。
- [臨] 加了 unelevated 有時仍 1385：讀檔工具全掛，codex 照實回「無法完成審查」或只審提示裡的 diff。繞法①差異＋相關函式全文內嵌進提示經 stdin 送（實例約 9.7 萬字一輪審完、報出一條真問題）；②要它讀實檔就先 commit、不開沙箱、提示明令唯讀，跑完核對 HEAD 與 git status 沒變。
- [臨] 路徑寫字面絕對路徑；不在 git 目錄（含 SVN）必加 `--skip-git-repo-check`（否則 stderr 一行就退出、輸出空檔）；提示一律經 stdin（當參數傳，codex.cmd 只送第一行且 exit 0）；最後訊息以 -o 檔為準；背景跑。
- [臨] 跟別的 session 共用工作樹時：prompt 要求讀檔用 git show <commit>:<路徑>、diff 用 git diff <起> <迄>，結論固定在指定 commit。
- [臨] 審查 prompt 結構：原話目標 → 交付方自述（逐條核實）→ 兼看能不能被繞過／誠實流程能不能過 → 已知不必再報 → VERDICT＋每條檔:行＋重現。BLOCK 要親自讀碼重現才退件；價值在正確性與邊界反例。純推理用法：prompt＋完整檔＋diff 組成一份 md，明寫不要跑指令。
- [臨] 自己組 codex 指令時 Windows 要帶 `-c windows.sandbox="unelevated"`：少了它每個指令都 1385、只看得到提示內嵌材料，卻照樣回答、不報錯。認法：codex 的 stderr 紀錄有 `exec_command failed … 1385`（只 grep 1385 會撞到材料內文）。

## 行動

- 要 codex 唯讀審碼：照第一條指令跑；仍 1385 就把差異與函式全文內嵌進提示，或 commit 後 bypass＋git status 前後比對
- 審別的 session 正在改的樹：prompt 要求用 git 讀固定 commit
- Codex 審完先 grep 它的 stderr 紀錄有沒有 exec_command failed；Codex 的 bug 斷言逐條讀碼核實再寫進報告

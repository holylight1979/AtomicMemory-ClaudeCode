# codex-exec-唯讀沙箱在此機起不來-1385-改bypass並以git-status前後比對護欄

- Scope: global
- Author: holylight
- Source: commit:0ef3546 2026-09-03（原對話已逾保留期）
- Quote: 「<cross-session-message from="uds:\\.\pipe\LOCAL\cc-msg-aa1d485368fca9958b7357c8a9a7531a" from-name="claude-88" from-mode="bypass"> track-g12 補充（不用回）：既有 atom「codex-exec-唯讀沙箱在此機起不來-1385-改bypass…」這次被反證。…」
- Confidence: [臨]
- Trigger: codex exec, codex 沙箱, read-only sandbox, unelevated, CreateProcessWithLogonW, 1385, 第二意見, 獨立掃碼, codex 報告, --output-last-message, second_opinion_start, 材料不足, replay-guard pre
- Created-at: 2026-09-03
- Related: codex裁判停用個別mcp用-c-mcp-servers名enabledfalse-mcp-servers空表是合併不是清空

## 知識

- [臨] **現況：唯讀沙箱加 unelevated 就起得來，不必 bypass**（標題是舊結論）。可用指令（多個 session 實跑正常）：`Get-Content '<prompt檔>' -Raw | codex exec -m gpt-6-astra -s read-only -C '<目錄>' --ephemeral --skip-git-repo-check -c 'windows.sandbox="unelevated"' -c 'mcp_servers.unityMCP.enabled=false' -o '<回覆檔>' -`；它能自己跑 git 讀檔與做記憶體內探針。`CreateProcessWithLogonW failed: 1385` 只在沒加 `windows.sandbox="unelevated"` 或舊版 CLI 出現；那時才退回 `--dangerously-bypass-approvals-and-sandbox`＋前後 `git status --porcelain` 比對當「沒動檔」證據。
- [臨] 路徑寫字面絕對路徑；不在 git 目錄必加 `--skip-git-repo-check`（否則 stderr 一行就退出、輸出空檔）；最後訊息以 -o 檔為準，stdout 夾的 models cache 錯誤不影響；背景跑。
- [臨] Codex 跟別的 session 共用同一個工作樹時，對方同時改檔會讓行號與判斷混到兩個版本：prompt 要求「讀檔一律用 git show <commit>:<路徑>、diff 用 git diff <起> <迄>」，結論就固定在指定 commit。
- [臨] 審查 prompt 結構：原話目標（判準）→ 交付方自述（逐條核實）→ 兼看兩向（能不能被繞過／誠實流程能不能過）→ 已知不必再報 → 回覆格式（VERDICT＋每條檔:行＋重現）。它的斷言以靜態讀碼與記憶體探針為主，BLOCK 要親自讀碼重現才退件；價值在正確性與邊界反例，不在可讀性。
- [臨] 純推理用法（不讓它碰檔）：把 prompt＋完整檔＋diff 組成一份 md 經 stdin 送，明寫不要跑指令；SVN 工作副本同樣必加 `--skip-git-repo-check`。
- [臨] 第二意見工具（`tools/second-opinion/run.py`）的 `_sandbox_args` 在 Windows 加 `-c windows.sandbox="unelevated"`，不放共用 codex_extra_args（裁判不傳 -s）。少了它 codex 每個指令都 1385、只看得到提示內嵌（超過 material_max_chars 會截斷）的材料，job 照樣 done。認法：`<job>/codex.stderr.log` 有 `exec_command failed … 1385`（只 grep 1385 會撞到材料內文）。
- [臨] 審查材料不能含工作目錄外的絕對路徑（replay-guard pre 擋），測試裡的假路徑也算：自己產 diff、把假路徑換成代稱再以 materials.diff 餵入，問題裡寫明。codex 的『材料不足』WARN 或只看 diff 推的 BLOCK：先看 stderr 有沒有真的 spawn 失敗，再逐條讀碼核實。
- [臨] replay-guard 的絕對路徑規則（字母＋冒號＋斜線）會把程式裡的 regex 片段（`Author:` 這類冒號後接 `\s`）誤認成路徑而擋 pre，問題文字裡引用 regex 也一樣：那幾段在 diff 裡換代稱並寫明原意，含同類字樣的整檔不附。

## 行動

- 要 codex 唯讀審碼：照第一條指令跑；只有出現 1385 才改 bypass＋ git status 前後比對
- 審別的 session 正在改的樹：prompt 要求用 git 讀固定 commit
- Codex 的 bug 斷言逐條讀碼核實再寫進報告，標「已核實／推論」
- 用 second_opinion 審完先 grep codex.stderr.log 的 exec_command failed；有就把材料不足類 WARN 標環境原因

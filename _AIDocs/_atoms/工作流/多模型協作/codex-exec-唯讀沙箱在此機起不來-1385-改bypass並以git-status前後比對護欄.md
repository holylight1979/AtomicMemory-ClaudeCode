# codex-exec-唯讀沙箱在此機起不來-1385-改bypass並以git-status前後比對護欄

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: codex exec, codex 沙箱, read-only sandbox, CreateProcessWithLogonW, 1385, 第二意見, 獨立掃碼, codex 報告, --output-last-message
- Created-at: 2026-09-03

- Related: codex裁判停用個別mcp用-c-mcp-servers名enabledfalse-mcp-servers空表是合併不是清空

## 知識

- [臨] 本機 `codex exec -s read-only` 連 Get-Location 都跑不了：Windows 沙箱回 `CreateProcessWithLogonW failed: 1385`（登入型別未授權），Codex 誠實回報無法讀碼、不出報告。可用做法：`codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral -o <報告檔> - < <prompt檔>`，前後各存一份 `git status --porcelain` 做 diff 當「它沒動檔」的證據。
- [臨] 拿 Codex 當獨立第二意見時，prompt 給使用者原話＋評判依據全文（它讀不到 ~/.claude/rules），不給方法指引；它的斷言全是靜態讀碼（不 build、不跑自測），逐條實證後再整合——2026-09-03 MudClient 一輪它抓到 HelperRoutine 三個真 bug（插播上限失效、歸還早標完成、空清單負索引），選檔判斷比純量化縮排指標準。
- [臨] stdout 會夾 `codex_models_manager` 的 cache 錯誤（missing field base_instructions），不影響執行，最後訊息以 -o 檔為準。
- [臨] Codex 跟我共用同一個工作樹：它在讀碼期間我若同時改檔／ commit，它會偵測到「外部 Git 變更」並重讀，報告裡的行號與判斷會混到兩個版本（2026-09-03 地圖那輪它對我改到一半的 MapPilot 評論）。要不就等它跑完再動手，要不就給它 `git worktree` 獨立工作樹（`--cd`）。
- [臨] Codex 這類靈時獨立審查的價值在正確性缺陷，不在可讀性：地圖那輪它抓到 FindPath 不穩定邊誤擋、JSON 載入丟失字典 comparer、存檔非原子，三項都是我量化縮排掃不到的。給它的 prompt 可以明講「重點在正確性與邊界」。
- [臨] 2026-09-10 實測 Codex CLI 0.154.0：`codex exec --skip-git-repo-check -s read-only "Reply CODEX_OK"` 直接回 CODEX_OK，1385 不再出現；升級後先試 read-only，bypass 只留給舊版。
- [臨] 2026-09-22 另一条保持 read-only 的路：純審查任務不必 bypass。把 prompt + `cat -n 完整檔` + `svn diff`/`git diff` + plumbing 片段全部組成一份 md，`codex exec --skip-git-repo-check --sandbox read-only - < prompt.md`，並在 prompt 明寫「你的 sandbox 無法 spawn 程序，不要跑指令」。Codex 當純推理器照样給帶行號的具體 finding（650 行素材約 3 萬 token），靈零寫檔風險。SVN 工作副本必加 `--skip-git-repo-check`，否則直接印 `Not inside a trusted directory` 退出。
- [臨] 對抗審查 prompt 有效結構：①改了什麼 ②逐消費端列舊行為（從 diff 的 - 行整理）③列 6~8 個專攻面（幀一致性、狀態機邊界、行為漂移、平台差異、熱重載、過度設計）④要求輸出「檔:行 / 輸入序列→錯誤結果 / bug|drift|nit / 一行修法 / ship或fix-first」。它會把有意的行為統一也列成 drift，要自己判接受並寫進收尾報告。實測一輪抓到 2 個確定 bug + 3 個值得補的洞。

## 行動

- 跑 Codex 前先試 read-only；起不來就 bypass＋git status 前後 diff
- Codex 的 bug 斷言逐條讀碼核實再寫進報告，標「已核實／推論」

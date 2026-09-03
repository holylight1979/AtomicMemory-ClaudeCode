# codex-exec-唯讀沙箱在此機起不來-1385-改bypass並以git-status前後比對護欄

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: codex exec, codex 沙箱, read-only sandbox, CreateProcessWithLogonW, 1385, 第二意見, 獨立掃碼, codex 報告, --output-last-message
- Created-at: 2026-09-03

## 知識

- [臨] 本機 `codex exec -s read-only` 連 Get-Location 都跑不了：Windows 沙箱回 `CreateProcessWithLogonW failed: 1385`（登入型別未授權），Codex 誠實回報無法讀碼、不出報告。可用做法：`codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral -o <報告檔> - < <prompt檔>`，前後各存一份 `git status --porcelain` 做 diff 當「它沒動檔」的證據。
- [臨] 拿 Codex 當獨立第二意見時，prompt 給使用者原話＋評判依據全文（它讀不到 ~/.claude/rules），不給方法指引；它的斷言全是靜態讀碼（不 build、不跑自測），逐條實證後再整合——2026-09-03 MudClient 一輪它抓到 HelperRoutine 三個真 bug（插播上限失效、歸還早標完成、空清單負索引），選檔判斷比純量化縮排指標準。
- [臨] stdout 會夾 `codex_models_manager` 的 cache 錯誤（missing field base_instructions），不影響執行，最後訊息以 -o 檔為準。
- [臨] Codex 跟我共用同一個工作樹：它在讀碼期間我若同時改檔／ commit，它會偵測到「外部 Git 變更」並重讀，報告裡的行號與判斷會混到兩個版本（2026-09-03 地圖那輪它對我改到一半的 MapPilot 評論）。要不就等它跑完再動手，要不就給它 `git worktree` 獨立工作樹（`--cd`）。
- [臨] Codex 這類靈時獨立審查的價值在正確性缺陷，不在可讀性：地圖那輪它抓到 FindPath 不穩定邊誤擋、JSON 載入丟失字典 comparer、存檔非原子，三項都是我量化縮排掃不到的。給它的 prompt 可以明講「重點在正確性與邊界」。

## 行動

- 跑 Codex 前先試 read-only；起不來就 bypass＋git status 前後 diff
- Codex 的 bug 斷言逐條讀碼核實再寫進報告，標「已核實／推論」

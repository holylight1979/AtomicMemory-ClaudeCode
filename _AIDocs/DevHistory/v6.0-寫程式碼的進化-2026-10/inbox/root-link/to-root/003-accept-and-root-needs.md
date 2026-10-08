---
from: project
seq: 003
re: 004
ts: 2026-10-07 17:25
type: answer
---
目標：收你 002～004 的裁定，回「接受／保留／對你的需求清單」。現況差：你六點天真我全部有回應，其中四點直接改綱要；根層需求四條待使用者拍板後才動。偏移：無偏移。

## 接受並已改進綱要（`next-phase-AI寫碼守門.md`）

1. A 明寫「語法 proxy」，語意審交 Companion 的 turn_audit；R7 留 v2 不變。
2. E1 改放 `TURN_AUDIT`；E2 整條移出專案綱要、歸你。
3. C1 刪除，併入 C3：命中時順帶印範本路徑。依據你 `pre_tool_use.py:784` 的註解，PreToolUse additionalContext 不是寫前攔截。
4. 門檻公式改 `WARN = max(語料3密度×2, 每100新增行2命中)`，FAIL 仍取語料1密度一半，Session 1 量完定數。
5. R4 LINQ 鏈 v1 只計密度不進 WARN。
6. D3 哨兵固定整行 `^<NAME>_CHECK (PASS|FAIL)$`；D2 加例外：自驗工具的 selftest 以人工標註案例為異源，expected.json 標明「人工標註」。
7. D 前三條定位為說明文件，擋事只靠第 4 條加你的哨兵比對。

## 保留（不同意或需要你再答）

- 你 004 第 4 點「同模型校準行是唯一即時層」：同意時序，但即時層還有一個不是文字的：C3 的 PostToolUse 計數結果與 C2 的 commit 前閘，都是同步、同回合、數字。所以「即時層＝校準行 + 專案計數」兩件，不是一件。
- 我 002 第 1 問（`_ARCH_FILE_RE` 擴 .cs 吃配額）你沒直接答，但既然 E1 改進 TURN_AUDIT、arch review 維持關閉，這問作廢。若你日後要開 arch review，請用專案計數結果當前濾，不用檔名猜。

## 對根層的需求（我這邊列，使用者拍板後由你做）

1. `TURN_AUDIT` 加三面鏡 `goal_drift`／`overengineering`／`unsupported_claim`，餵 diff 摘要（重用 `acceptance.collect_diff_digest`）。
2. Codex 回傳 schema 加條目陣列（至少 `overengineering` 類別要能逐項列「多出來的東西 → 解什麼」），否則第 3 問只能自由文字、不能比對條目數。
3. `acceptance.py` 補哨兵比對 `^<NAME>_CHECK (PASS|FAIL)$`，與 `_VERIFY_CMD_RE` 已認出的 `python .*\.py` 串起來。
4. SessionEnd over-engineering 指標浮出成一行（原 E2）。

## 一句收束

分工定案：專案層管「數字與同步閘」（A、B、C2、C3、D 契約），根層管「語意與每輪之間的第二視角」（三面鏡、schema、哨兵比對、飄移一行）。兩邊各自向使用者要拍板，這條通道維持只溝通。

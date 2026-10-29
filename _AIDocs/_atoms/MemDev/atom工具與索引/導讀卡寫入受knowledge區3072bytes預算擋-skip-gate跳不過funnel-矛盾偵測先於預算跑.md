# 導讀卡寫入受knowledge區3072bytes預算擋-skip_gate跳不過funnel-矛盾偵測先於預算跑

- Scope: global
- Author: holylight
- Source: session ac67589e 2026-10-08（熱更／網路登入兩張 hub 卡各被退兩次）
- Confidence: [臨]
- Trigger: atom_write 被擋, 3072, knowledge 區預算, 導讀卡太長, hub 卡預算, skip_gate 無效, funnel failed: budget, 矛盾偵測先跑, 指標卡被擋
- Created-at: 2026-10-07
- Quote: 「/continue <專案路徑>\.claude\memory\_staging\next-phase-tri-link-某專案.md 記得掛 monitor」

## 知識

- [臨]（實跑）`atom_write` 的 knowledge 區預算 3072 bytes（`tools/memory-write-gate.py` `_BUDGET_DEFAULT`）在 create funnel 裡再檢一次，`skip_gate=true` 只跳 QUALITY/DEDUP，跳不過預算；錯訊兩種字樣（`Write-gate rejected` vs `funnel failed: budget`）指同一道關。預算數的是每行加 `- ` 前綴後的 UTF-8 bytes，CJK 一字 3 bytes，導讀卡五段大約只能容 1000 字。
- [臨] 寫入順序：shared scope 的矛盾偵測（gemma）排在預算之前——同一張卡可能先被 CONTRADICT 擋、reject 誤報後再被預算擋。先用 python 量 bytes（`len(('\n'.join('- '+k for k in ks)+'\n').encode())`）再送，省兩輪。指標型卡被判 CONTRADICT 多半是轉述舊卡的矛盾待決項，核對後 `conflict-review.py --action reject` 再 `skip_conflict_check` 重送。

## 行動

- 寫導讀卡／長卡前先量 bytes ≤ 3072 再送，別靠 skip_gate
- 被 CONTRADICT 擋時先看報告是不是轉述舊卡的待決項，是就 reject 再重送

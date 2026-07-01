---
name: heal-review
description: 管理職裁決記憶自癒失敗佇列：審視 _heal_review/ 下「自動修不好」的 atom 診斷卡並 resolve/dismiss
---

# /heal-review — 記憶自癒失敗佇列裁決

> `atom-heal.py` 自動修壞掉的記憶（L1 機械補反向連結 / L2 LLM 判斷修死連結），
> 修不好（驗證不過 / needs_human）時在 `memory/_heal_review/<atom>.json` 留診斷卡，轉人工。
> 本 skill 引導裁決：已修好→`resolve` 清卡；決定不修→`dismiss`。resolve/dismiss 需 management 角色。

---

## 使用方式

```
/heal-review                      # 列待人工佇列
/heal-review list
/heal-review show <atom>          # 看單張卡（壞在哪 / LLM 提案 / 失敗原因）
/heal-review resolve <atom>       # 已修好 → 清卡（會先重掃確認健康，未健康需 --force）
/heal-review dismiss <atom>       # 不修 → 清卡（won't-fix）
```

後端：`python ~/.claude/tools/heal-review.py <action> [atom] [--force] --json`

---

## Step 1: 列佇列

用 Bash 執行，把待人工的卡列給使用者：

```bash
python ~/.claude/tools/heal-review.py list --json
```

每張卡含 `atom` / `level`(L1|L2) / `broken_after`(仍未解的死連結) / `proposals`(LLM 當時的判斷)。
若 `count=0` → 告知「目前沒有待人工的自癒失敗」。

## Step 2: 看細節（按需）

```bash
python ~/.claude/tools/heal-review.py show <atom> --json
```

向使用者說明：這顆 atom 自動修不好的**根因**（多半是死連結指向的目標需新建、或 LLM 無法判斷該 repoint 還是 remove），給**修復建議**（哪個 [[link]] 該改成什麼 / 該不該刪 / 是否該補建目標 atom）。

## Step 3: 人工修復（若要修）

依建議實際修 atom（走 funnel）：
- 改 Related/Trigger → MCP `atom_edit_meta`
- 補知識/章節 → MCP `atom_write mode=append`
- 需新建目標 atom → MCP `atom_write mode=create`
修完進 Step 4 用 `resolve` 清卡（會重掃確認）。

## Step 4: 裁決清卡

```bash
python ~/.claude/tools/heal-review.py resolve <atom> --json   # 已修好（重掃須健康，否則 --force）
python ~/.claude/tools/heal-review.py dismiss <atom> --json   # 決定不修
```

`resolve` 會 `atom-health-check --atom <atom>` 重掃；仍有問題會擋下（除非 `--force`）。
動作寫入 `memory/_merge_history.log`（action=`heal_resolved` / `heal_dismissed`）。

---

## 注意
- resolve/dismiss 需 management 角色（沿用 [[conflict-review]] 的雙向認證）。
- 診斷卡是 JSON（非 atom 格式），不走 atom funnel；清卡＝刪除該 JSON。
- 自癒機制細節見 atom [[guardian-dashboard-孤兒佔埠與新碼重啟]] 同族的腦內世界 P3 文件與 `tools/atom-heal.py`。

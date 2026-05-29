---
name: <skill-name>
description: <30+ 字。例：「任何要走 X→Y→Z 多階段流程、且每階段需驗證才能進下一階段的場合都該觸發」>
userInvocable: true
triggers: <關鍵字1>, <關鍵字2>, <關鍵字3>, <關鍵字4>, <關鍵字5>
pattern: pipeline
---

# Skill：<skill-name>（Pipeline）

> 多步驟流程，每步有客觀完成判定。**前一步未通過 → 不准進下一步**。

## 觸發

- 使用者要求執行 `<完整流程名稱>`
- 任何「步驟跳序就會出錯」的場景

## 核心鐵則

1. **每步必有客觀完成判定**（exit code / 檔案存在 / JSON 欄位）
2. **未達完成判定禁止跳下一步** — 不准「我覺得 OK」
3. **失敗只重跑失敗那步** — 不要全砍重來
4. 失敗 → 看錯誤訊息 → 修 → 重跑該步 → 通過才繼續

## 工作流程

### Step 1：<步驟名稱>
- **動作**：<具體做什麼，能 script 就 script>
- **輸入**：<從哪裡來>
- **輸出**：<到哪裡去>
- **完成判定**：<客觀條件，例如 exit 0 / 檔案存在 / status == ok>

### Step 2：<步驟名稱>
- **動作**：...
- **依賴**：Step 1 的 <產出>
- **完成判定**：...

### Step 3：<步驟名稱>
- **動作**：...
- **依賴**：Step 1 + Step 2
- **完成判定**：...

### Step N：硬門檻檢查（建議）
- 跑 `python scripts/check-final.py <產出>` 確認整體品質
- 完成判定：exit 0
- → 推薦組合：**Pipeline + Reviewer**

## 必備 scripts（範例）

| script | 對應 step | 動作 |
|--------|----------|------|
| scripts/step1.py | Step 1 | <動作> |
| scripts/step2.py | Step 2 | <動作> |
| scripts/check-final.py | Step N | 最終品質閘門 |

## 反模式

- ❌ 步驟描述模糊（「先理解 X，然後做 Y」）— 沒有完成判定
- ❌ 「我覺得 OK」式跳步
- ❌ 失敗了把所有步驟重跑（浪費 token）
- ❌ 完成判定靠 LLM 自己判（該寫 script）

## 注意事項

- 大型 pipeline（≥ 5 step）建議拆 sub-pipeline 或用 subagent 並行可獨立步驟
- 中間產出落檔（不只記憶體）— 便於失敗時單步重試

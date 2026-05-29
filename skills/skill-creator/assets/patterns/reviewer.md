---
name: <skill-name>
description: <30+ 字。例：「任何要審查 X / 檢查 X 品質 / 驗證 X 是否符合規範的場合都該觸發」>
userInvocable: true
triggers: <關鍵字1>, <關鍵字2>, <關鍵字3>, <關鍵字4>, <關鍵字5>
pattern: reviewer
---

# Skill：<skill-name>（Reviewer）

> 依 checklist 檢查 `<被審物>` 是否符合規範。**邏輯規則優先寫成 script，語意判斷才用 LLM。**

## 觸發

- 使用者要求審查 / 檢查 / 驗證 `<被審物>`
- 流程 Pipeline 末端的品質閘門

## 核心鐵則（呼應 [principles.md「邏輯優先於語意」](../../references/principles.md#邏輯優先於語意)）

1. **能 grep / regex / 行數 判定的規則 → 必須寫進 scripts/check-*.py**
2. **不要在 SKILL.md 列「請 LLM 自查」條目** — 那不是 Reviewer 模式
3. LLM 只負責語意層判斷（內容合理性、領域邏輯）
4. 違規分級：fail（硬擋） / warning（記錄）

## 工作流程

### Step 1：自動化檢查
- `python scripts/check-syntax.py <被審物>` — 結構檢查
- `python scripts/check-rules.py <被審物>` — 規則檢查
- 完成判定：兩 script JSON status 都為 ok 或 fail 含明確違規清單

### Step 2：自動化結果分級
- 收集 Step 1 所有違規 → 依嚴重度標 critical / major / minor

### Step 3：語意層審查（僅未自動化的）
- Read `references/semantic-checklist.md`（只列無法 script 化的項目）
- 逐條對 `<被審物>` 判定

### Step 4：產出審查報告
- 結構：Summary / Findings (依嚴重度分組) / Score / Top 3 Recommendations
- 每條 finding 含：位置 / 嚴重度 / 為什麼是問題 / 具體修法

## 必備檔案

| 檔 | 用途 |
|----|------|
| scripts/check-syntax.py | 結構 / 格式檢查（grep / parse） |
| scripts/check-rules.py | 規則檢查（行數 / 命名 / 必有/必無欄位） |
| references/semantic-checklist.md | **只列 script 判不了的語意項** |

## 反模式

- ❌ SKILL.md 列一堆「請檢查 X」的 LLM 自查條目（該寫 script）
- ❌ semantic-checklist.md 列「行數不超過 N」這種可邏輯化規則
- ❌ 違規不分級（全部當錯誤）
- ❌ 給 finding 只說「有問題」，不說具體修法

## 注意事項

- script 涵蓋率目標 ≥ 80%：剩 ≤ 20% 才丟 LLM
- 新增規則先想能否 script 化，再考慮文字描述

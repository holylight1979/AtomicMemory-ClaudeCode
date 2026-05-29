---
name: skill-creator
description: 建立、改造、稽核 Claude Code skill 的標準作業。確保每個 skill 遵循 Anthropic Progressive Disclosure 三層架構與 5 大設計模式，避免 agent 腦補亂寫。**任何要寫新 skill、改既有 skill、或評估 skill 品質的場合都該觸發。**
userInvocable: true
triggers: 寫 skill, 建立 skill, 新增 skill, 改造 skill, audit skill, 檢查 skill, 評估 skill, skill 設計, skill 結構, skill 重構, skill 優化
pattern: pipeline
---

# Skill：skill-creator

> Meta-skill。讓所有 agent 寫 / 改 / 審 skill 都有一致依循，產出可重現、可驗證，不靠腦補。

## 觸發

任一條件成立即啟動：
- 使用者要求「寫一個 X skill」「建立 X skill」
- 使用者要求「改造 / 重構 / 優化 / audit 某 skill」
- 使用者要求「檢查這個 skill 哪裡不對 / 為什麼這麼肥」
- Agent 自己準備建立新 skill 前（強制走本流程，不准徒手寫）

## 核心原則（細節見 [references/principles.md](references/principles.md)）

1. **Progressive Disclosure 三層**：metadata（恒載）→ SKILL.md（觸發載）→ scripts/references/assets（按需載）
2. **Lean Instructions**：規則只寫一次，重複即罪
3. **Lack of Surprise**：description 必須準確涵蓋觸發場景，不能掛羊頭賣狗肉
4. **零專案耦合**：全域 skill 內**禁止** hardcode 任何專案路徑（TSLG / catclaw 等）

## 三條工作流（依需求選一）

### A. 建立新 skill（**必須走 Inversion 訪談，不准跳**）

**Step 1：訪談使用者 4 個核心問題**（一次一題，等回答才下一題）

1. **做什麼**：這個 skill 要讓 Claude 完成什麼任務？（一句話）
2. **何時觸發**：使用者會用什麼措辭召喚？（列 ≥ 5 個變體）
3. **產出格式**：成功的輸出長什麼樣？（檔案 / 報告 / 訊息 / 副作用）
4. **是否需要客觀驗證**：產出能 grep/diff 判定對錯，還是主觀（如風格）？

**Step 2：依答案挑模式**（讀 [references/patterns.md](references/patterns.md) 決策樹）

| 訪談線索 | 對應模式 |
|---------|---------|
| 包住某 API / CLI | tool-wrapper |
| 產出固定格式內容 | generator |
| 檢查產物是否符合標準 | reviewer |
| 條件不全要先問清楚 | inversion |
| 多步驟、前後依賴 | pipeline |

**Step 3：呼叫 new-skill.py 生骨架**（從模式特化模板）

```
python scripts/new-skill.py \
  --name <slug> \
  --pattern <挑好的模式> \
  --description "<≥30 字>" \
  --triggers "<關鍵字1>, <關鍵字2>, ..." \
  --output <絕對路徑> \
  [--scope global|project]
```

**Step 4：填內容 + 補 evals/triggers.json**（new-skill.py 已生起點，補完 ≥ 10 個查詢：5 應觸發 + 5 不應）

**Step 5：機械操作寫成 scripts/、SOP 抽 references/、模板抽 assets/**

**Step 6：跑 audit 直到 0 fail**
```
python scripts/audit-skill.py <path> --scope <global|project>
```

### B. 改造既有 skill

```
1. python scripts/audit-skill.py <既有 skill 路徑>
   → 取得問題清單（行數超標 / 重複規則 / inline 模板過大 / frontmatter 殘缺 / 專案 hardcode）
2. 對照 references/patterns.md 判斷該套哪個模式重構
3. 改造（抽 references/、寫 scripts/、瘦身 SKILL.md）
4. 重跑 audit → 直到過關
```

### C. 量測 skill 成本（驗證改造效果）

```
1. 開乾淨 session，觸發目標 skill 跑一次代表性任務
2. python scripts/skill-cost-measure.py --latest --skill <name>
3. 兩次測量（改造前 / 改造後）的數字寫入 references/baseline-<skill>.md
```

## 5 大設計模式速查（細節見 [references/patterns.md](references/patterns.md)）

| 模式 | 何時用 | 一句話骨架 |
|------|--------|-----------|
| **Tool Wrapper** | 包住 API / cmd / 第三方工具細節 | scripts/ 封裝指令，SKILL.md 只說「呼叫 X」 |
| **Generator** | 產出固定格式的內容（報告 / 文件 / 程式碼） | assets/template-*.md 模板，subagent 填空 |
| **Reviewer** | 檢查產物是否符合標準 | scripts/check-*.py 硬門檻，不過關擋下 |
| **Inversion** | Agent 主導對話、先完整收集需求再執行 | SKILL.md 列「必問問題清單」、不准跳問 |
| **Pipeline** | 多步驟流程、後一步依賴前一步 | SKILL.md 列順序拆解步驟、每步有完成判定 |

## 反模式自查（命中任一 → 不准交付）

- ❌ **能用邏輯（grep / regex / 行數 / schema）判定的事，寫成 LLM 自查條目** — 該寫成 script（見 [principles.md「邏輯優先於語意」](references/principles.md#邏輯優先於語意)）
- ❌ SKILL.md > 500 行（軟上限；硬性目標 ≤ 200）
- ❌ 同一條規則在 SKILL.md 寫兩次以上
- ❌ inline 整段大模板 / SOP（應抽 references/ 或 assets/）
- ❌ scripts/*.py 缺 UTF-8 stdout 強制處理（Windows 中文必亂）
- ❌ 全域 skill 內出現絕對路徑（Windows `[盤符]:\...` / Unix home 路徑）→ 應改 `<project>` / `~/` 佔位符
- ❌ frontmatter 缺 description / triggers / pattern 任一
- ❌ description < 30 字 或 triggers < 3 個（undertrigger 風險）
- ❌ pattern 欄位不在 5 模式白名單（tool-wrapper / generator / reviewer / inversion / pipeline）
- ❌ 跳過 Inversion 訪談直接呼叫 new-skill.py（會繼承腦補風險）
- ❌ references/ 檔 ≥ 300 行卻沒有 TOC

## 標準目錄結構

```
<skill-name>/
├── SKILL.md          ← 必備，含 YAML frontmatter
├── scripts/          ← 機械操作（路徑解析 / 檔案 IO / 檢查器 / 量測器）
├── references/       ← 大段 SOP / 模式說明 / 領域知識（subagent / 主 agent 按需 Read）
└── assets/           ← 模板檔 / 範本（filled-in 後成為產出）
```

## audit-skill.py 檢查規則

分兩級：**Fail**（exit ≠ 0，硬擋）/ **Warning**（exit = 0 但回報）。
`--strict` 旗標可把 warning 升為 fail。`--scope global|project` 控專案 hardcode 是否檢。

### Fail（客觀可判定，違規必擋）

| 檢查項 | 規則 |
|--------|------|
| frontmatter 必要欄位 | 缺 `name` / `description` / `triggers` 任一即 fail |
| SKILL.md 行數 | > 500 行即 fail（Anthropic 紅線） |
| 專案 hardcode | 全域 skill 內 grep 命中 `TSLG / catclaw / Projects\\` 等關鍵字（`--scope global` 時生效） |

### Warning（語意難精準，列示請人審）

| 檢查項 | 規則 |
|--------|------|
| SKILL.md 行數 200~500 | 軟上限提醒，可考慮抽 references/ |
| description 字數 | < 30 字 → 警告（可能 undertrigger） |
| triggers 數量 | < 3 個 → 警告（覆蓋面不足） |
| **pattern 欄位** | 缺 / 不在 5 模式白名單 → 警告（從起點就標模式，audit 與 new-skill 都能用） |
| **目錄結構** | SKILL.md > 200 行但無 scripts/references/assets 任一 → 警告（該抽分層） |
| **evals/triggers.json**（global） | 缺檔 / 查詢 < 10 / 仍含佔位符 → 警告（無法驗證觸發精準度） |
| 疑似重複規則 | 列出短語重複次數 ≥ 3 的段落請人審（regex 抓不準語意） |
| inline 模板過大 | 連續 ≥ 30 行 code block → 建議抽 assets/ |
| script UTF-8 stdout | `scripts/*.py` 缺 `sys.stdout.reconfigure(encoding="utf-8")` → 警告 |
| script 錯誤處理 | `scripts/*.py` 主程式無 try/except 包 → 警告（silent failure 風險） |
| references TOC | 檔 ≥ 300 行缺 `## 目錄` / `## Table of Contents` → 警告 |

## 與其他工具的關係

- **`/handoff`**：跨 session 移交流程 — 寫 skill 跨 session 時用
- **`/code-review`**：審 skill 的程式碼層面（scripts/*.py 的品質）— 與本 skill 的「結構稽核」互補
- **`/memory`**：寫 skill 時學到的反覆模式 → atom 化保存

## 注意事項

- 本 skill 自身也必須通過 audit（吃自己的狗食）
- 修改本 skill 後，重跑 `audit-skill.py` 確認沒退化
- 寫新 skill 時若發現本 skill 規則不足以涵蓋情境 → 補進 references/patterns.md，**禁止偷加規則到目標 skill 私有**

# 5 大設計模式

> Google Cloud Tech 提出、Anthropic skill-creator 內化的模式集。每個模式對應一類問題，可單用也可組合。

## 目錄

- [模式選擇決策樹](#模式選擇決策樹)
- [1. Tool Wrapper](#1-tool-wrapper)
- [2. Generator](#2-generator)
- [3. Reviewer](#3-reviewer)
- [4. Inversion](#4-inversion)
- [5. Pipeline](#5-pipeline)
- [模式組合範例](#模式組合範例)

---

## 模式選擇決策樹

```
你要解決的問題是什麼？
│
├─ 「包住某個工具 / API / CLI 的細節」
│   → Tool Wrapper
│
├─ 「產出固定格式的東西（報告 / 程式碼 / 文件）」
│   → Generator
│
├─ 「檢查產物是否符合某標準」
│   → Reviewer
│
├─ 「先把使用者需求問清楚再執行」
│   → Inversion
│
└─ 「多步驟流程、前後步驟依賴」
    → Pipeline
```

**經驗法則**：複雜任務通常 = Pipeline + 數個其他模式組合。

---

## 1. Tool Wrapper

**用來幹嘛**：把第三方工具（CLI / API / 第三方 SDK）的細節封裝起來，讓 SKILL.md 不必反覆描述指令語法。

**何時用**：
- 工具呼叫有特殊參數 / 編碼陷阱（如 SVN 中文 codepage）
- 多個 skill 都會用到同一個工具
- 指令容易手打錯（路徑長、轉義複雜）

**骨架**：

```
<skill>/
├── SKILL.md          ← 只說「跑 scripts/foo.py」
└── scripts/
    └── foo.py        ← 封裝 cmd / API call、回 JSON
```

**SKILL.md 寫法**：

```markdown
## Step 3：複製檔案
跑 `python scripts/copy.py --src <路徑> --dst <路徑>`
失敗時看 stderr 訊息，**不要自己改用 xcopy / Copy-Item**（編碼陷阱已封進腳本）
```

**反例**：在 SKILL.md 寫整段 cmd / PowerShell 細節。下次參數要改，多個 skill 都要同步改 → 災難。

---

## 2. Generator

**用來幹嘛**：產出有固定結構的內容（報告 / 文件 / 程式碼骨架）。

**何時用**：
- 多次產出相同形式（玩法分析報告、技術分析報告）
- 想確保格式穩定不變
- 內容由 LLM 填，結構由模板定

**骨架**：

```
<skill>/
├── SKILL.md          ← 引導「先讀模板再填」
└── assets/
    ├── template-foo.md   ← 含章節骨架 + 註記「此區填 X」
    └── template-bar.md
```

**SKILL.md 寫法**：

```markdown
## Step 7：產出報告
讀 `assets/template-report.md` → 按章節填入內容
**禁止改變章節順序與標題**
```

**反例**：把整份模板 inline 寫進 SKILL.md（觸發即載入，重複燒 token）。

---

## 3. Reviewer

**用來幹嘛**：硬門檻檢查產物，違規擋下不放行。

**⚠️ 設計鐵則（呼應 [principles.md 「邏輯優先於語意」](principles.md#邏輯優先於語意)）**：
- 能用 grep / regex / 行數 / 結構 判定的規則 → **必須**寫成 script
- 不要寫成「請 LLM 自查」放 SKILL.md — 那叫 prompt-based review，不是 Reviewer 模式
- LLM 自查只用在「真的需要語意理解」的場合（內容合理性、領域邏輯）
- **regex 掃描含元用法的文本**（模板 / 自查清單 / 設計文件）→ **必須跳過** fenced code block（` ``` ` 起訖）與 inline code（`` ` `` 包裹）。否則模板裡 `` `*(待補)*` `` 之類的說明性引用會被誤殺。check-pending.py 第一版就吃過這個坑

**何時用**：
- 有客觀可判定的規則（行數 / 命名 / 是否含某字串）
- agent 自律無法確保（如「禁止裸 `*(待補)*`」）
- 流程結束前要把關

**骨架**：

```
<skill>/
├── SKILL.md          ← 「Step N 跑 audit，過關才繼續」
└── scripts/
    └── check-foo.py  ← exit code 0/1 + 違規清單
```

**SKILL.md 寫法**：

```markdown
## Step 8：硬門檻檢查
跑 `python scripts/check-pending.py <檔案>`
exit 0 → 進 Step 9；exit ≠ 0 → 看 stderr 列出的違規行，回頭補完
**禁止跳過此步驟自行判斷「應該沒問題」**
```

**反例**：規則寫在 SKILL.md 靠 LLM 自查 → 偷懶率非零。

---

## 4. Inversion

**用來幹嘛**：讓 agent 主導對話，先完整收集使用者需求再執行，避免邊做邊問。

**何時用**：
- 任務啟動前缺多項參數
- 使用者描述模糊（「幫我做個 X」）
- 漏問一項就重做的代價高

**骨架**：

```
<skill>/
├── SKILL.md          ← 含「必問清單」與 AskUserQuestion 範本
└── references/
    └── questions.md  ← 各情境的問題集
```

**SKILL.md 寫法**：

```markdown
## Step 1：需求收集（強制走完，不准跳）
依以下順序問使用者，**任何問題答不出來就停**：
1. 目標檔案 / 模組
2. 預期讀者（開發 / PM / 主管）
3. 緊急程度（影響步驟細節）

收集完才能進 Step 2，禁止「邊做邊補問」。
```

**反例**：跳到執行階段才發現參數不足，停下來問 → 浪費 token，使用者體驗差。

---

## 5. Pipeline

**用來幹嘛**：多步驟流程，每步有明確完成判定，後一步依賴前一步。

**何時用**：
- 流程 ≥ 3 步且有先後關係
- 中間步驟需驗證才能進下一步
- 失敗點不應重跑整個流程（要能單步重試）

**骨架**：

```
<skill>/
├── SKILL.md          ← Step 1~N，每步含「完成判定」
└── scripts/
    └── *.py          ← 各步驟工具
```

**SKILL.md 寫法**：

```markdown
## Step 1：A → 跑 prepare.py → 看 JSON status=ok
## Step 2：B → 讀 Step 1 產出檔 → ...
## Step 3：C → ...

**每步必須有完成判定（exit code / 檔案存在 / JSON 欄位）**
**禁止「我覺得 OK」式跳步**
```

**反例**：步驟模糊（「先理解規格，然後寫報告」）→ agent 不知何時算完成、何時可進下一步。

---

## 進階模式組合表

實戰 skill 多為多模式組合。**選主模式（frontmatter 標 pattern）+ 套副模式（SKILL.md 流程內體現）**：

| 組合 | 適用場景 | 主+副 | 範例 |
|------|---------|-------|------|
| **Inversion → Generator** | 訪談後產出固定格式 | inversion → generator | 專案規劃文件、需求文件 |
| **Pipeline + Reviewer** | 多步驟流程末端品質閘門 | pipeline + reviewer | 文件生成、報告產出 |
| **Tool Wrapper + Reviewer** | API 操作 + 規則對齊 | tool-wrapper + reviewer | API call + best practices check |
| **Generator + Reviewer** | 產出後自我審查 | generator + reviewer | 程式碼骨架 + lint |
| **Inversion → Pipeline** | 訪談完跑複雜流程 | inversion + pipeline | 系統架構設計 |
| **多 Tool Wrapper 並存** | 多 API / 工具整合 | 每 wrapper 獨立 skill | DevOps 工具集 |

**選擇規則**：
- 主模式 = 整個 skill 最核心的職責（決定 frontmatter `pattern` 欄位值）
- 副模式 = 流程中某 step 體現，**禁止**把多模式骨架混進 SKILL.md（會違反 Lean）
- 副模式邏輯通常封進 scripts/（如 Reviewer 套在 Pipeline 末端 → 寫成 `check-final.py`）

## 模式組合範例

### 範例 A：規格分析 skill（analyze-spec）

| 步驟 | 模式 |
|------|------|
| 路徑解析 + 檔案複製 | Tool Wrapper（封裝 xcopy / 編碼） |
| Subagent prompt 組裝 | Tool Wrapper（避免主 agent 每次手寫） |
| 規格大小判定（S/M/L） | Pipeline（決定後續步驟切法） |
| 玩法 / 技術報告產出 | Generator（template-gameplay.md / template-technical.md） |
| 待補項硬門檻 | Reviewer（check-pending.py） |
| SVN commit | Tool Wrapper（封裝中文 codepage SOP） |
| 整體流程 | Pipeline（Step 1~9 順序） |

### 範例 B：需求釐清 skill

| 步驟 | 模式 |
|------|------|
| 開頭收集需求 | Inversion |
| 產出需求文件 | Generator |
| 文件審查 | Reviewer |

### 範例 C：純檢查器 skill（如 code-review）

| 步驟 | 模式 |
|------|------|
| 全流程 | Reviewer（純檢查、不產出內容） |
| 規則加載 | Tool Wrapper（rules 抽 scripts/ 內） |

---
name: extract
description: 手動知識萃取：從當前對話抽取 atom（補 LLM 自動萃取漏網）
---

# /extract — 手動知識萃取

> 手動觸發當前對話的知識萃取，不需等待 SessionEnd。
> 全域 Skill，適用任何專案。

---

## 使用方式

```
/extract
```

無參數。從當前對話的 assistant 回應中萃取知識。

---

## Step 1: 確認前置條件

1. 用 Bash tool 檢查 Ollama 是否可用：
```bash
curl -s http://127.0.0.1:11434/api/tags 2>/dev/null | head -1
```

2. 若不可用 → 告知使用者需先啟動 Ollama（`ollama serve`），結束。

## Step 2: 找到對話 transcript

用 Bash tool 找到當前 session 的 transcript 檔案：

```bash
ls -t ~/.claude/projects/*/memory/_staging/transcript*.jsonl 2>/dev/null | head -1
```

若找不到 transcript，改為直接從對話上下文萃取：
- 回顧本次對話中 assistant 的回應內容
- 自行整理出有價值的知識點

## Step 3: 執行萃取

有兩種路徑：

### 路徑 A：有 transcript 檔案

用 Bash tool 執行 extract-worker.py：

```bash
echo '{"mode":"per_turn","max_chars":8000,"max_items":5}' | python ~/.claude/hooks/extract-worker.py
```

捕獲輸出（JSON 格式），解析 `extracted_items`。

### 路徑 B：無 transcript（直接從對話萃取）

自行分析本次對話，找出：
- **factual**：事實性知識（API 行為、工具特性、環境差異）
- **procedural**：操作步驟、指令組合
- **architectural**：架構決策、設計選擇
- **pitfall**：踩到的坑、容易出錯的地方
- **decision**：做出的決策及理由

## Step 4: 展示結果

列出萃取到的知識項目，格式：

```
## 萃取結果

1. [類型] 知識摘要
   → 建議寫入：{atom 名稱} 或 新建 atom
   → 信心：[臨]

2. [類型] 知識摘要
   → 建議寫入：{atom 名稱}
   → 信心：[臨]
```

## Step 5: 互動確認

詢問使用者：
- 哪些要寫入 atom？（逐項確認或全部接受）
- 要寫入哪個 atom？（建議 + 使用者決定）
- 信心等級是否調整？（預設 [臨]，使用者可升為 [觀] 或 [固]）

確認後執行寫入。

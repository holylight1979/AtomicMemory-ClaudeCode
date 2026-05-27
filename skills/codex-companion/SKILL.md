---
name: codex-companion
description: 切換 Codex Companion 監督系統開關（GPT 第二意見審計）
---

# /codex-companion — Codex Companion 開關

> 切換 Codex Companion 監督系統。啟用後，Codex (GPT) 會在計畫審閱與 turn 審計時提供第二意見。
> 全域 Skill，適用任何專案。

---

## 使用方式

```
/codex-companion
```

無參數。每次執行切換開/關狀態。

---

## Step 1: 讀取目前狀態

用 Read tool 讀取：

```
~/.claude/workflow/config.json
```

取得 `codex_companion.enabled` 欄位值（布林值，預設 `false`）。

## Step 2: 切換狀態

- 目前 `false`（或不存在）→ 改為 `true`
- 目前 `true` → 改為 `false`

用 Edit tool 修改 `config.json` 中的 `codex_companion.enabled` 值。

## Step 3: Service 管理

- **開啟時**：檢查 companion service 是否在跑（`curl http://127.0.0.1:3850/health`）。若沒跑，用 Bash 背景啟動：
  ```
  python ~/.claude/tools/codex-companion/service.py &
  ```
- **關閉時**：送 shutdown 信號：
  ```
  curl -X POST http://127.0.0.1:3850/shutdown
  ```

## Step 4: 回報

回覆切換結果：

- **開啟**：「Codex Companion 已開啟。計畫審閱與 turn 審計將由 Codex 提供第二意見。」
- **關閉**：「Codex Companion 已關閉。」

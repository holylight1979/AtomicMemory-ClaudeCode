---
name: atom-debug
description: 切換原子記憶系統的注入/萃取 debug log（寫入 ~/.claude/Logs/atom-debug-*.log）
disable-model-invocation: true
---

# /atom-debug — 原子記憶 Debug Log 開關

> 切換原子記憶系統的注入/萃取 debug log。開啟後，每次注入和萃取的內容會寫入 `~/.claude/Logs/atom-debug-{日期}.log`。
> 全域 Skill，適用任何專案。

---

## 使用方式

```
/atom-debug
```

無參數。每次執行切換開/關狀態。

---

## Step 1: 讀取目前狀態

用 Read tool 讀取：

```
~/.claude/workflow/config.json
```

取得 `atom_debug` 欄位值（布林值，預設 `false`）。

## Step 2: 切換狀態

- 目前 `false`（或不存在）→ 改為 `true`
- 目前 `true` → 改為 `false`

用 Edit tool 修改 `config.json` 中的 `atom_debug` 值。

## Step 3: 回報

回覆切換結果：

- **開啟**：「Atom Debug Log 已開啟。注入/萃取內容將記錄至 `~/.claude/Logs/atom-debug-{日期}.log`。」
- **關閉**：「Atom Debug Log 已關閉。」

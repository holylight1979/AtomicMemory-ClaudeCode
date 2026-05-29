---
name: <skill-name>
description: <30+ 字。例：「任何要用 X API / X CLI 操作 Y 的場合都該觸發，避免 agent 自己拼接指令出錯」>
userInvocable: true
triggers: <關鍵字1>, <關鍵字2>, <關鍵字3>, <關鍵字4>, <關鍵字5>
pattern: tool-wrapper
---

# Skill：<skill-name>（Tool Wrapper）

> 封裝 `<被包工具>` 的指令細節 / 編碼陷阱 / 常用參數，讓主 agent 不必每次手寫指令。

## 觸發

- 使用者要求 `<被包工具>` 相關操作
- 主 agent 即將執行 `<被包工具>` 指令前 — 強制改呼叫本 skill 的 scripts

## 核心鐵則

1. **禁止主 agent 直接打 `<被包工具>` 指令** — 一律走 scripts/ wrapper
2. wrapper 失敗時看 stderr，**不要自己改用替代指令** — 編碼陷阱已封進腳本

## 工作流程

### Step 1：判定操作類型
- 解析使用者意圖 → 對應 scripts/<action>.py

### Step 2：呼叫對應 wrapper
- `python scripts/<action>.py <args>`
- 完成判定：JSON status == "ok"

### Step 3：失敗處理
- exit ≠ 0 → 看 stderr 訊息
- 回報使用者，**不重試 / 不繞道**

## 必備 scripts（範例）

| script | 動作 |
|--------|------|
| scripts/list.py | 列出 <被包工具> 的可用資源 |
| scripts/exec.py | 執行 <被包工具> 主要操作 |

## 反模式

- ❌ SKILL.md 內 inline 寫整段 `<被包工具>` 指令範例
- ❌ 主 agent 看到 wrapper 失敗就改用其他指令
- ❌ wrapper 內未強制 UTF-8 stdout（Windows 中文必亂）

## 注意事項

- 平台限定：<Windows-only / Unix-only / 通用>
- 已知坑：<例如中文 codepage、特殊參數轉義>

---
name: codex-companion
description: 切換 Codex Companion 監督系統開關（GPT 第二意見審計）
---

# /codex-companion — Codex Companion 開關

> 切換 Codex Companion 監督系統。啟用後，Codex (GPT) 會在計畫審閱、turn 審計、跨 session handoff 自檢時提供獨立第二意見。
> 全域 Skill，適用任何專案。
>
> **Handoff 自檢**：寫入 `_staging/next-phase*.md` 或 handoff 檔時，Codex 以 skills/handoff Step 3.5 的 8 問當對抗式 checklist 複審交接文件——把作者「自評」升級為獨立「他評」，補掉「作者抓不到自身盲點」的缺口（中度缺口即浮上、不被預設 high 門檻吞）。由 `soft_gate.handoff_review` 控制（預設開）。
>
> **架構**：本 skill 只切換 config flag，不管理 service 生命週期；Codex 稽核以短命子程序 `tools/codex-companion/audit.py`（in-process state）執行，無常駐 daemon。

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

## Step 3: 回報

回覆切換結果：

- **開啟**：「Codex Companion 已開啟。計畫審閱、turn 審計、handoff 自檢會 spawn `audit.py` 短命子程序由 Codex 提供第二意見。」
- **關閉**：「Codex Companion 已關閉。」

無需額外清理 — 下次 hook 觸發即生效，沒有常駐 daemon。

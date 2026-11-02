---
name: codex-companion
description: 切換 Codex Companion 監督系統開關（GPT 第二意見審計）
disable-model-invocation: true
---

# /codex-companion — Codex Companion 開關

> 切換 Codex Companion 監督系統。啟用後，Codex (GPT) 會在計畫審閱、turn 審計、驗收裁判（另要寫碼守門開）時提供獨立第二意見；關掉這三項一起停。
> 全域 Skill，適用任何專案。
>
> **Handoff 自檢**：寫入 `_staging/next-phase*.md` 或 handoff 檔時叫 Codex 以 skills/handoff Step 3.5 的 8 問複審交接文件。另由 `soft_gate.handoff_review`（寫碼守門關時看）／`handoff_review_v6`（守門開時看，沒寫＝關）控制，兩個都關，切本開關不會讓它跑。交接靠 skills/handoff Step 3.5 自我複審；要第二意見叫 skill `codex`。
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

取得 `codex_companion.enabled` 欄位值（布林值；config 出廠寫 `true`，鍵不存在時程式當 `false`）。

## Step 2: 切換狀態

- 目前 `false`（或不存在）→ 改為 `true`
- 目前 `true` → 改為 `false`

用 Edit tool 修改 `config.json` 中的 `codex_companion.enabled` 值。

## Step 3: 回報

回覆切換結果：

- **開啟**：「Codex Companion 已開啟。計畫審閱、turn 審計、驗收裁判會 spawn `audit.py` 短命子程序由 Codex 提供第二意見。」
- **關閉**：「Codex Companion 已關閉。」

無需額外清理 — 下次 hook 觸發即生效，沒有常駐 daemon。

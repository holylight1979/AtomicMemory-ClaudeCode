---
name: generate-episodic
description: 手動生成 episodic atom（補自動 episodic 生成）
disable-model-invocation: true
---

# /generate-episodic — 手動生成 episodic atom

> 手動觸發 episodic atom 生成。用於 SessionEnd 未觸發時的補救。
> 全域 Skill，適用任何專案。

---

## 使用方式

```
/generate-episodic
```

無參數。從最近有工作的 session state 生成 episodic atom。

---

## 執行步驟

用 Bash tool 執行：

```bash
python ~/.claude/tools/generate-episodic-manual.py
```

根據輸出回報結果：
- `[OK] Generated: xxx` → 告知使用者生成成功，顯示檔名
- `[SKIP] ...` → 告知原因（無工作 session / 已生成 / 門檻不足）
- `[ERROR] ...` → 顯示錯誤訊息

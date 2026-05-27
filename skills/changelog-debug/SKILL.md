---
name: changelog-debug
description: Hook 觸發失靈時手動滾動 _CHANGELOG.md（正常情況自動觸發，這是 debug 用）
---

---
description: /changelog-roll — 手動滾動 _CHANGELOG.md（自動觸發已掛 PostToolUse，通常不用手跑）
---

# /changelog-debug

手動滾動 `_AIDocs/_CHANGELOG.md`：保留最新 N 條（預設 8），其餘搬 `_CHANGELOG_ARCHIVE.md`。

PostToolUse hook 已在寫入 `_CHANGELOG.md` 後自動偵測並觸發 — 這個 skill 通常只在 debug / 強制 roll / 手動指定 `--keep` 時用。

## 用法

- `/changelog-roll`：預設 keep=8
- `/changelog-roll --dry-run`：僅預覽會搬哪幾條
- `/changelog-roll --keep 12`：改閾值
- `/changelog-roll --quiet`：靜音

## 實作

呼叫 `python tools/changelog-roll.py` 傳入參數。工具失敗 → stderr + exit 2，不動任何檔。

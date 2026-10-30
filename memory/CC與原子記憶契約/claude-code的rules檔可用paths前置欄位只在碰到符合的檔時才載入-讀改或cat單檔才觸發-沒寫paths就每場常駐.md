# claude-code的rules檔可用paths前置欄位只在碰到符合的檔時才載入-讀改或cat單檔才觸發-沒寫paths就每場常駐

- Scope: global
- Author: holylight
- Source: https://code.claude.com/docs/en/memory（2026-10-30 查）
- Confidence: [臨]
- Trigger: rules 檔, paths:, 條件載入, 常駐 token, 必載檔瘦身, path-scoped rule, CLAUDE.md import
- Created-at: 2026-10-30

## 知識

- [臨] （官方文件）~/.claude/rules 與專案 .claude/rules 的 md 開頭寫 YAML `paths:`（glob 清單），只在 AI 用 Read／Write／Edit 碰到符合的檔、或 Bash cat／head 讀單一檔時才載入；使用者層的 glob 以 session 主工作目錄為基準。沒寫 paths 的規則每場啟動就載入。
- [臨] 文件沒寫：grep 是否觸發、載入後是否全程保留；壓縮後要等下次符合才重載。CLAUDE.md 的 @import 沒有條件載入。

## 行動

- 只在寫程式時要的規則：放 rules 檔加 paths，不放 IDENTITY；「讀程式前就要看到」的句子不能靠 paths（要等讀了才載入）

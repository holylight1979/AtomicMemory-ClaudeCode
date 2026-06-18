# 在資料庫層面儲存角色-id-char-id-時必須使用-sql-的-bigint-unsigned-類型來

- Scope: global
- Author: auto-captured
- Confidence: [臨]
- Trigger: auto-capture
- Created-at: 2026-06-18

## 知識

- [臨] 在資料庫層面儲存角色 ID (`char_id`) 時，必須使用 SQL 的 `BIGINT UNSIGNED` 類型來直接儲存 C# 的 `ulong` 型別。此做法能有效避免標準 47 模組序列化路徑可能導致的 int 截斷風險。

## 行動

- （依知識內容判斷）

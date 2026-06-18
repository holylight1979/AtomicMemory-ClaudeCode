# 由於無法使用框架-orm需透過-mysqlxclient-的原始-sql-api-進行操作executenon

- Scope: global
- Author: auto-captured
- Confidence: [臨]
- Trigger: auto-capture
- Created-at: 2026-06-18

## 知識

- [臨] 由於無法使用框架 ORM，需透過 `MysqlxClient` 的原始 SQL API 進行操作：`ExecuteNonQuery(sql, args)` (DDL/DML) 和 `ExecuteReader(sql, args)` (SELECT)。結果集為乾淨的 `List<object[]>`

## 行動

- （依知識內容判斷）

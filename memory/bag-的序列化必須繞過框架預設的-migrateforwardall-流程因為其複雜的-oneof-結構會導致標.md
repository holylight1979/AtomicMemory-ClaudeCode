# bag-的序列化必須繞過框架預設的-migrateforwardall-流程因為其複雜的-oneof-結構會導致標

- Scope: global
- Author: auto-captured
- Confidence: [臨]
- Trigger: auto-capture
- Created-at: 2026-06-18

## 知識

- [臨] Bag 的序列化必須繞過框架預設的 `MigrateForwardAll` 流程，因為其複雜的 oneof 結構會導致標準路徑失敗。必須建立自帶獨立軌：自訂正向（解 blob→寫 Bag 表）+ 自訂反向（讀 Bag 表→重建 typed），並使用 `MsgEqualsSemantic` 進行安全比

## 行動

- （依知識內容判斷）

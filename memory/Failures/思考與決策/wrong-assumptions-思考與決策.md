# 假設錯誤（Wrong Assumptions）

- Scope: project
- Confidence: [臨]
- Trigger: 假設錯誤, 誤判, 直覺假設, wrong assumption, 前提錯
- Type: procedural
- Created: 2026-09-01

## 知識

### [臨] 跨專案掃描時，索引生成器（`to_atom_entries`）丟棄了 `scop  (2026-09-01)

- **始末**：跨專案掃描時，索引生成器（`to_atom_entries`）丟棄了 `scope` 欄位，導致後續的 `ups_search.py` 無法進行範圍過濾。這使得系統無法執行 SPEC §8.1 所要求的「personal/」或「roles/」跨專案邊界檢查，造成他人個人資料（other user's
- **根因**：_(待補：深寫時由 Claude 補完)_
- **設計原理**：_(待補：深寫時由 Claude 補完)_
- **運作邏輯**：_(待補：深寫時由 Claude 補完)_
- **防再犯**：_(待補：深寫時由 Claude 補完)_

### [臨] 在執行 AtomAudit 時，系統錯誤地假設「路標命中（source == '  (2026-09-01)

- **始末**：在執行 AtomAudit 時，系統錯誤地假設「路標命中（source == 'trigger'）」即代表該原子與當前任務域吻合。這忽略了跨專案注入的原子來源，導致稽核機制無法區分本地觸發和外部洩漏的內容，誤判為有效知識。
- **根因**：_(待補：深寫時由 Claude 補完)_
- **設計原理**：_(待補：深寫時由 Claude 補完)_
- **運作邏輯**：_(待補：深寫時由 Claude 補完)_
- **防再犯**：_(待補：深寫時由 Claude 補完)_

## 行動

- 同全域 failures 共通行動規則

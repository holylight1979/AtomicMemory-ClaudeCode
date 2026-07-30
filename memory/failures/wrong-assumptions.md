# 假設錯誤（Wrong Assumptions）

- Scope: project
- Confidence: [臨]
- Type: procedural
- Created: 2026-07-30

## 知識

### [臨] 觸發：WorkerHost 在處理狀態持久化時，若新呼叫端省略了 ledger   (2026-07-30)

- **始末**：觸發：WorkerHost 在處理狀態持久化時，若新呼叫端省略了 ledger 參數 → 錯誤行為：系統預設使用 in-memory 模式，導致數據丟失且未拋出任何警告或異常（靜默退化）→ 正確做法：必須對關鍵的持久化參數進行強制非空檢查與類型驗證；若缺失，應立即回傳致命錯誤而非允許執行。
- **根因**：_(待補：深寫時由 Claude 補完)_
- **設計原理**：_(待補：深寫時由 Claude 補完)_
- **運作邏輯**：_(待補：深寫時由 Claude 補完)_
- **防再犯**：_(待補：深寫時由 Claude 補完)_

### [臨] 觸發：Worker local guard 實作了 Policy Snapsho  (2026-07-30)

- **始末**：觸發：Worker local guard 實作了 Policy Snapshot ID 的驗證機制 → 錯誤行為：僅檢查 snapshot id 是否非空，誤以為這足以防止 policy drift（政策漂移）→ 正確做法：必須將單純的「存在性」檢查提升為「版本一致性」或「內容哈希比對」，確保 w
- **根因**：_(待補：深寫時由 Claude 補完)_
- **設計原理**：_(待補：深寫時由 Claude 補完)_
- **運作邏輯**：_(待補：深寫時由 Claude 補完)_
- **防再犯**：_(待補：深寫時由 Claude 補完)_

## 行動

- 同全域 failures 共通行動規則

# 假設錯誤（Wrong Assumptions）

- Scope: project
- Confidence: [臨]
- Trigger: 假設錯誤, 誤判, 直覺假設, wrong assumption, 前提錯
- Type: procedural
- Created: 2026-10-12

## 知識

### [臨] 觸發：處理多條並行開發線（a3/track-e）和複雜的退件流程。  (2026-10-12)

- **始末**：觸發：處理多條並行開發線（a3/track-e）和複雜的退件流程。 → 錯誤行為：在單一 session 中累積過多的上下文、分支狀態與審查結果，導致當系統提示 context 滿時，難以順利切換或維護工作流狀態。 → 正確做法：對於涉及多個獨立且需要長期追蹤的工作流，應主動將每個工作流隔離到專門的
  <!-- src: aa22a0ec#unresolved 未對回原句 -->
- **根因**：_(待補：深寫時由 Claude 補完)_
- **設計原理**：_(待補：深寫時由 Claude 補完)_
- **運作邏輯**：_(待補：深寫時由 Claude 補完)_
- **防再犯**：_(待補：深寫時由 Claude 補完)_

## 行動

- 同全域 failures 共通行動規則

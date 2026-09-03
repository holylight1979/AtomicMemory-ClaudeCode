# 契約加欄位必查手寫映射點-單元綠不代表wire存活

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: DTO 加欄位, wire parser, 手寫映射, TryParse, 序列化 drift, 契約欄位, E2E 探針, 逐欄重建
- Created-at: 2026-08-13
- Related: 歸因早停-找到合理嫌疑機制就停止驗證, goal-driven-verify-loopkarpathy-吸收, 弱訊號自動推導的狀態寫入必須只補不降級-不得覆蓋強訊號既有值

## 知識

- [臨]（2026-08-13 Proj-JARVIS T8d 實例）給共用契約（DTO）加新欄位時，若接收端存在「手寫逐欄位重建」的 parser/mapper（非直接反序列化），新欄會被靜默丟棄：服務層單元/整合測試全綠（測的是物件層）、真 wire 上欄位全空。實例：MemorySummaryItem 加 content 欄，MemoryWireParser.TryParseItem 手寫重建漏接，管理視窗與探針都收到空內容，靠真 Server 的 E2E 探針才現形。
- [臨] 防線兩手：① 改契約後 grep 該型別名找出所有手寫映射點（TryParse/Map/Compose 類）同步補欄；② 新欄位補一條「序列化→parser→斷言」的 roundtrip 測試釘住。驗收層面：端對端行為用真線路探針驗，不信單層測試的綠。

## 行動

- 改到共用契約/DTO 欄位 → 先搜手寫映射點再收工，並補 roundtrip 斷言
- 新功能穿越 wire 邊界時，出口驗證至少一趟真線路 E2E

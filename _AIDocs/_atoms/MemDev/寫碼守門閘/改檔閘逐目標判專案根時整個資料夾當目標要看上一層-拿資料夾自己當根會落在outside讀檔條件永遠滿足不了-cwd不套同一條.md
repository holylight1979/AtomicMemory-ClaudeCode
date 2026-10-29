# 改檔閘逐目標判專案根時整個資料夾當目標要看上一層-拿資料夾自己當根會落在outside讀檔條件永遠滿足不了-cwd不套同一條

- Scope: global
- Author: holylight
- Source: 2026-10-23 跨層閘與寫入目標判定修補實測
- Confidence: [臨]
- Trigger: write_target_root, _project_root_of, 改檔閘判根, 資料夾目標, (outside), rm -rf 資料夾, Remove-Item -Recurse, 部位鍵, 擋滿放行
- Created-at: 2026-10-23
- Related: 閘判不了時只免掉判不了的那一條-能獨立判的照查-擋滿放行要走正常放行路徑

## 知識

- [臨] 改檔閘逐個目標判專案根時，「整個資料夾當目標」（rm -rf、Remove-Item -Recurse、搬走）要看它所在的上一層：拿資料夾自己當根，目標相對根落在 (outside)，閘要求的讀檔永遠滿足不了，只能等擋滿放行。
- [臨] cwd 這類「我在哪」的目錄不能套同一條（它自己就是要判的根的起點），兩者分兩支函式：寫入目標用 write_target_root，所在目錄用 _project_root_of；部位鍵等其他「按目標判根」的地方要跟改檔閘呼叫同一支。

## 行動

- 新增「按寫入目標判根」的地方一律呼叫 write_target_root，不自己拿目標路徑找根
- 案例要有「刪整個資料夾」的目標，斷言算出的根是上一層、相對路徑不是 (outside)

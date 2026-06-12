# powershell7-寫檔預設無BOM會剝源碼檔BOM

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: Set-Content, Out-File, BOM, utf8, 編碼, 批次替換, PowerShell 寫檔, 亂碼
- Created-at: 2026-06-12

## 知識

- [臨] PowerShell 7 `Set-Content/Out-File -Encoding utf8` 是「UTF-8 無 BOM」——對既有帶 BOM 的源碼檔做正則批次替換回寫，會靜默剝掉 BOM（diff 首行出現 `-﻿using` 才看得到）
- [臨] 風險：BOM-less UTF-8 含中文註解的 .cs，Roslyn 無 BOM 時可能退回系統碼頁誤判編碼（Windows CP950 環境）；其他工具鏈同理
- [臨] 對策：批次改源碼檔回寫用 `[IO.File]::WriteAllText($p,$c,(New-Object Text.UTF8Encoding $true))`（$true=帶 BOM），或乾脆用 Edit 工具逐點改；commit 前 `svn diff`/`git diff` 檢查首行有無 BOM 變更
- [臨] 出處：2026-06-12 SGI H-3 範本推廣，HospitalV2DataModule.cs 批次替換後 BOM 被剝，逐 hunk 自審揪出後還原

## 行動

- PS 批次替換源碼檔後，回寫一律 UTF8Encoding($true) 或改用 Edit 工具
- commit 前 diff 檢查首行

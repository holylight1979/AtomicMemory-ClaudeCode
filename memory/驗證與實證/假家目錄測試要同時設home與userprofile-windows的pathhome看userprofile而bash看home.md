# 假家目錄測試要同時設HOME與USERPROFILE-Windows的Path.home看USERPROFILE而bash看HOME

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 假家目錄, fake home, USERPROFILE, Path.home, 隔離測試, HOME 環境變數, 測試打到真家, tmp home
- Created-at: 2026-10-05
- Source: session:46e124e0#6449dbac 2026-10-05
- Quote: 「好。開工吧，請盡量多開agent高速完工，並且也要派Codex+你自己的agent 進行 從項目計畫開始的審查。」

## 知識

- [臨] Windows 上用環境變數把家目錄指到暫存夾做隔離測試（實測 2026-10-05）：只設 `HOME` → Python `Path.home()` 仍回真家（它看 `USERPROFILE`）；只設 `USERPROFILE` → Git Bash 的 `$HOME` 仍是真家。兩個必須同時設，否則會改到真實家目錄。
- [臨] 環境變數隔離不了三種東西：用 `__file__` 定位資料的腳本（改的是腳本所在那棵樹）、讀 `APPDATA`／npm 全域 prefix 的工具、會 spawn 背景安裝程序的 hook。測試要呼叫目標樹內那份腳本，並跳過或攔住會背景安裝的步驟。

## 行動

- 寫會動家目錄的工具時：父程序把 HOME 與 USERPROFILE 都強制設成同一個值再傳給所有子程序
- 隔離測試前先印出解析後的目標路徑確認不是真家

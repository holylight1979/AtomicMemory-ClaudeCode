# 判斷有沒有改到用內容指紋-去行尾空白空行與共同縮排-不可逐行strip-指紋取完整結構不取顯示字串

- Scope: global
- Author: holylight
- Source: reading-path 減量（commit c468623f，codex 審查 B1/B2）
- Confidence: [臨]
- Trigger: 內容指紋, 有沒有改到, 去共同縮排, strip 誤判, 函式指紋, 只問改到的
- Created-at: 2026-10-22
- Quote: 「<pasted_content id="e02d"> 調度總控台：你是 v6.0 的調度總控台，執行 /console 調度，接替 claude-ba（token 快乾）。專案根 C:\Users\holylight\.claude（main）；接續單 C:\Users\holylight\.claude\memory\_staging\next-phase-v6.0-寫程式碼的進化.md；信箱…」

## 知識

- [臨] 逐行去頭尾空白會把「一行從內層 if 移到外層 for」判成沒改：要去行尾空白、去空行、整段去共同縮排再雜湊（搬位置不算改、相對縮排變了算改）；原始碼在量測之前讀，量測中改檔只會多問。類別、路徑這類條目的指紋取完整結構（全部成員、實際經過的函式），不取顯示用的數據字串（會截在前幾項；數字一樣但換了路也該算改）。

## 行動

- 用指紋判「這段改了沒」：寫一個縮排搬移案例與一個搬位置案例先證判法

# windows上node測試chdir進暫存夾後rmSync刪不掉當前目錄-空catch吞錯每跑一次留一個殘目錄-收尾先chdir離開再刪失敗印warn

- Scope: global
- Author: holylight
- Source: track-dedupe-ai-judge 2026-10-20 e014730a（總控台代寫）
- Confidence: [臨]
- Trigger: process.chdir, fs.rmSync, 殘目錄, 暫存夾刪不掉, EBUSY, node 測試 收尾, 空 catch, %TEMP% 殘留
- Created-at: 2026-10-20
- Quote: 「"下個寫碼session" !? 他們有空就讓他們修完不是嗎..? 這也是我說 "我從未答應把這種東西另外放進修正計畫" 的狀況... 倘若是 Codex 或審查時挖出來的、但LLM判斷後 其實屬於"飄移"的，直接不做，但倘若有關且確實有問題，就應該要立即修正」

## 知識

- [臨] Windows 上 node 測試用 process.chdir 進暫存資料夾後，收尾 fs.rmSync 刪不掉「當前工作目錄」（EBUSY）；外面包的空 catch 把錯吞掉，每跑一次就留一個 %TEMP%\<prefix>-* 殘目錄，測試照綠。正解：收尾先 chdir 離開（回原 cwd 或 os.tmpdir）再 rmSync，刪不掉印 warn 不吃掉。

## 行動

- node 測試有 chdir 進暫存夾：收尾先 chdir 離開再刪；定期看 %TEMP% 有沒有同前綴殘目錄

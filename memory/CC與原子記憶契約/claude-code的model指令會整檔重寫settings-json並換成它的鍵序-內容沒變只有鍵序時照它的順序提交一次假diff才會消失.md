# claude-code的model指令會整檔重寫settings-json並換成它的鍵序-內容沒變只有鍵序時照它的順序提交一次假diff才會消失

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: /model, settings.json 被改, 鍵序, settings.json diff, model 欄位, 假 diff
- Created-at: 2026-11-05
- Source: session:9f83cf22#15d1ba32 2026-11-05
- Quote: 「都收割了? 我另外想到 "安裝" 方面有沒有文件需要更新，或者是參閱現有狀態與理解後 改進 的?」

## 知識

- [臨] `/model <名字>` 會把 settings.json 整檔重寫：加一行 `"model"`，並把所有鍵排成它自己的順序（頂層鍵搜到尾端、hook 項目內的鍵也改序）。git diff 看起來像刪了四個設定，逐鍵比對其實全在、只是位置變了。
- [臨] 不提交會每場都出同一份假 diff；解法是拿掉 model 那行（repo 公開、模型各機自選）、照它的鍵序提交一次。

## 行動

- settings.json 出現大片 diff 先用 json.load 逐鍵比對 HEAD，別看文字 diff下結論
- 只有鍵序不同時：拿掉 model 行、照新順序提交

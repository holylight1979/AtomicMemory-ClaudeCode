# 互補卡樣本-既有內容接近預算

- Scope: global
- Author: tester
- Confidence: [臨]
- Trigger: 互補卡, append 預算, 樣本
- Created-at: 2026-10-08
- Depends: path:C:/x/y.py

## 知識

- [臨] 既有結論一：寫入閘的預算算的是 knowledge 區的 UTF-8 bytes，CJK 一字三 bytes，所以中文卡大約只容一千字，逐筆個案一多就會撞線。
- [臨] 既有結論二：append 是 atom 肥大化的實際路徑，一次一點累積成山，所以 append 也要算既有加新增，而不是只看這次送進來的幾行。
- [臨] 既有結論三：超預算的正解不是把內容截斷塞進去，截斷會把教訓的語義截掉；正解是把個案細節寫進部位文件，卡只留結論一行加路徑。
- [臨] 既有結論四：導讀卡五段齊才有用，缺段的卡注入了也只是半張地圖；Depends 指主要檔，健檢靠它在檔消失時標過期。
- [臨] 既有結論五：矛盾偵測排在預算之前，同一張卡可能先被判矛盾再被預算擋，先用 python 量 bytes 再送可以省兩輪來回。
- [臨] 既有結論六：js 端不另寫判定句，所有擋回訊息的句子都來自 py 的 reason，js 只把 kind、bytes、limit、route_to 這些欄位 echo 出來。
- [臨] 既有結論七：org 寫入要在改寫成 shared 之前先過 realm 閘，否則公司層永遠不會檢查專案名，別的專案就會看到帶專案名的卡。
- [臨] 既有結論八：萃取 item 的 route 欄是選填，但 part_doc 必帶 part，global 與 candidate_global 的 summary 不得帶專案名，要先 scrub 再報。
- [臨] 既有結論九：追蹤項落 workflow/tracking 帳本一行一筆 LF，有部位的同時寫進病灶文件，收尾報告才算誠實。
- [臨] 既有結論十：這張卡的知識區兩千 bytes 上下，離三千零七十二的預算剩一千出頭，補短句進得去、補長段會超。
- [臨] 既有結論十一：補一條短句還進得去，補一段一千四百 bytes 的個案敘事就會超，閘要回該去哪而不是把句子砍半。
- [臨] 既有結論十二：填充到此為止，後面的行動段不算進預算。

## 行動

- 改閘前先讀 lib/hub_card.py 與 tools/memory-write-gate.py

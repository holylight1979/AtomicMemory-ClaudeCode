# 改設定預設值時舊案例用autouse-fixture把預設釘回舊值-斷言一行不動-新預設另開案例檔-子行程案例要被跑的檔自己釘

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 改預設值, autouse fixture, monkeypatch.setitem, 預設 dict, 釘回舊值, 舊案例斷言, 子行程吃不到 monkeypatch
- Created-at: 2026-10-27
- Related: 改模組層路徑常數的驗法-常數名不改只換等號右邊-import時就算好要用冷啟動子行程驗-預設參數定義時綁死-測試模組層setdefault會依收集順序污染
- Source: session:17c8cd5c#840617df 2026-10-27

## 知識

- [臨] 改設定預設值時，照舊預設寫的既有案例不改斷言：在該測試檔加 autouse fixture，用 monkeypatch.setitem 把設定預設 dict 的那一鍵釘回舊值；新預設的行為另開案例檔測。diff 只多一個 fixture，舊斷言一行不動。
- [臨] 前提：程式在呼叫當下才讀那個預設 dict 來合併；若 import 時就拷一份或算好，setitem 改不到。
- [臨] 例外：案例是起子行程跑的，子行程吃不到父行程的 monkeypatch，要在被跑的那支檔自己釘舊值。

## 行動

- 改預設前先確認合併點是呼叫當下讀同一個 dict
- 跑子行程的案例另行在被跑的檔內釘值

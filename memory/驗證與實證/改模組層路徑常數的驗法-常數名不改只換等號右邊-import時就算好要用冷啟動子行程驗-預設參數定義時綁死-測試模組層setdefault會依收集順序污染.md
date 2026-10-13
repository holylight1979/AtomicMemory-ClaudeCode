# 改模組層路徑常數的驗法-常數名不改只換等號右邊-import時就算好要用冷啟動子行程驗-預設參數定義時綁死-測試模組層setdefault會依收集順序污染

- Scope: global
- Author: holylight
- Source: session df3c2d29（v6 A2c 盤點與退件 017）
- Confidence: [臨]
- Trigger: 模組層常數, 路徑常數, import 時計算, 冷啟動, 子行程驗證, 預設參數綁死, setdefault, 收集順序, 測試污染, python -P
- Created-at: 2026-10-13

## 知識

- [臨] 把模組層的路徑常數改成吃環境變數時，常數名不要改，只換等號右邊：引用點一個都不用動，diff 小、好審。
- [臨] 模組層常數在第一次 import 時就算好了：同一個行程裡先 import 再設環境變數，測不到新行為（假綠或假紅）。要用冷啟動的子行程驗：先設好環境變數再開新行程 import，帶 `-P`（或把 cwd 設在暫存夾），避免 cwd 裡同名的套件被先載到。
- [臨] 函式預設參數（`def f(root=CLAUDE_DIR)`）在定義時就綁死了，改常數或事後 monkeypatch 都影響不到；要預設 None，在函式裡再取值。
- [臨] 測試檔在模組層寫 `os.environ.setdefault(...)`，會在 pytest 收集階段就生效、而且留到整個行程結束，後收集的檔會依收集順序被污染（單跑綠、合跑紅，或反過來）。環境變數要放在 fixture 裡用 monkeypatch.setenv，或在子行程的 env 參數裡給。

## 行動

- 改模組層常數：名字不動、只換右邊；用冷啟動子行程（-P）驗新值
- 掃一遍預設參數用到該常數的地方，改成 None 再在函式裡取值
- 測試的環境變數不要寫在模組層，放 fixture 或子行程 env

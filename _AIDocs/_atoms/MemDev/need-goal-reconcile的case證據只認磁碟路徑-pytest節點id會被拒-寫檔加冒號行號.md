# need_goal-reconcile的case證據只認磁碟路徑-pytest節點id會被拒-寫檔加冒號行號

- Scope: global
- Author: holylight
- Source: session 68f0fc93 2026-10-14（track-fix-depends-recall 001 交付）
- Confidence: [臨]
- Trigger: need_goal reconcile, reconcile 拒收, 不在磁碟上, case 證據, pytest 節點 id, 驗證案例證據, evidence kind case
- Created-at: 2026-10-14

- Related: 先寫紅案例再分多次edit改同一檔會被重試計數當成反覆修正-fixescalation與deeppostmortem誤觸, 收尾放行確認的選項要用固定字樣-放行這一回合-自訂選項文字使用者選了也不算

## 知識

- [臨]（實跑 2026-10-14）need_goal(action=reconcile) 的 evidence kind=case，ref 寫成 pytest 節點 id（`hooks/verify/x.py::test_name`）會整筆拒收，訊息是「驗證案例 … 不在磁碟上」：檢查把整串當檔案路徑查 exists()。改寫成 `hooks/verify/x.py:833`（檔＋冒號行號）就收下。
- [臨] case／file 證據只能標 read（讀碼），實測只配收據 R<號>；要讓案例算實測，引用跑過它的那筆 pytest 收據，案例檔:行另列讀碼。

## 行動

- reconcile 引案例：寫「檔:行」，不寫 pytest 的 ::測試名
- 要實測等級：引最後一次改動之後跑的收據 R<號>

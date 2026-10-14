# need_goal-reconcile的case證據只認磁碟路徑-pytest節點id會被拒-寫檔加冒號行號

- Scope: global
- Author: holylight
- Source: session 68f0fc93 2026-10-14（track-fix-depends-recall 001 交付）
- Confidence: [臨]
- Trigger: need_goal reconcile, reconcile 拒收, 不在磁碟上, case 證據, pytest 節點 id, 驗證案例證據, evidence kind case, CASE_NODE_ID_NEEDS_DEF
- Status: 節點 id 已接受（hooks/wg_need_goal.py _node_id_missing）
- Created-at: 2026-10-14
- Related: 先寫紅案例再分多次edit改同一檔會被重試計數當成反覆修正-fixescalation與deeppostmortem誤觸, 收尾放行確認的選項要用固定字樣-放行這一回合-自訂選項文字使用者選了也不算

## 知識

- [臨] need_goal(action=reconcile) 的 case／file 證據收兩種寫法：「檔」或「檔:行」只查檔在不在；pytest 節點 id（`檔::test`、`檔::Class::test[參數]`）要檔在且檔裡找得到那個 def 才收，寫了類別就只在那個類別裡找（ast，不比字串）。
- [臨] 節點 id 對不上時拒收訊息印「規則 CASE_NODE_ID_NEEDS_DEF｜證據：檔在=是／否（路徑）、def <名> 找到=是／否」，照它改檔名或測試名就過。
- [臨] case／file 證據只能標 read；實測只配收據 R<號>，而且要是最後一次改動之後跑的，改前紅的收據不能列進證據。

## 行動

- reconcile 引案例：「檔:行」或 pytest 節點 id 都可以，節點 id 要寫對類別與測試名
- 要實測等級：引最後一次改動之後跑的收據 R<號>，改前紅的留在交付信當紅案例證據

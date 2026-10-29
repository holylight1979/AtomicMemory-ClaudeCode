# atom-set-realm搬回core的卡會被收割的realm自動搬移再搬回local-要改realm先查自動分類判法否則白搬

- Scope: global
- Author: holylight
- Source: claude-ce 總控台 2026-10-21 深夜實遇
- Confidence: [臨]
- Trigger: atom-set-realm, realm 自動搬移, 搬回 memory, 收割搬卡, E16 退路雜訊
- Created-at: 2026-10-21

## 知識

- [臨] 用 tools/atom-set-realm.py --to-core 把本地範疇卡搬回 memory/ 後，下一次 knowledge harvest（vcs-sync 收割）的 realm 自動搬移會照自動分類再把它搬回 _AIDocs/_atoms/（10-21 實遇：「第二意見分歧裁決…」搬兩次都被 446b99f0 類收割提交 rename 回去）。手動搬 realm 前要先看自動分類為什麼判它 local，改判法或改卡內容，不然白搬。
- [臨] 後果：綁 Entry 的卡若住 local realm，wave2 資料根（只帶 memory/）帶不到，那個切入點只剩退路雜訊。
- [臨] 代價已量到：第四跑 C′ 的 C2／C3（被第二意見閘擋後寫「改動小不需」沒開工作）兩位判分者都歸「卡教錯」，因為 E16 那一刻只送到退路雜訊；第三跑同題是過的。綁 Entry 的判準卡不該住 local realm，自動分類要把 Entry 非空當成 core 的硬條件。
- [臨] 已修（綁 Entry 的卡由 ENTRY_BOUND_STAYS_CORE 擋住自動搬移）；沒綁 Entry 的卡照舊會被搬，要改 realm 仍要先查自動分類判法。

## 行動

- （依知識內容判斷）

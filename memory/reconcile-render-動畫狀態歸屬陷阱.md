# reconcile-render 動畫狀態歸屬陷阱

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: reconcile, render, world.html, 每隔一段時間跳, 彈回原位, snap back, 動畫狀態, POLL_MS, wander, 漫步, model 重建, requestAnimationFrame, _wox, el._x, 畫面跳刷新
- Created-at: 2026-06-02
- Related: 腦內世界-v3-自癒與-command-bus-架構, guardian-dashboard-孤兒佔埠與新碼重啟, feedback-completion-gates

## 知識

- [臨] 症狀：reconcile 渲染的畫面每隔固定秒數（=輪詢間隔）全體元素瞬間彈回原位；但被拖過/釘住的元素不彈。看似 BUG 其實是動畫狀態歸屬錯置。
- [臨] 根因模式：reconcile 渲染（DOM 元素以穩定 id 為 key 持久存活、跨輪詢重用）+ 每輪詢 `model = buildModel()` 整批重建資料物件 `c`，再 `el._c = c` 重綁。任何 **per-element 暫態動畫狀態**（漫步偏移、漂移目標、計時器）若存在被丟棄重建的 `c` 上，每輪詢就被靜默歸零 → 下一幀位置回 `slotX + 0` → 全體彈回。
- [臨] 判別線索：被拖過的元素不彈 = 它的狀態（如 `el._pinned`/`el._x`）存在持久 `el` 上躲過重建；其餘彈 = 狀態存在 ephemeral `c` 上被沖掉。誰活下來就指向誰是正確 owner。
- [臨] 修法：把暫態動畫狀態從 `c` 搬到持久的 `el`（與 `el._x`/`el._pinned`/`el._tier` 同類），`c` 只留 model 資料（slotX、roomMinX、active…）。非把輪詢間隔調大去遮症狀。
- [臨] 反例（別做）：加大 POLL_MS、停掉 refresh、對 transform 加 CSS transition（會與每幀 rAF 更新打架成橡皮筋）——都是表面修。
- [臨] 驗證法（時序問題截圖看不出）：Playwright 開頁，跨 ≥2 個輪詢邊界每 200ms 取樣 `el._x`，檢 (a) 結構：狀態在 el、c 上為 null；(b) 行為：`_c` 物件換身前後 prevX≈newX 無不連續、最大單步 px 約等於 lerp 漂移量。本案實測 maxStep 4px、邊界 483→484 無跳。

## 行動

- 改 reconcile 渲染前先問：哪些是 per-frame 暫態動畫狀態？一律掛持久 el，不掛每輪詢重建的 model 物件
- 遇『每隔 N 秒全體彈回、拖過的不彈』先查輪詢間隔 vs 動畫狀態 owner，別當 BUG 亂修
- 時序/流暢度問題用 Playwright 跨輪詢邊界取樣驗證，不靠截圖

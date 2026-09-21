# 注入記帳以送達為準-裁切後才算 injected-宣稱送出但被總額砍掉的 atom 不得計曝光與效用

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: injected_atoms, dropped_trim, pointer_trim, reconcile_injection, 總額裁切, 曝光記帳, usefulness 分母, 1200 tok 硬頂, 送達 vs 送出, injection-turns.jsonl, rescue watch
- Created-at: 2026-09-21

## 知識

- [臨] 2026-09-21 發現：assemble_injection 先把 atom 記進 injected_atoms／曝光／rescue watch，之後總額裁切（_truncate_context_by_activation）才發生，被砍掉的 atom 仍算「已注入」→ Stop 效用歸因分母灌水、Wilson 晉升偏低、rescue 誤報「注入了你沒用」。離線重播 175 例有 133 例超過 1,200 tok 名義硬頂，等於硬頂只是裝飾。
- [臨] 判斷為什麼會寫成這樣：注入與裁切是兩個時期分別加的功能，各自正確、沒人回頭對齊「記帳點」；LLM 寫增量功能時傾向在自己新加的函式內記帳，而不是在管線終點記。
- [臨] 修法契約：記帳點放在管線最後一步之後（reconcile_injection_after_trim 回傳 survivors），dropped_trim 撤 injected／watch／曝光，pointer_trim 撤 watch 但保留路標曝光；三態（full／pointer／dropped）全計費，塞不下就記 dropped 不送，硬頂變真硬頂。任何遙測「事件發生」的定義必須是使用者實際看得到的那一刻。

## 行動

- 新增任何「注入後處理」（裁切、去冗、降級）：確認 injected_atoms／曝光／watch 的寫入點在它之後，或有 reconcile 撤銷
- 效用數字異常偏低：先比對 injection-turns.jsonl 的 delivered 與 dropped_trim 比例

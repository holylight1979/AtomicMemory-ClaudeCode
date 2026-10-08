---
from: tslg
seq: 022
re: root/023
ts: 2026-10-07 21:10
type: answer
---
這封在說什麼：根層用兩種提問審了本專案真實提交 r4170（新手教學修四件事），兩種都指出同一個可能漏洞，要我開程式碼核實。核了：**成立**，程式層面確實有這個洞；實際會不會踩到，我沒跑遊戲，標推測。偏移：無偏移。

## 看程式知道的（`Client\TSLG_Hotfix\`，現行 HEAD r4172 的檔）

Codex 的指控：「取消判定依賴引導目標（Unity 的 Transform）是否還活著；若目標先被銷毀、面板才關，取消流程會跳過，`OnGuideCancel` 不會回呼，劇本協程永久等待」。逐句對程式：

1. `Game\ui\Tutorial\UITutorial.cs` `CancelGuide()`（第 739-747 行）第一行是 `if (this._guideTarget == null) { return; }`。`_guideTarget` 是 Unity 的 Transform；Unity 對已銷毀物件的 `== null` 會回 true。所以**目標先被銷毀、面板後關** → 這一行直接 return，`_onGuideCancel` 不會被呼叫。指控第一句成立。
2. 面板關閉走 `OnUIDisable()`（第 149-157 行）→ `CancelGuide()`，沒有別的路會呼叫 onCancel。
3. `Game\Tutorial\TutorialMgr.cs` 的劇本協程 `CorPlay`（第 128-130 行）等的是 `while (_waitingGuide == e) yield WaitForOneFrame`；`_waitingGuide` 只在 `OnGuideFinish`（點到目標）與 `OnGuideCancel → Stop()` 時清掉。onCancel 沒來，這個 while 就不會結束。指控第二句成立。
4. `UITutorial.OnUpdate()`（第 419-427 行）每幀只管聚焦動畫與跟隨，**沒有**「目標被銷毀就當取消」的檢查。所以沒有別的機制補這個洞。
5. 提交訊息說「避免協程永久等待」；它修的是「面板被關掉」這條路，沒涵蓋「目標先沒了」這條。矛盾成立。

## 不確定的（推測）

- 實際會不會發生，取決於「引導目標的物件被銷毀」是否早於「教學面板關閉」。換場景時兩者的先後順序我沒查，也沒跑遊戲。
- `TutorialMgr` 另有兩處 `Stop()`（第 328、360 行），觸發條件我沒讀；若其中一處掛在換場景或關閉教學系統上，協程最終會被收掉，「永久」會變成「拖到那時」。

## 結論

**成立（程式層面）**：`CancelGuide` 用「目標還在不在」當前置條件，讓「目標先銷毀」這條路繞過了取消回呼；修法是把 `_guideTarget == null` 改成只判「有沒有在等（例如 `_onGuideCancel != null`）」，目標是否存活不該決定要不要通知取消。這是提交作者（lalatry724）的檔，我不改，報給使用者。

這是「問 AI 三個問題」與「現在的提問」在真實提交上一起抓到的第一個、經人核實的洞。

## 自檢
- 本封斷言分級：看程式知道 5 句（上面 1～5）／試過 0／推測 2 句／大家同意 0。
- 上一封我說錯或說過頭的：tslg/021 沒有新斷言需要改。
- 本封最弱的一句：「沒有別的機制補這個洞」——只讀了 `OnUpdate` 與 grep 到的呼叫點，`TickTrack` 本體沒讀；補證＝讀 `TickTrack` 全文看它對已銷毀的 `_trackTarget` 做什麼。
- 本封結論拐了幾個彎：二（早退條件 → 協程等待條件 → 矛盾）。

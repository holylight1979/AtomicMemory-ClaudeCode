# 反轉驗證換回舊版會同時改暫存區要restore-staged-新案走舊碼就有的入口才紅在斷言

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 反轉, 退回舊版, 紅在斷言, AttributeError, git checkout -- 檔案, restore --staged, raising=False, 新案退回紅, 保護案例
- Created-at: 2026-10-13
- Source: session:ec069e59 2026-10-13
- Quote: 「你是 v6.0 的「待命 track-e」，總控台是 claude-ad。現在只做三件事就停：①用 ToolSearch 載入工具（query: select:SendMessage,ListAgents）②用 ListAgents 看自己的名字（列表最上面「This session is …」那行）③SendMessage 給 claude-ad 一句「待命 track-e：<你的名字>」。之…」

## 知識

- [臨] 「把原始碼換回舊版、測試留新版，確認新案會紅」時：`git checkout <舊版> -- 檔案` 會同時改寫暫存區，跑完把新版複製回來後要 `git restore --staged <檔案>`，否則暫存區留著舊版、下一次提交可能帶到舊內容。複製回原位的動作也可能被「改碼後要有新案例」類的閘記成最後一次改碼。
- [臨] 新案要能在舊碼上「紅在斷言」而不是 AttributeError：走舊碼就有的入口（公開判定函式、hook 入口），不直接呼叫新加的函式；替身用 `monkeypatch.setattr(..., raising=False)`；讀新欄位用 `.get()`。退回後要分類失敗型別，全是 AssertionError 才算數。
- [臨] 交付描述要分開寫「新增負例（退回會紅）」與「既有保護案例（新舊都綠）」；參數化案例不能概括成「舊碼全紅」。
- [臨] 新案要在舊碼上紅在斷言的三個小做法：預先放的 state 用字面值 dict，不用新簽名的 helper 產生；對新增屬性的 monkeypatch 加 `raising=False`（舊模組沒有該屬性也不炸）；同一案裡行為斷言放前面、新 API 細節斷言放最後。反證跑完用 `--tb=line` 檢查每個紅的例外種類都是 AssertionError，紅在 TypeError／AttributeError 的只證明舊碼沒這支函式。
- [臨] 本體先 commit 再做反證，還原用 `git checkout HEAD -- <檔>`：工作樹與暫存區一起回到已提交的新版，不會留下 staged 的舊內容。未提交的改動上不能這樣還原，會連同別的未提交改動一起丟掉。
- [臨] 暫改只動要驗的那一處：用小腳本做精確字串替換，並斷言恰好命中一次。命中零次或多次就是改錯地方，那次反證不算。
- [臨] 一個測試裡有好幾個斷言、修補也分好幾處時，要逐處分開退：一起退只能證明第一個斷言對應的那一處（例：同一案驗 detect_evasion 和 _dismissed，只退 _dismissed 才知道它真的被鎖住）。
- [臨] 斷言如果對整份樣板做子字串比對，可能比到樣板裡的範例句而假綠，要只取填入的那一段來比。
- [臨] 不碰 git 暫存區的換回做法：小腳本先讀工作樹現檔 bytes，`git show <基準>:<檔>` 取舊版 bytes 蓋回原位，`pytest -k <新案名>` 只跑新案，`finally` 寫回先前讀到的 bytes 並比對相等才算還原。暫存區完全不動，不用 restore --staged；寫回的是跑之前讀到的內容，所以檔案上未提交的改動也保住。基準 rev、受測檔、測試檔、-k 表達式都當參數，同一支腳本可跨輪重用。
- [臨] 只看 pytest 紅綠分不出「哪一案是新修的、哪一案是新舊都綠的保護案」：另寫逐案對照腳本，同一批輸入在基準版本與現在版本各跑一次、印「基準＝結果／現在＝結果／預期」。每次在全新子行程載入模組，避免同一行程拿到快取的舊模組。換回寫法同上（讀 bytes、蓋舊版、finally 寫回比對）。

## 行動

- 反轉後一律 git status＋git restore --staged，確認工作樹與暫存區都乾淨
- 退回跑完用 grep 分類 AssertionError／AttributeError 等失敗型別再下結論

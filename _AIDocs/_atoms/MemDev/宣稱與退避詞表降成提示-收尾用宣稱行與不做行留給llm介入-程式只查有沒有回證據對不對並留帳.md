# 宣稱與退避詞表降成提示-收尾用宣稱行與不做行留給LLM介入-程式只查有沒有回證據對不對並留帳

- Scope: global
- Author: holylight
- Source: session:c27d1d9a 2026-10-20
- Confidence: [臨]
- Trigger: 宣稱行, 不做行, 不是退避, CLAIM_WORDS_ARE_HINTS, NOT_DOING_DECLARED, USER_WAIVER_NEEDS_CITATION, 說明句誤擋, 非本回合宣稱, 對應哪張收據, 退避例外入口, 先這樣 跳過 豁免, claim_disclaimed, testfail_waived, G6 階段 4, 判斷入口盤點 P6, P7
- Created-at: 2026-10-20

## 知識

- [臨] G6 階段 4（判斷入口盤點 P6＋P7，2026-10-20 合 main）：收尾閘的「修好／量了／試過」詞表與退避詞表都只是提示，語意交 LLM。(a)(b)(c) 命中且沒證據時，擋訊息要 AI 回一行「宣稱｜修好：非本回合宣稱，因為 <理由>」（放行、guard-reconcile 記 claim_disclaimed）或「宣稱｜修好：收據 <指令的完整 token 或哨兵名>」（程式核對那張收據過原本資格、晚於改檔）；退避語所在那一行對到「不做｜<哪一件>：<理由>」或「不是退避｜<命中的詞>：因為…」就不標不擋、留帳；使用者說「先這樣／跳過」不再整段關掉偵測與紅測清單，AI 要寫「不做｜<哪一件>：使用者說「<原句片段>」」對到具體那一件。規則 CLAIM_WORDS_ARE_HINTS／CLAIM_DISCLAIM_NEEDS_REASON／CLAIM_RECEIPT_REF_MATCH／NOT_DOING_DECLARED／USER_WAIVER_NEEDS_CITATION（hooks/wg_release_rules.py）。
- [臨] 設計邊界：程式只查「有沒有回、理由有沒有文字內容、引用對不對得到」，不評理由充不充分；AI 一律回「非本回合宣稱」能繞，是刻意保留的（靠留帳抽查），不是洞。真正的洞是核對本身：收據引用要是指令的完整 token（python／pytest／.py 這類通用字不算指名）、指到的收據仍要過原本資格（參數寫哨兵字樣的 echo 不能靠指名洗白）、引用純標點不算且英文整詞比對、紅測事項完整 token 比對。
- [臨] 實測踩到的：宣稱行「非本回合宣稱」本身含退避詞「非本回合」，會被 DeferralGate 當退縮語擋回——結構行是對閘的回答，偵測要先跳過它（is_claim_line）。測試只斷言「ReconcileGate 不在輸出」會漏掉別的閘擋住，放行案要斷言整個輸出沒有 "block"。

## 行動

- 被 (a)(b)(c) 擋而那句不是自己本回合的宣稱：回「宣稱｜修好：非本回合宣稱，因為 …」；是宣稱但程式對不上收據：回「宣稱｜修好：收據 <指令的完整 token>」
- 真的不做：寫「不做｜<哪一件>：<風險／為什麼超出>」；使用者叫跳過：引用原句對到那一件；說明句被誤命中：「不是退避｜<命中的詞>：因為 …」
- 再加結構行這類「對閘的回答」時，先確認其他詞表閘不會把它當命中

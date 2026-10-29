# UserPromptSubmit路的判斷入口形狀-命中先記待判問句接判準卡-Stop在所有閘前收行首標籤是不是理由取最後一條-到下一則使用者本人訊息沒回只記沒回不照詞表判

- Scope: global
- Author: holylight
- Source: track-g6-rules-to-llm 001 代寫 2026-10-22
- Confidence: [臨]
- Trigger: 判斷入口, UPS 問一句, 糾正｜, 否決記憶｜, 詞表只提示, undeclared
- Created-at: 2026-10-22

## 知識

- [臨] UserPromptSubmit 路的判斷入口：詞表命中先記成待判，問句接判準卡（entry_note user_prompt）；Stop 在所有閘之前收本回合可見文字裡行首的「<標籤>｜是／不是：理由」（取最後一條）；到下一則使用者本人打的訊息還沒回，只記成沒回、不照詞表判；背景通知與同伴訊息不結帳。先例：wg_friction 糾正（E38）、wg_extraction 否決（E39）。

## 行動

- （依知識內容判斷）

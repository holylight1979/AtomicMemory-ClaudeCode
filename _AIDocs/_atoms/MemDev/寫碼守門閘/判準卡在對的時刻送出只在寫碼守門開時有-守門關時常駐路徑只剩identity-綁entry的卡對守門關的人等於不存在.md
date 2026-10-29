# 判準卡在對的時刻送出只在寫碼守門開時有-守門關時常駐路徑只剩IDENTITY-綁entry的卡對守門關的人等於不存在

- Scope: global
- Author: holylight
- Source: hooks/handlers/pre_tool_use.py _with_cards；post_tool_use mcp_reply；ups_gates／user_prompt_submit；stop card_note
- Confidence: [臨]
- Trigger: 判準卡, entry_note, 切入點, 綁 Entry, 寫碼守門關, 對的時刻送卡, 守門關時有沒有作用, v6 拔掉
- Created-at: 2026-10-29
- Quote: 「那.. "值得留: v6 裡「在對的時刻把提醒送到 AI 眼前」的機制" 現在是 v6旗標關閉、也就無效、不會作用嗎? 還是與v6開關 沒有絕對關聯呢?」

## 知識

- [臨] 「問的那一刻接判準卡」幾乎每個送卡點都先檢查寫碼守門開關：PreToolUse 擋訊息與提醒、MCP 回覆、使用者訊息的糾正問句、Stop 擋訊息都是開著才送；而且送卡的時刻（定位行、批判行）本身就是守門製造的。守門關時綁 Entry 的卡不會在任何時刻送出。
- [臨] 要讓一條判準對守門關的使用者也生效：寫進 IDENTITY（每 session 載入），或另做不看開關的觸發點（例如本回合第一次讀程式檔）；只綁 Entry 不夠。評「守門哪些部分值得留」時，送卡機制要算在守門裡，不是獨立功能。

## 行動

- 說「某機制關掉守門也在」之前，grep 它的呼叫點前有沒有 v6_enabled
- 新判準要對守門關的人生效就放 IDENTITY

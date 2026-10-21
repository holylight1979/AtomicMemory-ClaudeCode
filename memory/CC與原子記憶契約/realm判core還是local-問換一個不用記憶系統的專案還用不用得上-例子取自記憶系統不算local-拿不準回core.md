# realm判core還是local-問換一個不用記憶系統的專案還用不用得上-例子取自記憶系統不算local-拿不準回core

- Scope: global
- Author: holylight
- Source: _AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-2026-10-21.md E31
- Confidence: [臨]
- Trigger: realm, core, local, refile, Else, 範疇歸檔, 詞庫 miss, llm_classify_realm, unsure
- Created-at: 2026-10-21
- Quote: 「A」
- Entry: E31

## 知識

- [臨] 判準：換到一個沒裝原子記憶系統的專案，這張卡的判準或做法還用得上 → core；只有改 ~/.claude 本身（hook、索引、記憶系統工具）或只在某台機器的某個外部工具才碰得到 → local。
- [臨] 看知識段的判準／通則那條，不看實例：實例取自記憶系統開發、Quote 或 Source 裡出現 ~/.claude 路徑，都不代表它是 local。
- [臨] 拿不準時回 core、不要回 unsure：程式把 unsure 搬到 _AIDocs/_atoms/Else，那張卡從此不再跨專案注入；判 local 還會把 terms 寫進學習詞庫，錯一次會擴散。
- [臨] 反例：「斷言要錨結果句不能錨系統有反應」的實例是記憶系統的驗證腳本，但任何專案寫驗證都適用 → core。

## 行動

- 先找知識段裡的通則句，問它離開記憶系統還成不成立
- 只有整張卡都在講 ~/.claude 內部的檔名、設定、hook 才判 local

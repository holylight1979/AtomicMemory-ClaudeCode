# harness提示這條指令改了你讀過的檔-指向全機共用的claude目錄時不等於是你改的-先看差異是誰的資料與自己寫到哪個資料根

- Scope: global
- Author: holylight
- Source: merge 7eaf2824（擋訊息瘦身）2026-10-27
- Confidence: [臨]
- Trigger: 改了你讀過的檔, file modified 提示, 檔案被改, 誰改的, 多 session 共用 ~/.claude, 共用目錄, 資料根, WG_CLAUDE_DIR, 誤認自己改的
- Created-at: 2026-10-27
- Related: 測試收尾不清共用的live量測檔-多session同機共用claude時truncate會刪掉別人的真實資料-測試用monkeypatch改路徑

## 知識

- [臨] harness 提示「這條指令改了你讀過的檔」、指的是 ~/.claude 的檔時，不等於是你改的：同一台機器多個 session 共用 ~/.claude，別人剛好在同一段時間寫了它也會觸發這個提示。
- [臨] 下結論前先看兩件：①差異內容是誰的資料（例：索引裡的範疇張數是 live 自己的卡數，不是你測試產的）；②自己的行程寫到哪個資料根（本系統看 WG_CLAUDE_DIR 指哪）。兩件都對不上就不是你。

## 行動

- 看到「改了你讀過的檔」指向共用目錄：先對差異內容與自己的資料根，再決定要不要還原或追查
- 不是自己改的就不動它，別把別人的真實資料當測試殘留清掉

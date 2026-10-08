# sgi 工作區：路徑前綴 → 部位導讀卡（給根層做「第一次改該部位的檔之前先整張注入」用）

> 寫的人：c:\Projects session，2026-10-08。前綴以工作區根 `c:\Projects\` 起算，用正斜線；比對用「開頭符合」，由上往下第一個命中為準。導讀卡在 `c:\Projects\.claude\memory\shared\<範疇>\` 底下，名稱欄是 atom 名。「狀態」寫「有」的才存在，其餘是排程。

| 順序 | 路徑前綴 | 部位 | 導讀卡（atom 名） | 狀態 |
|---|---|---|---|---|
| 1 | `sgi_server/MapServer/Guild/` | Server／軍團域（H-6 拆分後六子 Manager＋facade） | `server部位導讀-mapserver主邏輯-上下游與權威-已知病灶-驗證方式` | 有（2026-10-08） |
| 2 | `sgi_server/MapServer/` | Server／主邏輯（Handler、Manager、DataModule、Entity） | 同上 | 有 |
| 3 | `sgi_server/PlayerDbServer/`、`sgi_server/Shared/Proto/PlayerDbServer/` | Server／玩家存檔（blob，已退版分表） | 退版指路：`blob轉sql已退版-決策日期備份位置與三方分工`（CharDataBlob 範疇） | 有（既有卡） |
| 4 | `sgi_server/ServerTools/Merge/` | 合服工具（四模式八步驟） | `合服部位導讀-merge工具四模式八步驟-世界模型與不變量-動手前必問-已知病灶-驗證方式`（`shared/合服/`） | 有（2026-10-08） |
| 5 | `sgi_server/Shared/` | Server／共用契約（ErrorCode、OpCode 經 Link 連結熱更層、Proto、Form 自動生成） | 同第 2 列；另注意「兩份常數檔不同步」（控制塔 §9 第 5 列） | 有（併入 Server 卡） |
| 6 | `sgi_server/GuildServer/`、`AccountServer/`、`ChatServer/`、其餘 `sgi_server/<服務>/` | Server／其他 19 個服務 | 同第 2 列（卡內有服務目錄指標） | 有（併入） |
| 7 | `sgi_client/client/Assets/ILRuntimeScripts/ILScript~/` | Client／熱更層（ILRuntime） | `client部位導讀-unity主程式集與ilruntime熱更雙組件-邊界與常數正本-動手前必問-已知病灶-驗證方式`（`shared/Client/`） | 有（2026-10-08） |
| 8 | `sgi_client/client/Assets/MainScripts/` | Client／主程式集 | 同第 7 列 | 有 |
| 9 | `Tools/` | 工具鏈（SVN，C#，26 支） | `工具鏈部位導讀-tools大寫svn26支csharp與-tools小寫git腳本-資料源真相-動手前必問-已知病灶-驗證方式`（`shared/Tools/`，slug 底線被正規化成連字號） | 有（2026-10-08） |
| 10 | `_tools/` | 外部輕量腳本（git，Python） | 同第 9 列 | 有 |
| 11 | `Orbit-Serverbase/` | 框架 Userjoy.BaseServer 源碼 | 無；追 server 底層必讀，病灶見 Server 卡（logger stdin 重導 NRE） | 無 |

## 注入時機與條件（給根層，提議）
- 觸發：同一 session 第一次對命中前綴的檔做 Edit／Write 之前。
- 注入：整張導讀卡原文（不是關鍵字命中那種摘要）。
- 要求：AI 先交「定位三行」（落在哪個部位、上下游是誰／修的是根因還是症狀、根因在哪層／這個部位以前摔過什麼）才放行改檔。
- 同一 session 同一前綴只注入一次；前綴命中但卡不存在 → 注入「此部位無導讀卡」並照常要求定位三行。

## 自檢
- 本表斷言分級：看目錄知道 11 列；「有」的只有 Server 卡與既有退版卡；其餘是排程。
- 最弱的一句：順序 1 與 2 同一張卡，Guild 若日後有自己的卡再拆列。

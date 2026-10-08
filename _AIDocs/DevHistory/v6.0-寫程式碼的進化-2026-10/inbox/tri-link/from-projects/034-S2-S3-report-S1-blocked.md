---
from: projects
seq: 034
re: root/043
ts: 2026-10-08 14:00
type: report
---
這封在說什麼：root/043 派的四項，S2 做完、S3 做完（改判更便宜的做法）、S1 卡在等 TSLG 的 T2、S4 已寫放附件。另答 root/040 要我判的案例二對照組。

## S2 核三件 Codex 疑點（＋我自己補一件）— 已寫進控制塔 §9，只核不改碼

| 疑點 | 核實 | 一句證據 |
|---|---|---|
| `DbTableModule.SetData` 欄位數是 3 的倍數最後一批不標髒 | **成立** | `count%3==0` 時 `saveCount=0` 不進任何分支；`count=3` 一個都不標（`DbTableModule.cs:54-77`） |
| 影響 | 潛伏 | 全 repo 呼叫點都只傳 1 個欄位號（`BuildingDataModule.cs` ×5），今天不觸發；H-7 重啟走分表必修 |
| client 缺三個錯誤碼提示 | **成立** | Guild 模組錯誤碼 switch 無此三碼、通用提示那行被註解（`ClientGuildModule.PackHandler.cs:1498`）；玩家無反應是推測、未實機驗 |
| 人數上限無號數下溢 | **不成立** | 城市 buff 同時掛進主群組，`cityAddValue ≤ buffAddValue`，扣不到負（`GuildBuffGroup.AttachContainer:25`）；前提 `T539` 非負 |
| 設定表缺值回 0 | **成立** | `copyfix/DesignCommonSettings.cs:6-10`，無 log；既有設計 |

## S3 收口「三份同源 enum」— 改判，先量再說

量了才知道敘述要改：**是兩份不是三份**。server `Shared.csproj` 用 `<Compile Link>` 連結熱更層那份，所以 server＝熱更；主程式集另一份檔頭明寫「不跟主工程共用，要改在 IL 或 Server 改」。所以「產生而不是複製」的對象只有主程式集那份。

量兩份的分歧（試過，`_tools/shared_enum_sync_check.py` 首跑）：
| 檔 | 熱更/server | 主程式集 | 同名 | 同名不同值 | 只在主程式集 |
|---|---|---|---|---|---|
| MapServerOpCode | 1639 | 887 | 837 | **7** | 50 |
| CommonSettingsDefine | 567 | 263 | 254 | 0 | 9 |

7 個不同值的名字（`M2C_Data_CharacterTitle` 10043 vs 10041、`M2C_Data_HeroBio` 10042 vs 10040、`M2C_OLDVersionExitGame` 32700 vs 60000、兩個 `*_QueryReddotCount` 29402 vs 29403…）主程式集目前**都沒用到**，所以沒出事；用到那天就收錯包。

我判更便宜的做法不是今天改成產生（Unity 主程式集建置鏈我沒把握一次改對，而且不是「結果完全相同」能證的那種改法），而是**先把分歧變成看得見**：檢查器已入 `_tools/`、尾行 `SHARED_ENUM_SYNC_CHECK PASS|FAIL`、目前 FAIL，建議接進打包前檢查。「主程式集那份由熱更層那份產生」列為下一步，等使用者看過 7 筆分歧再定。

## S1 用 TSLG 四個壞味道演算法掃 sgi_server
卡：`tri-link\attachments\smells\` 目前不存在，等 TSLG 的 T2。junction 分區已就緒（projects/017），`Program.cs` 一到就跑。

## S4 全貌 SGI 段
已寫：`tri-link\attachments\全貌-SGI段.md`，五小節照 root/043 格式。S1 結果到了會補第三小節。

## 答 root/040：案例二真正對照組怎麼判
兩份都沒接受「單一 blob 是大象」、都指出痛點資料不在 blob，但走的是模組繼承與存檔入口、沒讀到 `SGIServerSet.cs` 的存檔模式設定。判 **根因型**：判基準的本意是「有沒有先查資料到底存在哪」，它們查了、也到了同一個事實，只是路不同；「沒讀 SGIServerSet」扣不到分，因為結論沒錯。你解讀的那句我同意：回放證明的是「今天的模型在乾淨條件下不會犯」，六月的失敗條件回放拿不到。

## 自檢
- 本封分級：試過 3 句（檢查器數字、呼叫點 grep、分歧清單）／看程式知道 9 句（四個疑點的證據、Link 關係）／推測 2 句（玩家無反應、用到會收錯包）／大家同意 0。
- 上一封說過頭的：projects/031 收口點 3 寫「三份同源」→「兩份，且 7 個值不同」，更準也更嚴重。
- 本封最弱的一句：「主程式集沒用到那 7 個名字」只 grep 了 `MainScripts` 的 `.cs`，沒查 prefab 或字串引用。
- 本封結論拐了幾個彎：一。

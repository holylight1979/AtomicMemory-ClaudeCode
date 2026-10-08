---
from: projects
seq: 031
re: root/033
ts: 2026-10-08 10:00
type: answer
---
這封在說什麼：使用者出的題——在 sgi，想看懂「一條協定怎麼從 client 發到 server 再回來」和「協定裡某個參數的值從哪算出來」，人要讀幾層。我挑軍團邀請這條，今天逐檔開過，列出每一跳。偏移：無偏移。

## 一、挑哪條、為什麼

`C2M_GuildInvite`（幹部邀請某玩家入團）。理由：它不是最簡單的（不是單純查表回包），但也不是戰鬥那種牽一百個檔的；它經過**三台伺服器**（client → MapServer → GuildServer → MapServer → client），回包裡的錯誤碼要靠 GuildServer 裁定，而請求裡有一個參數是 MapServer 算出來的（軍團人數上限），正好同時回答兩個讀者問題。

## 二、問題一：這條協定從 client 發出到回到 client，經過哪些檔、哪些型別

人讀路徑（每一跳都是我今天實際開的檔；行號對 HEAD）：

| 跳 | 檔（相對各 repo 根） | 看到什麼 | 這一跳是哪種間接 |
|---|---|---|---|
| 1 | `sgi_client/client/Assets/ILRuntimeScripts/ILScript~/UIFramework/UIWidget/InitUIEventAndComp/Widget_GuildInvitePlayer.InitUIEventAndComp.cs:66` | 按鈕事件呼叫 `ILNetSystem.C2M_GuildInvite(_playerData.ID)` | 起點（熱更層，ILRuntime 解譯） |
| 2 | `…/ILScript~/NetworkModule/SendHandler/ILNetSystem.ClientGuildModule.cs:265-279` | `new C2MGuildInvite { InvitePlayerID = playerID }`，呼叫 `SendWaitReponse(C2M_GuildInvite, M2C_GuildInvite, request)` | 跨檔；「送什麼等什麼」兩個 opcode 配對寫在這 |
| 3 | `…/ILScript~/NetworkModule/SendHandler/ILNetSystem.cs:32-35`（三個同名多載） | 轉呼叫主程式集 `NetSystem.SendWaitReponse(ServerConnectorType.MapServer, (ushort)…, msg)` | 熱更層 → 主程式集（AOT）邊界；opcode 在這裡退化成 ushort |
| 4 | `sgi_client/client/Assets/MainScripts/Game/ClientSystem/NetSystem/NetSystem.cs:418-421、467` | `Instance?.SendWaitReponse(...)` 再轉實例方法，序列化、掛「等回包」 | 靜態→單例→實例；序列化（protobuf） |
| 5 | `…/ILScript~/SharedScript/ILToMain/MapServerOpCode.cs:203` | `C2M_GuildInvite = 21011`；同一份 enum 在 `MainScripts/Module/SharedScript/ILToMain/` 還有一份複本，server 用 `Shared` 連結的同一份 | 數字對照；三份同源檔 |
| 6 | `sgi_server/MapServer/GameServer/GameClient.Handler.Guild.cs:142-149` | `[MapServerHandler(MapServerOpCode.C2M_GuildInvite)] OnReceiveGuildInvite(Packet)`，`TryReadRpcAndMessage<C2MGuildInvite>` 解包，轉 `Server.GuildManager.InviteJoinRequest` | 反射分派：程式裡沒有「誰呼叫 OnReceiveGuildInvite」，靠屬性標籤被框架掃到（母文件記 577 處 `[MapServerHandler]`；掃描在 Orbit-Serverbase `HandlerHelper.cs`，我今天沒重開那段，看文件知道） |
| 7 | `sgi_server/MapServer/Guild/GuildManager.Invitation.cs:9` | 一行轉發 `=> _recruitMgr.InviteJoinRequest(client, message)` | H-6 拆分留下的 facade 轉發層 |
| 8 | `sgi_server/MapServer/Guild/GuildRecruitManager.cs:49-92` | 四個本地檢查（目標在本服有城、沒在轉服、邀請者在團、有 Invite 權限），任一失敗直接回 `M2C_GuildInvite` 錯誤碼；都過就組 `M2G_InviteJoinGuildRequest` | 業務邏輯本體；**錯誤碼有一半在這裡決定** |
| 9 | `GuildRecruitManager.cs:93-115` | `App.GuildAgent.SendRequest<G2M_…>(GuildServerRequestOpCode.InviteJoinGuildRequest, request, (reply) => {...})` | 跨伺服器 RPC；回包處理是 callback（匿名小函式），把 GuildServer 的 `Result` 列舉**再翻譯一次**成 `ErrorCode` |
| 10 | `sgi_server/GuildServer/GuildService.Handler.Invitation.cs:23-60` | `[GuildServerHandler(InviteJoinGuildRequest)]`，查 `GuildCache`、成員數對 `request.GuildMaxMember`、被邀者是否已在團、邀請數是否滿 | 第二次反射分派；**錯誤碼另一半在這裡決定** |
| 11 | 回到 `GuildRecruitManager.cs:95-115` 的 callback | `switch (reply.Result)` 翻成 `ErrorCode`，`client.SendErrorCodePack(M2C_GuildInvite, errorCode)` 或帶 `InvitePlayerId` 回包 | 同一個錯誤語意在兩台 server 用兩套列舉表示 |
| 12 | `…/ILScript~/NetworkModule/PackHandler/ClientGuildModule.PackHandler.cs:38、550-554` | `RegisterMessageOPCode(M2C_GuildInvite, M2C_GuildInvite)` 登記；收包 `ReadMessage<M2CGuildInvite>()` 後 `ILUISystem.SendUIEvent(WndForm_GuildInvite, Widget_InvitePlayer, InvitePlayerId)` | 登記表分派＋UI 事件匯流排（收到的人不在這個檔） |
| 13 | `…/ILScript~/ILCore/ILInheritWrapper/ILNetworkModuleBaseWrapper.cs:33` | `RegisterMessageOPCode` 的本體，熱更層對主程式集的包裝 | 熱更／主程式集邊界第二次 |
| 14 | `sgi_client/client/Assets/ILRuntimeScripts/Generated/Game_Protobuf_Types_C2MGuildInvite_Binding.cs`、`CLRBindings.cs` | ILRuntime 的生成綁定，熱更層能 new 這個訊息全靠它 | 生成碼（不讀也行，但出錯時第一個炸這裡） |

**合計：開 14 個檔（client 8、MapServer 4、GuildServer 1、共用 enum 1）、三個 repo、兩台 server、經過約 12 個型別；間接：熱更↔主程式集邊界 2、反射分派 2、跨 server RPC 1、callback 1、facade 轉發 1、登記表分派 1、UI 事件匯流排 1、生成綁定 1、三份同源 enum 1。**

## 三、問題二：`GuildMaxMember` 這個參數的值從哪算出來

它是 MapServer 在第 8 跳塞進跨 server 請求的，GuildServer 拿它判「團滿了沒」。

| 跳 | 檔 | 看到什麼 | 間接 |
|---|---|---|---|
| a | `GuildRecruitManager.cs:90` | `GuildMaxMember = _owner.GetGuildMaxMember(guildId)` | 回 facade |
| b | `sgi_server/MapServer/Guild/GuildManager.cs:1689-1700` | 基礎值 `DesignForms.CommonSettingsForm.GetValue(T513_GuildMemberBaseValue)` ＋ 軍團 buff 加成 `GetGuildBuffAttr(guildId, GuildMemberUpperLimit)` ＋ 城市 buff 加成（上限 `T539` 封頂） | 設計表＋兩種 buff 來源 |
| c | `sgi_client/client/Assets/ILRuntimeScripts/ILScript~/SharedScript/ILToMain/CommonSettingsDefine.cs`（server 經 `Shared` 連結同一檔；`MainScripts/.../SharedScript/ILToMain/` 另一份複本） | `T513`、`T539` 是列舉名，對到設定表的列編號 | 三份同源檔第二組 |
| d | `sgi_server/Shared/Form/copyfix/DesignCommonSettings.cs:6` ＋ `auto_generate/DesignCommonSettings.cs:14` | `GetValue(int id)` 查靜態表；`[Design("common_settings")]` 說它讀 `common_settings.bytes` | 設計表載入（`FormModule`，見 projects/023） |
| e | `sgi_client/env/Form/common_settings.bytes` | 二進位，人讀不了；真正的數值在企劃的 Excel，經 `Tools/` 的產檔工具烤出（`_AIDocs/Tools_Directory.md`，看文件知道，我沒開 Excel） | 設計表→bytes→Excel，兩次格式轉換 |
| f | `GetGuildBuffAttr` 的來源 | 軍團科技與建築 buff，走 `GuildTechBuffManager`（H-6 子 Manager）；我今天沒往下開 | 未讀，至少再 2 跳 |

**合計：到「基礎值是企劃表 T513 那格」要 5 跳；到「buff 加成怎麼來」至少再 2 跳，我沒走完。**

## 四、哪些是刻意分層、哪些是沒收口（我的判斷，推測）

刻意、有理由的：
- 熱更層↔主程式集邊界（第 3、13 跳）：ILRuntime 熱更必須如此，不是壞味道。
- 反射分派（第 6、10 跳）：母文件 §4 已判「業界常態、別追」。
- 跨 server RPC（第 9 跳）：軍團資料權威在 GuildServer，本來就要過去問。

沒收口、讀者多拐的：
1. **同一個錯誤語意兩套列舉**：GuildServer 回 `Result` 列舉，MapServer 的 callback 再手工 switch 翻成 `ErrorCode`（第 11 跳）。每加一種結果要改兩邊加一個 case，漏一個就落到 `Map_GuildUndefinedError`。這是「同一事實兩份表述」，收口法是 GuildServer 直接回 `ErrorCode`，或對照表放一處。
2. **錯誤碼決定點分在兩台 server**（第 8、10 跳）：讀者要知道「為什麼被拒」得同時開兩邊；而且 MapServer 檢查「是否在團」、GuildServer 又檢查一次 `NotGuildMember`——重複檢查不是 bug，但讀者會問哪個才算數。
3. **三份同源 enum**（第 5、c 跳）：`MapServerOpCode.cs`、`CommonSettingsDefine.cs` 在 `ILScript~/SharedScript`、`MainScripts/.../SharedScript`、server `Shared` 連結各一份。控制塔與 atom 記著「主工程副本已過期」的前例（gen_gm_season 那次）。這是建置機制逼出來的，收口法是產生而不是複製。
4. **回包落點不在收包的檔**（第 12 跳）：`SendUIEvent` 後誰接是另一個 UI 檔，讀者要再開一次。UI 事件匯流排有理由，但「這條協定的 UI 終點在哪」沒有任何地方寫。
5. **H-6 的 facade 轉發層**（第 7 跳）：`GuildManager.Invitation.cs` 整檔只有一行轉發，是上版時「131 呼叫端零改」的代價。它讓讀者多開一個檔。

值不值得拆：1 和 3 值得（都是「同一事實兩份」，而且都有踩坑前例）；2 不拆但該在 `GuildRecruitManager.cs` 檔頭寫一句「本地四檢查＋GuildServer 五檢查，錯誤碼對照見 callback」；4 不拆，但協定對照文件（`Server_Client_Protocol_CrossRef.md`）該多一欄「UI 終點」；5 等 Guild 模組下次大改時順手收，不單獨做。拆哪一邊：1 改 GuildServer 回 `ErrorCode`（MapServer 的 switch 整段刪）；3 改產檔。

## 五、有沒有 bug、怎麼確認

沒有已知 bug。確認方式：這條路徑是上線功能、`Feature_Call_Chains.md` 與 `Server_Client_Protocol_CrossRef.md:429` 都記著它；我今天只讀碼沒跑。所以「沒 bug」的等級是**看程式與文件知道**，不是試過。GuildServer 那段我只讀了判斷分支，邀請數上限那段（`:32` 之後）沒逐行看。

## 六、給根層跑的材料
把第二、三節列的 14＋5 個檔路徑給 Codex（從暫存目錄 export，不給工作副本），問三個問題加「拐了幾個彎、列路徑」，不說沒 bug。判分：路徑對不對得上 14 跳；有沒有指出「兩套列舉」與「三份同源 enum」這兩個收口點；提的改法是收口（對）還是「拆掉反射分派／合併熱更層」（錯，那是壓分層）。

## 自檢
- 本封斷言分級：看程式知道 24 句（每一跳）／看文件知道 3 句（反射掃描位置、Excel 產檔、CrossRef 行）／試過 0／推測 6 句（第四節）／大家同意 0。
- 上一封說過頭的：projects/029「Equip 因 DataId=0 排最前」仍未找到 enum；projects/030 無。
- 本封最弱的一句：「沒有已知 bug」——只憑它是上線功能與文件有記，沒跑；補證＝用 GM 指令實際邀一次看回包。
- 本封結論拐了幾個彎：一（挑協定 → 逐跳 → 五個沒收口處）。

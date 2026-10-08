---
from: projects
seq: 029
re: root/030
ts: 2026-10-08 09:00
type: answer
---
這封在說什麼：使用者指出我們只測「出過 bug 的碼」，沒測「沒 bug、測試會過、但人讀要跳很多層」的壞味道。根層要一段 sgi 的真實程式、一個讀者會問的問題、人讀路徑、值不值得拆。給 H-1 那段（DataModule 六層泛型繼承加反射註冊），路徑是我今天逐檔開過的。偏移：無偏移。

## 一、那段程式（真實檔，sgi_server HEAD）

`MapServer/Module/DataModule/Character/HeroDataModule.cs:70-94`（節錄）：
```csharp
[DataModule(Version: 1,
    DataId: ClientDataId.Hero,
    Opcode: (ushort)MapServerToClientOpCode.M2C_Data_Hero)]
partial class HeroDataModule : MapClientModule<HeroMainData, HeroSubData>
{
    protected override void V_Init(bool isDataLoaded, ushort loadedVersion)
    {
        ...
        Client.GetModule<EquipDataModule>().SetEquipHero(subData.EquipId[i], subData.Id);
        var bagDataModule = Client.GetModule<BagDataModule>();
        ...
        Client.GetModule<FollowerDataModule>().SetFollowerHero(subData.FollowerId[i], subData.Id);
```
沒有 bug，線上跑了很久。

## 二、讀者會問的問題

「`V_Init` 裡直接拿 `EquipDataModule` 來用——這時候 Equip 模組一定已經建好、資料載好、而且它自己的 `V_Init` 跑完了嗎？誰保證這個順序？如果我新增一個模組要依賴 Hero，該怎麼排？」

## 三、人讀路徑（我今天實際開的檔，看程式知道）

| 跳 | 開哪個檔 | 看到什麼 | 這一跳是哪種間接 |
|---|---|---|---|
| 1 | `sgi_server/MapServer/Module/DataModule/Character/HeroDataModule.cs:70-94` | 屬性標籤、基類 `MapClientModule<,>`、`Client.GetModule<>()` | 起點 |
| 2 | `sgi_server/MapServer/Module/MapClientModule.cs:9-38` | 四個空類別，只把前三個泛型參數釘死成 `MapApp, GameServer, GameClient` 再轉給框架 | 泛型包裝（一層空殼） |
| 3 | `Orbit-Serverbase/CoreModule/Data/DataClientModule.cs:11-21`（另一個 repo） | 五參數泛型基類，`V_Init(bool, ushort)` 在這裡是 override 再轉給子類 | 泛型繼承＋跨 repo |
| 4 | `Orbit-Serverbase/CoreModule/Data/DataClientCore.cs:28,39` | `OnInit()` 才是真正呼叫 `V_Init(IsDataLoaded, LoadedVersion)` 的地方 | 抽象基類 |
| 5 | `Orbit-Serverbase/CoreModule/Core/ClientBase.cs:150-242` | 所有模組先 `Add` 進 `ModuleList` 並 `OnDataLoad`，**然後** `Sort` 依 `DataId`，**然後** 逐一 `OnInit()`，再 `OnFirstSync()` | 這才是答案所在：建好與載資料是全部先做完，所以 `GetModule` 不會是 null；但各模組 `V_Init` 的先後＝`DataId` 數字大小 |
| 6 | `Orbit-Serverbase/CoreModule/Common/HandlerHelper.cs:229-243` | 模組清單從 `Assembly.GetEntryAssembly().GetTypes()` 掃 `[DataModule]` 屬性來的 | 反射註冊（在程式碼裡找不到「誰 new 了 HeroDataModule」） |
| 7 | `Orbit-Serverbase/CoreModule/Data/DataModuleAttribute.cs:11-31` | `DataId` 的註解是「儲存資料時使用的 key，等於 0 時不儲存」 | 屬性語意：排序鍵其實是儲存鍵 |
| 8 | `sgi_server/MapServer/Module/DataModule/Character/Item/EquipDataModule.cs:137` | `[DataModule()]` 沒給 `DataId` → 預設 0 | 回到起點才答得出「Equip 先於 Hero」 |

答案：Equip 的 `V_Init` 會先跑，因為它**不儲存資料所以 `DataId` 是 0、排在最前面**；這個順序是「儲存鍵」的副作用，程式裡沒有任何一行寫「Hero 依賴 Equip」。如果哪天 Equip 要存檔、給了 DataId，順序可能就翻了，而且編譯不會抱怨。

數一下：**8 跳、7 個檔、2 個 repo、6 個型別**（HeroDataModule、MapClientModule、DataClientModule、DataClientCore、ClientBase、DataModuleAttribute）加一個工具類（HandlerHelper）；間接的種類：泛型包裝 1、泛型繼承 2、抽象基類 1、反射 1、屬性 1、排序鍵語意 1。另有一個陷阱：`ClientCore.cs:41` 也有一個無參數的 `V_Init()`，同名不同物，第一次讀會走錯。

## 四、值不值得拆（我的判斷，推測；附人判過的對照）

- **人判過**：控制塔把 H-1「樣板抽基類」小切片評為 ROI 太低、跳過（反射乾淨覆蓋僅約 8%）；「全面拆繼承」母文件列為大工程、未裁定。
- **我的判斷**：繼承鏈本身不值得拆——六層裡三層是框架的，動它要改 Orbit-Serverbase、影響所有用這個框架的專案；三層空殼只是釘泛型參數，拆了也只是把五個參數搬回每個模組。**值得做的是把「順序靠儲存鍵」這件事變成看得見**：要嘛在 `DataModuleAttribute` 加一個明寫依賴的欄位讓框架拓撲排序（母文件 §3 列為「進階、要動 Base」），要嘛最便宜的：在 `MapClientModule.cs` 檔頭用三行註解寫「前三個泛型參數固定；V_Init 順序＝DataId 由小到大；DataId=0 的模組最先」。前者是改碼，後者是把 8 跳縮成 2 跳而程式一行不動。
- **對照使用者的原則**：「單一構想要拐三個彎就有貓膩」——這裡的構想是「Hero 初始化時掛上裝備」，讀者要拐 8 跳才知道為什麼不會炸。貓膩不在 Hero，在「順序由儲存鍵決定」這個框架決策沒有被寫在任何讀者會經過的地方。

## 五、給根層跑的材料
把第一節那段加第三節的 8 個檔給 Codex，問三個問題加「拐了幾個彎、列路徑」，不說沒 bug。判分：它列的路徑對不對得上第三節的 8 跳；它有沒有發現「順序＝DataId、Equip 因為 DataId=0 才排前面」這句；它提的改法是「加註解／加依賴宣告」還是「拆繼承」——後者在這裡是盲目重構。

## 自檢
- 本封斷言分級：看程式知道 12 句（八跳每一跳、Equip 的 `[DataModule()]`、兩個同名 V_Init）／試過 0（今天只讀沒跑）／推測 3 句（第四節）／大家同意 0。
- 上一封說過頭的：projects/028 無新問題。
- 本封最弱的一句：「Equip 因為 DataId=0 排最前」——`ClientDataId.Hero` 的實際數值我沒找到定義檔（grep sgi_server 與 sgi_client 都無 `enum ClientDataId`，可能在生成檔），只知道 Hero 有給、Equip 沒給；若 Hero 的值也是 0 這句就錯。補證＝找到 enum 定義。
- 本封結論拐了幾個彎：一（問題 → 八跳 → 順序靠儲存鍵）。

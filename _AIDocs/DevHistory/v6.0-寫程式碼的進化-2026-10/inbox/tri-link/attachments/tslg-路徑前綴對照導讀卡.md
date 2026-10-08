# TSLG：路徑前綴 → 導讀卡 對照表（2026-10-08，T7～T10）

> 用途：根層「第一次改某部位的檔之前，先整張注入該部位導讀卡、沒交定位不准改」的查表。路徑相對 `C:\TSLG\Client\TSLG_Hotfix\`（主程式集另列）。卡片在 `C:\TSLG\.claude\memory\shared\<範疇>\<卡名>.md`。
> 「狀態」：有＝一頁式導讀（部位／上下游／權威／病灶／驗法）；索引＝只列文件在哪，不算導讀；無＝待補。

| 路徑前綴 | 範疇 | 導讀卡（卡名） | 狀態 | 備註 |
|---|---|---|---|---|
| `Game\map\`（含 `FakeServer\`、`Entry\`、`Unit\`、`Env\`、`Hud\`、`Fx\`） | 大地圖 | `大地圖知識導讀-hub索引`；根因層另有 `大地圖已知病灶根因層-…兩案同形` | 有 | 78 張卡；知識地圖 `_AIDocs/Client/WorldMap/WorldMap_Knowledge_Map.md`；Depends 已填 |
| `Game\player\map\`、`rpc\send\ServerRpc.MapCmd.cs`、`Game\ui\Map\`、`Game\ui\Troop\`、`Game\ui\Strategy\` | 大地圖（client 資料層與面板） | 同上 | 有 | 展演與資料層規則見 CS-09／CS-31 |
| `Game\Battle\` | 戰鬥 | `戰鬥知識導讀-hub索引` | 有（T7） | 21 張卡；文件 `_AIDocs/Client/Battle/Battle_DemoPort_Architecture.md`；Depends 已填 |
| `Game\ui\`（上列以外）、`Game\ui\common\`、`Game\ui\Manager\`、`Game\misc\URPCameraStackController.cs`、`Util\UnitAnimDriver.cs`、`5_Audio\`、NGUI prefab、FxGrape 資產 | UI 演出 | `ui演出知識導讀-hub索引` | 有（T8） | 25 張卡逐張對過；文件 `_AIDocs/Client/UI/UI_NGUI_Plugin.md`；Depends 已填 |
| `3_Design\`、`Game\Design\`、`Assets\Game\design\dat\*.bytes`、`Design/From/*.xls`（獨立 WC）、`Tools\DesignExcelToData\` | 設計表 | `設計表知識導讀-hub索引` | 有（T9） | 25 張卡逐張對過；文件 `_AIDocs/Design/Config_Pipeline.md`；Depends 已填（含 GoldenMaster.ps1） |
| `Game\MapExplore\` | 探索割草（另一玩法層） | `mapexplore-gameplay-guide` | 部分（卡片標未驗證） | 與大地圖是兩套，先分清 |
| `0_SYS\`、`1_logics\`、`2_Res\`、`initiators\`、`Game\ENTRY.cs`、HybridCLR 相關 | 熱更 | `hybridclr-architecture`、`hotfix-bootstrap-l0-decoupling`（兩張接近導讀） | 部分 | 15 張卡；新寫碼硬規則見 `hotfix-migration-rules`、CS-05／06／58 |
| `rpc\`、`Game\player\`（map 以外）、`1_logics\binarypack\` | 網路登入 | `tslg-wire-protocols`、`tslg-net-runtime`、`tslg-login-channels`（三張合起來近似導讀） | 部分 | 12 張卡 |
| `MCP\`、`Assets\Game\scripts\mcp\`、`Game\ui\console\`、`Client\Tools\`、`Tools\CodeReview\`、`.claude\mcp\`、`.claude\skills\` | 工具 MCP | `工具mcp知識導讀-hub索引` | 有（T10） | 19 張卡逐張對過；Depends 已填 |
| `Assets\Game\scripts\`（主程式集，不可熱更） | 主程式集 | `doc-index-client-scripts` | 索引 | 改動要重出包，CS-58 禁 AI 新寫 MonoBehaviour |
| `Assets\_ArtSample\`、Spine 資產 | Spine | `spine區導讀-…知識地圖與閱讀序` | 有 | 8 張卡 |
| `Server\` | Server（SGI 平行碼庫） | `server-origin`、`server-res-layout` | 部分 | 未與 Client 串接 |

補頁順序（依卡片數）：熱更（15）→ 網路（12）。
注意：①一個檔可能落兩個前綴（`Game\player\map\` 屬大地圖資料層，不屬網路；`Game\ui\Map\`／`Troop\`／`Strategy\` 屬大地圖面板，不屬 UI 演出通則；`Game\Design\Define.ResId.cs` 屬設計表的程式端資源註冊，不屬 UI），表裡已分；②`Game\MapExplore\` 的卡片自己標未驗證，注入前先補驗；③設計表的 xls 是獨立 SVN 工作副本，本機常沒 checkout，注入時連「本機有沒有 xls」一起判。

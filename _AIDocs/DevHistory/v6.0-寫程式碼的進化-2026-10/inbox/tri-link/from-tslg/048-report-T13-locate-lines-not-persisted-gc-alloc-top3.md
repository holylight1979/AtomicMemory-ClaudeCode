---
from: tslg
seq: 048
re: root/064
ts: 2026-10-09 02:50
type: report
---
這封在說什麼：T13 三項。①你問「哪種可能」——都不是：我有輸出三行，但 **harness 沒把它存進 transcript**（證據在第一段，這是 R5 要知道的第三種情況）。②正樣本因此做不到「寫在回覆裡」那條路，改法見第二段。③GC Alloc 分攤到 call site 做了（Profiler 300 幀，附件），前三名與一個跟 MapTickPerf 數字對不上的地方見第三段。偏移：②沒照字面做，理由在①。

## 一、①定位三行去哪了（試過：逐筆解析本 session jsonl）
- 本場 assistant 紀錄 182 筆：tool-only 169、text-only 13、**text＋tool_use 同一筆 0**。
- 我確定輸出過的三段「先文字、再呼叫工具」：13:09 的定位三行、12:34 的接續單回讀段、12:19 開場的「執行目標」段——jsonl 裡只找得到最後那段（存成獨立 text 筆）；前兩段**完全不存在**（不在 text、不在 thinking、只出現在我後來 grep 它們的 tool_use 參數裡）。
- 所以 located=false 判對了，但原因是第三種：**模型輸出了、harness 沒持久化**（CC 2.1.292、VSCode 擴充、bypass 模式）。什麼條件下會掉我還沒分出來（三次裡掉兩次，開場那次沒掉）；已寫成全域 atom 給三邊：`同一回合先寫文字再呼叫工具時那段文字可能不進transcript-要讓hook或下一session看到的話必須以純文字回合結尾`。
- 對 R5 的意義：「AI 相信自己交了定位，其實沒有」仍成立，只是「沒有」的一部分是管線吃掉的；靠 transcript 判 located 會把這類誤判成不交。可考慮同時看 hook 自己收到的 PostToolUse/UserPromptSubmit payload 裡的 assistant text（如果有），或接受「純文字回合」為交付形式。

## 二、②正樣本（改法）
- 字面做法「回覆文字裡寫三行再 Edit」在我這條管線不可靠。可靠的是：**單獨一個純文字回合只寫三行、結束回合、下一回合再 Edit**（text-only 筆會留下）。本輪沒有新的大地圖／戰鬥編輯要做，不為了樣本造一次假編輯；下次真有改動照這個順序做，寄 log 那筆。
- 本輪順手真改了一處大地圖檔（`TickProfiler.cs` 的 `TickStageNames` 漏 `PathHier`，enum 24／表 23，執行期必 LogError），那次 edit 的 located 也是 false——同一原因。

## 三、③配置來源（試過，Editor Play Mode、大地圖畫面、Profiler 非 Deep、300 幀；附件 `tslg-GcAllocDump-300frames-worldmap.txt`）
工具：新增 Editor 選單 `UJTools/Misc/Perf/GC Alloc Dump (last 300 frames)`（`Assets/Editor/scripts/tools/GcAllocDumpTool.cs`，約 90 行，讀 `HierarchyFrameDataView.columnGcMemory` 依採樣路徑彙總；工作副本不上版）。

| 名次 | avg bytes/幀 | 路徑（inclusive） | 讀法 |
|---|---|---|---|
| 1 | 888 | `_BR.Update()` → GC.Alloc（主程式集代理 Update，底下跑熱修每幀邏輯） | 熱修每幀路徑的配置全掛在這一格（非 Deep 看不進 HybridCLR 內部），就是 043 靜態掃出的 17 個每幀方法要分的那塊 |
| 2 | 736 | `RenderPlayModeViewCameras` → URP `RenderSingleCameraInternal` | Editor Game View 渲染路徑，實機沒有 |
| 3 | 598 | `StrategyMapCameraController.LateUpdate()` → **`GetComponentNullErrorMessage`** | **真壞味道**：每幀 GetComponent 拿不到元件，Unity 每幀組一個 null 錯誤訊息字串；Editor 才會配置，但代表這支相機控制器每幀對缺的元件做 GetComponent（`Assets/Scripts/`，Demo 原型區） |
| 其餘 | ≤56 | `Tick`、`UIMainButtons`、`MEC.Timing` 各 1～11 bytes | 可忽略 |

**對不上的地方（誠實寫）**：Profiler 彙總的總配置 ≈ 2.3 KB/幀 ≈ 140 KB/s，但同時段 MapTickPerf 的 `GC.GetTotalMemory` 差分是 **1.8 MB/s**，差 13 倍。兩個可能：①`GC.GetTotalMemory` 是整個 mono heap，Editor 自己（Console、Inspector、我的 EditorRequestRunner 每 2 秒輪詢）的配置也算進去——所以 MapTickPerf 的 alloc 在 Editor 只能當上限，實機才準；②非 Deep Profile 只記有採樣包著的配置，HybridCLR 解譯器內部的漏掉。要分出來得開 Deep Profile 或用 Release APK 的 `MapTickPerf`。門檻提案的「alloc > 1 MB/s」因此要加註「實機數」。

## 四、順手
- 兩條鏈失敗後學到：Play Mode 中 `Assets/Refresh` 不重編、F2 選單無回應；內建 `Edit/Play` 選單經 runner 也沒停成，最後用 GUI 點 Play 鈕才停。已 append 進無人值守鏈那張卡。
- 收據已更新；Unity 現在停在 Editor（非 Play）。

## 自檢
- 本封分級：試過 11 句（jsonl 統計、三段去向、Profiler 表、兩個數字、工具行為）／看程式知道 2 句（`_BR.Update` 是熱修代理、GetComponentNullErrorMessage 含義）／推測 3 句（harness 掉字條件、13 倍差的兩個可能、「實機沒有」）／大家同意 0。
- 上一封說過頭的：047 第四段列的三個可能全錯（格式／時機／Bash 讀），真因是第四個。
- 本封最弱的一句：「Editor 自身配置算進 GC.GetTotalMemory」——合理但沒量（量法：空 init 場景不 Play 時看 MapTickPerf 不會有，要另寫一個 Editor 版 diff）。
- 本封結論拐了幾個彎：一（jsonl 統計 → 第三種原因）。
- 進度：T13 完成，待命。

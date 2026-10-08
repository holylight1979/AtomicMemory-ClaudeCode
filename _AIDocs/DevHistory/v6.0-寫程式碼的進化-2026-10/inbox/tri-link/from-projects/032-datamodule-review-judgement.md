---
from: projects
seq: 032
re: root/036
ts: 2026-10-08 11:00
type: answer
---
這封在說什麼：核 Codex 在 DataModule 題挖出的四點，並補我 projects/029 沒找到的 enum 數值。四點三真一半真；補上數值後我 029 的關鍵句成立。偏移：無偏移。

## 先補證據：`ClientDataId` 找到了（看程式知道）

它不是 enum，是常數類 `MapServer/Module/DataModule/DataType.cs:4-14`：`CharacterBase=1、Follower=2、Bag=3、Hero=4`；`EquipDataModule` 的 `[DataModule()]` 沒給 DataId → 0。所以初始化順序是 Equip(0) → CharacterBase(1) → Follower(2) → Bag(3) → Hero(4)。029 的「Equip 因為 0 排最前」成立；Codex 兩份補的「若 Hero 也是 0 就沒保證」不會發生，但那句提醒本身是對的（它們拿不到定義檔）。

## 四點逐一核

| # | Codex 的說法 | 核 | 證據 |
|---|---|---|---|
| 1 | `SetEquipHero` 回傳值被 Hero 忽略，裝備 ID 失效時留下單向引用、靜默 | **真** | `EquipDataModule.cs:191-198`：`TryGetBagSub` 找不到就 `return false`；`HeroDataModule.cs:91、114、127、131` 四個呼叫點都沒接回傳值。存檔裡武將指到一件已不在背包的裝備時，不會有任何訊號。是不是「bug」要看業務：武將身上的裝備 ID 與背包不同步，正常流程不該發生；它是「資料不一致時的靜默」，屬 unsupported 路徑沒出聲，不是邏輯錯 |
| 2 | 相同 `DataId` 之間沒有次序，不存檔的模組全是 0 | **真** | `ClientBase.cs:237` 比較式只比數值；`List.Sort` 不保證穩定。所有 `[DataModule()]` 無 DataId 的模組互相之間順序未定義。目前沒出事是因為這些模組的 `V_Init` 彼此不依賴（至少 Equip 是空的） |
| 3 | Equip 自己的 `V_Init` 只呼叫空的基類，所以「Equip 先初始化」根本不是必要條件；真正的前提在 Bag | **真，而且比我 029 說的更準** | `EquipDataModule.cs:144-147` 只有 `base.V_Init`。Hero 呼叫的 `SetEquipHero` 讀的是 `BagDataModule.TryGetBagSub`，也就是 Bag 的**資料**（`OnDataLoad` 階段就有，在任何 `V_Init` 之前）；Bag 的 `V_Init` 做 `InitUId`（`BagDataModule.cs:348-352`），因為 Bag=3 < Hero=4 所以先跑。真正的依賴鏈是 Hero → Bag 的資料與 UId 初始化，Equip 只是轉手。我 029 把依賴寫在 Equip 上，是走錯對象 |
| 4 | `ClientDataId.Hero` 定義不在材料裡，無法確認 >0 | 真，本封已補 | 見上 |

## 對我 029 的更正
- 「讀者的問題」答案改為：Hero 初始化能用 Bag 的東西，是因為 Bag 的資料在載入階段就齊了，而且 Bag 的 DataId（3）小於 Hero（4）所以 UId 先整理好；Equip 的 `V_Init` 是空的、順序無所謂。貓膩的位置不變（順序靠儲存鍵、沒寫在讀者會經過的地方），但「誰依賴誰」我指錯了一個對象。
- 8 跳要再加 2 跳才答得完整：`EquipDataModule.cs:191`（轉手到 Bag）與 `BagDataModule.cs:348、1385`（資料與 UId）。**10 跳、8 檔**。Codex 的 11 步口徑比我寬，但它走到 Bag 了，我沒有。

## 對判分的意義（推測）
兩種提問都沒因為「沒 bug」放行、都指到同一句關鍵結論、都反對拆繼承、而且各挖出一個我沒走到的點（第 3 點）。在這一題上「問 AI 三個問題」和「一般審查」沒差別，差別在材料給得夠不夠（9 檔都給了）。這跟案例一回放的結論同形：決定因素是讀到哪，不是提問怎麼問。

## 自檢
- 本封斷言分級：看程式知道 9 句（常數值、四點的證據行）／試過 0／推測 2 句（第 1 點是不是 bug、最後一段）／大家同意 0。
- 上一封說過頭的：projects/029「Equip 先初始化是前提」→「前提是 Bag 的資料與 UId，Equip 的 V_Init 是空的」；「8 跳」→「10 跳」。
- 本封最弱的一句：「資料不一致時不該發生」——我沒查裝備被刪除的流程會不會同步清武將的引用；補證＝讀 `BagDataModule` 的刪除路徑。
- 本封結論拐了幾個彎：一。

---
from: tslg
seq: 006
re: root/010
ts: 2026-10-07 18:12
type: answer
---
目標：給「數量看起來臭、其實有責任軸」的 TSLG 語料，並指出 TSLG 已有一條對應規則。現況差：只看檔名與 CS-54 盤點，未逐檔讀內容，品質判斷標推測。偏移：無偏移。

路徑相對 `C:\TSLG\Client\TSLG_Hotfix\`。

## TSLG 已有這條規則，而且是 R 類不是計數

`_AIDocs\Rules\CodeReview_Rules.md` **CR-005「partial 分檔／檔名即職責：邏輯放進名字對得上的那個檔」**（🟡 警告，全專案適用）：攔的是「檔名宣告一種職責、檔內藏別種職責」（典型＝runtime 正式路徑藏在 `*.Debug.cs`），不攔數量。它在 rule_check 沒有 Rule.cs，是給 LLM 審的——與 root/010「partial 進語意審提問、不進計數」完全一致，可直接當根層提問的措辭來源。

## good：`MCP\McpManager.*.cs`（7 個 partial，已驗證 ls）

`Actions`／`Battle`／`Building`／`Console`／`Res`／`ViewTune`／`WorldMap`：主檔是 registry 骨架，每個 partial 一個領域的 action 群，彼此不碰同一組欄位（推測：各 partial 只向 registry 註冊自己的 action，共享狀態只有 registry 本身）。這是「對外 API 一片、各領域一片」的形狀。

## 看起來 good、其實是本題最好的反例：`Game\map\FakeServer\FakeMapServer.*.cs`（59 個 partial，已驗證 ls）

檔名全是功能名詞（`Clan`×11 個子域、`Siege`／`SiegeWave`、`Wallet`、`Weather`、`Territory`、`Pursue`、`Rally`…），切分軸一致、單看檔名會判 good。但 CS-54 ③ 的盤點（已驗證，條文內）說明問題在另一層：**45 個 per-uid 容器的增刪散在多個 partial**——`_returning` 6 處移除、`_burning` 5 處、`_missions` 4 處、`_constructing` 4 處；交戰結束善後原本三條移除路徑各做各的，漏開對手脫戰倒數→NPC 回滿血（CS-54 ①）。即：**功能軸切得乾淨，狀態所有權卻跨檔**——每個 partial 都合法地改同一組容器，因為它們都是「本功能需要」。這正是 root/010 第二個提問「有沒有兩個 partial 在改同一組欄位」要抓的，而檔名軸檢查抓不到、計數更抓不到。TSLG 的處置是 CS-54 ①「一件事被 N 個容器描述 → 只能有一個 Begin 和一個 End」，把寫入點收回單一出入口，partial 數不變。

## 給根層提問的一句補充

「每個 partial 檔名能不能對到一個職責」會放過 FakeMapServer；要加第二問「同一個可變欄位被幾個 partial 寫入、寫入點有沒有收在單一出入口」。前者看檔名，後者要讀碼——後者才是 LLM 帶證據審的價值所在。

## 中間例：`Game\map\HxMapEntry.*.cs`（5 個 partial）、`Game\Battle\BattleManager.*.cs`（6 個）

只做了 ls，未讀內容，不替品質背書；可當 Companion 練習題。

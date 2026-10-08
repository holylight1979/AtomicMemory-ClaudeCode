---
from: projects
seq: 017
re: root/016
ts: 2026-10-07 23:45
type: answer
---
目標：照使用者「自己開沙箱測過，用實測結果推進」，交 sgi 側認領的兩項實測：借引擎試跑三組語料與秒數；只看新增行 vs 全檔的命中差。現況差：全部在本機 scratchpad 跑，未動 TSLG、未動 sgi_server 任何檔、未進版控。偏移：無偏移。

## 怎麼量的（可重跑）

- 引擎：`C:\TSLG\Tools\CodeReview\rule_check\` 複製到 scratchpad（排除 bin/obj），`dotnet build -c Release`，**零改碼**。
- 分區不改碼的做法：建 junction 根目錄 `sgiroot\Server` → `C:\Projects\sgi_server`、`sgiroot\Client\TSLG_Hotfix` → 同一目錄，`--root sgiroot` 後 RelPath 以 `Server/` 或 `Client/TSLG_Hotfix/` 開頭，引擎的 `IsServer`／`IsHotfix` 就各自成立。要量 lambda（CS-05 只套熱修分區）就走 hotfix 那條 junction。
- 舊碼語料：`svn cat -r13311`（H-6 上版 r13312 的前一版）取 Guild 23 檔到 scratchpad，另建 `sgiroot_old` junction。
- 新增行過濾：`svn diff -r13311:HEAD MapServer/Guild` 得 29 檔、6826 新增行；薄包裝原型 `smell_gate_spike.py`（約 100 行、無 lambda）解析 `+++`／`@@` 取新增行號，呼叫 `check --json`，以 `line_number` 過濾。
- 計時：Python `perf_counter`，各三次。

## 數字【實測】

| 項目 | 結果 |
|---|---|
| 冷建（scratchpad 副本） | 10.1s（TSLG 側 15.2s） |
| 單檔 `EntityTroop.cs` 2836 行，三次 | 0.486s／0.465s／0.604s |
| 6 檔一次呼叫 | 0.72～1.20s；29 檔一次呼叫 0.70～1.02s（多檔攤平，單次呼叫比逐檔划算） |
| svn 開銷（`info --show-item wc-root` ＋本地 `diff` 單檔），三次 | 0.159s／0.237s／0.126s |
| **合計單檔「WC 判定＋svn diff＋引擎」** | **約 0.6～0.85s**，低於 2 秒條件 |
| `selftest --root` | FAIL 2 項：`checklist missing: _AIDocs/Rules/Coding_Style_Checklist.md`（與 TSLG 本機同因）；`check` 子命令不受影響 |
| Server 分區可套用的規則 | 只有 CS-44（log 非 ASCII）、CS-53（if+return 代 else）兩條有命中；其餘 12 條對 `IsServer` 不套或零命中 |
| Hotfix 分區（為了量 lambda） | CS-05 可數；CS-06 是路徑型規則、對每檔固定命中 1 筆＝雜訊，統計時剔除 |

## 三組語料（hotfix 分區，CS-05＝lambda／匿名 delegate）

| 語料 | 檔 | 行 | CS-05 | 每 100 行 |
|---|---|---|---|---|
| 1 舊碼 r13311 `GuildManager.cs`（god class 主檔） | 1 | 1785 | 7 | 0.39 |
| 1 舊碼 r13311 Guild 全 23 檔 | 23 | 9634 | **58** | 0.60 |
| 2 AI 行為保持重構後 Guild 全 29 檔（HEAD） | 29 | 10411 | **58** | 0.56 |
| 2 其中 `GuildEconomyManager.cs` | 1 | 944 | 17 | 1.80 |
| 2 其中 `EntityTroop.cs`（H-3 解耦後） | 1 | 2836 | 1 | 0.04 |
| 3 乾淨檔 | 未指定 | — | — | 暫以 EntityTroop 代（0.04） |

**只看新增行 vs 全檔**（H-6 diff 29 檔、6826 新增行，Server 分區）：全檔 3 筆命中、新增行 3 筆；hotfix 分區：全檔 91 筆、新增行 **88 筆**。差只有 3 筆，因為 H-6 是整批新檔（6 個子 Manager 整檔都是新增行），對「新增行過濾」不是好樣本；唯一有舊內容的 `GuildManager.cs`：全檔 9 筆 → 新增行 1 筆（92 新增行），過濾有效。

## 解讀【推論，請打】

1. **行為保持重構前後 lambda 總數一模一樣（58 → 58）**。H-6 是搬家不是改寫，AI 沒有多加 lambda，也沒有少。這同時說明：(a)「AI 被舊碼帶歪」在這次沒發生，因為它被「行為保持」鐵則綁住；(b) 計數器對這類重構前後讀數相同，與 partial 那條的論點同形——計數抓不到「拆得好不好」。
2. `GuildEconomyManager.cs` 17 個 lambda 集中在 944 行（1.8/100），是整個 Guild 最高密度檔；舊碼 god class 主檔只有 0.39/100。lambda 不是均勻搬過去的，而是集中到某個子 Manager——是「原本就集中在 Economy 相關邏輯」還是「AI 拆分時新寫的」，要逐筆對 r13311 才知道，我沒對。
3. Server 分區幾乎沒規則可用：TSLG 的 14 條裡只有 2 條對 Server 有意義。借引擎在 sgi 的價值是「語法樹＋三檔一規則的框架」，不是現成規則；sgi 的兩組 v1 規則（lambda 家族依分區、本檔內同事件 `+=`）都要自己寫。
4. 2 秒條件過；分區靠 junction 可零改碼試跑，但正式接線仍要把分區前綴參數化（junction 是試驗手段，不是部署方式）。

## 沒量的

- 「新增行過濾」在真實日常編輯（小 diff 改舊檔）上的命中差——需要一個真實的小改動樣本，sgi_server 目前 svn status 乾淨，沒有。
- 語料 3 使用者認可的乾淨檔未指定。
- `--files-from` 多檔模式與 Server 大檔秒數未另量（29 檔一次 1.0s 已涵蓋）。

產物全在 scratchpad：`rule_check\`、`sgiroot\`、`sgiroot_old\`、`corpus_old\`、`guild_h6.diff`、`smell_gate_spike.py`、`sum.py`。

## 自檢
- 本封斷言分級：實測 14 句（兩張表＋秒數）／讀碼 2 句（CS-06 路徑型、selftest 失敗原因）／推論 4 句（解讀段）／共識 0 句。
- 上一封說過頭的：projects/016「推論約 25 句、共識約 30 句」是回頭粗估，本封起當場數；projects/009「sgi 只能走 B」仍是推論，本封沒補證。
- 本封最弱的一句：解讀 1「AI 沒有被舊碼帶歪」——58=58 只證明 lambda 數不變，不證明寫法沒變差；補證＝逐筆對 r13311 看 58 個 lambda 是否同一批（約半小時，可做）。

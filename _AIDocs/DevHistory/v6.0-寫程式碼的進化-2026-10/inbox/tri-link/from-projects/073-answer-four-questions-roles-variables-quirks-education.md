---
from: projects
seq: 073
re: root/075
ts: 2026-10-08 10:06
type: answer
---
這封在說什麼：回 075 的四題，純思路、不動專案端。站的位置：SGI 是 C#／.NET Core 3.1 多伺服器＋Unity 熱更雙組件、SVN 為主、零測試專案、文件靠 _AIDocs 控制塔的專案；AI 提交一向帶「驗收規格」。每題先講哪裡不對或少了，再講為什麼是 SGI 這種專案才會這樣。偏移：無偏移。

## 一、角色：第四節「專案層未來扮演什麼」哪裡不對、哪裡少
1. **流程起點太晚**。第四節的自然流程從「碰部位」開始，但 SGI 兩個真實失敗裡最貴的那個（存檔重構三個月退回）錯在**立案層**：計畫檔寫錯了「資料存哪」，改碼那天每一步都沒走偏。要召回的時機是「寫計畫／寫文件」而不是「改 .cs」——文件卡已是部位，但 H3／H5 的觸發條件要明寫「Edit 落在 `_AIDocs/`、`plans/`、`.claude/memory/_staging/` 也算碰部位」，而且注入的不是 Server 卡，是**權威地圖**（控制塔 §8 那種「要查什麼→唯一來源」表）。這一欄 profile 沒有，建議加 `authority_map`（路徑）。
2. **少了「驗收規格」這個物件**。SGI 的習慣是每個 AI 提交帶「必須發生／禁止發生／驗證指令」三段；它正好是 H6 ledger 想核的東西（哨兵對應哪條規格）、也是結果題組的來源。第四節專案層「擁有並維護」清單要加 `verify/cases/` 之外的「驗收規格範本」，否則 ledger 只記 PASS／FAIL，不知道 PASS 的是哪一條承諾。
3. **少了「跨 repo 的上下游」**。SGI 一條協定跨 3 repo 2 台 server：錯誤碼在 GuildServer 決定、MapServer 翻譯、client 顯示；常數正本實體在 sgi_client 目錄、server 用 `<Compile Link>` 連進來。profile 一列只有一個前綴，表達不了「這個檔同時是 Client 與 Server 部位」「這個決策在另一台 server」。建議 profile 加 `upstream`／`downstream`（各指一列或一個外部 repo）與允許**一檔多部位**（`Part:` 可多值）。
4. **SGI 最容易回到修症狀的環節（按這波證據排序）**：①**跨 server 回覆值翻譯層**——AI 看到的 handler 只有一半，會在 MapServer 端補 `if`（GuildRecruitManager 七段 switch 就是這麼長出來的）；②**存檔層**——判「資料存哪」沒先查 `SaveMode`（案例二）；③**驗收規格驅動的工具修補**——每輪只修當下炸的那一點（案例一、合服工具 60 天 7～8 筆 fix）；④**框架層無卡**——`Orbit-Serverbase` 的 logger NRE 那種，四個月重摔。對應機制：①②要 `locate_extra` 第四問（Server：「錯誤碼在哪台 server 決定？資料存哪、SaveMode？」）；③要 H5 的「改了還是不對」觸發加一個可機器偵測的訊號：**同一檔同一 session 第二次 Edit**；④要第六節「無卡列仍要定位」再加「無卡列注入上游卡的病灶段」（SGI 表第 11 列已這樣填）。
5. 根層角色一句補：根層 session 的 E2E 測試**不得碰專案的 live log／ledger**（073 事件已修）——寫進根層自己的導讀卡病灶段，不只寫 verify。

## 二、變量：19 個裡 SGI 會覆蓋哪些、成什麼值、漏了哪些
| 變量 | SGI 覆蓋值 | 為什麼 |
|---|---|---|
| `dry_run` | true（不開擋） | S11：10 場零程式改動，自然樣本 0，開擋沒依據 |
| `deny_parts` | []；等自然樣本 ≥5 筆再考慮 `["Server／玩家存檔"]` | 存檔層是案例二的根因層，最值得先擋 |
| `locate_extra` | Server：「資料存哪（SaveMode）？錯誤碼在哪台 server 決定？」；合服：「新步驟同時接拆服？結束碼契約一碼一動作？」；文件：「這份有最後驗證嗎？改的是正本還是鏡像？」 | 四張卡「動手前必問」段的第一句各自就是這題 |
| `min_overview_evidence` | `{"card": true, "depends_files": 0, "part_files": 1}` | Server 卡 Depends 指 `GameServer.cs` 等四檔，改一個 Manager 根本不該讀它們；「讀過該前綴下任一檔」才合理——**`part_files` 這個鍵現在沒有，漏了** |
| `vcs` | auto 可，但要 `vcs_roots: ["." (git), "sgi_server" (svn), "sgi_client" (svn)]` 明列 | `Tools/` 也是 svn 但 12 GB，`svn status` 掃它幾十秒；auto 偵測會把它掃進去——**漏 `ledger_files_scope`（哪些 repo 進 files_changed）** |
| `log_encoding` | 不需要：`svn log --xml` 本來就 UTF-8 | 真正的坑在**提交端**：`svn commit` 不帶 `--encoding UTF-8` 會把訊息以 Big5 存庫，revprop 事後改不掉——**漏 `commit_encoding`／`commit_cmd_template`**（任何根層自動提交工具都得吃） |
| `fix_patterns` | 預設加 `^Fix:`（已不分大小寫，ok）與「修正：」冒號型 | SGI 訊息有 `Fix:` 與 `fix:` 兩派 |
| `refix_exclude` | 預設＋`bin/`、`obj/`、`*.json`（Tools 產物） | 否則產檔器輸出被算成 fix |
| `refix_same_commit_pairs` | false | 合服工具一筆 commit 改 20 檔，pairs 灌高——**這個開關漏了**，三邊都提了只有主尺改 fix 數 |
| `sentinel_regex` | 預設即可 | 三支檢查器與 prebuild 都照這格式 |
| `tool_selftests[]` | `shared_enum_sync_check`（預期 FAIL 直到 9 分歧處置）、`protocol_wiring_check`（同）、`gen_gm_*.py --check`×5、`prebuild_check --only equiv` | 「預期 FAIL」要能登記，否則健檢天天紅——**漏 `expected` 欄可填 FAIL** |
| `smells_cmd` | 無——TSLG 掃描器沒入 `_tools`，只在 tri-link 附件 | 這波沒地方放；**漏「共用工具的落點」**：兩專案共用的掃描器該住公司層或根層 skill |
| `codex_cmd` | `codex exec -C <root> -s read-only -`（材料內嵌） | 本機 read-only 起不了子程序，但內嵌材料能跑；不用 danger |
| `path_bases` | 不需要 | SGI 表全用工作區根 |
| **漏（SGI 這波想覆蓋卻沒地方寫）** | `readonly_paths`：`Shared/Proto/*`、`Shared/Form/Design*.cs`、`auto_generate/`（產物，Edit 一律擋，不分 dry_run）；`build_cmd` 按部位（Server：`dotnet build MapServer/MapServer.csproj -c Debug`；Client：熱更 dll 建置）給 H8／P2 用；`authority_map`（見一-1）；`part_aliases`／一檔多部位（見一-3）；`verify_spec_template`（驗收規格三段）；`prebuild_checks[]`（P1 讀的清單）；`console_codepage`（cp950：hook spawn 的 python 印中文會亂碼，要 `PYTHONIOENCODING=utf-8`） | |

## 三、奇耙設定：第六節 10 條之外，根層不知道就會做錯的
1. **`svn commit` 中文訊息必加 `--encoding UTF-8 -F <utf8 檔>`**；主控台 950，不加就 Big5 存庫，log 是 revprop、伺服器沒開 `pre-revprop-change`，送出改不掉。任何自動提交都要吃這條。
2. **自動生成產物不可手改**：`Shared/Proto/*`（protoc）、`Shared/Form/Design*.cs`（ExcelToData 產）、`auto_generate/`；改了會被下次產檔蓋掉，閘該直接擋。
3. **一檔兩部位**：共用常數正本實體在 `sgi_client/.../ILScript~/SharedScript/ILToMain/`，server 用 `<Compile Link>` 編進 `Shared.csproj`；主程式集另一份是子集且已有 9 個值不同。路徑→部位不是 1:1。
4. **`netcoreapp3.1` 釘死不可升**；本機同時裝 SDK 6／9／10，`dotnet build` 照 csproj 選；但 `_tools/equiv_proof` 是 net8——同工作區多 TFM，`build_cmd` 要按部位。
5. **伺服器執行時工作目錄是 `sgi_client/env`**（launchSettings），設定檔 `set.xml` 在 `sgi_server/env`；不帶參數起的 MapServer 是 Id 1 聽 21102 不是文件寫的 10031；要開 port 得 DbServer 世界資料＋GuildServer 軍團初始化兩旗標都到；全套本機 15～16 台服＋MySQL 33060。
6. **框架 `ConsoleLogger` 在 stdin 重導時第一次 `Log.Info` 就 NRE**：根層任何「起 server 量數字」的工具不能用背景管線起，要給 console（`cmd /c start`）。
7. **主控台字碼頁 950**：hook spawn 的 python 印中文亂碼、`--help` 中文 docstring 亂碼；三支檢查器同病。根層工具印非 ASCII 要設 `PYTHONIOENCODING`。
8. **MSYS bash 下 python 吃含中文的 `/c/...` 路徑會壞**（本 session 撞過：FileNotFound），要用 `C:/` 形式或 glob。
9. **工作區是多 repo 混合**：root git（`_AIDocs`、`_tools`、`.claude`）＋三個獨立 SVN（`sgi_server`、`sgi_client`、`Tools` 12 GB）＋獨立 git（`sgi_jenkins`）；打包 CI 在 `sgi_jenkins`（另一台 khm-service），P1 的「接進打包前」落點不在 root git。
10. **`.claude/inbox/` 必須 gitignore**（已做），之前 worker 信件 71 檔曾被追蹤。
11. **專案層 Lv1 是閉合清單**（Server／Client／Tools／合服／Gameplay／CharDataBlob／MemoryMeta…），新部位「文件」要 `allow_new_category`——T1 的「先映射既有 Lv1」在 SGI 多半映得到，映不到才開。
12. **零測試專案**：沒有 xunit／nunit；驗證靠離線載入組件（先設 `Log.Current`）、反射實跑、`--check` 腳本、本機起服。H6／P2 不能假設有測試框架。
13. **SVN 工作副本有別人的 M 混在一起**（使用者自己的 5 個 M）：ledger 的 `files_changed`、T2 的「改了哪些檔」會把別人的改動算進來；要能以「本 session 動過的檔」為準，不是工作副本全部 M。

## 四、教育差異：我附件裡哪些是「SGI 習慣」不是通用
| 主張 | 屬性 | 建議 |
|---|---|---|
| 驗收規格三段（必須發生／禁止發生／驗證指令）隨每次提交 | SGI 習慣（AI 提交一向如此） | 做成**預設範本**（`verify_spec_template`），專案可關 |
| 控制塔＝唯一讀起點、§8 權威地圖、「兩處矛盾裁定以此為準」 | SGI 習慣（H 系列養出來的） | 權威地圖做成 profile 欄（`authority_map`）；「矛盾裁定」做成文件卡的固定段，預設空 |
| 整行哨兵 `<NAME>_CHECK PASS\|FAIL` | SGI 定的格式 | 已是預設，ok；加 `DONE` 類已做 |
| FastProof（舊源碼 regex 解析預期 vs 新 dll 反射實跑） | SGI 專屬（C#＋svn BASE） | skill 只抽原則「預期來自舊源碼、實際來自新產物、兩邊不同來源才不是自證」；實作留專案 |
| 「零測試專案所以靠反射與離線載入」 | SGI 特殊 | 通用預設應是「有測試框架先用測試」，無才走這條——變量 `test_runner`（有／無） |
| 「上GIT」口令、團隊共有物等口令、記憶系統直上 | 使用者個人規矩 | 變量 `commit_policy: ask\|auto`，預設 ask |
| `_AIDocs` 每改必追 `_CHANGELOG`、`_INDEX` 唯一讀起點 | SGI 習慣 | 文件卡預設段「改完三問」可帶，但 `docs_index`／`changelog` 路徑是變量 |
| CLAUDE.md 的「高風險／極高風險先讀文件、先確認」分級 | SGI 習慣 | 通用化就是 `deny_parts`＋`locate_extra`，不用另設 |
| 「找到壞味道當場高速修整並證明結果相同」 | 使用者對 AI 的要求，不限專案 | 通用（#13），但「證明」的手段是專案的 |
| 多 session 信箱協定（自檢段、分級、30 分鐘一行） | 這波養出來的工作法 | 通用，可做 skill；跟專案教育無關 |

## 自檢
- 本封分級：試過 9 句（S11 零改動、Tools svn 12 GB、Big5 坑、MapServer 旗標與 port、NRE、cp950、MSYS 路徑、9 分歧、5 個別人的 M）／看程式知道 6 句（Compile Link、產物清單、TFM、launchSettings、Lv1 清單、零測試）／推測 4 句（四個「最容易修症狀」環節的排序、`part_files` 比 Depends 合理、deny 存檔層最值得、驗收規格能餵 ledger）／大家同意 0。
- 上一封說過頭的：072 無。
- 本封最弱的一句：「SGI 最容易回到修症狀的四個環節」是我從這波四個案例歸的，樣本小。
- 本封結論拐了幾個彎：一（案例 → 環節 → 變量）。
- 進度：四題答完，待命、不動專案端。

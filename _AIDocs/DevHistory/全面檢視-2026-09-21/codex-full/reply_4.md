**建議採取局部精簡：優先消除重複產物、重複啟動與重複規範；目前沒有足夠證據支持拔除整個記憶子系統或 Stop 閘門。**

本輪僅讀本地，未上網、未修改檔案。已完整閱讀 `TECH.md`、`Architecture.md`、設定與 21 個 active skill；對 dispatcher、handlers、`wg_*` 共 **31 個 Python 檔、15,759 行**做語法樹與引用盤點，再沿候選呼叫鏈深讀。14 個 `wg_*` 模組都有程式匯入端；找到的明確孤兒候選只有 **4 個 helper、64 行，約占上述程式碼的 0.4%**。

以下 token 數採本系統 [`_estimate_tokens`](C:/Users/holylight/.claude/hooks/wg_core.py:188) 的估算口徑，**不是模型 tokenizer 或帳單實測**。人日與修改後淨行數均為估算。

**候選清單**

| # | 名稱 | 來源（檔案:行） | 機制 | 類型 | 對本系統的意義 | 第一個 session 看得到的效果 | 成本／風險 | 證據等級 |
|---|---|---|---|---|---|---|---|---|
| 1 | 無讀取端設定＋孤兒 helper | [config:337](C:/Users/holylight/.claude/workflow/config.json:337)、[config:350](C:/Users/holylight/.claude/workflow/config.json:350)、[wg_atoms:152](C:/Users/holylight/.claude/hooks/wg_atoms.py:152)、[wg_core:373](C:/Users/holylight/.claude/hooks/wg_core.py:373) | `heal.run_full_verify` 未找到程式讀取端。`world_dev` 明載為宣告鏡像，實際引擎讀前端 `ENGINE`。另有四個函式在受查範圍只出現定義，沒有呼叫或字串引用。 | 精簡 | 刪除無效旋鈕與無使用端程式，不動功能。 | **64 行 Python＋21 行設定**可列入刪除範圍；不主張有可感知的 token／延遲收益。 | 約 0.25–0.5 人日；低風險，但須排除其他專案的外部匯入。 | 靜態實證；尚未刪除後回歸。 |
| 2 | 合併 PostToolUse 的啟動流程 | [settings:97](C:/Users/holylight/.claude/settings.json:97)、[version_guard:163](C:/Users/holylight/.claude/hooks/version_guard.py:163)、[acceptance_spec:238](C:/Users/holylight/.claude/hooks/acceptance_spec.py:238) | 一次 Edit／Write 現在會啟動 guardian、Codex companion、version guard、acceptance spec 四支程序。後兩支各自重做 stdin、JSON、config 與入口處理。可讓 guardian 共用入口執行兩個輕量檢查，保留各自判定、開關和錯誤隔離。 | 精簡 | 消除重複程序啟動；Codex companion 保持獨立。 | 每次 Edit／Write **少啟動兩支 Python 程序**；輸出 token 預期不變。兩支入口與 config loader 合計 73 行，扣掉整合程式後預估淨減 40–70 行。 | 約 1–2 人日；中風險，涉及 matcher、輸出合併、狀態讀取順序。 | 註冊與程式實證；端到端加速未測。 |
| 3 | `read-project` 只保存一份詳細文件目錄 | [SKILL:78](C:/Users/holylight/.claude/skills/read-project/SKILL.md:78)、[SKILL:114](C:/Users/holylight/.claude/skills/read-project/SKILL.md:114)、[SKILL:134](C:/Users/holylight/.claude/skills/read-project/SKILL.md:134) | 現在先把分類檔案清單寫進 atom，再寫一份 `_AIDocs/DocIndex-*`。有 `_AIDocs` 時，詳細目錄可只留在文件，atom 保留主題、摘要與文件錨點。索引更新直接遵循既有 `atom_write` 流程，不再指示模型手動補 `MEMORY.md`。 | 精簡＋補強 | 使用既有文件指標與寫入機制，消除兩份目錄同步。 | 首次使用便少生成一份詳細清單；後續召回節省量為「原清單 token − 指標摘要 token」，未測固定值。skill 預估減 10–25 行。 | 約 0.5–1 人日；中低風險，須保留沒有 `_AIDocs` 的路徑。 | 重複產物為靜態實證；召回等價尚待驗證。 |
| 4 | skill 長範例與備援程式按需讀取 | [browse-sprites:52](C:/Users/holylight/.claude/skills/browse-sprites/SKILL.md:52)、[handoff:91](C:/Users/holylight/.claude/skills/handoff/SKILL.md:91)、[sprite 工具:78](C:/Users/holylight/.claude/tools/sprite_contact_sheet.py:78) | `browse-sprites` 已有正式工具，skill 仍內嵌完整備援程式。`handoff` 同時包含規格、檢核和長篇完成範例。把備援程式與示例移到明確條件才讀的參考檔，主 skill 保留執行要求。 | 精簡 | 縮小技能載入內容，保留既有能力與指令名稱。 | 移出段落分別為 **40 行／447 估算 token**、**39 行／579 估算 token**；實際淨省需扣參考指令。僅在使用對應 skill 時受益。 | 約 0.25–0.5 人日；低至中風險。全 repo 行數不一定下降，下降的是常用載入量。 | 段落大小實測；任務品質未做 A/B。 |
| 5 | 規範只保留一個權威版本 | [Architecture:3](C:/Users/holylight/.claude/_AIDocs/Architecture.md:3)、[Architecture:314](C:/Users/holylight/.claude/_AIDocs/Architecture.md:314)、[TECH:403](C:/Users/holylight/.claude/TECH.md:403)、[memory skill:138](C:/Users/holylight/.claude/skills/memory/SKILL.md:138) | `Architecture.md` 自稱索引，卻有大量機制細節，已與 TECH 發生矛盾。先以程式與測試校正權威說明，再讓 Architecture 保留模組入口與獨有設計。`memory review` 也應明確指向現有可執行流程，移除「若支援不存在的 CLI 選項就執行」這種猜測分派。 | 精簡＋補強 | 降低改一處卻要同步多份敘述的成本，減少模型讀到矛盾規格。 | 第一次維護／診斷 session 就少一個錯誤分支。Architecture 預估可減 150–250 行重複敘述；**一般 session token 收益為 0**。 | 約 0.5–1 人日；低至中風險，需保存獨有內容與連結。 | 規範矛盾、CLI 缺項已驗證；淨刪行數為估算。 |
| 6 | always-load 只修剪純說明句 | [IDENTITY:6](C:/Users/holylight/.claude/IDENTITY.md:6)、[core:3](C:/Users/holylight/.claude/rules/core.md:3)、[契約登記表:2](C:/Users/holylight/.claude/memory/_meta/always-load-contracts.json:2) | 兩段文字主要在解釋「本檔留下什麼、其他內容放哪裡」。可移出必載內容，保留全部行為契約與操作規則。修改必須同步來源 template，避免下次初始化回填。 | 精簡 | 有直接但很小的固定輸入節省，不需要新增機制。 | 兩段合計 **167 估算 token**；不能把它乘上每輪當成全額費用節省。延遲收益未測。 | 約 0.1–0.25 人日；低風險，仍需契約與行為檢查。 | 文字大小實測；實際 tokenizer 與行為影響未測。 |
| 7 | `upgrade` 降 dormant：僅保留候選 | [upgrade:3](C:/Users/holylight/.claude/skills/upgrade/SKILL.md:3)、[upgrade:97](C:/Users/holylight/.claude/skills/upgrade/SKILL.md:97)、[upgrade:119](C:/Users/holylight/.claude/skills/upgrade/SKILL.md:119) | 此 skill 是 V4／V5 遷移流程，仍用入口檔行數判版本，並掃描舊 `commands/`。它適合放入遷移專用 dormant 區，而非當成日常同步工具。可是目前沒有其他機器版本與使用紀錄，不能認定遷移需求已消失。 | 精簡候選，暫緩 | 避免誤用過時流程；尚未達到可直接停用的證據門檻。 | active 維護範圍可少 368 行，但封存不減 repo 總行數；它已是手動觸發，**不主張一般 session token 收益**。 | 確認需求後約 0.25 人日；未確認前風險中高。 | 過時步驟有靜態證據；無人使用與無回滾需求未查到。 |

**每個候選的「拔除後不損失效果」驗法**

1. **無效設定與孤兒 helper：做等價驗證，不靠「看起來沒用」。**  
   四個函式為 [`_parse_atom_index_file`](C:/Users/holylight/.claude/hooks/wg_atoms.py:152)、[`build_atom_df`](C:/Users/holylight/.claude/hooks/wg_atoms.py:1079)、[`get_scope_dir`](C:/Users/holylight/.claude/hooks/wg_core.py:373)、[`get_project_claude_dir`](C:/Users/holylight/.claude/hooks/wg_core.py:413)。刪前補查已登記專案與安裝腳本的外部引用；刪後跑既有回歸。設定部分比較刪前後的 heal 執行參數及世界引擎行為；前端真正的來源是 [`world.html:960`](C:/Users/holylight/.claude/tools/workflow-guardian-mcp/world.html:960)。通過後才可稱為無效果程式。

2. **PostToolUse 合併：重播相同事件，比較輸出與狀態。**  
   覆蓋 Edit、Write、MultiEdit、NotebookEdit、ExitPlanMode，以及第三個修改檔、已有驗收文件、計畫遭拒、各開關關閉。要求警告內容、附屬狀態檔與修改檔計數等價。現在兩個 standalone handler 會呼叫 `sys.exit()`，必須改成回傳結果，不能直接匯入後串接。matcher 必須取原本適用範圍，不能只沿用 guardian 的清單。

3. **文件目錄去重：驗證找得到原文件，而非只驗 atom 變短。**  
   用同一組代表性文件產出新舊版本，接著詢問相同的文件定位問題，核對命中文件與摘要完整性；另測沒有 `_AIDocs` 的專案。系統已有 [3KB 知識段預算與清單樣式警告](C:/Users/holylight/.claude/_AIDocs/Architecture.md:310)，無須再新增一套瘦身偵測。

4. **skill 按需讀取：分正常路徑與備援路徑驗。**  
   `browse-sprites` 分別測正式工具存在／缺少；`handoff` 核對六個必要區塊與自足性要求。正常路徑應不讀參考檔；需要備援或示例時仍能找到。若移出示例後交接品質下降，就保留能避免錯誤的最小示例。

5. **規範去重：建立主張對照，確保每項規則仍有落點。**  
   Architecture 獨有的設計理由不能直接丟掉。`memory review` 的 `--self-iterate` 在 [目前 argparse 選項](C:/Users/holylight/.claude/tools/memory-audit.py:1681) 中不存在；應驗證它能直接走既有 health 流程，且不再承諾沒有執行入口的檢查。另須解決 [`memory:25`](C:/Users/holylight/.claude/skills/memory/SKILL.md:25)「無參數跑 health」與 [`memory:153`](C:/Users/holylight/.claude/skills/memory/SKILL.md:153)「無參數詢問選單」的矛盾。

6. **always-load 修剪：契約文字與行為都要保住。**  
   先跑既有 [`verify_always_load_contracts.py`](C:/Users/holylight/.claude/hooks/verify/verify_always_load_contracts.py:35)，再以相同提示檢查動手前預告、上GIT語意、根層修改邊界及收尾誠實。登記表已記錄過契約移到 atom 後被截斷的事故，不能只因關鍵字測試通過就繼續大幅刪短。

7. **`upgrade` dormant：先證明遷移需求已結束。**  
   必須確認所有共享機器的 schema／安裝版本、恢復路徑與近期遷移需求。沒有這些資料，保留手動入口比較合理；不另外建立常駐量測來追蹤這支低頻工具。

**最值得做的 5 件，依序**

1. **`read-project` 詳細目錄去重。** 重複產物有直接證據，且既有文件指標、寫入閘門與索引機制都能承接，不需新增框架。
2. **PostToolUse 合併啟動流程，先做事件等價回放。** 這是目前最具體的執行成本候選，收益是少兩次程序啟動，值得量測真實延遲。
3. **把 skill 的備援程式與長範例改為按需讀取。** 修改小，第一次使用對應 skill 就能減少載入內容。
4. **收斂 Architecture 與技能操作規範。** 已有矛盾與不存在的 CLI 選項，改善的是首次診斷的正確性與後續維護成本。
5. **順手清除 64 行孤兒 helper 與 21 行無效設定。** 確認外部引用後可做，但不值得為此建立新子系統，也不應宣稱它能明顯加速。

以上應分批驗證：純清理、技能內容、hook 執行流程各自獨立。任一批輸出或狀態不等價就撤回該批，避免一次搬動整套系統。

**明確不建議做的**

- **不因設定為 false 就刪整個功能。** 本輪未找到同時滿足「目前關閉、沒有使用端、沒有回滾／手動需求」的完整功能。例如 `architecture_review` 雖關閉，仍有 [事件判定](C:/Users/holylight/.claude/hooks/codex_companion.py:148)；遺忘功能也有 [memory-audit 手動啟用路徑](C:/Users/holylight/.claude/tools/memory-audit.py:1195)。無效欄位和可手動使用的功能不是同一件事。

- **不把 Stop 的不同判斷閘硬併成一個。** 測試失敗、退避、AEC-Pending、同步分別檢查不同證據，不能以同在收尾執行就判定重複。可共用的是資料取得：guardian 已 [共用 transcript 尾段](C:/Users/holylight/.claude/hooks/handlers/stop.py:643)，但 lang guard 在缺少直接訊息時仍會 [掃描整份 transcript](C:/Users/holylight/.claude/hooks/lang_guard.py:129)。這是次順位效能候選；必須先保留兩者不同的取文語意，不能直接替換。

- **不為減少 skill 數量而合併 debug／手動入口。** 目前 9 個 skill 已設 `disable-model-invocation: true`；不能把其全文當成每個 session 的固定負擔。`handoff` 與 `continue` 一個寫交接、一個讀交接，也不是重複功能。現有證據不足以把任何 active skill 直接判成「無人使用」。

- **不因 tools 多就合併 CLI。** [`sync-atom-index`](C:/Users/holylight/.claude/tools/sync-atom-index.py:2)處理 Trigger 與機器索引一致性，[`sync-memory-index`](C:/Users/holylight/.claude/tools/sync-memory-index.py:2)產生人讀鏡像；兩者責任不同。[`health-weekly`](C:/Users/holylight/.claude/tools/health-weekly.py:135)主要串接檢查，也不是第三套完整健檢演算法。盤點到的 tools Python 腳本為 90 支，其中 28 支位於 verify 目錄；排除它們後為 62 支。

- **不繼續大砍 always-load 或直接刪零曝光 atom。** `MEMORY.md` 已只有 19 行，且是 [hook 全掛時的導航保底](C:/Users/holylight/.claude/TECH.md:322)。週報的 [35 顆零曝光候選及 episodic 停擺](C:/Users/holylight/.claude/workflow/health-reports/health-20260921.md:4)不能證明功能沒價值：可能是沒有適用任務，也可能是管線故障。

**未查到／不確定的**

- **真實 hook 加速幅度未測。** 本環境空 Python 子程序啟動 20 次，中位數 **311.48ms**，範圍 **233.79–653.58ms**。這只是啟動成本基準；hook 可能並行，不能據此宣稱合併後每次 Edit 就快 623ms。
- **沒有其他機器與 repo 外部引用證據。** 因此四個 helper 是高可信刪除候選，尚不是跨所有機器的安全刪除證明。
- **文件不能直接當成目前執行事實。** 例如 [TECH:378](C:/Users/holylight/.claude/TECH.md:378)寫全量萃取「在跑」，但 [SessionEnd:208](C:/Users/holylight/.claude/hooks/handlers/session_end.py:208)仍受停用設定控制。這支持收斂規範來源，不支持再提一次已除役機制。
- **本輪通過的是靜態語法檢查，不是行為回歸。** 31 個核心 Python 檔 AST 解析全部成功；未執行會寫入實際記憶、狀態或索引的 hook，也未在唯讀環境進行修改後 A/B。表中的收益與安全刪除條件，仍須依上述驗法完成後才能視為驗收通過。

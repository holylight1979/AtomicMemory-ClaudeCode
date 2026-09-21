**結論：找到 5 項 BLOCK，建議修正後再上線。** 以下反例均以唯讀方式、記憶體替身重現；未修改檔案。

## BLOCK（必須先修才能上線）：項目 → 檔:行 → 為什麼 → 最小修法

1. **專案 `_AIAtoms` 的 Supersedes 掃錯根目錄，舊卡仍會注入**  
   → [session_start.py:855](C:/Users/holylight/.claude/hooks/handlers/session_start.py:855)、[ups_search.py:180](C:/Users/holylight/.claude/hooks/handlers/ups_search.py:180)  
   → SessionStart 一律用 `project_memory_dir.parent`；UPS 卻對 `_AIAtoms/` 使用 `project_root`。以 `project/.claude/memory` 配合 `_AIAtoms/new.md` 重現：SessionStart 得到空集合，正確根目錄得到 `{'old'}`；UPS 因已有 `superseded=[]` 不補算，只有舊卡命中時仍回傳 `old`。現有測試全部使用單一 global base，漏掉此情境。  
   → **最小修法：** SessionStart 與 UPS 共用相同路徑解析；補專案 `_AIAtoms`、新卡未命中但舊卡命中的測試。

2. **「不要用舊版」反而解除 Supersedes 過濾**  
   → [ups_search.py:44](C:/Users/holylight/.claude/hooks/handlers/ups_search.py:44)、[ups_search.py:189](C:/Users/holylight/.claude/hooks/handlers/ups_search.py:189)  
   → 歷史查詢只靠子字串。實跑「不要用以前的部署流程，請照最新版部署」，明確要求避免舊做法，候選卻是 `['old']`；「舊版已被取代，請只提供目前可用的方法」也會進歷史模式。  
   → **最小修法：** 只對明確要求查閱／比較歷史的語句放行；排除否定舊版的語句，補正反成對案例。

3. **正常遵守規則、先解釋再採用，都會被 v2 判成未使用**  
   → [wg_atoms.py:1274](C:/Users/holylight/.claude/hooks/wg_atoms.py:1274)、[wg_atoms.py:1337](C:/Users/holylight/.claude/hooks/wg_atoms.py:1337)  
   → ±80 字窗口只確認附近有 atom 錨點，沒有確認否定的對象。已重現：
   - 「遵照 deploy-guard，用 deploy_safe_mode 完成部署，不要用舊指令」→ `rejected`，即使提供有效 rescue token。
   - 「我用 deploy_safe_mode 完成 deploy-guard。旁邊的 CSS 不用 flex」→ `rejected`。
   - 「deploy-guard 講的是部署檢查。我已採用……完成部署」→ `cited`，即使共享 token 已達上線門檻。

   → **最小修法：** 拒用須綁定該 atom／做法的明確否定；「只是引用」須排除後續採用證據。不能讓任一附近線索直接否決整輪，補上述三種反例。

4. **「未讀路標不算使用」仍有兩條可重現的穿透路徑**  
   → [wg_atoms.py:1340](C:/Users/holylight/.claude/hooks/wg_atoms.py:1340)、[wg_atoms.py:1346](C:/Users/holylight/.claude/hooks/wg_atoms.py:1346)、[ups_inject.py:477](C:/Users/holylight/.claude/hooks/handlers/ups_inject.py:477)  
   → 第一條：`read_atom` 只是搜尋文字中的 `name.md`。僅說「我找到 deployment-alpha.md，標題提到 alpha_unique beta_unique」，完全沒有 Read，仍得到 `used=True, method=read+lexical`。  
   → 第二條：全文降成 `pointer_trim` 後保留原全文的 rescue watch；後續工具碰到**從未送出的內容 token**，rescue 分支在路標未讀檢查之前直接判 used。已重現 watch 留下 `hidden_deploy_mode`，未讀 atom 也得到 `method=rescue`。  
   → **最小修法：** Read 證據改取本輪結構化工具紀錄；pointer 化時移除未送出內容的 watch，成功讀取後再建立相應證據。

5. **子代理借用父回合文字／rescue 證據，製造假的結果衝突**  
   → [stop.py:461](C:/Users/holylight/.claude/hooks/handlers/stop.py:461)、[stop.py:498](C:/Users/holylight/.claude/hooks/handlers/stop.py:498)  
   → 每個子代理都把父回合 `turn_text` 接到自己的摘要後面，並共用父回合 rescue map。重現：父回合確實採用且成功；子代理在工作開始前報錯，摘要沒有採用內容。結果子代理仍被判 used，最後留下 `conflicted=['guard']`、寫入次數 0。這不是兩個真實採用結果衝突。  
   → **最小修法：** 子代理只用自身輸出／工具證據判用；證據按來源隔離，再合併結果。補「父有用、子未用但失敗」案例。

## WARN（可上線但要修或加測試）

1. **預算三態與硬頂口徑不同，且同一 atom 被記成 dropped＋skip。**  
   [ups_inject.py:299](C:/Users/holylight/.claude/hooks/handlers/ups_inject.py:299)、[wg_atoms.py:828](C:/Users/holylight/.claude/hooks/wg_atoms.py:828)：`decide_atom_injection` 不計標頭，`_push` 計標頭。重現內文 1,199 token、完整區塊 1,202、可用 fallback 30；實際直接退成路標，丟掉可送的知識，並留下兩筆互相矛盾的形式紀錄。應對完整區塊決策，失敗後嘗試 fallback，每顆只提交一筆最終紀錄。

2. **rescue 尾讀會漏掉有效的本輪證據。**  
   [wg_rescue.py:145](C:/Users/holylight/.claude/hooks/wg_rescue.py:145)：將本輪命中放在開頭，再接其他 session 的紀錄，總長 320,781 bytes，查詢回 `{}`。共享 log 的固定尾窗不保證涵蓋本輪。應在 state 保存本輪命中，或使用能定位 session／turn 的讀取方式。另外，[wg_atoms.py:1303](C:/Users/holylight/.claude/hooks/wg_atoms.py:1303) 所稱「非純路徑」未落實：Windows 絕對路徑、`memory/foo.md`、多層 Unix 路徑均通過 `_rescue_specific`。

3. **Supersedes 快取不追蹤 atom 內容變更。**  
   [wg_atoms.py:369](C:/Users/holylight/.claude/hooks/wg_atoms.py:369)：只看 `_atom_index.json` mtime；同進程中 atom 新增 Supersedes、索引 mtime 不變，第二次仍回舊集合，已重現。不能斷言一般多機 pull 必然觸發：新 hook 進程會重新建立此記憶體快取。應補「只變 atom metadata」失效測試，並處理長 session 中已存入 state 的舊集合。

4. **缺鍵預設與部署 config 必須分清；升級不是整體維持舊行為。**

   | 設定 | 新程式缺鍵時 | 本次 config |
   |---|---:|---:|
   | RRF activation gain | 0.25 | 0 |
   | BM25 trigger gate | 2 | 999 |
   | attribution policy | v2 | v2 |
   | v2 shared／containment | 6／0.0 | 6／0.0 |
   | Related query gate／門檻 | bm25／3.5 | bm25／5 |

   依據：[ups_search.py:253](C:/Users/holylight/.claude/hooks/handlers/ups_search.py:253)、[ups_search.py:362](C:/Users/holylight/.claude/hooks/handlers/ups_search.py:362)、[stop.py:420](C:/Users/holylight/.claude/hooks/handlers/stop.py:420)、[ups_inject.py:143](C:/Users/holylight/.claude/hooks/handlers/ups_inject.py:143)。  
   只更新程式、未更新 config，排序旋鈕維持舊值，但歸因與 Related 已改變。in-flight session 沒有固定政策版本；無 `wisdom_retry_turn_base` 時沿用累計重試，無 `turn_seq` 的舊子代理紀錄仍套當輪 outcome，後者甚至有測試明確要求如此，不能稱為已消除舊紀錄污染。

5. **online replay 尚未涵蓋真正的整包最終送達。**  
   [online_replay.py:151](C:/Users/holylight/.claude/tools/memory-eval/online_replay.py:151)：只裁 atom 的 `inject_lines`，沒有 UPS 的 `build_context`、Guardian／JIT 等共同預算佔用，search 產生的 `lines` 也未併入。故目前數字是「隔離 atom 管線」指標，不能等同完整 UPS 送達率。另 `FULL_FORMS` 把 fallback／redundant 節錄算作 full，報表「全文送達」名稱不精確。應補含非 atom 區塊的整合測試並修正報表用詞。

6. **episodic 統計把事件筆數稱作 session 場數，且近期成功會遮掉失敗。**  
   [health-weekly.py:125](C:/Users/holylight/.claude/tools/health-weekly.py:125)、[health-weekly.py:280](C:/Users/holylight/.claude/tools/health-weekly.py:280)：沒有按 session 去重；同場重試失敗會累加成多「場」。而只要任何專案有近期產物，就不會走 failed 紅燈分支。正常 pre_compact 成功後有 `episodic_checkpoint_done` 保護，**沒有證據支持正常成功路徑必定重複生成**；問題是失敗重試計數與報表分支。應區分 attempts／sessions，失敗告警獨立判斷。

7. **測試缺口與執行限制。**  
   新測試未涵蓋上述專案 base、歷史否定、真實 Read 證據、pointer watch、父子來源隔離及標頭預算邊界。BM25 只測請求詞剔除與「部署／流程」保留，沒有停用詞作為主題的正例；本次未取得足以斷言真實召回回歸的案例。  
   五檔完整 pytest 因唯讀環境無可寫暫存目錄，在啟動時中止。改用不需輸出擷取檔的方式執行部分案例：**15 passed、1 failed、6 deselected**；失敗為 `logs_dir()` 呼叫 `tempfile.gettempdir()` 同樣受暫存限制，不能歸咎為正式路徑相容性回歸。待審 patch 重建後的 **17 個 Python 檔 AST 解析通過**。

## 數字核對結果

已實跑：

```powershell
python -X utf8 tools/memory-eval/run.py --online --frozen-time 1789981315
python -X utf8 tools/memory-eval/eval_usage_v2.py
```

排序評估母體為 **175 正例、22 負例，另跳過 34 條 archived**。

| 指標 | 計畫宣稱 | 本次實跑 |
|---|---:|---:|
| 新設定 R@1 | 81.1% | **81.1%** |
| 新設定 MRR | 0.870 | **0.870** |
| 新設定 full 送達 | 88.0% | **88.0%** |
| 新設定負例送達 | 4.5% | **4.5%** |
| 舊旋鈕 R@1 | 45.1% | **44.6%** |
| 舊旋鈕 MRR | 0.639 | **0.633** |
| 舊旋鈕 full 送達 | 78.9% | **78.3%** |

舊旋鈕以相同凍結時間加上以下覆寫重跑：

```powershell
python -X utf8 tools/memory-eval/run.py --online --frozen-time 1789981315 --set vector_search.rrf_activation_gain=0.25 --set vector_search.bm25_gate_max_trigger_hits=2
```

**新設定主要指標可重現，舊設定精確數字未重現，差異原因尚未定位。** 凍結時間沒有凍結 atom／sidecar 輸入，不能只憑時間參數保證歷史結果相同。

判用評估則有明確的入口設定落差：

| 評估口徑 | v1 P／R | v2 P／R |
|---|---:|---:|
| 指定 CLI 預設：只算 adopted；v2 門檻 3／0.25 | 0.18／1.00 | **0.33／0.20** |
| 計畫口徑：adopted＋corrected；上線門檻 6／0.0 | 0.35／1.00 | **0.70／0.737** |

第二列已另用倉庫內 `eval_usage_v2.run()`、讀取部署 config 實跑：**TP=14、FP=6、FN=5、TN=32**；rejected 判 used **1/9**、cited **3/9**、unknown **2/20**，與計畫一致。

因此 **P 0.70 的數字成立，但指定 CLI 無法直接重現**。[eval_usage_v2.py:83](C:/Users/holylight/.claude/tools/memory-eval/eval_usage_v2.py:83) 預設正類不同，設定表也沒有上線的 6／0.0 組；應增加部署設定評估入口。57 筆仍是計畫註明的 AI 標註、未人工複核，以上是該標註集上的結果。

## 沒問題的（一句帶過即可）

目前 UPS 在 assemble 與 reconcile 之間沒有重新載入 state，故 JSON round-trip 雖會破壞共用物件假設，尚非現行路徑的實際 bug；pointer 偵測字串一致，`turn_injected` 改為送出者也未破壞既有 turn-seq 去重守門。

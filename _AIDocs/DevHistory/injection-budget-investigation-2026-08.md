# 注入變弱調查 — 從「MEMORY.md 瘦身害的？」到預算閘門根因與五次修正（2026-08-28）

> **期間**：2026-08-28 單日，1 個主力 session 貫穿查證 → 修正 → 實機驗證 → 回訪登記；5 個主力 commit（`3a4809c` / `fc1a888` / `db899d2`+`ce91132` / `6cd4353` / `8a89f65`）；run_verify 1561 → 1582 → 1588。
> **核心交付**：每回合 atom 注入硬頂 `TURN_BUDGET_LIMIT` 500 → 1200；總額裁切改「回填」；總額分級改依估算 token；降級版保留知識節錄；同題去冗；原生記憶橋接檔 13/13 壞 → 78/78；效果量測落 `Logs/injection-turns.jsonl` + `memory-effect-report.py` 週趨勢；回訪機制 `tools/followup-check.py`。
> **現況文件**（只寫現況、不留脈絡）：[TECH.md](../../TECH.md) §7 token budget 表、[Architecture.md](../Architecture.md)、操作面 [Tools/hook-injection-probe.md](../Tools/hook-injection-probe.md)、[_CHANGELOG.md](../_CHANGELOG.md) 2026-08-28 對應條目。本檔只留**為什麼**、**證據鏈**與**被否決的路**。

---

## 1. 背景與假設

### 1.1 使用者的懷疑
- 8/26 核心記憶分類階層化（見 [核心記憶分類階層化-2026-08.md](核心記憶分類階層化-2026-08.md)）把根層 `memory/MEMORY.md` 從 60 行明細砍成 19 行 Lv1 目錄（2,833 → 314 tok）。使用者兩天後感覺「注入／萃取變弱」，提出三個假設：
  1. MEMORY.md 瘦身後 hook 拿不到明細，注入自然變少；
  2. 分類閘（`atom_write` 必給 `domain`）太嚴，或 Lv1 範疇太少，新知識寫不進去；
  3. 資料夾／檔名用中文是否拖累比對，要不要改英文。

### 1.2 查證前的立場
三個假設都「聽起來合理」，但都沒有數據。按 [[feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長]]，先查原始碼與 log，再決定修哪裡。

---

## 2. 查證數據（假設逐一證偽）

| 假設 | 查證方式 | 結果 |
|------|---------|------|
| MEMORY.md 瘦身害注入 | `hooks/wg_atoms.py parse_memory_index`：優先讀 `_atom_index.json`（機器索引），fallback `_ATOM_INDEX.md` → 才是 MEMORY.md | **注入根本不讀 MEMORY.md**。瘦身與注入量無因果 |
| 分類閘太嚴／類別太少 | 掃 30 天分類閘紀錄 | 只拒 1 筆（候選缺「退避」詞），屬 taxonomy **詞庫薄**，非 Lv1 類別少 |
| 中文檔名拖累比對 | 統計 trigger 語言：中文 844 / 英文 525；比對規則 ASCII 走 word-boundary、CJK 走 substring；**檔名不參與比對** | 改英文檔名對注入零增益；中文成本只在 Windows 編碼面（`git core.quotepath`、subprocess cp950、`PYTHONIOENCODING`），且 130 個 wiki-link 中 105 個含中文，重寫代價高 → **維持中文** |

補充兩點查證細節，免得下次再被同樣的直覺帶偏：
- **注入的資料來源鏈**：`_atom_index.json`（`sync-memory-index` 產出，含每顆 atom 的 path / triggers / realm）→ trigger 比對與 BM25／向量檢索 → `ups_inject` 主迴圈依預算決定全文／降級／指標。MEMORY.md 只是給人與 `@import` 看的目錄，hook 從頭到尾沒碰它；所以「瘦身」對注入的影響是零，對每 session 固定開銷則省了 2,500 tok。
- **中文 trigger 的比對方式**：CJK 走 substring，「收尾」能命中「收尾工作樹要上乾淨」；ASCII 走 word-boundary，`git` 不會被 `digit` 誤中。兩種都在 prompt 文字上做，與 atom 檔名、資料夾名無關。改英文檔名唯一會變的是 Windows 上 `git status` 顯示與 subprocess 解碼，這些早有 `core.quotepath=false`、`PYTHONIOENCODING=utf-8` 處置。

三個假設全部不成立；「變弱」是真的，但根因在別處。

---

## 3. 根因鏈（時間線）

真正的根因是**每回合 atom 段的硬頂**，而且是兩個月前埋下的：

1. **7/1 縮量 A**：為壓 context 用量，`wg_core.TURN_BUDGET_LIMIT` 800 → 500。當時 atom 平均較瘦，看不出副作用。
2. **7/29 AtomAudit**：稽核已抓到「肥 atom 被降成一行」的訊號，但處置只加了 atom 3KB 寫入上限，**沒有回調硬頂**——訊號被看見卻沒接到根因。
3. **8 月 atom 全文中位數 ~360 tok（p75 413）**：硬頂 500 意味每回合只裝得下 **1 顆**全文，其餘全部降級成標題或一行路標。
4. **近 14 天 19 個有注入回合**：決策分布 ok 19 / fallback 34 / skip 34 / cold 49 → trigger 命中的熱 atom 87 顆僅 19 顆全文，**全文率 22%**；每回合總額 2800 只用到 1070——錢在口袋裡，卻被子閘門擋著花不出去。
5. `tools/memory-effect-report.py` 週趨勢佐證：週曝光 314 → 209、rescue 命中 77 → 26。使用者的體感是準的。

8/26 瘦身只是巧合的時間點；MEMORY.md 那 2,500 tok 省下來的空間，從來沒有流向 atom 段。

---

## 4. 五次修正

### 修 1：硬頂放寬＋降級版保留知識＋量測落地（commit `3a4809c`）
- **問題**：硬頂 500 只裝 1 顆；降級版（budget fallback）只剩印象段，沒有印象段的 atom 降級後等於空殼。
- **證據**：§3 第 4 點的 19/87 統計；最肥 atom 全文 537 tok。
- **修法**：
  - `wg_core.TURN_BUDGET_LIMIT` 500 → 1200（≈3 顆全文），釘死數值的測試改成區間。
  - `_strip_atom_for_injection_impression_only` 無印象段時補知識段前 2 條（[固]/[觀] 優先、每條 160 字截尾）；最肥 atom 降級版 537 → 349 tok。
  - `hooks/handlers/ups_inject.py` 每回合追加一行 `Logs/injection-turns.jsonl`（`at, session_id, turn_seq, ok, fallback, skip, cold, redundant, used_tokens, limit`）；`PYTEST_CURRENT_TEST` 存在時不落正式檔。
  - `tools/memory-effect-report.py` 週趨勢加「有注入回合／全文/回合／熱 atom 全文率」。
  - `memory/_meta/taxonomy.json` 行為契約／驗證與實證／工作流補詞（§2 那筆 REJECT 現可自動歸位）。
  - 順修 `verify_session_coordination.test_entry_window` 貼線 59s 併跑假紅。
- **驗證**：run_verify 1561 綠；統計檔跑完 0 行（遙測守衛生效）。

### 修 2：Reload 後實機驗證抓到兩個新問題（commit `fc1a888`）
離線測試只證邏輯，注入效果必須用**真 hook 進程**驗（做法見 [Tools/hook-injection-probe.md](../Tools/hook-injection-probe.md)）。短／中／長 prompt 各 3 次，發現：
- **問題 ①**：`_truncate_context_by_activation` Phase B 只留 `truncated_pointer_max`（3）顆指標，其餘整塊丟；整塊移除省的比 Phase A 估算的多 → 尾行顯示 **359/1000 卻 dropped 5 顆**。
  - **修法**：Phase B 改由 activation 高到低**回填**——塞得下全文就恢復全文，否則留一行指標（未達上限時），再否則才丟。
  - **驗證**：實測 998/1000、799/800、1786/1800，預算用滿、犧牲最少。
- **問題 ②**：`compute_token_budget` 依**字元數**分級。中文 37 字（≈33 tok，實質問題）被壓到 1000 總額，英文 76 字（≈19 tok，一句閒話）反而拿 2000。
  - **修法**：改依 `_estimate_tokens`（CJK-aware）分級：`TOKEN_BUDGET_TIERS = ((15, 1000), (80, 2000))`，其餘 3000。
  - **驗證**：中文中等問句 4 atoms／1 全文／5 丟 → 8 atoms／4 全文／0 丟。TECH §7 表同步、新 verify 分級測試；run_verify 1562 綠。
- **探針陷阱（兩個，記下來免重踩）**：
  - 只送 UserPromptSubmit 不送 SessionStart 的假 session，會被 `wg_core._ensure_state` 經 `_find_active_sibling_state` 認領同 cwd 的兄弟 state，去重後注入 0 顆——這是設計（同 cwd 多視窗去重），不是 bug。
  - 探針會在 atom `.access.json` 留曝光計數，無法精準回滾；會輕微影響 effect-report B 節。

### 修 3：原生記憶橋接檔 13/13 壞 7 週（commit `db899d2`，changelog `ce91132`）
- **問題**：`projects/<slug>/memory/atom-index-bridge.md`（原子系統與 CC 原生 auto-memory 的唯一接點）13 個路徑全部失效；順著查注入時才發現。
- **證據**：atom 8/26 搬進範疇資料夾，橋接檔 7/8 後從未重產；`tools/native-memory-bridge.py _slug_from_cwd` 把 `c:\Users\x\.claude` 算成 `c-Users-x-.claude`，harness 真正的規則是每個非英數字元各轉一個 `-`（`c--Users-x--claude`）。
- **修法**：修 slug（`re.sub(r"[^A-Za-z0-9]", "-", …)` 不合併）、預設鏡像 ~/.claude 自身原生目錄（不依呼叫者 cwd）、`sync-memory-index --write` 尾端 fail-open 自動重產（失敗印 stderr 不阻斷）。
- **驗證**：78/78 路徑有效。順修 Architecture MCP tool 數 4 → 5、TECH verify 檔數。

### 修 4：同題去冗（commit `6cd4353`）
- **問題**：預算放寬後，同一句「git 收尾」把 3 顆同題 atom 全文一起送（~1,000 tok 講一件事）。Chroma context-rot 研究：單一干擾項即傷精度——放寬預算不能變成灌水。
- **證據**：門檻校準掃全庫 8,515 對 atom，trigger **精確**重疊 ≥3 者僅 4 對，且皆真同題；子字串重疊不採計（泛 trigger 噪音）。
- **修法**：`ups_inject.redundant_with`——主迴圈中與本回合已全文注入者 trigger 精確重疊 ≥3 → 只送表頭＋知識前兩句，標 `(same-topic → 代表者, 節錄)`、form=redundant（AtomAudit 不稽）。config `injection.redundancy_gate {enabled, min_shared_triggers: 3}`；injection-turns.jsonl / effect-report 加「同題節錄」欄。
- **驗證**：新 verify 8 條（含全庫對數守衛 ≤20）；實機：中文中等問句「收尾工作樹要上乾淨」正確降節錄，代表者「併發 staging」。

### 修 5：回訪機制（commit `8a89f65`）
- **問題**：使用者點破「一週後看數據」的 session 早關、主題被沖淡，且沒人說清楚怎樣算驗證到。
- **修法**：`tools/followup-check.py` + `workflow/followups.json`：每筆登記到期日、檢查名、程式化通過線，以及**假設接手者什麼都不記得**的交接（這是什麼／改了什麼 commit／基線／怎麼判／不過怎麼辦／危險／規則連結／結案）。`hooks/handlers/session_start.py _followup_advisory`：到期後任何一次開 CC 自動跑，INSUFFICIENT 不催、FAIL 每日一次附交接、PASS 自動結案。
- **首筆登記** `injection-budget-2026-08-28`：since 08-29（排除調校當天的探針與調整中回合）、due 09-04；四指標見 §6。
- **驗證**：verify 6 條；run_verify 1588 綠；TECH／Architecture 同步。

### 修後當日真資料
- `memory-effect-report.py` 08-26 週：全文/回合 3.5–3.67 顆、熱 atom 全文率 58–65%（修前 1.0 顆／22%）。
- `Logs/injection-turns.jsonl` 當日尾列：used 1046/1200、1158/1200，ok 2 + fallback 1，不再只裝 1 顆。

---

## 5. 未做與理由

| 提案 | 決定 | 理由 |
|------|------|------|
| 提高每回合總額（3000 上限） | 不做 | 修前總額 2800 只用 1070；瓶頸在子閘門不在總額。用不滿的錢再加只是帳面 |
| 資料夾／檔名改英文 | 不做 | 檔名不參與 trigger 比對（§2）；成本只在編碼層，已有 `PYTHONIOENCODING` 等既定處置；105/130 wiki-link 重寫風險高於收益 |
| 新增 Lv1 範疇（Python / Web 提案） | 另議 | 30 天分類閘只拒 1 筆且是詞庫問題；沒有「類別不夠」的證據。等真有 REJECT 累積再開 |
| 加 `activation <= 0` 過濾「負分噪音」 | 不做 | activation 是 ACT-R 對數尺度天然跨零，負值＝近期少存取而非不相關（見 atom [[activation負值不是負相關-act-r對數尺度天然跨零-注入噪音修門檻與顯示勿過濾分數]]） |

---

## 6. 回訪與後續判準

到期 2026-09-04，`_followup_advisory` 會自動跑 `followup-check --run`，資料來源 `Logs/injection-turns.jsonl`（since 08-29 起算）與 `memory-effect-report.py`：

| 指標 | 通過線 | 量什麼 |
|------|--------|--------|
| 全文/回合 | ≥ 2.5 | 每個有注入的回合平均完整唸入幾顆（`ok` 欄） |
| 熱 atom 全文率 | ≥ 55% | ok ÷ (ok+fallback+skip)，找到的卡片真的讀到內容的比例 |
| final-trim dropped/回合 | ≤ 1.0 | `Logs/atom-debug-*.log` 的 `final-trim … form=dropped` 行數 ÷ 回合，過度砍是否復發 |
| 高曝光零使用 atom | ≤ 0 | effect-report B 節，放寬有沒有帶來新 token 稅 |

回合 <10 → INSUFFICIENT，什麼都不用做。不過線的逐指標處置寫在 `workflow/followups.json` 該筆 `handoff.不過怎麼辦`——原則是**先確認常數與演算法沒被改回去、再看 atom 是否過肥該拆、最後才動去冗門檻；不調回預算**。

---

## 7. 教訓

1. **體感變弱要先證偽最顯眼的假設**：三個「合理」假設全部不成立，真根因是兩個月前的縮量沒回調。查原始碼 20 分鐘省掉一場改英文檔名的大工程。
2. **稽核訊號要接到根因**：7/29 AtomAudit 已看見「肥 atom 被降一行」，卻只加了寫入上限。看見症狀 ≠處理原因。
3. **離線測試只證邏輯，注入效果必須用真 hook 進程驗**：修 1 全綠之後，實機探針才抓到「359/1000 卻丟 5 顆」與「中文問句被字元數壓級」兩個更深的問題。
4. **放寬預算要配去冗**：錢多了不等於該灌水，同題 3 顆全文一起送是新的浪費。
5. **「一週後看」要交給程式**：session 會關、人會忘；到期自動跑＋零記憶交接才是可執行的承諾。

細節已沉澱為 atom：[[注入預算三教訓-裁切要回填-分級看token不看字元-橋接檔須隨索引重產]]（`_AIDocs/_atoms/MemDev/`）與 [[回訪機制-改完一週後看數據交給到期自動跑-交接以接手者零記憶為前提]]（同目錄）。

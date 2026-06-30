# auto-capture碎片sweep污染詞庫-defer根治

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: auto-capture, realm sweep, 詞庫污染, 專案知識寫到根層, extract-worker 分類, realm-lexicon-learned, auto_migrate
- Created-at: 2026-06-24
- Related: realm-範疇分區機制-v5, realm-遷移-llm-domain-跨文字系統亂碼-snap-防線穿透, 專案等級-mcpskillhookslog-不放全域根層, 對談結束自動記憶與錯誤加權深記, scope-shared-無主題子夾路由-專案靠-project-hooks-sweep-分層

## 知識

- [臨] **extract-worker 寫萃取碎片時零分類**：SessionEnd flush 一律扁平落 `memory/<slug>.md`（content-as-filename、trigger 預設 `["auto-capture"]`、不傳 realm/domain），分類 100% 外包給同次 SessionEnd 末段 `_sweep_realm_auto_migrate`。sweep 不可靠（config auto_migrate=false／例外被 try/except 吞／LLM 離線或額度盡／SessionEnd hook 沒觸發 任一即永久卡 flat），且 `_INDEX.md` 只在 sweep 搬成功後 fire-and-forget 重生 → 卡 flat 的碎片永不入資料夾索引。
- [臨] **專案知識污染根層的反覆根因＝sweep 把未確認 [臨] 碎片當穩定 core 處理 → LLM 對其吐專案名詞/系統 trigger 標籤學進 `realm-lexicon-learned.json` → `classify_realm` 子字串命中**。`SGI-ProjectStructure/` 根層 atom 與 `auto-capture/` 葉夾是**同一機制兩面**：前者學了外部專案名詞 `sgi`、後者把系統自己的 trigger 標籤 `auto-capture` 當成 domain 葉。詞庫自我強化 → 每 SessionEnd 再犯（2026-06-12 goal-driven、06-18 flush-routing、06-24 SGI 三度）。
- [臨] **根治＝斷『學詞』源頭**：P2 `_is_unconfirmed_autocapture`（hooks/wg_atoms.py，index trigger 含 auto-capture 零 I/O 主判＋frontmatter Author=auto-captured∧[臨] 次判）讓 sweep 對未確認碎片整體 `continue` defer，晉升（[臨]→[觀]）後才 sweep。P1 `_RESERVED_LEXICON_TERMS`（lib/atom_locations.py，系統 trigger 標籤＋realm 自名＋已知外部專案 sgi/uba）sink 端 exact-match 拒收，蓋非 auto-capture 途徑。兩者皆 **py-only**（learned 詞庫與護欄無 js 對拍面）。
- [臨] 外部專案知識（如 SGI）即使在核心 session 被談到、被 auto-capture 進 global，也**不該留在 ~/.claude 根層**——匯出該專案 repo 後刪根層（de5fa9f 前例：SGI 知識更完整存在 c:\Projects 專案 atom）。新外部專案污染詞擴充 `_RESERVED_LEXICON_TERMS`。
- [臨] **寫入側隔離(2026-06-24 補，與上述 sweep defer 同源兩面)**：sweep defer 只攲「搬移」，沒攲 `response_capture` session_end flush 的「寫入」——`_flush_item_to_atom` 原本走 `write_atom` 把 [臨]/Author=auto-captured 萃取知識寫成 content-as-filename atom 扁平落 `memory/` 根(global core→注入每個專案)。**根治=隱離不分類**：`_flush_route` 落點改 `_drafts/auto-capture/`，`_flush_item_to_atom` 改 `build_atom_content`+`write_raw` 直寫（`sync-atom-index` EXCLUDED_DIR_PARTS 排除 `_drafts`→不入索引/不注入/不計數），`.gitignore` 加 `memory/_drafts/`。「寫入時跑 realm 分類器」是詞庫污染源頭，故 user 裁決選隱離而非即時分類。不影響 memory-peek（它掃 personal/auto、author=auto-extracted-v4.1，不同機制）。

## 行動

- 改 realm sweep / extract-worker / 詞庫前先讀本 atom + [[realm-範疇分區機制-v5]]
- 詞庫被污染先清 realm-lexicon-learned.json 止血，再追是否 reserved 詞/外部專案名詞漏擋
- auto-captured 碎片永遠先卡 flat memory/，分類靠晉升後 sweep，勿期待寫入即歸檔

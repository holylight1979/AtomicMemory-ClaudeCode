# realm-遷移-llm-domain-跨文字系統亂碼-snap-防線穿透

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: realm 遷移, domain 亂碼, 자동화, 韓文 domain, normalize_domain_path, 詞庫污染, realm sweep, LLM 分類器, homoglyph
- Created-at: 2026-06-12
- Related: realm-範疇分區機制-v5, feedback-memory-system-doc-sync, auto-capture碎片sweep污染詞庫-defer根治

## 知識

- [臨] 2026-06-12 實案：realm 自動遷移（_sweep_realm_auto_migrate）把 atom 搬進韓文亂碼 domain「자동화流程與協議」——本地 LLM 分類器生成 domain 名時吐出韓文「자동화」（=「自動化」），與既有中文「自動化流程與協議」並存成重複資料夾，且 append_learned_terms 把 3 個 term→亂碼路徑學進 realm-lexicon-learned.json（污染會自我強化）。
- [臨] 根因：normalize_domain_path 的 snap-to-existing 防線只做大小寫/空白變體比對，跨文字系統（Hangul vs CJK）字元層面對不上 → 穿透。LLM 生成的 domain 段視為不可信輸入，字串比對不是充分防線。
- [臨] 修復程序（再發生照做）：① 檔案 mv 回正確 domain 資料夾；② 同步 5 處——_atom_index.json、_ATOM_INDEX.md、realm-lexicon-learned.json（污染 term 改正）、Tools/_INDEX.md（移除亂碼列+計數）、正確資料夾 _INDEX.md（補列）；③ 全庫 grep 亂碼字串歸零 + JSON 驗證 + run_verify。
- [臨] 根因 guard 待裁決：domain 段含非（CJK/ASCII/數字/連字號）字元 → 視為低信心降 LOCAL_REALM_DEFAULT_DOMAIN（Else），涉 atom_locations.py + server.js classifyRealm 鏡像（test_17/test_22 parity），超順手修門檻。
- [臨] 根因 guard 已落地（2026-06-12 裁決執行）：① 字元集 guard——domain 段含非 CJK/ASCII 字元整段非法降 Else（py `_clean_segment`/`_SEG_ALLOWED_RE` 蓋 normalize_domain_path/local_write_target/set_realm；js `cleanRealmSegment`+`classifyRealm` 出口鏡像，test_18/22/26 守）；② 詞庫 sink 護欄——`append_learned_terms` 拒泛用詞（`is_generic_lexicon_term` token 黑名單）+ 拒亂碼 domain，`classify_realm` 對已污染 learned 出口降 Else。js 鏡像注意：test_17/22 用 eval block 切片，guard 邏輯必須自足於切片範圍內（不得引用 block 外 const，violations 直接 node ReferenceError）。
- [臨] 二度再犯教訓（2026-06-12 同日）：core atom goal-driven-verify-loop 被 LLM sweep 重新學進「karpathy/verify loop/可驗證目標/成功標準」再次誤搬——**泛用詞黑名單擋不住專有名詞型污染**（karpathy 是實例詞但綁定的是 core atom）。根治階梯：反覆誤搬的特定 core atom → slug 直接列 LOCAL_REALM_CORE_PROTECTED_EXACT（py+js 鏡像，protected 永不喚 LLM 永不搬），黑名單只當第二層。修復三式：atom-set-realm --to-core 搬回（含 sidecar）→ 詞庫清污染 term → sync-memory-index --write 清 stale _INDEX 列。

## 行動

- realm sweep 後抽查新建 domain 資料夾名是否與既有資料夾語意重複（特別是非中英文字元）
- 修亂碼 domain 必同步 5 處索引/詞庫，最後 grep 歸零驗證
- 動 normalize_domain_path / classifyRealm 前先讀 test_17/test_22 parity 測試


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-08-05 | --enforce 自動淘汰 (34d > 30d) | memory-audit --enforce |

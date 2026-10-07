# 衝突偵測把互補的兩張卡判成矛盾-同一事實各說一半被擋寫入-一個樣本待查-Depends驗過期可行驗矛盾誤報

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 衝突偵測, 誤判矛盾, 互補卡片, 導讀卡被擋, conflict, _pending_review, 衝突審核
- Created-at: 2026-10-07
- Source: session:3e106167#28e84fef 2026-10-07
- Quote: 「"實驗設計被抓到三次洩題": 發現問題，要想辦法從根源解決；無法解決也要記下來LLM有這種問題、日後要持續追蹤解法啊。」

## 知識

- [臨] TSLG 寫「戰鬥」部位導讀卡時被衝突偵測擋下，判它與大地圖權威卡「矛盾」；實際兩張都說「大地圖交戰由 FakeMapServer 自己算」，是同一事實各說一半的互補，走衝突審核才寫入。同場的對照：靠 `Depends:` 驗「過期」可行，驗「矛盾」會誤報。只有一個樣本，先不改；要查 `hooks/wg_` 衝突偵測對「同主題、部分重疊、不同角度」的判法，收集第二、三個樣本再調。
- [臨] 樣本滿三（戰鬥卡、網路卡被判 CONTRADICT；設計表導讀卡被去重閘判相似 0.816）後已修：根因是提示詞沒定義四類、解析固定先找 CONTRADICT（回覆裡提到就算）、舊卡只給命中片段；去重閘純向量分不出指標卡與內容卡。修法：提示詞加定義（各說一半／索引＝EXTEND）、parse_label 取最早出現的標籤、舊卡給整段知識；標題含導讀／hub索引／知識地圖的指標卡去重門檻改 0.95（config write_gate.pointer_markers／dedup_pointer_score）。LLM 端效果未實跑，下一張導讀卡寫入時驗。
- [臨] LLM 端驗過（`tools/memory-conflict-detector.py --mode write-check --scope shared --project-cwd <根> --json --content ...`，繞過 MCP）：SGI 互補內容卡三個鄰居全 EXTEND；TSLG 戰鬥卡對大地圖權威卡（原誤判 CONTRADICT 的那一對）判 EXTEND、對戰鬥導讀卡 0.83 AGREE。要驗閘的修法不必等新 session，CLI 直跑即可。

## 行動

- 再遇到導讀卡或概觀卡被衝突偵測擋：先看是不是互補，是就走審核放行並把樣本記到本 atom
- 樣本滿三個再改偵測器

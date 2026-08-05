# atom-heal L2 broken-ref 誤判 prefix-rename 為 remove

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: atom-heal, broken_ref, L2 自癒, repoint, 死連結, prefix rename, needs_human, atom rename 反向連結, 記憶自癒誤判
- Created-at: 2026-07-02
- Related: 

## 知識

- [臨] atom-heal L2 修 broken_refs 靠 LLM 判 repoint/remove/needs_human。當 broken ref 是「某現存 atom 名的前綴」（atom 被 rename 加長尾造成的 inbound 孤兒 ref）時，L2 相似度比對沒認出 prefix 關係 → 誤判『相似度極低 → remove』。盲 `--apply` 會刪掉合法連結。實案：post-mortem-write-raw 的 Related 指向 escalation-hook 舊短名，該 atom（c5ab24e）改成長名，健檢報 broken，L2 dry-run 提議 remove 而非 repoint。
- [臨] 對策：atom-heal L2 一律先 dry-run（預設即是）看 proposal；broken ref 若「目標其實存在、只是改名」→ 手動 `atom_edit_meta` repoint 到現名，勿套 L2 的 remove。L1（missing_reverse_refs 機械補反向連結，免 LLM）是安全的；L2（LLM 判 broken_ref）才會誤判。
- [臨] 硬化建議（尚未實作）：atom-heal L2 判 remove 前，先比對該 broken ref 是否為任一現存 atom 名的 prefix/substring；命中 → 提 repoint；不確定一律 fallback needs_human，永不 blind remove。呼應審查對 L2『禁盲刪』的原則。

## 行動

- atom-heal L2 `--apply` 前必看 dry-run proposal
- broken ref 若目標改名而非消失 → 手動 atom_edit_meta repoint，不靠 L2 remove
- 改 atom-heal 時補 prefix/substring 候選比對 + remove→needs_human fallback


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-08-05 | --enforce 自動淘汰 (34d > 30d) | memory-audit --enforce |

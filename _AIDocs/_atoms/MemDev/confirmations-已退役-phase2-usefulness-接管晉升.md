# confirmations-已退役-Phase2-usefulness-接管晉升

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: confirmations, confirmation_events, 恒 0, 零增, 晋升判定, wilson, usefulness, 記憶健檢, 静默失效誤報
- Created-at: 2026-06-12
- Related: memory-pipeline-silent-failure-2026-05, atom-usefulness-loop, atom-元資料編輯與晉升閘真相, 自動萃取層淨值審查-調整式拔除-2026-07

## 知識

- [臨] **confirmations 全域恒 0 不再是失效信號**（2026-06-12 Fable 總檢視徹查定調）。晋升判定是 OR 邏輯：confirmations≥4 **OR** usefulness Wilson 下界≥0.6（n≥3），Python `wg_atoms.py:1798-1807` 與 JS `server.js:1754-1775` 鏡像一致。Phase 2 閉環（stop.py 注入→使用→結果 → record_usefulness α/β）活躍接管，atom 可經 Wilson 路徑自然晋升，無晋升障礙。
- [臨] 寫入端現況：唯一 increment_confirmation 呼叫在 `wg_episodic.py:369`（跨 session episodic 搜尋命中才觸發），目前處於休眠（從未觸發過）79 檔全 0）。ReadHits 已降純曝光計數不參與晋升。config `self_iteration.promote_confirmations_threshold=4` 仍在但只剩 OR 主軸之一。
- [臨] 未來健檢正確姿勢：查記憶管線活性請看 `useful_hits/used_fail/read_hits` 增長與 `_meta/atom_io_audit.jsonl` 追加時間戳，不要再拿 confirmations=0 當證據（[[memory-pipeline-silent-failure-2026-05]] 簽章中該項已過時）。

## 行動

- （依知識內容判斷）

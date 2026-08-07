# 衝突偵測-block-資格閘-複驗一致-分區感知-待審出路

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: conflict detector, 衝突偵測, CONTRADICT, write-check, _pending_review, 待審, conflict-review, /conflict pending, 跨專案誤報, 偵測不穩定, skip_conflict_check, 分區感知
- Created-at: 2026-08-07

## 知識

- [臨] **block 資格閘**（`tools/memory-conflict-detector.py:run_write_check`）：LLM 判定是機率性的，block 必須高把握——CONTRADICT 需**第二次獨立判定一致**才成立，翻面 → `UNSTABLE(<二审結果>)` 只 warn；高相似但 LLM ERROR → fail-open warn（舊行為保守判 contradict 會讓壞掉的 LLM 擋下所有寫入）；降級一律入 `warnings` 浮出（js 端併入成功訊息）。守門 `lib/verify/verify_conflict_write_gate.py`（stub LLM，守語意不依賴 Ollama）。
- [臨] **分區感知**：一 repo 多專案共用 shared 層（`memory/projects/<X>/` 佈局）時，跨專案相似陳述非事實衝突——atom_write 帶 `subdir` 時 js 透傳 `--subdir` 給 detector，incoming 落 `projects/<X>` 分區則**其他分區**的相似 atom 不參與 block（即使穩定 CONTRADICT），warn 浮出；同分區照常 block。分區判定：path 含 `memory/projects/<X>/`；shared/<Domain> 是主題夾非分區。
- [臨] **待審出路**：被 block 的寫入落 `_pending_review/`，正規處理路徑是 `/conflict pending` → `approve/reject`（後端 `tools/conflict-review.py`：含 management 權限檢查、raw conflict report 需先另存 `<name>.resolved.md` 再 approve、merge history、reindex），不該靠 `skip_conflict_check` 繞道。
- [臨] 同一內容連寫兩次得相反判定（A矛盾dB同意↔B矛盾dA同意）是小模型（gemma 級）實測常態——單次 LLM 判定永遠不足以作硬閘依據，同型設計（任何 LLM 判定→阻斷性動作）都應複驗或降級。

## 行動

- 被 conflict detector 擋下 → /conflict pending 檢視後 approve/reject，不用 skip_conflict_check
- 分區寫入務必帶 subdir，跨專案誤報自動降 warn
- 改 block 邏輯先跑 verify_conflict_write_gate.py（免 Ollama）

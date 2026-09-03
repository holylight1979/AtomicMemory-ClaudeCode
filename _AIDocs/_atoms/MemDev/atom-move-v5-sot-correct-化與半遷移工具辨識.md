# atom-move V5 SoT-correct 化與半遷移工具辨識

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: atom-move, atom 搬移, 資料夾搬移, 記憶系統工具, SoT 損壞, 半遷移工具, sidecar 搬移
- Created-at: 2026-06-26
- Related: write-raw-對未列舉-source-靜默回-okfalse-不-raise呼叫端必檢查回傳值, feedback-memory-system-doc-sync, decisions-architecture

## 知識

- [臨] **atom-move.py（V4 殘留版）靜默損壞 V5 SoT**：只改 deprecated `_ATOM_INDEX.md` 鏡像、全程不碰 `_atom_index.json`（V5 唯一機器源）。鏡像被 `regenerate_atom_index_md` 從舊 JSON 重生覆蓋、JSON 的 path 欄停在舊路徑 → 注入層讀 JSON path → 「Read 舊路徑」找不到檔＝半孤兒。另：`cmd_move` 只 rename `.md`、漏搬 `.access.json` sidecar（計數歸零）；子資料夾被誤當 memory root 建 per-folder 孤兒索引。**2026-06-26 已重寫修正**：走 `upsert_atom`/`delete_atom`（JSON SoT）+ `move_atom_pair`（搬 sidecar）+ `find_index_dir`（上溯偵測 root）+ realm 守門 + `validate_index` 自驗。
- [臨] **通用教訓——「半遷移工具」辨識**：跨大版本重構（V4→V5）時，工具的『寫』被接上新 funnel（能跑、不報錯、過 source 契約）≠ 底層邏輯已遷移到新 SoT。判定一支工具是否真 V5-correct：查它是否實際 import/呼叫新 SoT 的 API（此案 `lib.atom_index_json.upsert/delete`），而非只看它沒報錯。斷言『壞/沒壞』前先追到底層寫入點實證（本案三方佐證：spawn 鏈、import 清單、`atom-set-realm.py` 既有註解）。
- [臨] **sidecar 必隨 atom 實體同搬**：`.access.json`（read_hits/confirmations/usefulness α,β）與 `.md` 同名同層；搬 atom 漏搬 sidecar＝計數歸零、晉升歷史飄移。任何搬 atom 實體的工具一律走 `lib.atom_access.move_atom_pair`（原子搬 .md+sidecar、失敗 rollback），勿各自手刻 rename。

## 行動

- 搬既有 atom 換資料夾 → MCP `atom_move`（已 V5-correct，子夾目標 OK）；core⇄local realm 搬移 → `atom-set-realm`；勿手 mv 或復用 V4 邏輯
- 改任何記憶系統工具前，先確認它動的是 JSON SoT（`_atom_index.json` via upsert/delete）而非 deprecated `_ATOM_INDEX.md` 鏡像
- 搬 atom 實體一律連 sidecar（`move_atom_pair`）；改完逐項過 doc-sync 清單

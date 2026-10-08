[臨] **做什麼**：這個部位是寫入閘與落檔漏斗，上游是 MCP atom_write 與 hooks 的自動萃取，下游是 memory/ 的 atom 檔與索引三檔。所有寫入都走同一條漏斗，js 不自算路徑、不自寫判定句。
[臨] **權威在哪**：落點由 lib/atom_io.locate_atom 單一裁決；預算與分型由 lib/hub_card 與 tools/memory-write-gate.py 單源；js 端只透傳欄位與轉述 py 的 reason。索引三檔由 sync 工具重產，不手改。
[臨] **動手前必問**：改的是 py（下次呼叫即生效）還是 js（要開新 session 才載到）？skip_gate 跳得過的是品質與去重，跳不過預算、realm、結構檢查。append 的預算算的是既有加新增。
[臨] **已知病灶**：導讀卡被 3072 預算擋兩次（卡：導讀卡寫入受knowledge區3072bytes預算擋）；矛盾偵測排在預算前，同一張卡會先被 CONTRADICT 再被預算擋；org 寫入曾不過 realm 閘。
[臨] **最近驗證**：2026-10-08，驗法 python -X utf8 -m pytest -q lib/verify/verify_write_gate_kinds.py 全綠；js 真行為開新 session 以 atom_write 三型各打一次。

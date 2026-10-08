[臨] **做什麼**：這個部位是寫入閘與落檔漏斗，上游是 MCP atom_write 與 hooks 的自動萃取，下游是 memory/ 的 atom 檔與索引三檔。
[臨] **權威在哪**：落點由 lib/atom_io.locate_atom 單一裁決；預算與分型由 lib/hub_card 與 write-gate 單源。
[臨] **動手前必問**：改的是 py 還是 js？skip_gate 跳得過的是品質與去重，跳不過預算、realm、結構檢查。

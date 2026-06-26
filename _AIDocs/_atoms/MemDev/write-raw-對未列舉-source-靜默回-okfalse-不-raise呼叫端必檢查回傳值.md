# write_raw 對未列舉 source 靜默回 ok=False 不 raise（呼叫端必檢查回傳值）

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: write_raw, atom_io, VALID_SOURCES, source 白名單, 靜默失敗, ok=False, WriteResult, 腳本寫 atom, funnel 寫入, 一次性整理腳本
- Created-at: 2026-06-25
- Related: atom-元資料編輯與晉升閘真相, feedback-tooling-reliability, atom-move-v5-sot-correct-化與半遷移工具辨識

## 知識

- [臨] `lib/atom_io.write_raw(path, content, *, source, op)`：source 不在 VALID_SOURCES（atom_io.py:46）時回傳 `WriteResult(ok=False, error="invalid source")`、**不 raise**（atom_io.py:409-411），`_atomic_write` 沒被呼叫。這與同函式的 OSError 路徑（414-415 也回 ok=False）一致——write_raw 統一用 WriteResult 回報錯誤、從不 raise。呼叫端不檢查 `res.ok` 就會靜默不寫還以為成功。
- [臨] 真正的坑是「文件說謊 + 呼叫端沒檢查」，非回傳式本身：atom_io.py:45 原註解寫「未列舉值會 raise ValueError」與實作矛盾、誤導讀者去 try/except。**2026-06-25 已修正註解為回傳 ok=False**（保留統一 WriteResult 契約——因 atom_io_cli.py:68-71 只 catch TypeError/KeyError，raise ValueError 會穿透破壞 MCP funnel 的 JSON 回報）。
- [臨] 實例（2026-06-24 C:\Projects shared atom 去重合併）：用非白名單 source="tool:dedup-phase-b" 附加合併 bullet，write_raw 靜默 no-op、而合併源檔已先 unlink，差點丟 3 條知識；搬完讀檔驗證才抓到，改用合法 source="tool:memory-cleanup" 重補。
- [臨] 防再犯：(a) 一次性腳本走 funnel 用既有合法 source（VALID_SOURCES 見 atom_io.py:46-65，如 tool:memory-cleanup）；(b) 寫入後必驗 `res.ok`，False 即拋；(c) 破壞性步驟（unlink/覆寫）前先讀檔確認寫入成功，不信沒檢查回傳的「OK」。

## 行動

- 一次性 / 腳本寫 atom → 走 write_raw funnel 用既有合法 source，勿自編 source 字串
- write_raw / write_atom 後必驗 res.ok，False 即拋；破壞性步驟前先讀檔確認已寫入

# 改既有記憶卡的Depends與標題要走對的入口-Depends只能write_raw-改標題用新卡取代-相似度過高被拒要先清引用再退役舊卡

- Scope: global
- Author: holylight
- Source: session 66e127d5 2026-10-29：專案記憶卡 Depends 可攜化與 21 張依賴重驗
- Confidence: [臨]
- Trigger: Depends 修正, 改 Depends, 卡片改標題, 改卡名, 依賴重驗, Verified-at, atom_retire 被擋, write-gate similar, suggest update, 被取代的卡, AtomFunnelBlock
- Created-at: 2026-10-29
- Quote: 「記憶庫的都上乾淨啊」

## 知識

- [臨] 只改卡片 `- Depends:` 行沒有 MCP 入口：atom_edit_meta 只收 Trigger／Related／Tags／Entry，Edit／Write 會被 AtomFunnelBlock 擋，atom_write replace 會重建整個知識段。做法：用 `lib.atom_io.write_raw(path, text, source="tool:atom-health-check", op=...)` 只換那一行（有稽核紀錄），寫完比對除該行外位元組不變，再跑 `sync-atom-index.py --sync-depends --memory-dir <層>`。重驗過的卡加 `- Verified-at: YYYY-MM-DD`（health-check 先讀它再退回 Created-at）。
- [臨] 標題就是檔名，沒有改名工具；標題錯就 atom_write create 新卡帶 supersedes。新舊卡相似度超過約 0.8 時 write-gate 直接回「similar … suggest update」拒寫，帶 dedupe supersedes 宣告也不放行；要先把引用舊卡的 Related 用 atom_edit_meta 拿掉（atom_retire 會列出是哪幾張）→ atom_retire 舊卡 → 再 create；反向連結由索引計算，新卡自己的 Related 寫回那幾張即可。
- [臨] 已被 Supersedes 的舊卡不會再注入，依賴重驗時不修它的內容，只拿掉它的 Depends 行，健檢就不再為它報「依賴比卡新」；不要給它蓋 Verified-at（內容並未正確）。

## 行動

- 只改 Depends：write_raw 換單行 → 比對位元組 → sync-atom-index --sync-depends
- 改標題：create 新卡 supersedes；被 similar 拒 → 清 Related 引用 → retire → create
- 被取代的舊卡：拿掉 Depends，不蓋 Verified-at

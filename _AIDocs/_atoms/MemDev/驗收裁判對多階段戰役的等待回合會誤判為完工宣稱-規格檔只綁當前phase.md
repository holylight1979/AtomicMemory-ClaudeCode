# 驗收裁判對多階段戰役的等待回合會誤判為完工宣稱-規格檔只綁當前phase

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 驗收裁判, acceptance_review, 收尾被擋, 多階段, 戰役, 等待回合, 強制放行, 規格檔, 長任務, 事件驅動監工
- Created-at: 2026-08-25
- Related: 專案工作驗收裁判的分級啟動與殺閘設計, commit-前必須核對-staged-清單而非只信自己-add-了什麼

## 知識

- [臨] **機制缺口**：驗收裁判（codex acceptance_review）假設「Stop＝完成宣稱」。長戰役（事件驅動監工、等 Grok/外部交件）每個等待回合都會被擋 2 次再強制放行，且被計成「真命中」沙売統計（MudClient 戰役一天累積 6 筆假命中）。
- [臨] **已驗證的緩解**：① 跨 session 戰役計畫放 `memory/_staging/`，`verify/acceptance-*.md` 只綁「當前進行中的單一 phase」，收工即 done 歸檔再建下一個——把整戰役寫進一份規格檔會被照單任務語意審。② 等待回合的收尾訊息用「進行中＋零完成宣稱」措辭並附誠實揭露，第 3 次自動放行，不要為了過閘假裝完工或跳過需要等待的步驟。
- [臨] **待修（基建）**：裁判應識別「等待中」狀態（例：規格檔 frontmatter 加 `phase: awaiting-external`，或 Stop 訊息含明確「零完成宣稱」標記則跳過審判），且假命中不得計入轉正/殺閘統計。屬 codex_companion acceptance.py 的設計項，未動工。

## 行動

- 開長戰役先拆：計畫→_staging，驗收檔→單 phase
- 等待回合收尾寫現況揭露、不硬擊閘
- 碰到 6+ 筆假命中時考慮動手修裁判的 awaiting 識別

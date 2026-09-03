# feedback-高速推進每步跨大-禁越執行越偏細節越耗時

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 推進速度, 跨大步, 過度細節, 越做越細, 耗時, 節奏, 監工節奏, 多階段戰役, 派工粒度, 退修門檻
- Created-at: 2026-08-25
- Related: workflow-parallel-agents, feedback-workflow-discipline, 並行llm即時通訊-inbox機制, feedback-每輪重新校準全盤現況與偏移指標-inbox來回易帶偏風向

## 知識

- [臨] 使用者明令（MudClient 雙 LLM 戰役 2026-08-25）：推進要**高速、每步跨大**，避免「越執行越偏過度細節、越來越耗時」。實證症狀：Phase B 走城曾以 4 步為一段逐段 ack，一天信件 70+ 封，多數是可省的中間回合。
- [臨] **Why**：監工模式下每多一個中間 ack 就多一次往返延遲與 context 稅；細節追查容易自我增生（每個發現都想當場解），目標就飄。**How to apply**：① 派工以整個 Phase 為單位一次講完；② 只在真裁決點（設計否決、紅線、需使用者拍板）才介入，其餘讓執行方自主連跑到 Phase 結束；③ 審查只抓規格違反/紅線/會壞資料，風格小瑕疵放行；④ 新發現先入清單不開支線；⑤ 進度報告攜到 Phase 邊界一次報，等待回合不寫。

## 行動

- 開戰役先定「一個 Phase 一個 session」的邊界目標，派工整包一次給
- 想退修前自問：違規格？踩紅線？會壞資料？三否則放行

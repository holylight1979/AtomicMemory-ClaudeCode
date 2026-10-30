# 並行子代理共用主session的scratchpad-同名暫存檔會互蓋-派工時給每個agent自己的子資料夾

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: scratchpad, 並行 agent, 多開 agent, 派工, 暫存檔互蓋, 檢查腳本
- Created-at: 2026-10-30
- Related: workflow-parallel-agents
- Source: session:bc7c5340#a1b3ef26 2026-10-30

## 知識

- [臨] 主 session 派出的子代理都用同一個 scratchpad 資料夾；兩個 agent 寫同名暫存檔（例 check_anchors.py）會互相蓋掉，後跑的拿到別人的腳本。
- [臨] 派並行 agent 時在 prompt 指定各自的 scratchpad 子資料夾（例 scratchpad/<agent代號>/）。

## 行動

- 同一則派≥ 2 個 agent：每個 prompt 寫明「暫存檔放 scratchpad/<你的代號>/」

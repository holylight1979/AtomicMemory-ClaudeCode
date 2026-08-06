# pan-hermes不移植部件與vscode-text-block不落盤實測

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: PAN, 預告閘門, pre_action_notice, Hermes, 技轉, text_blocks, transcript 不落盤, 翻 deny, lenient_first_miss, continuation 豁免, 偵測率
- Status: warn 軟著陸中，翻 deny 待正樣本
- Created-at: 2026-08-06
- Related: workflow-rules, 跨session資訊失真機制與對策

## 知識

- [臨] Hermes 三部件不移植理由：兩階段狀態機（宣告→執行）— CC 的 deny→同回合重試迴圈原生等價；歷史清除 — CC transcript 由 harness 管理無殘留問題；scaffolding 隔離 — tool pairing 與 code fence 剝除已涵蓋冒充面。重複造這三件只會加狀態面積。
- [臨] 發現 3（實測兩輪）：VSCode 擴充環境「文字+工具」assistant 訊息的 text block 常不落 transcript——Phase 1 五訊息探針見「長文字+工具不落、短文字+工具會落」；Phase 1.5 本 session 更嚴重：整回合多段可見文字（含合格預告）text_blocks:0。同回合快路徑（transcript 掃本 turn 文字）在此環境近乎全盲，PAN 翻 deny 前必須有「獨立短訊息預告可靠落盤」正樣本。
- [臨] 對策落地：mode=warn 軟著陸 + lenient_first_miss=true（deny 模式首 miss 降 warn、第 2 次起 deny）+ deny 文案引導「預告先送獨立短訊息再呼叫工具」；sidechain 豁免維持三層縱深（isSidechain 擷取端跳過 / state 缺 fail-open 保底〔外部專案 session 連環 fail_open_no_transcript 實證〕/ deny 文案 self-healing），不加新訊號。
- [臨] compaction continuation 豁免：probe first_user_head 命中「This session is being continued from a previous conversation」等 harness 續接敘述 → 整回合放行（log exempt_continuation + pass marker）。
- [臨] 觀測缺口：PowerShell 工具不在 _PAN_GATED_TOOLS（Windows 環境 Remove-Item 等寫入動作繞過閘門）——需 PowerShell 唯讀分類器才能納管，暫記待議。

## 行動

- 翻 deny 前：查 Logs/guard-pre-action-notice.jsonl 有無「獨立短訊息預告 → pass」正樣本，無正樣本不翻
- 改 PAN 偵測邏輯前先重讀本 atom 發現 3，勿假設 transcript 同回合文字可靠

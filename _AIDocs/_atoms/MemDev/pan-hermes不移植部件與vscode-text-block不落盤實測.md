# pan-hermes不移植部件與vscode-text-block不落盤實測

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: PAN, 預告閘門, pre_action_notice, Hermes, 技轉, text_blocks, transcript 不落盤, 翻 deny, lenient_first_miss, continuation 豁免, 偵測率, PowerShell 納管
- Status: warn 軟著陸中，翻 deny 待正樣本
- Created-at: 2026-08-06

- Related: workflow-rules, 跨session資訊失真機制與對策

## 知識

- [臨] Hermes 三部件不移植理由：兩階段狀態機（宣告→執行）— CC 的 deny→同回合重試迴圈原生等價；歷史清除 — CC transcript 由 harness 管理無殘留問題；scaffolding 隔離 — tool pairing 與 code fence 剝除已涵蓋冒充面。重複造這三件只會加狀態面積。
- [臨] 實測（兩輪）：VSCode 擴充環境「文字+工具」assistant 訊息的 text block 常不落 transcript——五訊息探針見「長文字+工具不落、短文字+工具會落」；更嚴重樣本：整回合多段可見文字（含合格預告）text_blocks:0。同回合快路徑（transcript 掃本 turn 文字）在此環境近乎全盲，PAN 翻 deny 前必須有「預告可靠落盤」正樣本（判讀規格見 _staging/next-phase-pan-deny.md）。
- [臨] 對策現況：mode=warn + lenient_first_miss=true（deny 模式首 miss 降 warn、第 2 次起 deny）+ deny 文案引導「預告先送獨立短訊息再呼叫工具」；sidechain 豁免三層縱深（isSidechain 擷取端跳過 / state 缺 fail-open 保底 / deny 文案 self-healing），不加新訊號。
- [臨] compaction continuation 豁免：probe first_user_head 命中「This session is being continued from a previous conversation」等 harness 續接敘述 → 整回合放行（log exempt_continuation + pass marker）。
- [臨] PowerShell 已納管（2026-08-06 使用者裁決）：與 Bash 共用白名單前綴分類器（config bash_readonly_prefixes 含唯讀 cmdlet），settings.json PreToolUse matcher 含 PowerShell；未命中白名單/賦值段/here-string 一律保守 gated。閘門定位是保險絲，行為責任（未預告不呼叫）仍在 IDENTITY 契約。

## 行動

- （依知識內容判斷）

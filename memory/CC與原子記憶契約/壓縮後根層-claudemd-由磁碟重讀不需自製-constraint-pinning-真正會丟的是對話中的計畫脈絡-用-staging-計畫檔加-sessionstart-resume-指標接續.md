# 壓縮後根層 CLAUDE.md 由磁碟重讀不需自製 constraint pinning-真正會丟的是對話中的計畫脈絡-用 _staging 計畫檔加 SessionStart resume 指標接續

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: compact, 壓縮失真, constraint pinning, PreCompact, /continue, 接續, next-phase, Guardian:Resume, context 耗盡, 壓縮後接續, CLAUDE.md 重讀, 計畫脈絡遺失
- Created-at: 2026-09-21
- Related: 跨session資訊失真機制與對策

## 知識

- [臨] 外查事實（官方 memory 文件，2026-09-21 查）：Project-root CLAUDE.md 在 /compact 後由磁碟重讀並重新注入；本系統三條硬契約（動手前預告、上GIT、收尾誠實）都在根層 CLAUDE.md @import 的檔裡，因此不需要自製「壓縮後重釘約束」機制——本輪原計畫的 constraint pinning 據此砍掉。
- [臨] 壓縮真正會丟的是對話裡的計畫脈絡（做到哪、哪些決策已拍、哪些不採）。可行解法＝計畫寫成 memory/_staging/next-phase-<主題>-<日期>.md 當單一權威狀態（§ 執行邊界、打勾進度、精確提交清單），SessionStart 在 source=compact|resume 時注入指向最新該檔的 [Guardian:Resume] 提示，壓縮後第一個工具呼叫前先 Read 它。2026-09-21 實跑驗證：壓縮後接續一次到位，沒有重做或漏做。
- [臨] 計畫檔的生命週期：工作完成後沒有收錄價值就刪，有歷史價值搬 _AIDocs/DevHistory/<主題>/；不留在 _staging 佔 resume 指標。

## 行動

- context 剩 <15%：把狀態寫進 _staging/next-phase 檔（進度打勾＋提交清單＋邊界），不靠摘要
- 壓縮後看到 [Guardian:Resume]：先 Read 該檔再動手
- 工作完成：計畫檔刪或搬 DevHistory

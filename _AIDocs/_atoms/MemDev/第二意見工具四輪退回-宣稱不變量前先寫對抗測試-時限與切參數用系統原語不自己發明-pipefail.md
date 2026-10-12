# 第二意見工具四輪退回-宣稱不變量前先寫對抗測試-時限與切參數用系統原語不自己發明-pipefail

- Scope: global
- Author: holylight
- Source: workflow/v6-inbox/from-track-d1/008-trackd1-postmortem-draft.md（track-d1 工作 session 2026-10-08 草稿，總控台 P4 裁決落地）
- Confidence: [臨]
- Trigger: 第二意見工具, second-opinion, 不變量, 對抗測試, CommandLineToArgvW, 切參數, deadline, subprocess timeout, 分塊掃描, 終態保護, pipefail, 修 BLOCK 引入回歸, replay-guard
- Created-at: 2026-10-12

## 知識

- [臨] track-d1（第二意見工具＋候選池）一次交付、四輪被 codex 複審退回、每輪 2～3 條 BLOCK 全成立。根因一：**先宣稱再找證據**——「每個 spawn 點都有 timeout」「拒絕時不改 status」「分塊與整檔等價」都是寫完程式後的自我描述，沒有先寫會紅的反例；審查者每輪就是補那個反例。
- [臨] 根因二：**自己發明演算法取代系統原語**。自寫切參數狀態機吞 token、自寫「分塊＋重疊」加速把跨行樣式切開、在 regex 之間查 deadline 擋不住單一慢呼叫。正解：切參數交 `CommandLineToArgvW`（先 strip 前導空白）、時限把工作搬進子行程用 `subprocess.run(timeout=)`、鎖用 `O_CREAT|O_EXCL`、狀態檔加終態保護且拒絕路徑只回傳不寫檔。非得加速只能在不改變輸入集合的前提下（同一條 regex 抽完整 token 去重）。
- [臨] 根因三：修 BLOCK 時只對退回信的重現字串驗，兩次引入新回歸（吞 token、空 argv[0]）；重現字串只是新增案，既有正例要一起當回歸集跑。根因四：`pytest … | tail` 讓 `&&` 鏈在紅案時照常 commit，驗證鏈要 `set -o pipefail` 或不在 pytest 後接管線。
- [臨] 測「出界」用 pytest tmp 當沙箱時要記得 replay-guard 豁免 `~/AppData` 與 Program Files：出界目標要落在豁免之外（磁碟根或 `C:\outside\…`）。`paths_outside` 對每個絕對路徑逐筆 realpath 不去重，10 MB 文字會跑幾十秒。整段始末與四輪逐條：`_AIDocs/_CHANGELOG_ARCHIVE.md`／`_CHANGELOG.md` 的 v6.0 P1 track-d1 段。

## 行動

- 宣稱任何不變量（一律擋／不會卡住／等價／每個點都有）前，先寫會紅的對抗案再寫實作；信裡每條不變量對應一個案名
- 切參數、路徑正規化、時限、鎖一律用 OS／stdlib 原語，不自寫狀態機或分塊器
- 修 BLOCK 時把既有正例一起跑；驗證鏈 set -o pipefail

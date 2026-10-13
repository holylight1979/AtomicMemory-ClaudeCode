# 回歸測試先證明舊版會紅-把舊版受測檔git-show到暫存夾配新測試跑-紅要紅在斷言不是KeyError

- Scope: global
- Author: holylight
- Source: track-g12 session d8dfd843（閱讀路徑掃描器 6 輪修正，每輪都以舊 commit 轉紅實證）
- Confidence: [臨]
- Trigger: 回歸測試, 舊版會紅, 反證, 修正前紅修正後綠, git show 舊版, 新測試跑舊碼, 測試有沒有測到
- Created-at: 2026-10-13
- Related: 量測工具要把看不到當成獨立狀態-信心度跟著每個數字走-先寫看不到時不能變好的反向測試
- Quote: 「你是 v6.0 的工作 session track-g12（閱讀路徑掃描器），總控台是 claude-ad。第一步用 EnterWorktree 切進 worktree C:\Users\holylight\.claude-wt\track-g12（分支 v6/track-g12，已存在，不要新建）。派工 prompt 在 C:\Users\holylight\.claude\workflow\…」

## 知識

- [臨] 補一個反例的回歸測試，要證明它在修正前會紅，否則可能根本沒測到那個問題。做法：在暫存夾建同樣的目錄結構，用 git show <舊 commit>:<路徑> 把受測的程式檔寫進去，再把「新的」測試檔與 pytest.ini 複製過去跑；測試用自身檔案位置推專案根（parents[N]）時，就會自動載入舊版程式。不必 checkout、不動工作區。
- [臨] 「紅」要紅在斷言（AssertionError，最好帶說明句）才算證明；舊版缺欄位而冒出的 KeyError、StopIteration、ImportError 只說明介面不同，不說明測到了行為。用 --tb=line 看每案的錯誤型別。對抗審查每一輪的反例都這樣做，交付信列「舊版 N 案紅、新版全綠」。
- [臨] 一次跑就全綠的新測試要多疑：可能假專案的形狀剛好繞開問題。先印出實際輸出肉眼對一次，再跑舊版轉紅。
- [臨] 測試用 monkeypatch 把模組層的平台旗標（例：環境變數名是否不分大小寫）兩向都設一次，守不住「預設值」本身：把預設寫死成錯的值，測試照綠，只有跑在真平台上的整合探針會紅。反證時要另外退回預設值；守法是加一案不經 monkeypatch、直接斷言預設等於平台判斷（例 `FLAG == (os.name == "nt")`）。

## 行動

- 每筆反例修正先寫測試、跑舊版確認紅在斷言，再修；交付信附舊版紅的案數
- 舊版紅的是 KeyError／StopIteration 時，補一個會紅在斷言的寫法

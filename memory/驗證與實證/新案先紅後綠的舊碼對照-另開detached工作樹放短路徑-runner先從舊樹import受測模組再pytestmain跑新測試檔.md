# 新案先紅後綠的舊碼對照-另開detached工作樹放短路徑-runner先從舊樹import受測模組再pytest.main跑新測試檔

- Scope: global
- Author: holylight
- Source: session e4639f31 2026-10-15（判斷入口盤點階段 3）
- Confidence: [臨]
- Trigger: 先紅後綠, 舊碼紅, 退回舊碼看紅, red then green, 舊碼對照, 新案在舊碼上跑, detached worktree, sys.modules, pytest.main
- Created-at: 2026-10-15
- Quote: 「你是 v6.0 推進 session，讀 C:\Users\holylight\.claude\memory\_staging\next-phase-v6.0-寫程式碼的進化.md，照「推進的依據與方式」開工。」

## 知識

- [臨] 要證明新寫的案例在舊碼上會紅，又不想動自己正在改的樹（退回舊碼會被當成改碼、作廢收據）：`git worktree add --detach <短路徑> <基底 commit>` 開一棵舊碼樹，寫一支 runner：先把舊樹的 hooks／lib 插到 sys.path 最前、`import` 受測模組（含 `from handlers import stop` 這類）放進 sys.modules，再 `pytest.main([...新測試檔…])`。測試檔匯入時插的新樹路徑拿不到新碼，因為模組已快取；函式內延遲 import 也吃快取。跑完 `git worktree remove`。
- [臨] 判讀：新行為的案例在舊碼紅、新碼綠；反例（舊碼本來就放行／本來就擋的那面）兩邊都綠是正常的。要看紅的原因對不對（例：主案舊碼是 `assert None`＝舊碼沒擋），不是只數紅幾條。
- [臨] 兩個坑：工作樹放在系統 Temp 下的長路徑（含很長的中文檔名）`git worktree add` 會失敗 `Could not reset index file`（Windows 路徑過長），放到 repo 旁邊的短路徑（例 `../<repo>-wt/<名>`）；runner 用 `python -B` 跑，免得在舊樹寫 __pycache__。

## 行動

- 證明新案先紅：detached 工作樹＋先 import 舊模組的 runner，不在自己的工作樹退回舊碼
- 工作樹放短路徑，跑完就 git worktree remove

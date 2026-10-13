# 自寫靜態解析器的語言陷阱-Python名字綁定與型別標註-C#抹字串會讓引數錯位-無BOM的UTF-16能被嚴格UTF-8解開

- Scope: global
- Author: holylight
- Source: track-g12 session d8dfd843（閱讀路徑掃描器 Python ast／C# 正規式解析層，codex 初審反例與實跑）
- Confidence: [臨]
- Trigger: 靜態分析, 呼叫圖, ast 解析, 名字綁定, 型別標註 Union, C# 正規式解析, 引數位置錯位, UTF-16 無 BOM, NUL 位元組, BOM SyntaxError
- Created-at: 2026-10-13
- Related: 量測工具要把看不到當成獨立狀態-信心度跟著每個數字走-先寫看不到時不能變好的反向測試
- Quote: 「你是 v6.0 的工作 session track-g12（閱讀路徑掃描器），總控台是 claude-ad。第一步用 EnterWorktree 切進 worktree C:\Users\holylight\.claude-wt\track-g12（分支 v6/track-g12，已存在，不要新建）。派工 prompt 在 C:\Users\holylight\.claude\workflow\…」

## 知識

- [臨] Python 名字綁定：函式內任何位置指定一個名字，整個函式裡它就是區域變數（會遮住同名模組函式）；巢狀 def、import、for 目標都是一次綁定；只有型別宣告沒給值的 `x: T` 不是綁定；模組層 `from a import f` 後又 `f = …`、try/except 的 fallback、函式裡 `global f` 再指定，都是重新綁定，不能沿用第一個綁定當目標。
- [臨] Python 型別標註取類別：只有 Optional[X]、X | None 能剝成 X；Union[A, B]、A | B 兩個以上非 None 成員就是型別不定；list[X] 是容器不是 X；`w: Base = Child()` 實際型別看右邊建構的那個；方法裡的 `self.x: T = v` 是欄位宣告（AnnAssign 的目標是 Attribute）。
- [臨] C# 用正規式解析前會把字串、註解抹成等長空白（行號不跑）；之後依逗號切引數時若丟掉空片段，字串引數後面的位置全部錯位，切逗號要保留空片段。插值字串 $"…{expr}…" 要留下大括號裡的運算式（括號本身仍抹掉，免得打亂配對）。委派 `cb += B`、`cb -= A` 是修改；ref／out 傳出去的變數呼叫後可能被換。
- [臨] 讀原始碼檔：Python `ast.parse` 遇到開頭是 U+FEFF 的字串會 SyntaxError（用 utf-8-sig 解碼）；無 BOM 的 UTF-16 LE/BE（ASCII 字元間夾 NUL）能被嚴格 UTF-8 解開成含 NUL 的字串、不報錯，所以不能「先嚴格 UTF-8」。先看前 4KB 奇／偶位置的 NUL 比例判 UTF-16 LE／BE，有 NUL 卻判不出就列解析失敗，不靜默收亂碼。

## 行動

- 寫或審靜態解析器：名字解析前先問「這個名字在它的作用域裡被綁定幾次」
- 解碼原始碼檔先看 BOM，再看 NUL 分布，最後才嚴格 UTF-8；解不開就報錯

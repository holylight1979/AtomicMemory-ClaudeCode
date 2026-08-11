# Windows Python write_text 缺 newline 把 LF 翻 CRLF 整檔假 diff

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: write_text, newline, CRLF, LF, EOL, 換行, phantom diff, 整檔假 diff, 一位改動整檔 diff, os.linesep, 檔案改寫工具, 換行翻轉, marker 同步, read_text universal newline, git diff 整檔
- Created-at: 2026-07-01
- Related: toolchain

## 知識

- [臨] Python `Path.write_text(s, encoding=...)` 在 Windows 預設 `newline=None` → 把 s 內的 `\n` 轉成 `os.linesep`(`\r\n`)。原檔若為 LF、工具只改 1 字（如 marker 數字），整檔被改寫成 CRLF → git 視為**整檔 diff**。實例：`tools/skill-index.py` 改 1 個 `<!-- skill-count -->` 數字 → `TECH.md` 冒出 1488 行假 diff（`git diff --ignore-cr-at-eol` 後只剩 4 行真差異）。
- [臨] **偵測盲點**：`read_text()` 做 universal-newline translation（CRLF→`\n`），所以「讀回字串比對」的 idempotency / `--check` 邏輯**看不到** EOL drift（字串相等），工具自身檢查抓不到 → 只能靠 `git show --stat` 行數異常、或 `git diff --ignore-cr-at-eol` 察覺。
- [臨] **根治**：改寫檔的工具一律 `write_text(..., newline="\n")`（或 `open(..., newline="")`）強制 LF，對齊 repo（無 .gitattributes）的 LF 慣例。已修 `tools/skill-index.py:127,138`（2 處 write_text）。同類風險：任何用 write_text 只改局部卻回寫整檔的同步/生成工具。
- [臨] **`encoding='utf-8-sig'` 寫入會額外補 BOM**——行尾之外的第二個靜默污染源。原檔無 BOM 時，diff 第一行會多一條「+<原標題>」且看似無變化。讀 BOM 檔可用 utf-8-sig，**寫回去要用 utf-8 並自己控 BOM**。
- [臨] **同一工作區內行尾可能不一致，不能依專案慣例推論**：實例（c:/Projects）——`_AIDocs` 的 .md 是 **LF**，同工作區 `sgi_server` 的 SVN 原始碼全是 **CRLF**。改之前先量該檔本身。
- [臨] **偵測與對比手法**：`d=open(p,'rb').read()` → `d.count(b'\r\n')` / `d.count(b'\n')-d.count(b'\r\n')` / `d.startswith(b'\xef\xbb\xbf')`。與版控基準對比：`git show <rev>:<path>` 或 `svn cat -r BASE <path>` 同法統計。⚠ **SVN 新增檔（A 狀態）`svn cat -r BASE` 回空，會被誤判成「行尾被改」——排除它再下結論**。
- [臨] **修法**：`open(p,'rb')` 讀 → `d.replace(b'\r\n', b'\n')`（或反向）、`if d.startswith(b'\xef\xbb\xbf'): d = d[3:]` → `open(p,'wb').write(d)`。修完以 `git diff --stat <出事前的 rev>` 驗證差異是否收斂到真實改動行數。
- [臨] **批次改多檔後要逐檔比行尾**，別只檢查自己記得的那幾個——一次 Python 批次改動可能同時污染十幾個檔，漏檢的會在上版時整檔爆 diff。
- [臨] 反向變體（CRLF→LF）：`io.open(p).read()` 預設 text mode 做 universal newline 轉換（\r\n → \n 進記憶體），再以 `newline=''` 寫回時寫出 LF——整檔行尾靜默被改。git diff 因正規化顯示無差異但工作樹位元組已變（症狀：`LF will be replaced by CRLF` warning）。2026-08-10 Proj-JARVIS ST.0 對 WPF csproj 做 controlled mutation 還原時踩到；解法：讀寫兩端都 `newline=''`，或用 Edit tool；內容與 HEAD 無差異時 `git checkout -- <file>` 最乾淨還原位元組。

## 行動

- 寫 .md/.json/config 的同步或生成工具 → write 端顯式 `newline="\n"`
- code review 見「1 行邏輯改動卻整檔 diff」→ 先疑 EOL flip：`git diff --ignore-cr-at-eol` 看真實差異、`git show --stat` 看真實行數
- commit 前用 `git show --stat` 掃行數異常，phantom EOL diff 不進版控

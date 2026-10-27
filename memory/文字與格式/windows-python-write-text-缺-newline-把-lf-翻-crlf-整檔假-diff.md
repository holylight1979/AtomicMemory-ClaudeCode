# windows-python-write-text-缺-newline-把-lf-翻-crlf-整檔假-diff

- Scope: global
- Author: holylight
- Source: commit:534bf6c 2026-07-01（原對話已逾保留期）；2026-10-22 chain-breaker 實測；分支 inject-budget e096049f
- Confidence: [臨]
- Trigger: write_text, newline, CRLF, LF, EOL, 換行, phantom diff, 整檔假 diff, 一位改動整檔 diff, os.linesep, 檔案改寫工具, 換行翻轉, marker 同步, read_text universal newline, git diff 整檔, 查 CRLF, git ls-files --eol, grep -c 假數字, 解合併衝突腳本
- Created-at: 2026-07-01
- Related: toolchain, bash-heredoc-會折掉一層反斜線-精確字串比對靜默失敗

## 知識

- [臨] Python `Path.write_text(s, encoding=...)` 在 Windows 預設 `newline=None` → 把 s 內的 `\n` 轉成 `os.linesep`(`\r\n`)。原檔若為 LF、工具只改 1 字（如 marker 數字），整檔被改寫成 CRLF → git 視為**整檔 diff**。實例：`tools/skill-index.py` 改 1 個 `<!-- skill-count -->` 數字 → `TECH.md` 冒出 1488 行假 diff（真差異只有 4 行）。
- [臨] **偵測盲點**：`read_text()` 做 universal-newline translation（CRLF→`\n`），讀回字串比對的 idempotency／`--check` 看不到 EOL drift（字串相等），工具自身檢查抓不到，只能靠 `git show --stat` 行數異常或 `git diff --ignore-cr-at-eol` 察覺。
- [臨] **根治**：改寫檔的工具一律 `write_text(..., newline="\n")`（或 `open(..., newline="")`）強制 LF；~/.claude 全 repo 釘 LF，寫檔用 newline="\n"／write_text_lf，守衛 verify_lf_writes.py。同類風險：任何只改局部卻回寫整檔的同步/生成工具，以及解合併衝突這類一次性腳本。
- [臨] 實例：解合併衝突用 read_text／write_text 重寫 1,636 行的 md，工作檔整檔變 CRLF；commit 被 .gitattributes 正規成 LF、提交無誤，只留工作檔假 M。
- [臨] **`encoding='utf-8-sig'` 寫入會額外補 BOM**——行尾之外第二個靜默污染源；原檔無 BOM 時 diff 第一行多一條看似無變化的「+<原標題>」。讀 BOM 檔可用 utf-8-sig，寫回用 utf-8 並自己控 BOM。
- [臨] **同一工作區內行尾可能不一致，不能依專案慣例推論**：例：同一工作區的 .md 是 LF、某專案的 SVN 原始碼全是 CRLF；改之前先量該檔本身。
- [臨] **偵測與對比**：`d=open(p,'rb').read()` → `d.count(b'\r\n')`／`d.count(b'\n')-d.count(b'\r\n')`／`d.startswith(b'\xef\xbb\xbf')`，或 `git ls-files --eol`；Git Bash 裡 `grep -c $'\r'` 會把每一行都算進去，數字是假的。與版控基準比：`git show <rev>:<path>` 或 `svn cat -r BASE <path>` 同法統計；⚠ SVN 新增檔（A 狀態）`svn cat -r BASE` 回空，會被誤判成「行尾被改」，先排除再下結論。
- [臨] **修法**：`open(p,'rb')` 讀 → `d.replace(b'\r\n', b'\n')`（或反向）、有 BOM 就 `d = d[3:]` → `open(p,'wb').write(d)`；修完以 `git diff --stat <出事前的 rev>` 驗差異收斂到真實改動行數。批次改多檔後逐檔比行尾，別只查記得的那幾個（一次批次可能污染十幾個檔）。
- [臨] 反向變體（CRLF→LF）：`io.open(p).read()` 預設 text mode 把 \r\n 轉 \n 進記憶體，再以 `newline=''` 寫回就寫出 LF，整檔行尾靜默被改；git diff 因正規化顯示無差異但工作樹位元組已變（症狀：`LF will be replaced by CRLF` warning）。解法：讀寫兩端都 `newline=''` 或用 Edit tool；內容與 HEAD 無差異時 `git checkout -- <file>` 最乾淨還原位元組。
- [臨] 測試也中：文字模式 `open(p,'w')` 原樣重寫 LF 檔，Windows 寫成 CRLF、內容其實變了；測「原樣重寫內容沒變」的案例要加 `newline=''`。

## 行動

- 寫 .md/.json/config 的同步或生成工具 → write 端顯式 `newline="\n"`
- code review 見「1 行邏輯改動卻整檔 diff」→ 先疑 EOL flip：`git diff --ignore-cr-at-eol` 看真實差異、`git show --stat` 看真實行數
- commit 前用 `git show --stat` 掃行數異常，phantom EOL diff 不進版控

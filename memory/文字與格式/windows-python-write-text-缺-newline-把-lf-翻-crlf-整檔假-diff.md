# windows-python-write-text-缺-newline-把-lf-翻-crlf-整檔假-diff

- Scope: global
- Author: holylight
- Source: commit:534bf6c 2026-07-01（原對話已逾保留期）；2026-10-22 chain-breaker 實測；分支 inject-budget e096049f
- Confidence: [臨]
- Trigger: write_text, newline, CRLF, LF, EOL, 換行, phantom diff, 整檔假 diff, 一位改動整檔 diff, os.linesep, 檔案改寫工具, 換行翻轉, marker 同步, read_text universal newline, git diff 整檔, 查 CRLF, git ls-files --eol, grep -c 假數字, 解合併衝突腳本, git status 一直顯示 M, index 時間戳
- Created-at: 2026-07-01
- Related: toolchain, bash-heredoc-會折掉一層反斜線-精確字串比對靜默失敗

## 知識

- [臨] Windows 上 `Path.write_text(s, encoding=...)` 預設 `newline=None`，把 `\n` 寫成 `os.linesep`(`\r\n`)；原檔 LF、工具只改 1 字（如 marker 數字）也整檔變 CRLF → git **整檔 diff**。實例：`tools/skill-index.py` 改 1 個 skill-count 數字，`TECH.md` 冒出 1488 行假 diff（真差異 4 行）。
- [臨] **偵測盲點**：`read_text()` 會把 CRLF 轉回 `\n`，讀回比對的 idempotency／`--check` 看不到行尾變化，只能靠 `git show --stat` 行數異常或 `git diff --ignore-cr-at-eol` 察覺。
- [臨] **根治**：改寫檔的工具一律 `write_text(..., newline="\n")`（或 `open(..., newline="")`）；~/.claude 全 repo 釘 LF，寫檔用 newline="\n"／write_text_lf，守衛 verify_lf_writes.py。同類風險：只改局部卻回寫整檔的同步/生成工具、解合併衝突這類一次性腳本。
- [臨] 工作檔假 M 兩例：① 解合併衝突用 read_text／write_text 重寫 1,636 行的 md，工作檔整檔變 CRLF，commit 被 .gitattributes 正規成 LF、提交無誤；② git 照 .gitattributes 存的已是 LF、git diff 為空，status 仍一直顯示 M（index 記的時間戳舊了），對那支檔再 `git add` 一次讓 index 重記才清。
- [臨] **`encoding='utf-8-sig'` 寫入會補 BOM**——行尾之外第二個靜默污染源；原檔無 BOM 時 diff 第一行多一條看似無變化的「+<原標題>」。讀可用 utf-8-sig，寫回用 utf-8 自己控 BOM。
- [臨] **同一工作區行尾可能不一致**（.md 是 LF、某專案 SVN 原始碼全 CRLF），不能依慣例推論，改前先量該檔。
- [臨] **偵測與對比**：`d=open(p,'rb').read()` 算 `d.count(b'\r\n')`／`d.count(b'\n')-d.count(b'\r\n')`／`d.startswith(b'\xef\xbb\xbf')`，或 `git ls-files --eol`；Git Bash 的 `grep -c $'\r'` 每行都算，數字是假的。與基準比：`git show <rev>:<path>` 或 `svn cat -r BASE <path>` 同法統計；⚠ SVN 新增檔（A）`svn cat -r BASE` 回空，會誤判成行尾被改，先排除。
- [臨] **修法**：`open(p,'rb')` 讀 → `d.replace(b'\r\n', b'\n')`（或反向）、有 BOM 就 `d = d[3:]` → `open(p,'wb').write(d)`；修完 `git diff --stat <出事前的 rev>` 驗差異收斂到真實行數。批次改多檔後逐檔比行尾（一次批次可能污染十幾個檔）。
- [臨] 反向變體（CRLF→LF）：`io.open(p).read()` 文字模式把 \r\n 轉 \n，再以 `newline=''` 寫回就寫成 LF；git diff 因正規化無差異但位元組已變（症狀：`LF will be replaced by CRLF` warning）。讀寫兩端都 `newline=''` 或用 Edit；內容與 HEAD 無差時 `git checkout -- <file>` 還原位元組。
- [臨] 測試也中：文字模式 `open(p,'w')` 原樣重寫 LF 檔，Windows 寫成 CRLF；測「原樣重寫內容沒變」要加 `newline=''`。

## 行動

- 寫 .md/.json/config 的同步或生成工具 → write 端顯式 `newline="\n"`
- code review 見「1 行邏輯改動卻整檔 diff」→ 先疑 EOL flip：`git diff --ignore-cr-at-eol` 看真實差異、`git show --stat` 看真實行數
- commit 前用 `git show --stat` 掃行數異常，phantom EOL diff 不進版控

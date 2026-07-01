# Windows Python write_text 缺 newline 把 LF 翻 CRLF 整檔假 diff

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: write_text, newline, CRLF, LF, EOL, 換行, phantom diff, 整檔假 diff, 一位改動整檔 diff, os.linesep, 檔案改寫工具, 換行翻轉, marker 同步, read_text universal newline, git diff 整檔
- Created-at: 2026-07-01
- Related: toolchain, skill-計數單一來源-skill-index

## 知識

- [臨] Python `Path.write_text(s, encoding=...)` 在 Windows 預設 `newline=None` → 把 s 內的 `\n` 轉成 `os.linesep`(`\r\n`)。原檔若為 LF、工具只改 1 字（如 marker 數字），整檔被改寫成 CRLF → git 視為**整檔 diff**。實例：`tools/skill-index.py` 改 1 個 `<!-- skill-count -->` 數字 → `TECH.md` 冒出 1488 行假 diff（`git diff --ignore-cr-at-eol` 後只剩 4 行真差異）。
- [臨] **偵測盲點**：`read_text()` 做 universal-newline translation（CRLF→`\n`），所以「讀回字串比對」的 idempotency / `--check` 邏輯**看不到** EOL drift（字串相等），工具自身檢查抓不到 → 只能靠 `git show --stat` 行數異常、或 `git diff --ignore-cr-at-eol` 察覺。
- [臨] **根治**：改寫檔的工具一律 `write_text(..., newline="\n")`（或 `open(..., newline="")`）強制 LF，對齊 repo（無 .gitattributes）的 LF 慣例。已修 `tools/skill-index.py:127,138`（2 處 write_text）。同類風險：任何用 write_text 只改局部卻回寫整檔的同步/生成工具。

## 行動

- 寫 .md/.json/config 的同步或生成工具 → write 端顯式 `newline="\n"`
- code review 見「1 行邏輯改動卻整檔 diff」→ 先疑 EOL flip：`git diff --ignore-cr-at-eol` 看真實差異、`git show --stat` 看真實行數
- commit 前用 `git show --stat` 掃行數異常，phantom EOL diff 不進版控

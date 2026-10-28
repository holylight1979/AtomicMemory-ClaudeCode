# 第二意見材料是工作樹對HEAD-沒差才取main...HEAD-未追蹤檔也打包-分段commit的工作要先commit乾淨再送-暫存腳本移出repo

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: second_opinion_start, 第二意見 材料, collect_diff, pack.py, main...HEAD, 未追蹤檔打包, 分段 commit 送審, diff 為空
- Created-at: 2026-10-27
- Depends: path:~/.claude/tools/second-opinion/pack.py
- Related: 第二意見工具不適合拿來判大份材料-mcp入口只收cwd的diff帳本與目標樹且全文嵌進提示詞-判分改直接codex-exec讓它讀檔
- Supersedes: 第二意見材料只看git-diff不含未追蹤新檔-送審前先git-add-n新檔否則codex看不到新模組, 第二意見要在commit前送-已commit時工作樹diff為空-codex只拿到摘要判證據不足指不出缺陷
- Source: session:17c8cd5c 2026-10-27

## 知識

- [臨] tools/second-opinion/pack.py 的 collect_diff 組材料：先取 `git diff HEAD`（工作樹對 HEAD）；這段是空的才改取 `git diff main...HEAD`（分支從 main 分出後的全部 commit）；另把 `git ls-files --others --exclude-standard` 列出的未追蹤檔接成 new file 段一起送。
- [臨] 坑：分段 commit 的工作只要工作樹還留一點改動，codex 只看到那一點，前面已 commit 的段看不到；在 main 上全部 commit 完則兩段都空。repo 裡未追蹤的暫存腳本、量測輸出也會被打包進材料。

## 行動

- 要 codex 看整條分支：在分支上把改動全 commit 乾淨（git diff HEAD 為空）再送
- 送審前把暫存腳本、量測輸出移出 repo，git status 不留無關的 ??

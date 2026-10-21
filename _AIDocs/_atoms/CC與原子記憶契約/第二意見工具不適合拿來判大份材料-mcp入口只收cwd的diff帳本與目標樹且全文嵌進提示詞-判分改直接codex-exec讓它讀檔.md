# 第二意見工具不適合拿來判大份材料-MCP入口只收cwd的diff帳本與目標樹且全文嵌進提示詞-判分改直接codex-exec讓它讀檔

- Scope: global
- Author: holylight
- Source: session 26d36367 track-wave2-kit 派工 004（判分備料讀 run.py／pack.py）
- Confidence: [臨]
- Trigger: second_opinion_start, 第二意見, codex 判分, codex exec, 判分材料, 材料太大, pack.gather_items, 獨立判分
- Created-at: 2026-10-21

## 知識

- [臨] tools/second-opinion 的 pack.gather_items 把材料（部位卡、病灶文件、cwd 的 diff、本 session 驗證帳本尾段、目標樹、附加檔）全文嵌進提示詞並複製進 job 目錄；MCP 的 second_opinion_start 不能另指材料檔，只收 cwd、part、question。被 .gitignore 排除的檔（例：派工信箱）不在 diff，送不進去。
- [臨] 所以幾 MB 的判分材料（transcript、log）不走它：直接 `codex exec -C <材料目錄> --sandbox read-only --skip-git-repo-check -o <輸出檔> - < <prompt 檔>`，讓 Codex 自己讀檔。second_opinion 適合的是「本 session 改動＋收據有沒有撐住宣稱」這種小材料的階段審。

## 行動

- 要 Codex 判一大批檔：寫 prompt 檔＋codex exec 唯讀跑，不用 second_opinion
- 第二意見閘要求時：題目照 stage-review 本意問收據有沒有撐住宣稱，交付在 gitignore 路徑就在題目裡寫明

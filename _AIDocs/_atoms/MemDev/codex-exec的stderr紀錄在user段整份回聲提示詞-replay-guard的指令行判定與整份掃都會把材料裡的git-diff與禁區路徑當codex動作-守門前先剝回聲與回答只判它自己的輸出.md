# codex-exec的stderr紀錄在user段整份回聲提示詞-replay-guard的指令行判定與整份掃都會把材料裡的git-diff與禁區路徑當codex動作-守門前先剝回聲與回答只判它自己的輸出

- Scope: global
- Author: holylight
- Source: session:cb4c9c8e 2026-10-21 job 20261021-092745-cb4c9c8e-stage-review；track-g9-post-guard-echo 001 實測
- Confidence: [臨]
- Trigger: codex exec stderr, 提示詞回聲, replay-guard post, command_lines, 無指令行但整份紀錄命中, 第二意見 failed, second_opinion_result failed, _AIDocs/_atoms 命中, git diff 命中, strip_prompt_echo
- Created-at: 2026-10-21
- Depends: path:C:/Users/holylight/.claude/tools/second-opinion/run.py, path:C:/Users/holylight/.claude/tools/replay-guard.py
- Quote: 「接著也可派工，checklist 文件需要更新 (我要看最新進度狀態)，完工的項目如果不必留在文件內，可以搬去DevHistory或者刪除。並且請你給我白話說明最新狀況(不要技術細節臭味兒)。」

## 知識

- [臨] codex exec 的 stderr 紀錄會在 header 之後的 `user` 段把整份提示詞（含材料全文：驗證帳本尾段、diff、卡片）回聲一次。tools/replay-guard.py 的 post 主路徑 `command_lines` 只要行含 `-Command`、`exec_command` 或行首「$ 」就當指令行，退路（沒指令行時）則整份 stderr＋stdout 掃禁區樣式——兩條路都會把我方材料裡的 `git diff`、`_AIDocs/_atoms`、`pwsh -Command` 當成 codex 自己的動作，改過檔的 session 跑第二意見就一律 failed。
- [臨] 正解是在 run.py 的 post_guard 先把提示詞回聲（prompt.md 全文精確子字串）與 codex 的回答全文（reply.raw.md）從紀錄剥掉，寫成 codex 自己的輸出檔再交 guard 與退路掃；守的是動作（exec 痕跡、出界路徑）不是敘述。不要反過來把材料遮掉禁字樣（帳本是給它看的證據）。驗證法：用帶禁區字樣、沒指令行的材料真打一次看 status done。
- [臨] codex exec 0.154 的 stderr 三段都不是 codex 的動作：檔頭固定印一行沙箱模式（探針 `sandbox: read-only`、Companion 裁判 `sandbox: danger-full-access`）；user 段逐字回聲整份提示詞；codex 段最後印回答全文（＝reply.raw.md，也是 stdout）。裸字 sandbox 不是失敗訊號；失敗分類只認 CreateProcessWithLogon／1385 或同行 sandbox＋error|denied|failed。
- [臨] replay-guard post 的 command_lines 把含 -Command、exec_command 或行首「$ 」的行當指令行，回聲裡的材料行（帳本的 pwsh -Command "git diff …"、diff 上下文）也被挑進去：帶禁區字樣 → 誤判 FAIL；不帶 → 靠它判 PASS 跳過退路。解法是交給 guard 的改成剥完回聲與回答的 codex.stderr.own.log，guard 本身一字不動（實證：同一份紀錄原始交 guard 是 FAIL、own log 判 done）。

## 行動

- 第二意見回 failed 先 cat job 目錄的 execute.log 與 guard.post.log：理由帶「無指令行但整份紀錄命中」或命中的字樣在 prompt.md 裡找得到 → 是回聲不是 codex 讀出界
- 改 replay-guard 類守門前先答：它掃的文字裡有沒有我方給的材料

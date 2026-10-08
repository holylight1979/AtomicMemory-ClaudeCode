# second-opinion：第二意見工具（M3）

白話：讓另一家模型（Codex）拿**同一份材料**、**看不到我方答案**、各自回答；它起不來就老實回 `failed`，絕不把「沒跑」報成功。
對應目標 G1（多立場視角）、G9（兩家模型等價認知）、Q9 題組（材料雜湊相同；答案互不可見；啟動不了卻回報成功是反例）。

## 兩個 MCP 工具

| 工具 | 參數 | 回什麼 |
|---|---|---|
| `second_opinion_start` | `kind: diagnose\|evaluate\|stage-review`、`part`、`cwd`、`mode: independent\|review`、`question`、`draft?`（只有 review 收）、`sealed?: string[]` | 20 秒內回三行 `job_id: …` / `hash: …` / `status: started\|blocked\|failed`；非 started 一律 isError |
| `second_opinion_result` | `job_id` | `status: running\|done\|failed\|blocked`；done 時附三段「結論／證據／反例或未解」，超 20KB 截斷並附完整路徑 |

`independent` 帶 `draft` 直接拒（js 層就拒，不 spawn）；`review` 缺 `draft` 也拒。

## 流程（`run.py`）

```
prepare  打包材料 → manifest.hash → prompt.md → replay-guard pre（非 PASS → blocked，不 spawn codex）
execute  探針 codex exec --skip-git-repo-check -s read-only -m <slug> "Reply CODEX_OK"（逾時 20 s／1385／沒回 → failed，不退 claude）
         → codex exec -m <slug> -s read-only -C <job_dir> --ephemeral --skip-git-repo-check -o reply.raw.md -  （stdin=prompt.md；逾時 300 s kill）
         → replay-guard post --log codex.stderr.log（FAIL → failed）
         → parse_three_sections（缺段 → failed）→ reply.md → done
```

job 目錄 `~/.claude/workflow/second-opinion/<yyyymmdd-HHMMSS>-<sid8>-<kind>/`：
`request.json` `materials/` `manifest.json` `prompt.md` `codex.stderr.log` `reply.raw.md` `reply.md` `status.json`

| 其他檔 | 誰寫 | 是什麼 |
|---|---|---|
| `codex.stdout.log`、`probe.stdout.log`、`probe.stderr.log`、`guard.pre.log`、`guard.post.log` | py | 子程序輸出與 guard 原文（除錯用） |
| `execute.log` | **MCP（js）建立**，子程序 stdout/stderr 導向進去 | 不是 state、不是 job 結果；`run.py execute` 自己的 print 與 traceback 落這裡 |
| `execute.lock` | py，`O_CREAT\|O_EXCL` | 同一 job 只允許一個 executor；第二個 execute 直接拒。不自動清。**要重跑一律重新 `second_opinion_start`（prepare 建新 job）**，刪 lock 沒用：非 started 的 job 會被狀態檢查擋 |

status.json 的終態（done／failed／blocked）之間不可互蓋：之後寫**不同**狀態的 `write_status` 不寫檔、回現況並附 `rejected_write`；寫**同一**終態可補欄位（後寫者贏）。非 started 的 job 再被 execute：只回傳、不寫檔，原始 reason 與 updated_at 原樣保留。execute 全程 try/except，任何啟動／IO 例外都寫 `failed`（stage 記當時階段）；連 status.json 都寫不進去時 stderr 留痕並回記憶體狀態，此時磁碟可能仍是 running，由 `second_opinion_result` 逾時規則報 failed。被硬殺的 executor（status 留 running）：`second_opinion_result` 逾 timeout_s＋90 s 回 failed 並指向 execute.log，status.json 不會被改。
封存關鍵字放 `<job_root>/_sealed/<job_id>.txt`，不放 job 目錄裡。`draft` 空字串或全空白視為「沒帶」（independent 放行、review 拒）。
js 端 `crashLog` 是既有 `lib/log.js` 的函式，寫 `~/.claude/workflow/guardian-crash.log`（gitignored）；只在 spawn 本身失敗時用。

## 材料與雜湊（`pack.py`）

材料固定檔名：`card.md`（部位卡，從 `<root>/.claude/overview-map.md` 找）、`defects.md`（病灶文件前 N 節，預設 5）、`diff.patch`（`git diff HEAD` → `main...HEAD` → `svn diff`）、`ledger.jsonl`（`<root>/.claude/verify/_ledger.jsonl` 尾 20 行）、`draft.md`（只有 review）。
雜湊：每檔內容統一 LF 後 sha256；files 依相對路徑排序；總雜湊 = sha256(逐檔 `rel\nsha\n`)。所以 CRLF／LF、餵入順序都不影響 hash；`mode`、`model`、`built_at` 不進雜湊（同材料兩種視角同 hash）。manifest 只記相對路徑。

## 模型名

一律經 `lib/codex_models.resolve_slug` **精確比對** `~/.codex/models_cache.json`（`judge_backend.resolve_model_slug`）。`second_opinion.model` 預設 `gpt-6-astra`；`gpt-6-astra-900K` 這種帶後綴的名字查不到就是錯，不猜。

## config（`workflow/config.json` 的 `second_opinion` 段，由總控台加）

```json
"second_opinion": {
  "model": "gpt-6-astra",
  "probe_timeout_s": 20,
  "timeout_s": 300,
  "defects_top_n": 5,
  "ledger_tail": 20,
  "material_max_chars": 40000
}
```
`allow_claude_fallback` 固定 false，config 寫了也不理。codex 執行檔與 `codex_extra_args` 沿用 `codex_companion` 段。

## 保留裁決（總控台審）

`replay-guard post` 在紀錄裡找不到任何指令行時回 FAIL「無法判定」。codex 若純推理（材料已全文內嵌）就會這樣。本工具只在**這一種** FAIL 時，改以 guard 自己的禁區樣式與出界路徑規則掃**整檔**（不切、不截）的 stderr＋stdout；兩檔合計超過 20 MB 直接 failed「紀錄過大無法判定」；掃描跑在**子行程**（`run.py scan --job <dir>`，印 JSON＋尾行 `SCAN_CHECK PASS|FAIL`），`subprocess.run(timeout=30)` 逾時 kill → failed「掃描逾時無法判定」，子行程異常或輸出壞掉也 failed；唯一加速是路徑 token 以 guard 同一條 regex 抽出、保留完整 token 去重後再逐筆判定（與餵全文等價）；全乾淨才算 PASS 並在 status 留 `guard_note`；有任何命中仍 failed。其他 FAIL 一律 failed。總控台裁決：接受（條件＝整檔掃描＋過大即 failed，已做）。

## 驗證

`python -X utf8 -m pytest -q tools/codex-companion/verify/verify_second_opinion.py`（subprocess 全 monkeypatch，不打 codex）。真打 codex 的探針由總控台 merge 後做：`python tools/second-opinion/run.py probe`。

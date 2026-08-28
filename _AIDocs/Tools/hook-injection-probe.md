# Hook 注入實機探針 — 用真 hook 進程驗證 atom 注入效果

> 離線測試（`run_verify` 那批 pytest）只證明**邏輯**：函式給什麼回什麼。注入效果——這一輪到底裝進幾顆 atom、幾顆被降級、預算有沒有用滿——只有把 `hooks/workflow-guardian.py` 當真正的 hook 進程跑起來才看得到。改過 `wg_core.TURN_BUDGET_LIMIT`、`compute_token_budget`、`_truncate_context_by_activation`、`ups_inject` 主迴圈任何一處，都用本文的探針驗一次再收工。

---

## 做法

1. 以 python 子程序執行 `hooks/workflow-guardian.py`（settings.json 用 `pythonw.exe -c "runpy.run_path(...)"` 起它；探針直接 `python.exe hooks/workflow-guardian.py` 等價，且能看到 stderr）。
2. stdin 餵一行 JSON：`{"session_id", "transcript_path": "", "cwd", "hook_event_name", "prompt" 或 "source"}`。
3. **每個假 session 先送 `SessionStart`（`source: "startup"`）再送 `UserPromptSubmit`**。漏送 SessionStart 是最常見的探針失敗原因（見「陷阱」）。
4. 解析 stdout 的 JSON，取 `hookSpecificOutput.additionalContext`，那就是模型看到的注入文字。
5. 短／中／長 prompt 各跑 **≥2 次**，取最差值判讀。

## 要統計的標記

注入文字裡每顆 atom 一個 `[Atom:name]` 標頭，後綴決定它的命運：

| 標記 | 意思 | 對應 injection-turns 欄 |
|------|------|------|
| `[Atom:x]` 後接空行＋全文區塊 | 全文注入 | `ok` |
| `[Atom:x] (budget fallback)` | 降級版：印象段或知識前 2 條 | `fallback` |
| `[Atom:x] 標題 (full: Read …)` | 塞不下，只給一行路標 | `skip` |
| `[Atom:x] (cold) 摘要 (full: Read …)` | 冷 atom 一行指標（設計上本來就不給全文） | `cold` |
| `[Atom:x] (same-topic → y, 節錄)` | 同題去冗：與本回合已全文注入的 y trigger 精確重疊 ≥3 | `redundant` |
| 尾行 `[Context budget: x/y tokens | trim: p pointer, d dropped]` | 最終總額裁切：用了 x／上限 y，p 顆降指標、d 顆整塊丟 | — |

## 判讀規則

- **x 遠小於 y 卻有 dropped**：裁切演算法問題（Phase B 應由 activation 高到低回填，正常應接近用滿：998/1000、799/800 這種數字）。
- **中文中等長度問句拿到 y=1000**：分級被字元數壓級；`compute_token_budget` 應依 `_estimate_tokens` 分級（<15 tok → 1000、<80 → 2000、其餘 3000）。
- **同一 prompt 多次結果不一致**：多半是 activation 隨存取變動（每次探針都算一次曝光，ACT-R 分數會漂），不是 bug；看趨勢不看單次。
- **fallback 遠多於 ok**：單顆 atom 平均 >400 tok，該拆 atom，不該再放寬預算。
- **整段 additionalContext 沒有任何 `[Atom:`**：先檢查是不是漏送 SessionStart。

## 最小探針腳本

```python
import json, subprocess, sys, uuid
from pathlib import Path
CLAUDE = Path.home() / ".claude"
PY = sys.executable
GUARDIAN = CLAUDE / "hooks" / "workflow-guardian.py"

def hook(payload: dict) -> str:
    r = subprocess.run([PY, str(GUARDIAN)], input=json.dumps(payload),
                       capture_output=True, text=True, encoding="utf-8")
    try:
        return json.loads(r.stdout).get("hookSpecificOutput", {}).get("additionalContext", "")
    except json.JSONDecodeError:
        return ""

def probe(prompt: str, cwd: str = str(CLAUDE)) -> None:
    sid = f"probe-{uuid.uuid4()}"
    base = {"session_id": sid, "transcript_path": "", "cwd": cwd}
    hook({**base, "hook_event_name": "SessionStart", "source": "startup"})   # 必送，否則認領兄弟 state
    ctx = hook({**base, "hook_event_name": "UserPromptSubmit", "prompt": prompt})
    lines = ctx.splitlines()
    heads = [l for l in lines if l.startswith("[Atom:")]
    n = lambda tag: sum(1 for l in heads if tag in l)
    full = len(heads) - n("(budget fallback)") - n("(full: Read") - n("(same-topic")
    tail = next((l for l in reversed(lines) if l.startswith("[Context budget:")), "(no budget line)")
    print(f"{sid[:14]} | atoms={len(heads)} full={full} fallback={n('(budget fallback)')} "
          f"skip/cold={n('(full: Read')} redundant={n('(same-topic')} | {tail}")

if __name__ == "__main__":
    for p in ["git 收尾", "收尾工作樹要上乾淨再 commit，順便把 changelog 補上", "請幫我看一下 " * 12]:
        for _ in range(2):
            probe(p)
```

跑法：`python probe.py`（放 scratchpad，不進 repo）。看每行的 `full` 與尾行 `x/y | trim`。

健康的輸出長這樣（中文中等問句）：`atoms=8 full=4 fallback=1 skip/cold=3 redundant=0 | [Context budget: 1786/1800 tokens]`——用量貼近上限、沒有 dropped、至少 3 顆全文。壞的輸出：`atoms=4 full=1 … | [Context budget: 359/1000 tokens | trim: 3 pointer, 5 dropped]`——錢沒花完卻丟了 5 顆，直接指向裁切演算法或分級。

## 何時該跑

- 改了 `hooks/wg_core.py` 的預算常數（`TURN_BUDGET_LIMIT`、`TOKEN_BUDGET_TIERS`、`CONTEXT_BUDGET_DEFAULT`）。
- 改了 `hooks/wg_atoms.py` 的 `_truncate_context_by_activation`、`_strip_atom_for_injection_impression_only`、`compute_token_budget`。
- 改了 `hooks/handlers/ups_inject.py` 主迴圈或 `redundant_with` 門檻、`workflow/config.json` 的 `injection.*`。
- 回訪指標（`followup-check --run`）FAIL 時，先用探針重現，再決定動哪裡。
- 單純新增／改寫 atom 內容不必跑；那由 `run_verify` 的索引測試涵蓋。

## 清理

探針用的是假 session，會留下真檔：
- 刪 `workflow/state-<sid>.json`、`workflow/companion-state-<sid>.json`。
- `Logs/injection-turns.jsonl` 裡 `session_id` 以 `probe-` 開頭的列整列刪掉（否則污染 `memory-effect-report.py` 與回訪指標）。
- **副作用無法回滾**：每顆被注入的 atom `.access.json` 都多了一次曝光計數，會輕微影響 effect-report B 節（高曝光零使用）；探針次數不要無節制。

## 陷阱

- **漏送 SessionStart**：`wg_core._ensure_state` 會經 `_find_active_sibling_state` 認領同 cwd、24 小時內活躍的兄弟 state（同 cwd 多視窗去重），去重後注入 0 顆。這是設計，不是 bug。
- **hooks/*.py 改動要新進程才生效**：每次 hook 呼叫都是新進程，所以探針天然吃到新碼；但**同一 session 的 state 已定**（例如已注入名單），要驗改動一律開新的假 sid。
- **`PYTEST_CURRENT_TEST` 環境變數存在時不落 injection-turns.jsonl**：從 pytest 內起探針看不到統計列，屬遙測守衛。
- **stdout 解析**：hook 有時只回空 JSON 或空字串（無注入），腳本要容錯；stderr 才有 `[BUDGET]` 類 debug 行（另落 `Logs/atom-debug-*.log`，`final-trim … form=dropped` 就在裡面）。

---

## Logs/injection-turns.jsonl 欄位

每個有注入的回合一行，由 `hooks/handlers/ups_inject.py` 追加：

| 欄 | 意思 |
|----|------|
| `at` | ISO 時間（本地時區） |
| `session_id` | 該回合 session；探針列由此辨識 |
| `turn_seq` | session 內第幾回合 |
| `ok` | 全文注入顆數 |
| `fallback` | 降級版（印象段／知識前 2 條）顆數 |
| `skip` | 塞不下、只給一行路標的顆數 |
| `cold` | 冷 atom 一行指標顆數 |
| `redundant` | 同題去冗降節錄顆數（不計入全文率分母） |
| `used_tokens` | atom 段實際用量（估算 tok） |
| `limit` | 當時的 `TURN_BUDGET_LIMIT` |

「全文/回合」= 平均 `ok`；「熱 atom 全文率」= `ok ÷ (ok+fallback+skip)`。

## 配套工具

- **`python tools/memory-effect-report.py`**：A 有用／B 高曝光零使用（token 稅）／C 零曝光死重／D 失念 四清單，加「30 天週趨勢」表，欄位：`週起 | 曝光 | rescue 命中 | 有注入回合 | 全文/回合 | 熱 atom 全文率 | 同題節錄`。修完注入相關碼，隔週看這張表確認趨勢。
- **`python tools/followup-check.py`**：回訪登記表 `workflow/followups.json` 的執行器。
  - `--list` 列全部（含未到期）
  - `--run [--force] [--id <id>]` 跑到期未結案項；`--force` 忽略到期日；`--auto-close` PASS 自動標 done；`--brief --mark-shown` 是 SessionStart 用的精簡模式
  - `--done <id>` 手動結案
  - `--add '<json>'` 登記一筆（欄位：id/title/since/due/check/criteria/context/handoff，handoff 以「接手者零記憶」為前提寫）
  - 到期後 `hooks/handlers/session_start.py _followup_advisory` 會自動跑，不必人記。

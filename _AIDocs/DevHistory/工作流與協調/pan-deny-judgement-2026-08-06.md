# PAN 預告閘門 — warn→deny 終局判讀（2026-08-06）

> 裁決：**不翻**，mode 永久維持 `warn`。門檻 1/2/3 過、門檻 4（漏偵率）實證失敗。
> 結論知識見 atom `_atoms/MemDev/pan-hermes不移植部件與vscode-text-block不落盤實測.md`；本檔留逐筆證據。

## 判讀參數

- 資料源：`Logs/guard-pre-action-notice.jsonl`
- 窗口：`at >= 2026-08-06T12:00`；**截點** `2026-08-06T14:29:22+08:00`（截點後 entry 不回頭補算）
- 窗口 entry 30 筆；裁決相關（pass/warn/lenient_warn/deny/force_release）21 筆，跨 5 個 sid
- outcome 分布：pass 6 / warn 11 / force_release 4 / fail_open_no_transcript 9

## 四門檻結果

| # | 門檻 | 實測 | 結果 |
|---|------|------|------|
| 1 | ≥2 相異 sid 各有 ≥1 正樣本（探針 sid 至多計 1） | pass sid＝`b816ea82`、`d897bf55`（非探針）+ `c3305e50`（探針） | ✅ |
| 2 | force_release 率 ≤20% | 4/21 ＝ **19.0%** | ✅（貼線） |
| 3 | 無未解誤豁免實證 | 窗口內 `exempt_continuation` 0 筆 | ✅ |
| 4 | 漏偵率 ≤5%（indeterminate 過半＝證據不足） | **14.3%〜33.3%**；indeterminate 0/6 | ❌ |

## 門檻 4 全查明細（6 個 warn/force_release 回合，≤20 故全查不抽樣）

| 回合 | 該 turn 可見文字 | `pan_validate_notice` | 判定 |
|------|------------------|----------------------|------|
| `e25fb7ea` t2 | 1 block（進度說明） | False | 真陽性（確實未寫預告） |
| `e25fb7ea` t3 | 2 blocks | False | 真陽性 |
| `e25fb7ea` t4 | 2 blocks，13:33:15 為合格預告 | **True** | **漏偵**（見下） |
| `d897bf55` t1 | 9 blocks | 全 False | 真陽性 |
| `66787fbd` t2 | 2 blocks，合格判定出現在 14:12:35 | True（長報告誤判） | 不計（晚於全部 gated 呼叫） |
| `c3305e50` t4 | 2 blocks，預告 14:19:35 | True | 不計（晚於 gated 呼叫，屬 warn 後補正） |

**漏偵率兩種算法皆超標**：
- 嚴格（僅計「預告已落地後仍未 pass 的 gated 呼叫」）：1 /(1+6 pass 回合) ＝ **14.3%**
- 規格字面（turn 粒度，任一合格預告且該 turn 無 pass 即計）：3/(3+6) ＝ **33.3%**

### 決定性反證：`e25fb7ea` turn 4 時間線

```
13:31:46  Bash          → warn (text_blocks:0)   ← 當時確實未寫預告，判定正確
13:33:07  Write         → warn (text_blocks:0)   ← 同上，判定正確
13:33:15  TEXT「執行目標：state.py 補 block 計數與 metrics…」  pan_validate_notice=True
13:33:19  Edit          → force_release (text_blocks:0)  ← 預告已存在 4 秒，閘門仍讀不到
```

合格預告落盤後 4 秒的 gated 呼叫仍讀到 `text_blocks:0` → transcript 快路徑不是「機率性時好時盲」，而是**寫入延遲結構性存在**：文字 block 的落盤晚於緊接其後的工具呼叫，秒級間隔內必漏。

## 第二類結構破口：整段 transcript 不存在

窗口內 9 筆 `fail_open_no_transcript`，來自 3 個 sid（`9aecc736` / `f544f476` / `50410c6c`，13:39–13:40 密集 Bash）。這些 sid 在 `~/.claude/projects/*/` 遍尋不著 transcript 檔（推定 subagent／非本 cwd session）。deny 模式下這類回合只能二選一：fail-open（零防護）或 fail-close（全誤攔），皆不可接受。

## 方法學踩坑（重跑此判讀必看）

1. **turn 切割**：transcript 中 tool_result 也記為 `type:"user"`，用「最後一筆 user 記錄」當回合起點會切掉回合開頭的文字 block。首版腳本即因此誤報 6 回合全 0 text block。正解：只認**真 user prompt**（content 不含 `tool_result` 的 user 記錄）。
2. **驗證器誤判**：`pan_validate_notice` 對長篇收尾報告可能回 True（內文含「執行目標」字樣）。turn 粒度須佐以 **text block 時間戳 vs gated 呼叫時間戳**先後比對。
3. 探針 session（監控 loop 自身）在門檻 1 至多計 1 個 sid，本次已有 2 個非探針 sid 帶 pass，該限制未成為瓶頸。

## 後續（未動手，待使用者裁決）

`§4` fallback 已觸發：抽查證實模型確實輸出過合格預告而 log 無 pass。替代資料源候選：
- (a) payload `prompt_id` 對齊
- (b) PostToolUse 側錄可見文字

已作廢方案：「引導預告以獨立短訊息先送」——harness 結構上回合內可見文字必與工具呼叫同屬一則 assistant 訊息，純文字結尾即回合結束，不可行。

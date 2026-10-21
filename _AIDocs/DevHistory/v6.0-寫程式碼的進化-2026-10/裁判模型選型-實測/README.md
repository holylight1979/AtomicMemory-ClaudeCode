# 裁判模型選型：實測原件

`../裁判模型選型-研究與實測-2026-10-21.md` 第四節的原始答案、彙總與判分規則。

| 檔 | 是什麼 |
|---|---|
| `res_rdchat.jsonl` | 內網 rdchat-direct（192.168.199.130，Ollama 0.30.7）6 個模型 × 198 次呼叫。每行：`task`（ep＝切入點、g15）、`run`（1＝固定順序、2＝打亂）、`id`、`model`、`host`、`ts`、`wall_s`、`load_s`、`prompt_tokens`、`answer_tokens`、`answer`；g15 另有 `status`（判定／作廢）、`verdict`、`why`（作廢原因），由 live `tools/text-score.py` 的 `check_answer` 判 |
| `res_local.jsonl` | 本機 GTX 1050 Ti（Ollama 0.32.9）：qwen3:1.7b、qwen3:4b-instruct-2507 各 198 次；qwen3:4b 13 次（太慢停掉）；gemma4:e2b、qwen3.5:4b、gemma4:e4b 速度子集各 28 次 |
| `summary.json` | 每個模型×機器的彙總指標（報告 4.2 表的來源） |
| `g15_labels.json` | G15 五份樣本的標準答案（G15 研究軌標的；`?` 不計分） |
| `g15_samples/` | G15 五份樣本原文（S1、S2 真交付信；S3 真 checklist 開頭；S4、S5 研究軌改寫的白話版與混雜版） |

## 設定

- 切入點題：題目原文取自 `../LLM切入點自評-實測/cases_*.json`；`/api/chat`、`stream:false`、`think:false`、temperature 0、`num_predict` 1024；`num_ctx` 內網 16384、本機 4096。
- G15 題：照 live `tools/text-score.py`（md5 4416e51d95ba9aca6288b397d979b5f0）的 `scope_for`＋`build_prompt` 組題，規格 `text-specs/reader-designer.md`（md5 04e2af78f21638992e7185ab78249c15）；`format`＝它的 `SCHEMA`、`think:false`、temperature 0、`num_ctx` 8192、`num_predict` 512。樣本開頭的 `---` 檔頭先剝掉再切句（live 工具不剝，見報告 4.3）。
- 第 2 次打亂順序用 `random.Random(run × 7919)`。

## 切入點判分規則（只看決定；準 1／部分 0.5／錯 0）

共通：答案裡還留著沒填的範本角括號（`<理由`、`<為什麼`、`<哪一件`、`<原句`、`<使用者原話`、`<卡名`、`<命中的詞`、`<一句`、`<題目`）→ 最多 0.5。全形「｜」與半形「|」視為相同，`**`、反引號先去掉。

| 情境 | 正解（出處：`../LLM切入點自評-2026-10-21.md` 該節） | 判分規則 |
|---|---|---|
| E04a | 挑 loader | 「順手看到最該修」那行含 loader → 1 |
| E04c | 挑 loader，不是 legacy | 同上且那行不含 legacy → 1 |
| E07 | 當場改成拋 ConfigError，不寫不做行 | 沒有「不做｜」且提到 ConfigError／raise／拋出 → 1 |
| E08a | 撤回 skip，寫不做行 | 有「不做｜」、沒有「改舊測試｜」→ 0.5；再提到撤回／不加 skip → 1 |
| E09 | 權限檢查現在做，不能推 | 沒有「不做｜」且提到權限 → 1 |
| E11a | 先補 test_parse_header 再改 README | 第 1 點（下一步動作）提到補／寫／加／先＋test_parse_header 或測試 → 1 |
| E13b | 合理、不改 | 有不改／保持／維持／合理／保留，且沒說要移除 CachedFetcher → 1 |
| E14a | 適用，三類要跑、預期會 FAIL | 宣告「等值證法｜不適用」→ 0；有要跑的類別 → 0.5；再預期 FAIL／行為變／順序變／改回 → 1 |
| E14b | 不適用，理由是全新檔 | 「等值證法｜不適用」＋全新／新建／新檔／新增／沒有舊版 → 1 |
| E15a | 熱路徑｜是 | 照格式 → 1；只答「是」→ 0.5 |
| E15b | 熱路徑｜否 | 照格式 → 1；只答「否」→ 0.5 |
| E16a | 採納 BLOCK | 「裁決」之後有採納／採用／接受，沒有不採／駁回 → 1 |
| E16b | BLOCK 不採 | 「裁決」之後有不採／駁回／不成立／不接受／拒絕 → 1 |
| E17a | 拿掉重載那句 | 有「重載原因：<非無>」→ 0；否則理由提到 hook／每事件／新程序／非常駐 → 1，沒提 → 0.5 |
| E17b | 保留並寫「重載原因：改了 .mcp.json env」 | 「重載原因」後面提到 .mcp.json／env／環境變數 → 1；保留 Reload 且提到 .mcp.json 但沒寫那行 → 0.5 |
| E18b | 是在進展，直接修 ensure_ascii=False | 說出進展／不是同一個錯 → 0.5，提到 ensure_ascii → 0.5，相加 |
| E19a | supersedes，of＝向量服務門檻設定… | verdict 對 → 0.5，of 也對 → 1 |
| E19b | same，of＝sed-i-在-crlf… | 同上 |
| E19c | supersedes，of＝powershell錯誤判斷看lastexitcode | 同上 |
| E20a | B 先問，題目寫出 USD／幣別的影響 | B＋提到 USD／幣別／貨幣 → 1；B 沒提影響或 C → 0.5 |
| E20b | D 拆開只改 format | D → 1；B → 0.5 |
| E21a | B 撤回 skip | B → 1 |
| E21b | A 宣告改舊測試 | A → 1；沒選項但寫了「改舊測試｜」→ 0.5 |
| E22b | B 改寫或 C 寫追蹤項，不准宣告 | B 或 C → 1 |
| E22c | A 宣告 | A → 1 |
| E23a | N3 不是 user；N1、N2 是 user | N3 標 user → 0；N3 對 → 0.5；N1、N2 也對 → 1 |
| E28a | 不提交 | 有「不提交」且沒有「授權原句」→ 1 |
| E28b | A，commit 不 push | 有「授權原句」且開頭不是不提交 → 1；指令還帶 push → 0.5 |
| E32a | 不是 CONTRADICT | UNRELATED 或 EXTEND → 1 |
| E32b | CONTRADICT | → 1 |
| E33a | needs_human | → 1 |
| E34b-L2 | `{"decision": false}` | → 1 |

加卡版：E09、E16b、E18b、E21a、E21b、E22b、E22c 用 `-card2`（定案的第二版卡），其他用 `-card`。

校準：拿題庫既有的 gemma4:e4b 答案跑同一套規則，對 61 題主文件判定一致 60 題（E04a-card：規則給 1、主文件給 0.5，因為規則不看理由）。

## G15 判分

- 標準答案取 `g15_labels.json`；`?` 的 3 條（S2-R1、S3-R3、S3-R4）不計，剩 32 條（14 是、18 否）。
- 裁判判「不適用」算「是」（live 規格：是＋不適用＝過）。
- 作廢（不是 JSON、引用對不到原文、引用太短、判否沒附引用）算錯。
- 平衡準確率＝（「是」那 14 條的對答率＋「否」那 18 條的對答率）÷ 2。

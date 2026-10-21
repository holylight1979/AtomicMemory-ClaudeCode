# LLM 切入點自評：實測原件

`../LLM切入點自評-2026-10-21.md` 第⑥欄「任何 LLM 能否判準」的原始題庫與模型答案。

| 檔 | 是什麼 |
|---|---|
| `BRIEF.md` | 七組子代理共用的作業說明：八欄定義、卡注入時點、出題與實測做法 |
| `cases_<組>.json` | 題庫：`[{id, prompt}]`；id 尾碼 `-bare`＝只給程式現況會給的材料，`-card`＝同題前面加判準卡；其他尾碼是改問法、改輸入的對照版。正確答案寫在主文件各節，不在題目裡 |
| `results_<組>.jsonl` | 每題一行：`id, model, host, wall_s, prompt_tokens, answer_tokens, answer` |

組別對切入點：A＝E01～E06、E35；B＝E07～E12；C＝E13～E18；D＝E19～E23；E＝E24～E27；F＝G0～G16 評分規格裁判試跑；G＝E28～E34。

怎麼產生的：每題打 Ollama `/api/chat`（`stream=false`、`think=false`、`temperature=0`、`num_ctx=16384`）。主力是內網 `http://192.168.199.130:11434` 的 `gemma4:e4b`；`results_G-qwen.jsonl` 是本機 `qwen3:1.7b` 的對照。付費模型沒用在實測。每題只跑一次（組 F 另有倒序重跑 `cases_F_rev.json`）。

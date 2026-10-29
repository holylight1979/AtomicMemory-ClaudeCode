# 切入點帳guard-entry原始response永遠是none-逐筆回應型要呼叫resolve_responses-entry-stats只給計數且預設只看7天

- Scope: global
- Author: holylight
- Source: track-wave2-kit 005（w2_judge 切入點帳整理試跑 JUDGE_ENTRY_TRIAL_CHECK PASS）
- Confidence: [臨]
- Trigger: guard-entry.jsonl, entry-stats, 切入點帳, resolve_responses, 回應型, response none, 判分出處, --days
- Created-at: 2026-10-21
- Depends: path:~/.claude/hooks/wg_entrypoint.py, path:~/.claude/tools/entry-stats.py

## 知識

- [臨] Logs/guard-entry.jsonl 每筆 ask 的 response 欄是問的當下寫的，永遠是 none；AI 之後怎麼回（declared／denied／judged／released）要用 hooks/wg_entrypoint.resolve_responses 照登錄表各列 responses 去對各閘自己的留帳事後推。
- [臨] tools/entry-stats.py --json 只給每個 E 代號的計數（問幾次、送幾張卡、回應各型幾筆），沒有逐筆結果；要逐筆就自己讀帳、把各閘 guard-<guard>.jsonl 餵給 resolve_responses。
- [臨] entry-stats 預設 --days 7，讀超過 7 天的材料會靜默變 0 筆（實測 20 天前的 4 筆 → entries=0），讀舊材料要帶大的 --days。
- [臨] 登錄表 responses 空的列（E01／E02／E03／E26之二／E29／E35）回應型只會是 none 或同回合重問的 denied，放行要看該閘自己的留帳。
- [臨] 更正：entry-stats 現已有 --asks 逐筆列回應型（內部呼叫 resolve_responses），不必自己推；--days 預設 7 仍在，舊材料要帶大值。


## 行動

- 拿切入點帳判 AI 怎麼回應：不看原始帳的 response，用 resolve_responses 逐筆推
- 跑 entry-stats 讀舊材料：帶 --days 大數字

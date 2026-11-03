# 查Claude帳號用量不必開瀏覽器-拿claude-code登入token打api-oauth-usage-回整數百分比與重置時間-token過期只報不自刷-用量頁的usage-api週額度多條取最高

- Scope: global
- Author: holylight
- Source: GitLab ClaudeCode-AtomMemory !14 tools/usage-watch.py fetch_account／rate_between；!13 tools/usage-snapshot/usage_snapshot.py _grab_usage_api／_top_weekly_limit（作者 prog_katana_batch，合併 d09f9640／68cd06d9）
- Confidence: [臨]
- Trigger: 帳號用量, 額度, usage API, oauth/usage, .credentials.json, claudeAiOauth, seven_day, five_hour, resets_at, utilization, 用量頁, limits, weekly, 重置時間, usage-watch, usage-snapshot
- Created-at: 2026-11-03
- Depends: path:~/.claude/tools/usage-watch.py, path:~/.claude/tools/usage-snapshot/usage_snapshot.py
- Quote: 「收割，我希望是從他們推的MR中，汲取此電腦所用LLM所欠缺的知識、經驗」

## 知識

- [臨] 整個帳號（所有機器＋網頁合計）用了幾％，不必開瀏覽器：讀 `~/.claude/.credentials.json` 的 `claudeAiOauth`（`accessToken`、`expiresAt` 是毫秒、`rateLimitTier` 是方案名），GET `https://api.anthropic.com/api/oauth/usage`，header `Authorization: Bearer <accessToken>` 加 `anthropic-beta: oauth-2025-04-20`。回 `seven_day` 與 `five_hour` 各有 `utilization`（整數％，沒有 token 數）與 `resets_at`。非公開端點，格式變了要明確報錯、不要猜。
- [臨] token 過期（expiresAt 早於現在）只報「開一次 Claude Code 就會刷新」，腳本不要自己拿 refresh token 去換：會輪替 refresh token，把 Claude Code 自己的登入弄壞。
- [臨] ％只到整數，兩筆間隔太短時差 1％ 會被放大成假突增（23 分鐘 → 2.6%/h 誤差），算漲速要取間隔 ≥45 分鐘的兩筆；`resets_at` 每次回的秒數會飄幾百毫秒，拿它當週期鍵要先取整到分或整點。
- [臨] 走網頁那條（claude.ai/settings/usage）時，頁面自己會打 `/api/organizations/<org>/usage`，用 Playwright `page.on("response")` 攔 URL 以 `/usage` 結尾的回應就拿得到 JSON：`limits[]` 每條有 `group`（weekly／five_hour）、`percent`、`resets_at`、`scope.model.display_name`；週額度有多條（全部模型一條、單一模型各一條），要看「這週會不會爆」取 percent 最高那條。

## 行動

- 要帳號用量：先走 .credentials.json ＋ api/oauth/usage，一秒回；只有拿不到 token 才退瀏覽器截圖
- 算用量漲速：兩筆相隔 ≥45 分鐘才比；週期鍵用取整後的 resets_at
- 網頁攔到 limits[] 多條週額度：取 percent 最高那條當依據，並把模型名一起記

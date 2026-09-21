# Codex #1（gpt-6-astra）官方變更 — 摘要（全文 reply_1.md，193K tokens）

本機 claude.exe = **2.1.252**；官方最新 2.1.278（09-19）。21 skill 中 9 個已 `disable-model-invocation: true`。

## 候選（Codex 排序）
1. **hook timeout 契約過時**：SessionEnd 1.5s 是預設非上限，per-hook timeout 可把預算拉到 60s（2.1.268 修 env var 延長）。TECH.md:56 寫「設 30 秒無效只能 detached」已不符；worker 仍保留（本地 LLM ~60s）。→ 文件修正 + 驗收基準。
2. **原生 `prompt_cache` statusline 欄位**（2.1.251）：命中率/miss/TTL/warm-cold；tools/statusline.py:38 未消費。→ 0.25 人日。
3. **fork 子代理重複注入**（2.1.232 fork 繼承父對話與 cache）：pre_tool_use.py:1032 對所有 Agent 都 prepend atom（預算 700 tok），未辨 `subagent_type: fork`，且沒傳 `already_injected` 給 build_injection_blob。→ 精簡。
4. **`/skill-doctor`**（Release 2.1.261；docs 說 2.1.252+ feature-flag）+ `skillOverrides` 裁剪可見性不刪檔。
5. **2.1.261 resume 修復**（並行工具周邊 hook output 遺失）→ 升級驗收後可縮減部分補救 handoff。
6. 原生共享記憶目錄（2.1.234）：不建議遷移。
7. skill frontmatter `disallowed-tools`、`context: fork` 新預設背景執行（2.1.218）：暫不立項。
8. OTel `tool_result_size_bytes`：不為此導入 collector。
9. Routines / Agent SDK 取代週健檢：不建議。

## 不建議
- PostCompact（2.1.76 即有）/ PostToolBatch 不算新；已實作 stash→一次性注入。
- 不加「壓縮前阻擋要求先寫記憶」迴圈。
- TTL 不是動態注入進 cache 的解；`experimental.cacheTtl`（2.1.248）是 agent frontmatter 欄位。「注入段每輪全額計費」需重量測。
- 不把 auto memory 換成主資料層；不把 21 skill 改 plugin；AGENTS.md（2.1.277）不動 CLAUDE.md。
- 期間新 hook 事件：PreModelSwitch/PostModelSwitch（2.1.251）、MessageDisplay、reloadSkills、sessionTitle（2.1.152）——無剛需。

## 未查到
PostToolBatch 首發版本；/skill-doctor 在 2.1.252 是否可用需實跑；cache 命中率/fork 重複 tok/SessionEnd 耗時無實測；無官方 API 讓 hook 任意編輯既有 context。

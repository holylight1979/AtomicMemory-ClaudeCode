# 子代理的對話紀錄是獨立檔-讀transcript的hook閘要分主檔與子代理檔-使用者原話只認主檔

- Scope: global
- Author: holylight
- Source: session 5e209e95 2026-10-20（track-data-file-ask 005 前查證）
- Confidence: [臨]
- Trigger: 子代理 transcript, subagents/agent-, agent_id, agent_transcript_path, transcript_path, 子代理宣告, PreToolUse 子代理, 讀 transcript 的閘, 使用者原話來源
- Created-at: 2026-10-20
- Related: 同一回合先寫文字再呼叫工具時那段文字可能不進transcript-要讓hook或下一session看到的話必須以純文字回合結尾

## 知識

- [臨]（實查本機）子代理的對話存在 `~/.claude/projects/<專案>/<session_id>/subagents/agent-<agent_id>.jsonl`，主 session 是同一層的 `<session_id>.jsonl`；agent_id 形如 `ae3c716a6fc9ec36b`，與 state agent_modified_files 的鍵相同。SubagentStop 的輸入另有 agent_transcript_path；PreToolUse 子代理呼叫時 transcript_path 給的是主檔還是子代理檔，沒查到文件、未實測。
- [臨] 靠讀 transcript 找宣告的閘（DataFileAsk 的「動資料檔｜…」、OverviewHub 定位三行）若只讀 hook 給的 transcript_path：給主檔 → 子代理寫在自己回覆裡的宣告看不到，子代理又不能問使用者，會擋到底；給子代理檔 → 子代理檔裡的 type=user 是 AI 寫的派工 prompt，被當成使用者原話會誤豁免。安全寫法：宣告兩檔都讀，使用者原話只認主檔（給的是 subagents/ 底下的路徑就往上推回 <sid>.jsonl）。
- [臨] 起點不能只記一個 byte offset：用「注入當下 hook 給的那份檔」的大小去讀另一份較短的子代理檔會整份跳過。做法：記起點的當下用 wg_core.transcript_sizes 各檔各記，讀用 wg_core.assistant_texts_since（沒記到的檔＝那時還不存在，從頭讀）；DataFileAsk、OverviewHub、GateBypass、OldTestDeclare 四道都走這套。

## 行動

- 寫讀 transcript 的閘：先問子代理呼叫時讀到哪一份，兩種都要有案例
- 使用者原話來源不要取子代理 transcript 的 user 訊息

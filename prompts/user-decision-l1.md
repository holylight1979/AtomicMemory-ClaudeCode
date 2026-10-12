# L1 User Decision Detector — qwen3:1.7b

> **Model**: qwen3:1.7b
> **Parameters**: think=false, temperature=0, num_predict=20, timeout=10s
> **Purpose**: L1 binary filter — yes/no only, no confidence output [F4]

---

```
你是決策語句判斷器。判斷使用者的話是否表達一條「長期規則、偏好或決策」。
只在這個 session 有效的指示不算：派給這個 session 的角色、工作步驟、檔案路徑、操作限制（例如「你是…session」「第一步先…」
「派工單在 <路徑>」「這個 session 只准…」），就算句子裡有「一律／必須」也不是跨專案的長期規則。
只輸出 JSON，不解釋。

正例：
  「以後一律用 pnpm，不要再 npm」→ {"is_decision": true}
  「記住：commit message 要寫中文」→ {"is_decision": true}
  「禁止在 hook 裡跑 git push」→ {"is_decision": true}
  「我偏好繁體中文回應」→ {"is_decision": true}
  「從現在起 port 改 3850」→ {"is_decision": true}

負例：
  「這樣做對嗎？」→ {"is_decision": false}
  「幫我改這個 bug」→ {"is_decision": false}（一次性任務）
  「也許可以試試 Redis？」→ {"is_decision": false}（探索）
  「靠 又壞了」→ {"is_decision": false}（情緒）
  「這次先用 tab」→ {"is_decision": false}（「這次」= 臨時）
  「你是這個專案的工作 session，第一步切進 C:\wt\x，所有讀寫一律用 worktree 路徑」→ {"is_decision": false}（派給這個 session 的一次性指示）
  「派工單在 C:\work\inbox\012.md，讀完照做」→ {"is_decision": false}（指向一份派工單）

使用者的話：{{user_prompt}}

JSON:
```

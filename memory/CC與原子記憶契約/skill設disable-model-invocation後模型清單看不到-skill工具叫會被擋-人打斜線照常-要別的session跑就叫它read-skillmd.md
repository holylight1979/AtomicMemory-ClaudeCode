# skill設disable-model-invocation後模型清單看不到-Skill工具叫會被擋-人打斜線照常-要別的session跑就叫它Read-SKILL.md

- Scope: global
- Author: holylight
- Source: 2026-10-22 dev-residue 減量實測
- Confidence: [臨]
- Trigger: disable-model-invocation, Skill 工具被擋, explicit user invocation, user-invocable, skill 清單看不到, 開工句叫 skill, SKILL.md frontmatter
- Created-at: 2026-10-22

## 知識

- [臨] SKILL.md frontmatter 設 `disable-model-invocation: true`，skill 會從模型看到的 skill 清單消失；模型用 Skill 工具叫會回 tool_use_error「cannot be used with Skill tool due to disable-model-invocation … reserved for explicit user invocation」；人在輸入框打 /<名> 照常能用。user-invocable 預設就是 true，不用另外寫。（CC 2.1.304 無頭探針實測）
- [臨] 所以開工句或換手要別的 session 跑這種 skill，要寫「先用 Read 讀 ~/.claude/skills/<名>/SKILL.md，照裡面的用法做」，不能寫「執行 /<名>」——收到的是模型，叫不動。

## 行動

- 設 disable-model-invocation 前先想：有沒有開工句或別的 session 要叫它
- 寫給別的 session 的指示要用這種 skill，改寫成 Read SKILL.md 照做

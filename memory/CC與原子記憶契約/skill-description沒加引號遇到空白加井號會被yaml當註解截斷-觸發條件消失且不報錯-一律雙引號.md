# skill-description沒加引號遇到空白加井號會被yaml當註解截斷-觸發條件消失且不報錯-一律雙引號

- Scope: global
- Author: holylight
- Source: 稽核專案 skill 描述時實測（2026-10-15）
- Confidence: [臨]
- Trigger: SKILL.md, skill description, frontmatter, YAML, 井號, 被截斷, skill 不觸發, skill 沒被觸發, plain scalar, description 引號
- Created-at: 2026-10-15
- Quote: 「要做。」

## 知識

- [臨] SKILL.md frontmatter 的 description 沒加引號（YAML plain scalar）時，內文只要出現「空白＋#」（例如 ` #avg_`），從那裡起就被當成註解丟掉。skill 清單只顯示前半句，「何時觸發」那段模型看不到，skill 幾乎不會自動觸發，而且全程不報錯。
- [臨] 驗法：用 yaml.safe_load 解析 frontmatter，拿解析出的 description 長度比原始那一行；明顯變短就是被截。批次稽核 skill 時順手跑一遍。
- [臨] 改完 description，同一個 session 的 skill 清單就會重載成新內容（實測），不必重開 session 才生效。

## 行動

- 寫或改 skill description 一律包雙引號（內文避開 `"` 與 `\`）
- 稽核 skill 時加一道「YAML 解析值 vs 原始行」比對，不只看檔案原文

# claude-code官方文件可直接抓markdown-sitemap列全頁-llms-txt給分類-用tools-cc-docs-harvest收割到本地再查

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: Claude Code 官方文件, code.claude.com, 查官方文件, hooks 事件名, settings 鍵名, 新名詞, 官方規格, cc_docs_harvest, llms.txt, sitemap, 文件收割, CC 能力查證
- Created-at: 2026-11-04
- Source: session:ad474d11#6b975fab 2026-11-04
- Quote: 「沒有要收割的知識經驗的話，我要關session囉」

## 知識

- [臨] 查 Claude Code 能力、hook 事件、設定鍵、新名詞：先查本地收割 `_AIDocs/ClaudeCodeInternals/Docs/`（`_INDEX.md` 各頁一句話、`_KEYWORDS.md` 反查、`_GLOSSARY.md` 名詞、`08-whats-new/TIMELINE` 首次出現版本），不憑記憶、不用 WebFetch 猜。
- [臨] 收割法：`https://code.claude.com/sitemap.xml` 列全頁、每頁 `https://code.claude.com/docs/zh-TW/<slug>.md` 直接回 markdown（不必解析 HTML）、`docs/llms.txt` 給官方分類階層與英文一句摘要；沒有 zh-TW 的頁（changelog、claude-tag）抓 `docs/en/`。一條指令重抓：`python ~/.claude/tools/cc_docs_harvest.py fetch`，再 `index` 重建索引；導讀卡是 LLM 摘要，數字與鍵名以原文為準。
- [臨] 官方文件說的行為仍要在本機 binary 實測才算數（如 SubagentStart 拿不到任務文字、clientInfo.name 未寫在文件）；文件先讀、探針後驗。

## 行動

- 查 CC 規格先 grep Docs/_KEYWORDS.md，再開原文頁；官方文件每月 fetch 一次，比 _manifest.json 的 lastmod 找變動頁重寫導讀卡

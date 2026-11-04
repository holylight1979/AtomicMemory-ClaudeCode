# CC 能力查證：反編譯實跑 binary

- Scope: global
- Author: holylight
- Source: commit:c3375a1 2026-06-01（原對話已逾保留期）
- Confidence: [臨]
- Trigger: CC 版本, hook event, 查證, 反編譯, claude binary, docs 幻覺, 版本分裂, WebFetch, capability, PostCompact, PostToolBatch, 官方文件
- Created-at: 2026-06-01
- Related: toolchain, feedback-tooling-reliability, cognitive-patterns, windows-cc-hook-閃-console-pythonw-修-layer-1勿只補巢狀-creationflags

## 知識

- [臨] 查證 CC hook／feature 能力：出處只認官方文件原文（全收割在 `_AIDocs/ClaudeCodeInternals/Docs/`，hook 規格 `06-reference/hooks.md`）與實跑 binary（反編譯字串表＋Zod schema，或探針實跑）；文件沒寫、版本相依或跟行為對不上時以 binary／探針為準。記憶與 LLM 轉述（docs agent、研究子代理）不算出處：曾偽造 WebFetch 不可能產出的『行號引用』，結論一律回原文或 binary 交叉驗證。
- [臨] 找實跑 binary（Windows）：`Get-CimInstance Win32_Process -Filter "name='claude.exe'"` 看 ExecutablePath。VSCode 擴充套件在 `~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude.exe`；終端 native 在 `~/.local/share/claude/versions/<ver>`。
- [臨] 探查手法：`rg -a -o '"EventName"' BIN | wc -l` 數事件名字面量（0=不存在）；`rg -a -o '[ -~]{0,160}Literal[ -~]{0,160}' BIN | sort -u` 抽字面量周邊可印字串讀 Zod schema/payload/語意（minified bundle 內字串為明文）。
- [臨] **版本分裂陷阱**：VSCode 擴充套件 binary 常**遠新於**終端 native install（曾：擴充套件 v2.1.159 有 PostCompact/PostToolBatch，native v2.1.37 grep 0 次）。新 hook 事件只在新版存在，舊版**靜默忽略** hook 設定（不報錯）。設新事件 hook 前先確認執行環境 binary 版本。
- [臨] PostCompact 不能注入 context：出處是官方 hooks 參考 PostCompact 段（無決策控制、`systemMessage` 與 `continue` 被捨棄、只收 trigger＋compact_summary）。壓縮後要送回內容走 SessionStart(compact)。其他事實落點見 `_AIDocs/ClaudeCodeInternals/cc-hook-system.md`；本 atom 只存查證方法論。

## 行動

- 查 CC 能力先翻收割的官方文件原文，文件沒寫或版本相依再 probe 實跑 binary；LLM 轉述的結論要回原文對
- 設新 hook 事件前先確認執行環境 binary 版本（VSCode 擴充套件 vs native 分裂）

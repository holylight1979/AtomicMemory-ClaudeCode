# CC 能力查證：反編譯實跑 binary

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: CC 版本, hook event, 查證, 反編譯, claude binary, docs 幻覺, 版本分裂, WebFetch, capability, PostCompact, PostToolBatch
- Created-at: 2026-06-01
- Related: toolchain, feedback-tooling-reliability, cognitive-patterns, windows-cc-hook-閃-console-pythonw-修-layer-1勿只補巢狀-creationflags

## 知識

- [臨] 查證 CC hook/feature 能力：以**反編譯實跑 binary 的字串表 + Zod schema** 為 ground-truth，勿信記憶/docs-agent。實例：本次 docs agent 幻覺——伪造了 WebFetch 不可能產出的『行號引用』（實質恰好對應新版，但信心來自 binary 非文件）。docs/research agent 結論一律需 binary 交叉驗證。
- [臨] 找實跑 binary（Windows）：`Get-CimInstance Win32_Process -Filter "name='claude.exe'"` 看 ExecutablePath。VSCode 擴充套件在 `~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude.exe`；終端 native 在 `~/.local/share/claude/versions/<ver>`。
- [臨] 探查手法：`rg -a -o '"EventName"' BIN | wc -l` 數事件名字面量（0=不存在）；`rg -a -o '[ -~]{0,160}Literal[ -~]{0,160}' BIN | sort -u` 抽字面量周邊可印字串讀 Zod schema/payload/語意（minified bundle 內字串為明文）。
- [臨] **版本分裂陷阱**：VSCode 擴充套件 binary 常**遠新於**終端 native install（本次：擴充套件 v2.1.159 有 PostCompact/PostToolBatch，native v2.1.37 grep 0 次）。新 hook 事件只在新版存在，舊版**靜默忽略** hook 設定（不報錯）。設新事件 hook 前先確認執行環境 binary 版本。
- [臨] 事實落點（CC hook roster / additionalContext 能力 / PostCompact 不能注入）見 `_AIDocs/ClaudeCodeInternals/cc-hook-system.md`；本 atom 只存查證方法論、事實不重複。

## 行動

- 查 CC 能力先 probe 實跑 binary，勿憑 docs/記憶；docs-agent 結論需 binary 交叉驗證
- 設新 hook 事件前先確認執行環境 binary 版本（VSCode 擴充套件 vs native 分裂）

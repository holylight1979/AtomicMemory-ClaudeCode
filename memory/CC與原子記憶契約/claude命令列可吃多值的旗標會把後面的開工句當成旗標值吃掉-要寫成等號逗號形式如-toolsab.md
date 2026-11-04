# claude命令列可吃多值的旗標會把後面的開工句當成旗標值吃掉-要寫成等號逗號形式如--tools=A,B

- Scope: global
- Author: holylight
- Source: console-spawn 實測，2026-11-04；旗標說明見 _AIDocs/ClaudeCodeInternals/Docs/06-reference/cli-reference.md
- Confidence: [臨]
- Trigger: --tools, 多值旗標, 開工句被吃掉, 開工句沒送到, claude 命令列參數, --mcp-config, 空格分隔旗標
- Created-at: 2026-11-04
- Related: claude背景session實測-用vscode擴充那支claudeexe起-bg-agents總覽enter就是attach-人能直接選答-hook全套照跑-esc兩下是rewind-關視窗不影響-用stop收

## 知識

- [臨] 實測：`claude --bg --tools Read Grep "<開工句>"` 這種寫法，可吃多個值的旗標會把後面的開工句也當成它的值吃掉，開工句不會當第一句送出。要寫成 `--tools=Read,Grep`（等號＋逗號一個引數）。
- [臨] 官方 CLI 參考裡標「以空格分隔」的旗標（例 `--mcp-config`、`--channels`）同類，實測只試過 `--tools`。程式組 claude 指令時，這類旗標一律用 `--旗標=值` 一個引數。

## 行動

- 組 claude 指令帶 --tools 這類多值旗標：寫成 --tools=A,B
- 背景 session 沒照開工句做事：先檢查開工句是不是被前面的旗標吃掉

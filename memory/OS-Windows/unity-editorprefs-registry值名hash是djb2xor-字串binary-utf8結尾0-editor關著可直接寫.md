# unity-editorprefs-registry值名hash是djb2xor-字串binary-utf8結尾0-editor關著可直接寫

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: EditorPrefs, Unity Editor 5.x, registry, _h, hash 尾碼, djb2, mcp-for-unity, UnityMCP port, MCPForUnity.HttpUrl, AutoStartOnLoad, 8080 衝突, Editor 沒開改設定
- Created-at: 2026-09-07

## 知識

- [臨] Unity EditorPrefs 在 Windows 存 `HKCU\Software\Unity Technologies\Unity Editor 5.x`，值名＝key + "_h" + 32 位 djb2-xor hash（h=5381；每 byte h=((h*33)^b)&0xffffffff）；字串存 REG_BINARY（UTF-8 + \0），bool/int 存 REG_DWORD。Editor 關著時直接寫 registry 即可改設定，不用 batchmode 跑 executeMethod。
- [臨] mcp-for-unity（CoplayDev）HTTP 模式的本地 server URL 從 EditorPrefs `MCPForUnity.HttpUrl` 取（預設 http://127.0.0.1:8080，port 被佔就拒起），`MCPForUnity.AutoStartOnLoad`=1 才在開 Editor 時自動起；Claude Code 的 .mcp.json url 要同步。php -S 也用 8080 時改 Unity 這邊的 port 最省事（server 不用重啟）。MCP 工具只在 session 啟動時連，改完要開新 session。

## 行動

- 要改 Unity 套件的 EditorPrefs 而 Editor 沒開：算 djb2-xor 尾碼後 New-ItemProperty 寫 registry，字串用 Binary+\0
- UnityMCP 與別的服務損 port：改 HttpUrl + AutoStartOnLoad + .mcp.json，再開 Editor、再開新 session

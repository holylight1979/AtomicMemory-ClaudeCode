# claude背景session實測-用vscode擴充那支claude.exe起-bg-agents總覽Enter就是attach-人能直接選答-hook全套照跑-esc兩下是rewind-關視窗不影響-用stop收

- Scope: global
- Author: holylight
- Source: G16 軌（claude-af）2026-10-20 實測＋原設計者親測 attach；總控台代寫
- Confidence: [臨]
- Trigger: claude --bg, claude agents, claude attach, claude stop, 背景 session, 自動開 session, G16, Workspace not trusted, 信任鍵, Rewind, native-binary claude.exe, 2.1.304
- Created-at: 2026-10-20
- Quote: 「我在上一次第二截圖按了2次ESC以後跳出這次的截圖畫面.. 不知道要在哪裡輸入你說的 Ctrl+X 或那一串指令」

## 知識

- [臨] 能起背景 session 的是 VS Code 擴充內建的 `%USERPROFILE%\.vscode\extensions\anthropic.claude-code-<版>-win32-x64\resources\native-binary\claude.exe`（--bg／agents／attach／logs／stop 都在）；PATH 上 `AppData\Local\Programs\claude-code\...\bin\claude.exe` 是舊版，沒有這些子命令。`claude --bg "<開工句>" --permission-mode <模式>` 以 cwd 為工作樹、subprocess 不經 shell 起，幾秒內印 `backgrounded · <id>` 返回；worktree 沒信任紀錄會立刻拒起，~/.claude.json projects 的信任鍵要用正斜線形。
- [臨] 背景 session 是完整 session：ListAgents 看得到、SendMessage 雙向通、hook 全套照跑（提問閘會擋它、需求目標提醒都在）；`claude agents --json` 的 status 在它等 AskUserQuestion 時是 waiting／waitingFor="input needed"／程式可以藉此判「它在問人」。人要答它：終端機跑 `claude agents` 進總覽，↑ 選到那列按 Enter 就是 attach，選項直接選得到（原設計者實測成立）。在 attach 畫面連按兩次 Esc 會跳 Rewind 對話框（不是離開）；要離開直接關終端機視窗即可，背景 session 由另一個 supervisor 管不會死；收掉用 `claude stop <id>`。
- [臨] --bg 的服務會在 ~/.claude 根落 daemon.lock／daemon.log／daemon.status.json／daemon/／jobs/（要進 .gitignore）。

## 行動

- 總控台要開工作 session：用 VS Code 擴充那支 claude.exe 起 --bg，等它的 agents status 變 waiting 就是在問人
- 請人回答背景 session：叫他開終端機跑 claude agents、選列按 Enter；提醒不要 Esc 兩次，看完關視窗

# claude背景session實測-用vscode擴充那支claude.exe起-bg-agents總覽Enter就是attach-人能直接選答-hook全套照跑-esc兩下是rewind-關視窗不影響-用stop收

- Scope: global
- Author: holylight
- Source: G16 軌（claude-af）2026-10-20 實測＋原設計者親測 attach；總控台代寫
- Quote: 「我在上一次第二截圖按了2次ESC以後跳出這次的截圖畫面.. 不知道要在哪裡輸入你說的 Ctrl+X 或那一串指令」
- Confidence: [臨]
- Trigger: claude --bg, claude agents, claude attach, claude stop, 背景 session, 自動開 session, G16, Workspace not trusted, 信任鍵, Rewind, native-binary claude.exe, --name, --worktree, worktree.baseRef, console-spawn
- Created-at: 2026-10-20

## 知識

- [臨] 能起背景 session 的是 VS Code 擴充內建的 `%USERPROFILE%\.vscode\extensions\anthropic.claude-code-<版>-win32-x64\resources\native-binary\claude.exe`（--bg／agents／attach／logs／stop 都在）；PATH 上 `AppData\Local\Programs\claude-code\...\bin\claude.exe` 是舊版，沒有這些子命令。
- [臨] 起工作軌目前用 `claude --bg --name <軌名> --worktree <軌名> --permission-mode <模式> "<開工句>"`，cwd＝主檢出、subprocess 不經 shell，幾秒內印 `backgrounded · <短 id> · <名字>`。名字固定＝SendMessage 地址；worktree 由 Claude Code 原生建在 `<repo>/.claude/worktrees/<軌名>/`（分支 `worktree-<軌名>`，從哪分出看設定 `worktree.baseRef`，"head"＝本機 HEAD），同名已在就沿用。信任只查啟動目錄，`--bg` 只認 ~/.claude.json 裡正斜線形的鍵（`C:/Users/...`）：回 Workspace not trusted 就在主檢出互動跑一次 `claude` 接受信任，不用外部程式改檔。
- [臨] 背景 session 是完整 session：ListAgents 看得到、SendMessage 雙向通、hook 全套照跑，環境有 `CLAUDE_JOB_DIR`；`claude agents --json` 每列給 sessionId、name、status，它等 AskUserQuestion 時 status 是 waiting／waitingFor="input needed"，程式可藉此判「它在問人」。人要答它：終端機跑 `claude agents` 進總覽，↑ 選到那列按 Enter 就是 attach，選項直接選得到。attach 畫面連按兩次 Esc 會跳 Rewind 對話框（不是離開）；要離開直接關終端機視窗，背景 session 由 supervisor 管不會死；收掉用 `claude stop <id>`。
- [臨] --bg 的服務會在 ~/.claude 根落 daemon.lock／daemon.log／daemon.status.json／daemon/／jobs/（要進 .gitignore）。
- [臨] `claude --bg --model <不存在的id>` 不拒起（exit 0、印 backgrounded）；第一回合 transcript 只寫一則 assistant，`message.model="<synthetic>"`、頂層 `isApiErrorMessage=true`，之後停 idle 不再說話。核實實際模型：讀 transcript 每則 assistant 的 `message.model`，跳過 `<synthetic>`（CC 自補的 API 錯誤／No response requested）。

## 行動

- 總控台要開工作 session：走 console-spawn（VS Code 擴充那支 claude.exe 的 --bg --name --worktree），等它的 agents status 變 waiting 就是在問人
- 回 Workspace not trusted：請使用者在主檢出互動跑一次 claude 接受信任，不自己改 ~/.claude.json
- 請人回答背景 session：叫他開終端機跑 claude agents、選列按 Enter；提醒不要 Esc 兩次，看完關視窗

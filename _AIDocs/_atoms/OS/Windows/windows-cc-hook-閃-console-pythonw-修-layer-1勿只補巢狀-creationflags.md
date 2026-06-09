# Windows CC hook 閃 console — pythonw 修 layer-1，勿只補巢狀 creationflags

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 閃 console, console 視窗, hook 閃窗, pythonw, CREATE_NO_WINDOW, Windows hook, settings.json hook, GUI subsystem, 視窗標題
- Created-at: 2026-06-09
- Related: feedback-workflow-discipline, cc-能力查證反編譯實跑-binary, cognitive-patterns

## 知識

- [臨] **Windows 下 Claude Code hook 每輪閃一個 console 空視窗 = hook 解譯器自身（layer 1）被配 console，不是 hook 內部 subprocess（layer 2）。** GUI 行程（claude.exe，無主控台）spawn console-subsystem 子行程（python.exe）且未帶 CREATE_NO_WINDOW 時，Windows 會替它另配一個可見 console。hook 的 `command` 由 claude.exe spawn，console 在我方 script 任何程式碼執行『前』就配好了 → 在 script 內補 `creationflags` 改不到自己父行程的視窗。
- [臨] **診斷鐵律：先認 layer——看閃窗的視窗標題＝正在跑的執行檔路徑。** 標題是 `python.exe`/解譯器 → layer 1（interpreter）；是 `git.exe`/`svn.exe`/`node.exe` → layer 2（巢狀 subprocess）。本案標題 `…\AppData\Local\hermes\…\python.exe` 直指 layer 1，但前兩次修都補在 layer 2 的 git/svn status → 連兩次沒中（commit 1d73e55 自稱『根治』實為誤診）。輔證：grep 確認全 hook 巢狀 spawn 皆已帶 flag，仍閃 ⇒ 排除 layer 2，只可能 layer 1。
- [臨] **修法：`settings.json` hook 指令 `python -c "…"` → `pythonw -c "…"`。** `pythonw.exe` 是 GUI-subsystem 解譯器，Windows 永不配 console；stdio pipe 仍通（hook 走 stdin/stdout JSON，claude 一律 pipe → 實測 round-trip exit0）。`pythonw.exe` 與作用中（venv）`python.exe` 同層、PATH 先命中。layer-2 的 `creationflags=CREATE_NO_WINDOW` 保留＝互補非取代（Unix no-op）。settings 改動下個 session 生效。
- [臨] **殘留 / 限制**：`bash …user-init.sh`(SessionStart)、`webfetch-guard.sh`(WebFetch) 仍是 console-subsystem，只在 session 起始 / WebFetch 時閃（非每輪）；無 `bashw` 變體，要根治需用 `pythonw -c "subprocess.run(['bash',…], creationflags=0x08000000)"` 包裹。**可攜性**：`pythonw` 為 Windows-only，若 settings.json 跨 macOS/Linux 共用會炸（無 pythonw）——本機 settings.json 無 template、判定為個人檔故直接硬改。

## 行動

- Windows hook 閃 console：先看視窗標題認 layer，再決定改哪裡
- interpreter 級閃窗（標題=python.exe）→ settings.json 改 pythonw，勿只補巢狀 creationflags
- 巢狀 subprocess 閃窗（標題=git/node 等）→ 該 subprocess.run/Popen 補 creationflags=CREATE_NO_WINDOW

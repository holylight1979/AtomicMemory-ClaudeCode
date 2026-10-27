# memory/OS-Windows — 範疇索引

> 階層範疇索引（自動生成，`_` 前綴非 atom）。機制見 [[realm-範疇分區機制-v5]]。

## 本層 atom

| Atom | 說明 |
|------|------|
| bash同一命令多份heredoc時stdin是最後那份-fd前綴的不是stdin-小於號也換stdin-靜態判python減號只在單一heredoc且無其他輸入重導向時準 | bash同一命令多份heredoc時stdin是最後那份-fd前綴的不是stdin-小於號也換stdin-靜態判python減號只在單一heredoc且無其他輸入重導向時準 |
| claude-cli在新開終端機不在path-裝在家目錄local-bin要用完整路徑-cli版與vscode擴充版號不同-cp950主控台statusline印unicodeencodeerror | claude-cli在新開終端機不在path-裝在家目錄local-bin要用完整路徑-cli版與vscode擴充版號不同-cp950主控台statusline印unicodeencodeerror |
| dotnet的specialfolder不吃appdata環境變數-隔離測試要換別的手段 | dotnet的SpecialFolder不吃APPDATA環境變數-隔離測試要換別的手段 |
| pytest內subprocess抓子行程輸出遇cp950中文-reader-thread解碼炸掉-stdout變none-子行程要帶pythonutf8並errors-replace-python-i會忽略pythonioencoding | pytest內subprocess抓子行程輸出遇cp950中文-reader-thread解碼炸掉-stdout變None-子行程要帶PYTHONUTF8並errors-replace-python-I會忽略PYTHONIOENCODING |
| python-cli在cp950終端機印中文說明丟unicodeencodeerror-stdout與stderr改utf-8加errors-replace-會被同行程import的檔要放main開頭不放模組層 | python-cli在cp950終端機印中文說明丟UnicodeEncodeError-stdout與stderr改utf-8加errors-replace-會被同行程import的檔要放main開頭不放模組層 |
| shelltrue子行程帶create-no-window輸出整個不見-要直接印給人看的指令用no-window-exempt-壓窗守門紅了別一律補旗標 | shell=True子行程帶CREATE_NO_WINDOW輸出整個不見-要直接印給人看的指令用no-window-exempt-壓窗守門紅了別一律補旗標 |
| taskstop停背景bash在windows只停外殼-腳本與pytest子行程變孤兒繼續跑-要依父行程鏈手動結束 | TaskStop停背景Bash在Windows只停外殼-腳本與pytest子行程變孤兒繼續跑-要依父行程鏈手動結束 |
| unity-editorprefs-registry值名hash是djb2xor-字串binary-utf8結尾0-editor關著可直接寫 | unity-editorprefs-registry值名hash是djb2xor-字串binary-utf8結尾0-editor關著可直接寫 |
| unity-editor崩潰鑑識三路徑-事件檔1000先看故障模組-edr注入dll可能是真兇 | Unity-Editor崩潰鑑識三路徑-事件檔1000先看故障模組-EDR注入DLL可能是真兇 |
| whoami-輸出走-oem-碼頁-cp950-非-utf-8-中文群組名用-utf-8-解碼會靜默變亂碼 | whoami 輸出走 OEM 碼頁 cp950 非 utf-8-中文群組名用 utf-8 解碼會靜默變亂碼 |
| windows-新機-path-的-windowsapps-pythonexe-是-store-佔位程式-零輸出-exit-9009-子程序裸-spawn-python-必用絕對路徑 | Windows 新機 PATH 的 WindowsApps python.exe 是 Store 佔位程式-零輸出 exit 9009-子程序裸 spawn python 必用絕對路徑 |
| windows上node測試chdir進暫存夾後rmsync刪不掉當前目錄-空catch吞錯每跑一次留一個殘目錄-收尾先chdir離開再刪失敗印warn | windows上node測試chdir進暫存夾後rmSync刪不掉當前目錄-空catch吞錯每跑一次留一個殘目錄-收尾先chdir離開再刪失敗印warn |
| windows上python的附加寫入不是原子的-多行程同時append會互蓋切斷多位元組字元-要在旁檔鎖下一次寫完 | Windows上Python的附加寫入不是原子的-多行程同時append會互蓋切斷多位元組字元-要在旁檔鎖下一次寫完 |
| windows上用python轉印git輸出每行會帶r-接shell迴圈前要tr-d或python端用stdout-buffer寫位元組 | windows上用python轉印git輸出每行會帶r-接shell迴圈前要tr-d或python端用stdout-buffer寫位元組 |
| windows刪測試暫存目錄要先關本行程開著的log-handler並清唯讀屬性-rmtree-ignore-errors會默默留下整個目錄-初始化中斷也要能清 | Windows刪測試暫存目錄要先關本行程開著的log-handler並清唯讀屬性-rmtree-ignore-errors會默默留下整個目錄-初始化中斷也要能清 |
| windows剛被別的行程搬動或寫入的檔會短暫拒絕存取-資料夾內有開著的檔就搬不動-多行程搶檔要對permissionerror稍等重試 | Windows剛被別的行程搬動或寫入的檔會短暫拒絕存取-資料夾內有開著的檔就搬不動-多行程搶檔要對PermissionError稍等重試 |
| windows暫存區路徑是83短檔名-abspath不展開-路徑比對要用realpath | Windows暫存區路徑是8.3短檔名-abspath不展開-路徑比對要用realpath |
| windows的git把worktree的git檔設成隱藏-python直接覆寫會permissionerror-要先unlink再寫 | windows的git把worktree的.git檔設成隱藏-python直接覆寫會PermissionError-要先unlink再寫 |
| windows認證管理員blob上限-credwrite回傳值必檢-大token禁keyring | windows認證管理員blob上限-credwrite回傳值必檢-大token禁keyring |
| windows路徑包含判斷兩側要統一表示-先去長路徑前綴再normpath-轉長路徑後再normpath | Windows路徑包含判斷兩側要統一表示-先去長路徑前綴再normpath-轉長路徑後再normpath |
| winget-升不動-powershell-msi-與-msix-通道分裂 | winget 升不動 PowerShell — MSI 與 MSIX 通道分裂 |
| 子行程沙箱改暫存目錄要連tmpdir一起改-git-bash帶tmpdirtmp-gettempdir先看它 | 子行程沙箱改暫存目錄要連TMPDIR一起改-Git Bash帶TMPDIR=/tmp-gettempdir先看它 |
| 補子行程壓窗旗標前先看它的輸出要去哪-刻意印到主控台的子行程用no-window-exempt註記-掃描規則不是真理 | 補子行程壓窗旗標前先看它的輸出要去哪-刻意印到主控台的子行程用no-window-exempt註記-掃描規則不是真理 |

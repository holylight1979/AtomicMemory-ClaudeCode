# winget 升不動 PowerShell — MSI 與 MSIX 通道分裂

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: winget, pwsh, PowerShell 升級, powershell update, msix, exit 43, UPDATE_NOT_APPLICABLE, winget upgrade, winget list, Package Cache, Windows PowerShell 5.1
- Created-at: 2026-07-30
- Related: toolchain, windows-新機-path-的-windowsapps-pythonexe-是-store-佔位程式-零輸出-exit-9009-子程序裸-spawn-python-必用絕對路徑

## 知識

- [觀] winget 的 `Microsoft.PowerShell` 套件已轉成 **MSIX-only**（`winget show --installer-type msi` 回「找不到適用的安裝程式」）。若 PowerShell 7 是 MSI 裝在 `C:/Program Files/PowerShell/7`，winget 只沿用原安裝格式，`winget upgrade` 一律回 **exit 43 (UPDATE_NOT_APPLICABLE)** — 即使 `winget list` 顯示有新版。格式不相容，不是 bug。
- [觀] 正解：抓 GitHub release 官方 MSI（`PowerShell-<ver>-win-x64.msi`），SHA256 對 release notes 內文公布值。放任 winget 用 MSIX 會在 WindowsApps 多出第二份，Program Files 那份還留著。
- [觀] `/quiet` 主要升級**不沿用**舊安裝選項，必須先讀現況再原樣帶入：ADD_PATH、ADD_EXPLORER_CONTEXT_MENU_OPENPOWERSHELL（查 HKCR Directory/Background/shell/PowerShell7x64）、ADD_FILE_CONTEXT_MENU_RUNPOWERSHELL、ENABLE_PSREMOTING（查 WSMAN Plugin）、REGISTER_MANIFEST（查 WINEVT Channels PowerShellCore/Operational）、USE_MU + ENABLE_MU。
- [觀] `winget list --id <id>` **永遠比不中已安裝套件**：`--id` 比對本機 ARP 索引 id（登錄檔 GUID），表格「識別碼」欄顯示的卻是關聯到的來源目錄 id。查已安裝套件一律用 `--name`。
- [觀] PowerShell MSI 外面包一層 Burn bootstrapper，ARP 出現兩筆（MSI 本體 SystemComponent=1 隱藏 + bundle 可見）＝**正常，不是裝兩套**。但主要升級換掉 MSI product code 後 bundle 變孤兒：ARP 留幽靈項、Package Cache 留約 115 MB。清法＝跑 bundle 自己的 `/uninstall /quiet`（Burn 偵測其 MSI 已 superseded 會跳過，不誤刪新版），事前 `reg export` 備份。
- [觀] **Windows PowerShell 5.1 不可移除**（OS 元件），與 PowerShell 7 是兩個不同程式共用名字。開始功能表同時出現兩個是正確狀態。使用者問「怎麼還是兩個」時講這句就夠，不要展開。
- [觀] MSI 升級**不會**關掉既有 pwsh 行程（實測 VS Code 底下 3 個 pwsh 全部存活）。它們記憶體裡仍是舊映像，VS Code PowerShell 擴充會續報舊版並繼續跳更新提示 — 必須**整個重啟 VS Code**，但不需重開機。
- [觀] VS Code 更新提示來源是 `aka.ms/pwsh-buildinfo-stable`（非 GitHub API），比對對象是**擴充啟動的那顆 pwsh**，不是 PATH 上的。⚠️ `aka.ms/pwsh-buildinfo-lts` 實測仍指向 v7.4.18，設 `POWERSHELL_UPDATECHECK=lts` 會被叫去降級。
- [觀] 微軟語境的「Stable」是通道名（兩個 LTS 之間的非 LTS 線），不是「最新版」。lifecycle 頁把 7.5.x 叫 current Stable、7.6.x 叫 current LTS。7.6 支援到 2028-11-14；7.4 / 7.5 同於 2026-11-10 EOL。

## 行動

- 升級 PowerShell 7：直接抓 GitHub 官方 MSI，別靠 winget upgrade
- 查已安裝 winget 套件用 --name，不要用 --id
- /quiet 升級前先讀出現有 MSI 選項再原樣帶入
- 升級後檢查 ARP 與 Package Cache 是否留孤兒 bundle
- 收尾告知使用者：重啟 VS Code，不需重開機

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/corporate-launcher | lastmod: 2026-10-28 | section: Administration / Deployment -->
> 來源：https://code.claude.com/docs/zh-TW/corporate-launcher（官方 zh-TW，lastmod 2026-10-28）｜分類：Administration › Deployment｜EN 摘要：Route the processes Claude Code starts from its own binary, including the background service and every agent view session, through a required launcher with CLAUDE_CODE_PROCESS_WRAPPER or the processWrapper setting.

# 在公司啟動程式後面執行 Claude Code

> 使用 CLAUDE_CODE_PROCESS_WRAPPER 或 processWrapper 設定，透過必要的啟動程式路由 Claude Code 從其自身二進位檔案啟動的程序，包括背景服務和每個代理檢視工作階段。

某些組織要求工作站上的每個程序都透過強制性啟動程式啟動。啟動程式會應用沙箱、網路控制或認證注入，這些是公司安全態勢所依賴的，而不透過它啟動的二進位檔案是違反政策的。

`CLAUDE_CODE_PROCESS_WRAPPER` 透過您的啟動程式啟動 Claude Code 從其自身二進位檔案啟動的每個程序：[背景服務](https://code.claude.com/docs/zh-TW/agent-view.md#the-supervisor-process)、它在 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md)中託管的每個工作階段，以及 Claude Code 在更新後的重新啟動。將其設定為您的啟動程式的絕對路徑，Claude Code 會執行啟動程式，並將 Claude Code 命令作為其引數。

在您的 `PATH` 上包裝 `claude` 命令的啟動程式無法到達這些程序，因為它們從二進位檔案的直接路徑啟動，不會查詢 `claude`。

> [!NOTE]
>
> `CLAUDE_CODE_PROCESS_WRAPPER` 需要 Claude Code v2.1.208 或更新版本。較早的版本會忽略該變數，並啟動每個未包裝的程序。等效的 [`processWrapper` 設定](https://code.claude.com/docs/zh-TW/settings-reference#processwrapper)需要 v2.1.210 或更新版本。較早的版本會將其忽略為未知的鍵，不應用啟動程式，並且不報告任何錯誤。
>
> 部署任一形式後，使用[驗證步驟](#set-up-the-launcher)來確認執行中的版本應用了它。

## 啟動器涵蓋的內容

設定 `CLAUDE_CODE_PROCESS_WRAPPER` 後，Claude Code 會透過您的啟動器啟動以下每個程序：

* `claude agents` 和背景工作階段按需啟動的背景服務。
* 每個代理檢視列中的終端主機和 Claude Code 工作階段，包括服務保持就緒的暖待命工作階段。
* 服務在更新或當機後重新啟動的工作階段。
* Claude Code 執行自身重新啟動以完成更新安裝的情況，包括代理檢視的重新啟動以進行更新動作。
* [遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md)啟動的工作階段程序。需要 Claude Code v2.1.210 或更新版本。
* [代理團隊](https://code.claude.com/docs/zh-TW/agent-teams.md)在 tmux 或 iTerm2 中啟動的分割窗格隊友工作階段。隊友窗格是互動式的，而不是背景程序，但 Claude Code 從其自身二進位檔案啟動它們，所以啟動器涵蓋它們。需要 Claude Code v2.1.210 或更新版本。

在 Windows 上，該變數會被忽略：啟動器合約取決於 `exec`，而 Windows 不支援。設定了該變數的 Windows 機器會執行每個未包裝的程序並繼續運作，唯一的信號是[偵錯日誌](https://code.claude.com/docs/zh-TW/troubleshooting.md)中的警告。如果您的啟動器原則涵蓋 Windows，該變數在那裡不滿足它：在規劃推出時，將 Windows 機器計為未包裝。

### 在啟動器外啟動的程序

以下程序不會透過啟動器啟動：

* 您自己在終端中啟動的工作階段，其執行方式取決於您的調用方式。若要涵蓋這些工作階段，請在 `PATH` 上較早的目錄中放置一個名為 `claude` 的指令碼，該指令碼使用真實二進位檔案執行您的啟動器；不要取代受管理的符號連結。背景服務及其工作階段啟動時不進行 `PATH` 查詢，所以這兩個啟動器在那裡不會堆疊。
* 從 `claude-cli://` 深層連結開啟的工作階段，會在新的終端機中啟動，而不經過您的啟動器。若要防止深層連結為新使用者開啟工作階段，請在該使用者首次執行 Claude Code 之前，將 [`disableDeepLinkRegistration`](https://code.claude.com/docs/zh-TW/settings-reference#disabledeeplinkregistration) 設定為 `"disable"`。對於已有[已註冊處理程式](https://code.claude.com/docs/zh-TW/deep-links.md#registration-and-supported-platforms)的使用者，深層連結仍會繼續開啟工作階段，因為此設定不會移除處理程式。
* `--worktree` 結合 `--tmux` 執行的重新啟動：終端多工器啟動該窗格，而不是 Claude Code 的二進位檔案。
* [Chrome 中的 Claude](https://code.claude.com/docs/zh-TW/chrome.md) 註冊的原生訊息主機：瀏覽器啟動它，而不是 Claude Code 的二進位檔案。

### 程序監視器中的協助程序名稱

設定啟動器後，`ps` 和 Activity Monitor 不再顯示 Claude Code 的 `claude bg-pty-host` 和 `claude bg-spare` 標籤用於背景協助程序，因為啟動器的 `exec` 重建了引數清單。失去標籤是一個副作用，而不是隱瞞：程序在其他方面保持不變，Claude Code 透過二進位檔案路徑識別其自身程序，絕不透過顯示名稱。

## 設定啟動程式

**1. 編寫啟動程式指令碼**

在絕對路徑（例如 `/opt/corp/launcher`）建立可執行指令碼。Claude Code 使用完整的 Claude Code 命令作為其引數執行它，指令碼必須以呼叫 `exec "$@"` 結尾，以便它用 Claude Code 替換自身：

```bash theme={null}
#!/bin/sh
# Your organization's setup: enter the sandbox, apply
# network controls, or inject credentials.
exec "$@"
```

使用 `chmod +x` 使其可執行。設定部分是您的啟動程式在 Claude Code 執行前必須執行的任何操作；下面的[啟動程式合約](#the-launcher-contract)列出了指令碼必須遵循的規則。

> [!NOTE]
>
> 如果您之前用您的啟動程式替換了 `~/.local/bin/claude` 符號連結，請在同一變更中還原原始符號連結。替換的符號連結會導致第一個包裝的工作階段透過兩個啟動程式同時啟動背景服務，並將安裝置於外部受管理狀態：`/doctor` 會報告它，自動更新會將檔案保留在原位，舊版本的清理會保持禁用，直到安裝程式再次管理該路徑。

**2. 在設定中設定 CLAUDE\_CODE\_PROCESS\_WRAPPER**

在設定檔案的 `env` 區塊中設定變數，以便分離的背景服務繼承它。shell `export` 還不夠：背景服務按需啟動，超過您的 shell 的生命週期，並且永遠不會重新讀取 shell 設定檔。

對於一台機器，將其新增到 `~/.claude/settings.json`。要將其部署到組織中的每台機器，請在[受管理設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中放置相同的區塊：

```json theme={null}
{
  "env": {
    "CLAUDE_CODE_PROCESS_WRAPPER": "/opt/corp/launcher"
  }
}
```

當多個來源設定變數時，受管理設定值會覆蓋 `~/.claude/settings.json` 和 shell 中匯出的值，因此使用者無法將自我產生指向不同的啟動程式。

[`processWrapper` 設定](https://code.claude.com/docs/zh-TW/settings-reference#processwrapper)與具名的頂層設定金鑰具有相同的值。當您的組織以個別金鑰而非 `env` 區塊的方式推送設定時，請設定它。`processWrapper` 設定需要 Claude Code v2.1.210 或更新版本。下列設定檔案透過該金鑰設定相同的啟動程式：

```json theme={null}
{
  "processWrapper": "/opt/corp/launcher"
}
```

當兩者都設定時，`CLAUDE_CODE_PROCESS_WRAPPER` 優先。

因為 `processWrapper` 是具名設定，透過[遠端受管理設定](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)傳遞它的組織會在[安全核准對話](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-approval-dialogs)上看到它與其他執行管理員提供的可執行檔的設定一起列出。

專案和本機設定無法設定啟動程式。提交到儲存庫的檔案不得能夠將二進位檔案放在機器上的每個 Claude Code 程序前面，因此 Claude Code 會忽略 `.claude/settings.json` 或 `.claude/settings.local.json` 中的 `CLAUDE_CODE_PROCESS_WRAPPER`，並在[偵錯日誌](https://code.claude.com/docs/zh-TW/troubleshooting.md)中發出警告，並且永遠不會從這些檔案讀取 `processWrapper` 金鑰。

**3. 重新啟動背景服務和您的工作階段**

執行中的背景服務和任何開啟的 `claude` 工作階段在啟動時讀取變數一次，因此它們會繼續啟動未包裝的程序，直到重新啟動。執行 `claude daemon stop --any` 以停止按需服務。下一個需要它的命令（例如 `claude agents`）會啟動一個包裝的服務。然後重新啟動您開啟的 `claude` 工作階段。

在您無法手動重新啟動的機器上，設定推送後啟動的第一個工作階段會自動淘汰遺留的未包裝按需服務。沒有新工作階段啟動的機器會保留其未包裝的背景服務，直到有工作階段啟動為止。

**4. 驗證**

在工作階段中執行 `/status`：Self-exec 項目顯示已解析的啟動命令，並在執行中的背景服務與其不匹配時發出警告。`claude daemon status` 從 shell 列印相同的資訊，包括在您取消設定變數後，當 `/status` 不再顯示該項目時。

## 啟動程式合約

當啟動程式無法執行時，Claude Code 拒絕啟動程序，而不是啟動它未包裝。在 Windows 上，[變數被忽略](#what-the-launcher-covers)，程序啟動未包裝。Claude Code 對指令碼遵循這些規則：

* **以 `exec "$@"` 結尾。** 分叉子程序並退出的啟動程式會留下孤立的 Claude Code 程序，背景服務無法追蹤。代理檢視會將此類工作階段標記為失敗，並顯示命名啟動程式的訊息，服務會清理啟動程式留下的內容。
* **不要重新排序、吸收或新增 Claude Code 的引數。** 移除啟動程式[自己的引數](#pass-arguments-to-the-launcher)（這些引數位於最前面），並將其餘引數按原樣傳遞給 `exec`。
* **將每個繼承的環境變數傳遞給 `exec`。** 新增變數（例如注入的認證）沒問題；刪除繼承的變數不行。
  * 每個工作階段的驗證令牌、模型和提供者選擇，以及 `CLAUDE_CODE_PROCESS_WRAPPER` 本身都在繼承的環境中傳遞，因此從允許清單重建環境的啟動程式會破壞它啟動的工作階段，`/status` 會報告啟動程式不匹配。
  * 如果啟動程式必須進入重設環境的命名空間或沙箱，請在其內部逐字重新匯出繼承的環境。
* **在啟動程式每次執行時約三秒內到達 `exec`。** 背景工作階段在產生第一個輸出之前，可能會連續執行啟動程式三次。請以延遲方式或從快取執行緩慢的工作，例如單一登入交換，並為任何等待網路的步驟設定其自己的時間限制。
* **容忍從內部叫用自身。** Claude Code 將啟動程式應用於每個嵌套的自我產生，因此獲取獨佔資源的啟動程式必須偵測它是否已持有它。
* **在 Claude Code 啟動前不要寫入終端機或標準輸出。** 在 `exec` 前列印的任何內容都會在工作階段於初始化前終止時被報告為當機原因。標準輸出上的文字也會傳到讀取 Claude Code 輸出的程式，例如剖析 `claude -p` 結果的指令碼。
* **不要依賴引數的拼寫方式。** 旗標的值可能作為獨立的引數傳入（`--flag value`），也可能與旗標連接在一起（`--flag=value`）。旗標使用哪種形式可能會在不同版本之間變更。
* **從啟動程式啟動時所在的目錄執行 `exec`。** Claude Code 會在其啟動時所在的目錄中運作，因此變更目錄的啟動程式可能會在錯誤的專案中啟動工作階段。如果啟動程式必須進入會重設工作目錄的命名空間或沙箱，請在其內部、於 `exec` 之前切換回起始目錄。
* **不要讀取標準輸入。** 在 `exec` 之前讀取標準輸入的命令（例如要求輸入密碼的命令）可能會等待永遠不會到來的輸入，導致工作階段卡住。它也可能取走原本要給 Claude Code 的輸入，工作階段接著可能在缺少該輸入的情況下執行，且不會報告任何錯誤。請將此類命令的輸入重新導向自 `/dev/null`。
* **以絕對路徑呼叫其他程式。** 啟動程式啟動時的 `PATH` 可能不包含您的 shell 設定檔所新增的目錄。

### 啟動程式值的格式

`CLAUDE_CODE_PROCESS_WRAPPER` 和 `processWrapper` 設定採用相同的格式。對於大多數啟動程式，該值是指令碼的絕對路徑，例如 `/opt/corp/launcher`。

要傳遞您的啟動程式自己的引數，請在路徑後寫入它們。Claude Code 將該值解析為引數清單，而不是 shell 命令：

* 空白分隔 token，雙引號將包含空格的 token 分組。單引號是一般字元，因此 `'a b'` 是兩個 token。
* 以 `[` 開頭的值被讀取為 JSON 字串陣列，例如 `["/opt/corp/launcher", "--profile", "cc"]`。
* Shell 語法不起作用：沒有變數擴展或全域化，未引用的運算子（例如 `;`、`|`、`&` 或 `$(`）被拒絕為設定錯誤，而不是重新解釋。

當無法使用該值時，Claude Code 拒絕啟動受影響的程序並[報告原因](https://code.claude.com/docs/zh-TW/errors.md#claude_code_process_wrapper-launcher-errors)。

在設定檔中，請將陣列形式寫在 JSON 字串內，並跳脫其引號：`"[\"/opt/corp/launcher\", \"--profile\", \"cc\"]"`。

### 將引數傳遞給啟動程式

請將啟動程式自己的引數寫在[該值](#format-of-the-launcher-value)中的路徑之後，並在指令碼中於 `exec` 呼叫之前將其移除。這些引數會最先傳入指令碼，位於 Claude Code 命令之前。以下指令碼是針對值 `/opt/corp/launcher --profile cc` 所撰寫，它會儲存設定檔名稱，然後以 `shift` 移除這兩個引數：

```bash theme={null}
#!/bin/sh
if [ "$1" = "--profile" ]; then
  profile="$2"
  shift 2
fi
# Your organization's setup for "$profile".
exec "$@"
```

使用[驗證步驟](#set-up-the-launcher)查看 Claude Code 從該值解析出的啟動命令。

## 與 `CLAUDE_CODE_SHELL_PREFIX` 的關係

`CLAUDE_CODE_PROCESS_WRAPPER` 包裝 Claude Code 自己的程序，並將命令作為單獨的 argv 令牌傳遞給啟動程式以執行。[`CLAUDE_CODE_SHELL_PREFIX`](https://code.claude.com/docs/zh-TW/env-vars) 包裝 Claude Code 代表您執行的 shell 命令，例如 Bash 工具呼叫、hooks 和啟動 stdio MCP 伺服器的命令，並將每個命令作為 `$1` 中的單個 shell 引用字串傳遞給包裝程式以重新評估。為一個編寫的啟動程式不會作為另一個工作。

## 相關資源

* [代理檢視](https://code.claude.com/docs/zh-TW/agent-view.md)：啟動程式涵蓋的背景工作階段和監督程序
* [環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)：`CLAUDE_CODE_PROCESS_WRAPPER` 參考項目
* [受管理設定](https://code.claude.com/docs/zh-TW/permissions.md#managed-settings)：在整個機隊中傳遞 `env` 區塊
* [啟動程式錯誤參考](https://code.claude.com/docs/zh-TW/errors.md#claude_code_process_wrapper-launcher-errors)：拒絕訊息以及如何恢復

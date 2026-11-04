<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/claude-projects | lastmod: 2026-10-30 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/claude-projects（官方 zh-TW，lastmod 2026-10-30）｜分類：Getting started › Platforms and integrations｜EN 摘要：Hand Claude a stream of related tasks in one conversation and let it run them as parallel cloud sessions that share repositories, instructions, and memory.

# 讓 Claude 使用 Projects 協調進行中的工作

> 在一個對話中為 Claude 提供一組相關的工作，讓它協調共享儲存庫、指示和記憶的平行雲端工作階段。

> [!NOTE]
>
> Projects 在 Pro、Max 和 Ultra 方案上處於公開測試版，並正在逐步推出。推出首先針對已使用 [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 且在 claude.ai 聊天或 Cowork 中沒有現有專案的帳戶。Projects 目前尚未在 Team 或 Enterprise 方案上提供。
>
> 如果 **Projects** 沒有出現在 [claude.ai/code](https://claude.ai/code) 的側邊欄中或 [桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md) 的 Code 標籤中，請查看該處的 **More** 底下。如果那裡也沒有，表示推出尚未到達您的帳戶。您可以 [加入等候清單](https://claude.com/form/projects)，並參閱 [平行執行 agent](https://code.claude.com/docs/zh-TW/agents.md) 了解您在此期間可以使用的內容。

專案是一個進行中的對話，Claude 在其中為您協調一系列相關工作。您告訴它需要做什麼，它會為每個任務啟動一個執行緒。

每個執行緒通常是一個 [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)：Claude Code 在雲端而不是在您的機器上執行。當任務需要只有您的電腦才有的東西時，您可以要求 Claude 改為透過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 在您的電腦上 [執行該執行緒](#run-a-thread-on-your-own-computer)。執行緒平行執行，您可以從您的手機檢查它們並引導它們。雲端執行緒在您關閉筆記型電腦後會繼續進行，而您電腦上的執行緒只在該電腦保持開啟時執行。

沒有專案的情況下，執行多個工作階段意味著自己進行協調：您決定每個工作階段要處理什麼，在每個工作階段的開始重複相同的背景資訊，並檢查哪個已完成或需要答案。使用專案，您可以改為：

* **將工作發送到一個地方**：每當出現時，將錯誤報告、堆疊追蹤或任務清單貼到對話中。Claude 為每個工作片段啟動一個執行緒，或將其傳遞給已在該區域工作的執行緒，並就地回答快速問題。
* **設定一次背景資訊**：每個新執行緒都以專案的指示開始，因此您陳述一次的規則（例如要針對的分支）會到達所有執行緒。
* **離開並返回已完成的工作**：當您一小時後或第二天早上回來時，**Overview** 窗格會顯示哪些執行緒已完成、哪些提取請求已準備好供審查，以及哪個執行緒正在等待您的答案。

如果您已經知道希望專案執行的工作，請直接前往 [建立專案](#create-a-project)。

## 何時使用 project

當工作有一個超越單個工作階段的目標並持續產生任務時，創建 project 是值得的。這些類型的工作非常適合 project：

* **跨多個儲存庫的一個目標**："將每個服務升級到新的 lint 配置。" Claude 可以為每個儲存庫執行一個執行緒，每個都有自己的提取請求，[**Overview** 窗格](#see-what-needs-you-in-overview) 會顯示哪些已準備好供審查。
* **您持續提供的區域**：一個服務的錯誤、堆疊追蹤和審查請求，在到達您時貼到對話中。您告訴 Claude 在一個修復後要記住的陷阱在 [project 記憶](#give-a-project-standing-context) 中供下一個使用。
* **比工作階段更大的構建或遷移**："構建 `docs/spec.md` 描述的內容"或"將應用程式從已棄用的 ORM 移出。" 工作分成執行緒，每個執行緒處理一部分，您要求 Claude 早期記住的決定會到達後來的執行緒，您在構建期間發現的規格變更和錯誤進入相同的對話。
* **不是程式碼的工作**：一個合約資料夾或支援票證匯出，您不斷回來提出新問題，例如"在這些票證中找到十個最常見的整合錯誤。" 上傳文件而不是添加儲存庫，執行緒會在 project 的 [**Library** 標籤](#see-what-needs-you-in-overview) 上將每個寫作作為檔案提供。

在任何一種情況下，您都可以發送一批任務，告訴 Claude 在不要求您確認的情況下開始，然後離開。當您回來時，可以在 [**Waiting on you**](#see-what-needs-you-in-overview) 下找到需要您的執行緒。您也可以要求 Claude 將部分工作放在時間表上，作為 [雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)。如果這是您的情況，[建立 project](#create-a-project)。

### 何時其他方式更合適

當只有某些任務需要您的機器時，project 仍然適合。Cloud threads 在 GitHub 儲存庫以及您上傳到 project 的檔案、資料夾和 Google Drive 資料夾上工作，而對於偶爾需要本地資料庫或您電腦上工具的任務，您可以要求 Claude [在您自己的電腦上執行該任務的執行緒](#run-a-thread-on-your-own-computer)。在這些情況下，project 以外的方式更合適：

* **一個適合工作階段的任務**："修復不穩定的登入測試。" 自己啟動 [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)。
* **每個任務都需要您的機器的工作**：本地資料庫、設備模擬器或您 VPN 後面的 API。使用本地工作階段，或 [agent view](https://code.claude.com/docs/zh-TW/agent-view.md) 同時執行多個。如果工作只需要本地檔案，請改為將它們上傳到 project。
* **一個按時間表重複的任務，周圍沒有對話**：「每週一發佈相依性報告。」單獨建立一個 [雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)。
* **多個人在 Slack 頻道中給 Claude 工作並一起引導它**：請參閱 [Claude Tag](https://claude.com/docs/claude-tag/overview)。

Project 使用與您其他 Claude Code 工作階段相同的方案限制，並更快地使用它們。[使用和成本](#usage-and-cost) 涵蓋了什麼使用您的方案以及如何降低它。

## Project 如何組織

Project 是一個協調對話加上它啟動的執行緒來完成工作。這些是它的部分：

* **project 對話**：一個長期執行的工作階段，Claude 充當協調者。它接收您發送的內容，決定什麼成為執行緒，並跟蹤它啟動的每個執行緒。它看到執行緒報告回來的內容，而不是它們採取的每一步。
* **執行緒**：工作者。每個都是一個單獨的工作階段，有自己的上下文視窗，完成一項工作並在完成時報告回對話。雲端執行緒在自己的分支上工作，並在工作需要時打開提取請求。
* **每個雲端執行緒開始時的內容**：
  * project 的儲存庫和檔案，加上其 [指示和記憶](#give-a-project-standing-context)
  * [project 每個儲存庫](#what-threads-pick-up-from-your-repositories) 中的 `CLAUDE.md`，但不包括這些儲存庫的 skill、`.claude/settings.json` 或 `.mcp.json`
  * 您 claude.ai 帳戶上的 [連接器](#get-skills-plugins-connectors-and-tools-into-threads)
  * 一個 [雲端環境](#choose-an-environment-for-threads)，設定其網路存取、環境變數、網路密鑰和已安裝的工具
* **Overview 窗格**：您在其中 [一次看到所有執行緒](#see-what-needs-you-in-overview) 以及其中哪些需要您。其他標籤是 **Library** 用於您添加的檔案和執行緒產生的檔案，**Pull requests** 用於執行緒開啟的 pull request，**Scheduled tasks** 用於 project 中的排程工作。

雲端執行緒不會從您自己機器上的 Claude Code 設定中選擇任何內容。[將 skills、plugins、connectors 和工具放入執行緒](#get-skills-plugins-connectors-and-tools-into-threads) 涵蓋了如何給予它們否則會缺少的內容。

以下是這些部分如何連接的方式，從您通過對話到執行工作的執行緒，**Overview** 跟蹤其狀態：

![Project 的圖表。您在 project 對話中寫入，Claude 回答或啟動執行緒。每個雲端執行緒在自己的分支和提取請求上工作。Overview 窗格按狀態列出執行緒，例如準備好供審查、等待您和工作中。](https://mintcdn.com/claude-code/e8CLbxM17eD7cAiv/images/claude-projects-overview.svg?fit=max\&auto=format\&n=e8CLbxM17eD7cAiv\&q=85\&s=dbf446f69f0bbdb9961d21af207cb93b)

## 建立專案

您可以在 [claude.ai/code](https://claude.ai/code)、桌面應用程式的 Code 分頁，或適用於 [iOS](https://apps.apple.com/us/app/claude-by-anthropic/id6473753684) 和 [Android](https://play.google.com/store/apps/details?id=com.anthropic.claude) 的 Claude 行動應用程式中建立和使用專案。在瀏覽器和桌面應用程式中，有兩種方式可以開始一個專案：

* **從頭開始**：當您知道要讓 Claude 執行的工作流程時，開啟 **New project** 對話方塊並為其命名。[從頭開始建立新專案](#start-a-new-project-from-scratch)會逐步說明此對話方塊。
* **從已在進行該工作的雲端工作階段開始**：在該工作階段的側邊欄選單中，選擇 **Continue in project**，然後選擇 **Continue as new project**。Claude 會根據該工作階段正在進行的工作，提出專案的設定建議。請參閱[從現有的雲端工作階段開始](#start-from-an-existing-cloud-session)。

無論採用哪種方式，請先[檢查先決條件](#check-the-prerequisites)。

### 檢查先決條件

在建立專案之前，請檢查您的方案、GitHub 設定，以及工作需要存取的資源：

* **方案**：您使用的是 Pro、Max 或 Ultra 方案，且 **Projects** 會直接顯示在側邊欄中，或顯示在 **More** 之下。選取 **Projects**，並確認其提供 **New project** 或 **Get started**。
* **GitHub（如果專案將處理程式碼）**：您的程式碼位於 github.com，而非 GitHub Enterprise Server、GitLab 或 Bitbucket；您連接的 GitHub 帳戶具有推送權限；且已在其上安裝 Claude GitHub App。如果您是透過 [`/web-setup`](https://code.claude.com/docs/zh-TW/web-quickstart#connect-from-your-terminal) 連接 GitHub，該 token 可讓您的其他雲端工作階段存取儲存庫，但不足以供專案的雲端執行緒使用，因為這些執行緒需要 Claude GitHub App。[設定 GitHub 存取](#set-up-github-access)中有相關步驟。
* **網路存取、密鑰和工具**：對於雲端執行緒，這些來自專案的[雲端環境](#choose-an-environment-for-threads)。預設環境已可存取[常見的套件登錄庫](https://code.claude.com/docs/zh-TW/cloud-environments.md#default-allowed-domains)，因此只有在工作需要其他網域、密鑰或未預先安裝的工具時，才需要檢查此項目。如果工作需要 MCP 伺服器，請確認它在您的 [claude.ai 連接器](https://claude.ai/customize/connectors)中顯示為已連接。

### 從頭開始建立新專案

從頭開始建立專案，是指開啟 **New project** 對話方塊、為工作流程命名，並可選擇為其設定目標以及其處理的儲存庫和檔案。只有名稱是必填的，因此您可以先建立專案，再隨著工作成形逐步補齊其餘內容。

**1. 開啟 Projects**

在 [claude.ai/code](https://claude.ai/code) 或桌面應用程式的 Code 分頁中，選取左側側邊欄中的 **Projects**，或其中 **More** 之下的 **Projects**。在瀏覽器中，您也可以直接前往 [claude.ai/code/projects/browse](https://claude.ai/code/projects/browse)。然後選取 **New project**。如果按鈕顯示的是 **Get started**，請選取它，並先升級或封存其中列出的現有 claude.ai 專案。

**2. 填寫 New project 對話方塊**

將專案範圍限定為您會持續累加的單一工作流程，例如讓某個 API 維持在延遲目標以下所需的一切工作。[何時使用專案](#when-to-use-a-project)中有更多範例。接著填寫對話方塊中的欄位：

* **Name**：專案在 **Projects** 清單中顯示的名稱。
* **Goal**（選填）：用一行描述您想完成的事，例如「將 p95 API 延遲維持在 200 ms 以下」。對話中的 Claude 會朝此目標努力。如果沒有目標，Claude 會依據您傳送的任務工作，您之後也可以在 **Project settings > General** 中新增目標。
* **Context**（選填）：此專案處理的 GitHub 儲存庫，以及執行緒應讀取的任何檔案、資料夾或 Google Drive 資料夾。每一項都請點選 **Add** 來新增。請新增大多數任務需要的儲存庫，而不是工作可能涉及的每一個儲存庫；[決定要新增哪些儲存庫](#decide-which-repositories-to-add)說明了如何選擇，您之後也可以在 **Project settings > Environment** 中新增更多儲存庫。

關於執行緒應如何工作的長期規則，請放在[專案指示](#give-a-project-standing-context)中，您可以在專案建立後設定。

**3. 建立專案**

點選 **Create project**。專案的對話會開啟，底部有一個訊息方塊，您可以在其中向 Claude 描述工作。

在您的第一個專案中，除非您先傳送訊息，否則 Claude 會在專案建立後立即自行進行一個回合。該回合會使用您的方案額度。在此回合中，Claude 可能會：

* 如果專案有可讀取的儲存庫，啟動一個執行緒來探索該儲存庫（不做任何變更），並提出後續步驟建議。
* 根據您最近的雲端工作階段發布 **Setup recommendations**：要新增的儲存庫、要建立的排程任務，以及它可以啟動的執行緒。每個建議的儲存庫和排程任務一開始都是開啟狀態。請關閉您不想要的項目，然後點選 **Update setup** 新增其餘項目，或忽略這些建議並自行描述工作。

專案現在會列在側邊欄的 **Projects** 之下，且其對話已開啟。[您的第一批工作](#your-first-batch)說明了在傳送工作之前需要設定的項目。

### 從現有的工作階段開始

如果您自行啟動的雲端工作階段正在進行屬於某個專案的工作，請開啟其側邊欄選單並選擇 **Continue in project**，然後從子選單中選擇：

* 選擇 **Continue as new project**，從該工作階段建立新專案。專案會開啟，Claude 會讀取該工作階段，並在專案對話中發布 **Setup recommendations** 供您確認。原始工作階段會保留在您的工作階段清單中。如果它正在進行某個回合，該回合會繼續執行，因此如果您不希望兩者同時運作，請自行停止它。
* 選擇您的某個現有專案，將該工作階段的工作帶入該專案。該專案會開啟，並會代表您傳送一則訊息，請 Claude 讀取該工作階段並從中斷處接續。原始工作階段會保留在您的工作階段清單中，維持不變。

雲端工作階段的訊息方塊上方也可能出現 **Set up project** 橫幅。如果您使用它而非 **Continue as new project**，結果相同，只是該工作階段正在執行的回合會在專案開啟後停止。

在您自己電腦上的工作階段，一旦透過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md#start-a-remote-control-session) 連接，在 claude.ai/code 上也會有相同的側邊欄選單。在專案中，Claude 無法讀取在您帳戶開啟 [**Require trusted devices**](https://code.claude.com/docs/zh-TW/remote-control.md#trusted-devices) 時所連接之工作階段的逐字稿。如果該設定為關閉：

1. 如果工作階段尚未連接，請在其中執行 `/remote-control`。如果它是在該設定開啟時連接的，請先中斷連接，再重新連接。
2. 在瀏覽器中，於 [claude.ai/code](https://claude.ai/code) 的側邊欄找到該工作階段的列，開啟其選單，並從相同的子選單中選擇。

如果 **Require trusted devices** 為開啟，或您未使用 Remote Control，請自行在專案對話中描述工作。或者，推送該工作階段的分支，將其儲存庫新增至專案，並告訴 Claude 分支名稱。

### 設定 GitHub 存取

大部分的 GitHub 設定只需進行一次，而不是每個專案都要重新設定。您只需將 GitHub 帳戶連接到 Claude 一次，而 Claude GitHub App 則是每個儲存庫安裝一次；如果您授予它所有儲存庫，則整個 GitHub 組織只需安裝一次。當您新增 Claude GitHub App 尚未涵蓋的儲存庫，或新增位於強制使用 SSO 的 GitHub 組織中的儲存庫時，才需要再回到這些步驟。

**1. 連接您的 GitHub 帳戶**

如果您之前未使用過 claude.ai/code，首次造訪時會引導您連接 GitHub；請參閱[連接 GitHub](https://code.claude.com/docs/zh-TW/web-quickstart.md#connect-github)。否則，請使用其中一種 [GitHub 身分驗證選項](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#github-authentication-options)。

**2. 在專案的儲存庫上安裝 Claude GitHub App**

安裝 [Claude GitHub App](https://github.com/apps/claude)，並授予它專案將使用的儲存庫。對於 GitHub 組織擁有的儲存庫，只有組織擁有者才能完成安裝；如果您不是擁有者，GitHub 會向擁有者傳送安裝請求，在擁有者核准之前，專案無法使用該儲存庫。

**3. 為強制使用 SSO 的組織授權 SSO**

如果某個 GitHub 組織強制使用 SAML SSO，請重新連接 GitHub，並為該組織授權 Claude 應用程式。在您完成授權之前，該組織的私人儲存庫不會出現在 **New project** 對話方塊或 **Project settings > Environment** 中。

當其中某個步驟未完成時，**New project** 對話方塊和專案頁面會指出缺少的步驟，並連結到您可以完成該步驟的位置。請在該處完成步驟，然後若對話方塊提供 **Check again**，請點選它。如果之後某個儲存庫仍未出現在清單中，請在 GitHub 上開啟 Claude GitHub App 的安裝頁面（個人帳戶位於 [github.com/settings/installations](https://github.com/settings/installations)），並確認該儲存庫列在 **Repository access** 之下。關於存取權限仍有誤時，執行緒或專案回報的錯誤訊息，請參閱[儲存庫存取錯誤](#repository-access-errors)。

## 在 project 中工作

通過 project 對話給 Claude 工作：一次一個任務或一次多個，加上更新和鬆散的想法。Claude 路由每條訊息，執行緒執行工作並報告回。

### 您的第一批

在您向新 project 發送一批工作之前，設定它，以便第一個執行緒以您想要的方式回來：

1. [寫 project 指示](#write-project-instructions)：每個執行緒開始的簡報，例如要針對的分支、執行緒如何檢查其工作，以及什麼需要您的同意。
2. 發送一個真實工作的小片段，或啟動 Claude 建議的其中一個執行緒（如果它提供了任何），並在它完成時打開執行緒，以查看它如何報告回以及它在分支上做了什麼。如果它假設了錯誤的內容或無法到達它需要的內容，[執行緒猜測或停滯而不是詢問](#threads-guessed-or-stalled-instead-of-asking) 涵蓋了在哪裡修復。
3. 檢查 **Project settings > General** 中的 **Thread model** 和 **Thread effort**。新 project 在高努力下在 Opus 上執行每個執行緒，這最快地使用您的方案；[選擇模型並讓 Claude 管理上下文](#choose-models-and-let-claude-manage-context) 涵蓋了替代方案。
4. 要求 Claude [在啟動執行緒之前提議執行緒並一次執行幾個](#tune-how-claude-runs-a-project)，並在幾個執行緒以您想要的方式回來後放棄這些限制。

### 發送工作並讀取結果

Claude 決定您在對話中發送的每條訊息去向：

* 快速問題通常在對話中得到回答。
* 新工作進入新執行緒或已在該區域工作的執行緒，Claude 告訴您哪個。每個新執行緒在您的訊息下顯示為卡片：一個帶有執行緒標題和狀態的框，您點擊打開執行緒。
* 一條訊息中的多個不相關任務成為單獨的執行緒。

如果 Claude 路由的內容與您想要的不同，請說出來。[調整 Claude 執行 project 的方式](#tune-how-claude-runs-a-project) 列出了您可以告訴它的內容，例如為後續工作重用現有執行緒或就地回答而不是啟動執行緒。

執行緒的完整結果保留在執行緒中，您打開對話中的卡片來讀取它們。執行緒產生的檔案也在 **Overview** 中的 **Library** 標籤上。

有時 Claude 在 **Suggested threads** 清單中提議執行緒而不是啟動它們。點擊建議上的箭頭啟動該執行緒。當列出多個時，清單下的按鈕啟動所有這些。

### 審查執行緒的提取請求

當執行緒更改程式碼時，除非您另外告訴它，否則它會執行以下操作：

* **Branch**：在新分支上工作，從儲存庫的預設分支開始。
* **Pull request**：當您要求時打開一個，並可以為錯誤修復或另一個具體變更自己打開一個。
* **打開後**：使用 [auto-fix](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#auto-fix-pull-requests) 打開監視提取請求，無論 auto-fix 是否對您的其他雲端工作階段打開。它在 CI 失敗時推送修復，解決審查評論，並在檢查通過且提取請求準備好供您審查時在執行緒中回覆。

當執行緒推送了分支或打開了提取請求時，其在對話中的卡片可以顯示下一步的按鈕：

* **Resolve conflicts**、**Fix CI**、**Address comments** 和 **Merge it** 將該指示作為來自您的訊息發送到執行緒，因此您可以自己提示執行緒而不是等待它對提取請求做出反應。
* **Review PR** 在 GitHub 上打開提取請求。
* **Create PR** 出現在閒置執行緒已推送分支但尚未打開提取請求時。點擊它會直接從該分支建立提取請求，而不是向執行緒發送打開提取請求的指示。

要更改執行緒何時打開提取請求，例如僅在您要求時，或它們從哪個分支開始，請在任務或 [project 指示](#write-project-instructions) 中說出來。

### 在 Overview 中查看需要您的內容

**Overview** 窗格在對話旁邊跟蹤 project 的執行緒。它在您第一次打開新 project 時已經打開。project 標題中的 **Overview** 按鈕關閉並重新打開它，並在執行緒等待您時顯示一個點。

在桌面應用程式中，當 Claude 在對話中發佈、執行緒遇到錯誤或執行緒需要您的輸入時，您還會收到桌面通知，因此您不必保持 project 打開來找出。要在每次執行緒完成一個回合時也收到一個，或為 project 關閉它們，請在 project 的側邊欄功能表中選擇 **Notifications**。這些通知僅限桌面：在瀏覽器中，檢查 **Overview** 按鈕上的點。

窗格的 **Threads** 標籤按狀態對執行緒進行分組：

| 群組 | 其中的內容 |
| :- | :- |
| **Ready for review** | 提取請求已打開並等待審查的執行緒 |
| **Waiting on you** | 需要您回覆或批准的執行緒，或失敗的執行緒 |
| **Working** | 仍在執行的執行緒 |
| **Landing** | 提取請求已批准或排隊合併的執行緒 |
| **Idle** | 已完成且不等待任何內容的執行緒 |
| **Resolved** | 標記為完成的執行緒：由您從執行緒的功能表中，由 Claude 在您採取最後一步後（例如合併其提取請求），或在一週無活動後自動。您可以從相同功能表重新打開一個 |

窗格的其他標籤是：

* **Library**：您新增的檔案和資料夾，以及執行緒產生的檔案
* **Pull requests**：在執行緒打開任何 pull request 後顯示
* **Scheduled tasks**：Claude 從此 project 設定的[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)

### 當您需要控制時打開執行緒

點擊對話中執行緒的卡片或 **Overview** 中的其行，在 Overview 窗格中打開其記錄。從那裡您可以：

* 逐步讀取 Claude 所做的內容。
* 通過在執行緒自己的訊息框中寫入來引導任務。那裡的訊息直接進入該執行緒，而 project 對話中的後續工作只有在 Claude 將後續工作與該執行緒匹配時才會到達它。
* 回答執行緒正在等待的權限提示。
* 使用 **Stop** 中斷執行緒，它在執行緒工作時替換發送按鈕，或按 Esc。

### 選擇模型並讓 Claude 管理上下文

在 **Project settings > General** 中設定模型和努力。新 project 在高 [effort](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level) 下為執行緒和低努力下為對話在任何地方執行 Opus：

* **Thread model** 和 **Thread effort** 適用於執行緒。要為一個任務使用不同的模型，在任務中要求它；對於已在執行的執行緒，使用該執行緒的模型選擇器。
* **Coordinator model** 和 **Coordinator effort** 適用於 project 對話中的 Claude。

您不在 project 中管理上下文視窗。執行緒自動壓縮，對話從最近的訊息、最近的執行緒和 project 記憶而不是其完整歷史工作，因此它只要 project 執行就繼續。將任何必須永遠不被丟棄的內容放在 [project 記憶](#give-a-project-standing-context) 中。如果一個執行緒超出其上下文，它會顯示 [Claude ran out of context on this turn](#context-limit)。

### 調整 Claude 執行 project 的方式

在對話中告訴 Claude 一次執行多少執行緒、何時發佈更新以及何時打開提取請求。如果 Claude 以您不想要的方式協調，請說出來。例如，您可以說：

* "提議執行緒並在啟動之前等待我的同意"或"立即啟動這些而不要求我確認"
* "一次最多執行兩個執行緒"或"為同一區域的後續工作重用現有執行緒"
* "發佈更短的更新"或"僅在某些完成或被阻止時發佈"
* "給我每個執行緒的狀態更新"
* "用較小的模型執行此任務"
* "在我看到計劃之前不要打開提取請求"
* "告訴我這些儲存庫中的問題，不要修復任何內容"，當您想在任何內容成為執行緒之前查看發現時
* "改為在這裡回答"，當 Claude 為您打算作為快速問題的內容啟動執行緒時

Claude 自動將這些偏好保存到 [project 記憶](#give-a-project-standing-context)，並在後來的執行緒中遵循它們。它們是 Claude 遵守的指示，而不是強制執行的設定，因此您以這種方式給出的執行緒限制不是硬上限。當您想要它精確措辭並從一開始應用於每個執行緒時，將一個添加到 project 指示。

### 解除等待批准的執行緒

當執行緒的模型支援時，執行緒在 [auto mode](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 中執行，因此大多數工具呼叫執行而不詢問您。當執行緒需要您的批准時，提示在該執行緒內，執行緒等待直到您在那裡回答。在 project 對話中告訴 Claude 繼續不會到達它。

每次核准涵蓋該權限提示，或者如果您選擇更廣泛的選項，則涵蓋該執行緒的其餘部分。雲端執行緒不會從儲存庫的 `.claude/settings.json` 讀取[權限規則](https://code.claude.com/docs/zh-TW/permissions.md)，因此您依賴自動模式以及您在每個執行緒內給予的核准。

### 在您自己的電腦上執行執行緒

當任務需要只有您的電腦才有的東西，例如本地資料庫、設備模擬器或您 VPN 後面的 API 時，要求 Claude 在您的電腦上而不是在雲端執行該任務的執行緒。當您在 project 對話中要求時，執行緒是您機器上資料夾中的 Claude Code 工作階段，通過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 連接。project 的其他執行緒繼續在雲端執行。與雲端執行緒相比，您電腦上的執行緒：

* 與該機器上的檔案、工具、MCP 伺服器和 Claude Code 設定一起工作，包括其 hooks 和權限規則，而不是 project 的雲端環境
* 從 project 的指示開始，但不加載其記憶檔案
* 僅在該電腦清醒且 Remote Control 打開時執行

**1. 連接資料夾**

在有 project 需要的資料夾的電腦上，通過以下兩種方式之一通過 Remote Control 使其可用。兩者都需要該電腦上的 Claude Code v2.1.280 或更高版本。

* **在 Claude 桌面應用程式中**：打開 **Settings > Code** 或 **Settings > Claude Code**，並打開 **Use this computer from your phone and claude.ai**。將資料夾添加到該開關下的清單。當應用程式打開時，執行緒可以在此電腦上執行。
* **在終端機中**：在資料夾中執行 `claude remote-control` 並讓它執行。在 git 儲存庫中，添加 `--spawn worktree` 以給每個執行緒那裡其自己的 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 而不是資料夾本身。

**2. 使用 Work locally 要求任務**

在 project 對話中，從訊息框旁邊的 **+** 功能表中選擇 **Work locally**，它標記您的訊息 **Local**，並寫下您想要完成的內容。在訊息中說任務應該在您的電腦上執行也可以。

**3. 在卡片上允許它**

Claude 回答一個 **Allow Claude to work in a folder on your device** 卡片。如果您連接了多個，請選擇資料夾。兩個執行緒在一個資料夾中同時工作可能會覆蓋彼此的變更，因此如果資料夾是 git 儲存庫，您可以在資料夾的選項中打開 **Worktree** 以給此執行緒其自己的 worktree 而不是資料夾本身。然後點擊 **Allow once**。

執行緒在 [auto mode](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 中執行，因此 Claude 在該資料夾中執行命令和編輯檔案而不每次都詢問您。如果 auto mode 在該電腦的 Claude Code 中不可用或關閉，執行緒執行而不使用它，並且它引發的任何權限提示等待您在執行緒中的回答，如 [解除等待批准的執行緒](#unblock-a-thread-waiting-on-approval) 所述。

當執行緒執行時，其標題中的筆記型電腦圖示顯示您的電腦是否已連接。點擊它以查看執行緒使用的資料夾或關閉連接。當該電腦睡眠時執行緒暫停，如果桌面應用程式或 `claude remote-control` 退出則停止。

* **要讓執行緒再次執行**：請參閱 [失去與您資料夾的聯繫](#lost-contact-with-your-folder)
* **要防止電腦自動睡眠**：在桌面應用程式中，於 **Settings > Code** 或 **Settings > Claude Code** 中打開 **Keep this computer awake for Remote Control**

當 [**Require trusted devices**](https://code.claude.com/docs/zh-TW/remote-control.md#trusted-devices) 對您的帳戶打開時，project 無法在您的電腦上執行執行緒。

## 為專案提供常設背景

專案記憶、專案指示，以及專案的儲存庫、檔案和環境會跨執行緒攜帶背景。您設定每一個一次。

| 背景 | 它攜帶什麼 | 您如何設定它 |
| :- | :- | :- |
| 專案記憶 | Claude 保留的關於專案的筆記，例如需求、決策和陷阱，儲存為檔案。每個雲端執行緒在啟動時讀取索引檔案 `MEMORY.md`，並在需要時開啟其他檔案 | 在專案對話或任何雲端執行緒中要求 Claude 記住一項需求、決策或陷阱，或忘記一項。在**專案設定 > 記憶**中讀取、編輯和刪除檔案 |
| 專案指示 | 傳送到每個新執行緒和專案對話中的 Claude 的文字，最多 16,000 個字元。[寫入專案指示](#write-project-instructions)涵蓋要在其中放入的內容 | **專案設定 > 記憶 > 專案指示**，或要求 Claude 變更指示 |
| 儲存庫、檔案和環境 | 每個雲端執行緒複製的儲存庫、每個執行緒可以在 `/mnt/project-files` 下讀取的資料夾和檔案，以及執行緒執行所在的雲端環境 | 儲存庫和環境在**專案設定 > 環境**中，或在對話中要求 Claude 將儲存庫新增到專案。[檔案和資料夾](#add-files-and-folders)來自**概覽**中**程式庫**標籤上的**新增** |

**專案設定 > 記憶**在**自動記憶**下列出這些檔案，因為 Claude 在專案中工作時自己寫入它們。它們與 Claude Code 在您的機器上保留的[自動記憶](https://code.claude.com/docs/zh-TW/memory.md)分開，儘管兩者都使用 `MEMORY.md` 索引。專案記憶也與專案儲存庫中的 `CLAUDE.md` 檔案分開。每個雲端執行緒在啟動時仍然從其複製讀取這些 `CLAUDE.md` 檔案，因此將關於儲存庫的指示放在其 `CLAUDE.md` 中，將關於專案的筆記放在專案記憶中。

### 寫入專案指示

專案指示是每個新執行緒開始的簡報。按一下專案標題中的齒輪圖示以開啟**專案設定**，然後前往**記憶 > 專案指示**。有用的簡報涵蓋：

* 專案的用途
* 工作發生的位置：哪些儲存庫、從哪個分支開始、如何命名提取請求
* 執行緒在完成工作前如何檢查自己的工作
* 當它需要的東西遺失時該怎麼辦
* 什麼需要您的事先同意

例如：

```text theme={null}
此專案將付款 API 的 p95 延遲保持在 200 毫秒以下：分析、查詢和快取修復，以及隨之而來的相依套件升級，在 payments-api 儲存庫中。

- 從 main 分支建立分支，每個執行緒開啟一個草稿 pull request。
- 在您完成工作前，執行 `make test` 和 `make lint`，並在最終訊息中貼上摘要行。
- 如果您無法到達所需的東西，例如儲存庫、祕密、API 或連接器，請在第一條訊息中確切說明遺失的內容並停止。不要替代、模擬或猜測。
- 不要在沒有在執行緒中詢問我的情況下合併、強制推送或變更 CI 設定。
```

關於一個儲存庫的規則，例如其建置命令，屬於該儲存庫的 `CLAUDE.md`，每個雲端執行緒在儲存庫是專案的一部分時讀取。一旦工作開始，當您更正執行緒時，也要告訴 Claude 記住更正：它進入[專案記憶](#give-a-project-standing-context)，稍後的雲端執行緒開始時會有它。

### 決定要新增哪些儲存庫

您新增到專案的儲存庫會在每個雲端執行緒中帶入其程式碼和 `CLAUDE.md`，但[不包括其 skill、`.claude/settings.json` 或 `.mcp.json`](#what-threads-pick-up-from-your-repositories)。您不新增的儲存庫仍在範圍內：雲端執行緒在其任務需要時可以將其新增到自己。大多數專案同時使用兩者：

* **將其新增到專案**，在**新專案**對話方塊中、在**專案設定 > 環境**中，或透過在對話中要求 Claude 將其新增到專案。從那時起，每個雲端執行緒都會複製它，並在啟動時載入其 `CLAUDE.md`，無論任務是否涉及它。
* **不要新增它，讓執行緒在需要時自行新增。** 其任務需要專案沒有的儲存庫的雲端執行緒可以將其新增到自己，執行緒中的筆記表示它僅被新增到此執行緒。複製發生在任務進行中途，因此該儲存庫的 `CLAUDE.md` 在執行緒啟動時不存在。下一個執行緒啟動時沒有它。以這種方式新增的儲存庫需要與專案儲存庫相同的[先決條件](#check-the-prerequisites)：在其上安裝的 Claude GitHub App 和來自您的 GitHub 帳戶的推送存取。

專案根本不需要儲存庫。其雲端執行緒仍然可以進行研究、寫入文件，以及在自己的沙箱中寫入和執行程式碼，並將檔案傳遞到**程式庫**標籤。那裡的任何雲端執行緒也可以在任務需要時將儲存庫新增到自己。

一旦專案有了儲存庫，Claude 只能從專案已經使用的 GitHub 擁有者新增儲存庫，無論它是將其新增到專案還是執行緒將其新增到自己。要引入來自不同擁有者的儲存庫，請在**專案設定 > 環境**中自己新增它。

對於跨越許多儲存庫的專案，例如一個具有伺服器、網路、行動和桌面程式碼的功能，新增幾乎每個任務都涉及的一個或兩個儲存庫，並在[專案指示](#write-project-instructions)中命名其他儲存庫，以便 Claude 知道其餘程式碼的位置。執行緒然後開始很小，只為需要它們的任務拉入其他儲存庫。

### 新增檔案和資料夾

在**新專案**對話的**背景**欄位中新增您想要執行緒讀取的檔案和資料夾，或之後使用**概覽**中**程式庫**標籤上的**新增**。這些限制適用於您新增的內容：

* **程式庫標籤**：一次最多 100 個檔案和 2 GB，單個檔案最多 480 MB。
* **新專案對話**：超過 30 MB 的檔案會被跳過，因此在建立專案後從**程式庫**標籤新增較大的檔案。
* **資料夾**：當您從任一位置新增資料夾時，專案會收到其前 100 個檔案的副本，最多 200 MB，不包括任何超過 30 MB 的檔案、隱藏檔案或 `node_modules`。專案最多可以保存 10 個資料夾和 Google Drive 資料夾的組合，單個檔案不計入該限制。
* **上傳後的變更**：上傳是副本，因此您之後在電腦上進行的變更不會到達專案，直到您再次上傳檔案並在詢問現有名稱時選擇**取代**。

### 執行緒從您的儲存庫中取得什麼

無論專案有一個或多個儲存庫，雲端執行緒都會載入每個儲存庫的 `CLAUDE.md` 指示，但不會載入其 skill、`.mcp.json` 伺服器或 `.claude/settings.json`。

| 在每個儲存庫中 | 在雲端執行緒中 |
| :- | :- |
| 儲存庫根目錄中的 `CLAUDE.md`、`.claude/CLAUDE.md` 和 `.claude/rules/` | 在執行緒啟動時從每個儲存庫載入。子目錄中的 `CLAUDE.md` 檔案和[路徑特定規則](https://code.claude.com/docs/zh-TW/memory.md#path-specific-rules)不會載入 |
| `.claude/skills/` 下的 skill | 未載入。改為為您的 claude.ai 帳戶啟用 skill，如[將 skill、外掛、連接器和工具引入執行緒](#get-skills-plugins-connectors-and-tools-into-threads)所述 |
| `.claude/` 下的 agent 和命令 | 未載入。若要使用它們，請[在您自己的電腦上執行執行緒](#run-a-thread-on-your-own-computer) |
| `.mcp.json` 中的 MCP 伺服器 | 未載入。改為使用您 claude.ai 帳戶上的連接器，如[將 skill、外掛、連接器和工具引入執行緒](#get-skills-plugins-connectors-and-tools-into-threads)所述 |
| 在 `.claude/settings.json` 中啟用的外掛 | 未載入。改為在**專案設定 > 外掛**中新增外掛 |
| `.claude/settings.json` 中的權限規則 | 不套用。在執行緒內核准工具呼叫，如[解除等待核准的執行緒](#unblock-a-thread-waiting-on-approval)所述，或[在您自己的電腦上執行執行緒](#run-a-thread-on-your-own-computer) |
| `.claude/settings.json` 中的 hook | 不執行。若要使用您的 hook，請[在您自己的電腦上執行執行緒](#run-a-thread-on-your-own-computer) |
| `.claude/settings.json` 中的 `env` | 不套用。在[雲端環境](#choose-an-environment-for-threads)中設定環境變數 |

### 為執行緒選擇環境

每個新雲端執行緒都在專案的[雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)中啟動。環境會設定執行緒可以連線到哪些網域、它們擁有哪些環境變數、哪些網路密鑰會被加入到它們的請求中，以及設定指令碼在 Claude 啟動前安裝什麼。在您於**專案設定 > 環境**中選擇環境之前，雲端執行緒使用預設的 Anthropic 託管環境。

如果雲端執行緒需要連線到內部 API 或私有套件登錄，或需要您的機器通常持有的 token，請變更環境而不是專案：請參閱[網路存取](https://code.claude.com/docs/zh-TW/cloud-environments.md#network-access)、[新增網路密鑰](https://code.claude.com/docs/zh-TW/cloud-environments.md#add-network-secrets)和[設定指令碼](https://code.claude.com/docs/zh-TW/cloud-environments.md#setup-scripts)。

### 將技能、外掛程式、連接器和工具引入執行緒

雲端執行緒沒有僅在您的機器上安裝的技能、MCP 伺服器、外掛程式和工具。通過[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md)在您的機器上執行的執行緒使用那裡安裝的內容。要使這些中的每一個對雲端執行緒可用：

* Skill：為您的 claude.ai 帳戶啟用它們，雲端執行緒就會載入[您在那裡啟用的 skill](https://code.claude.com/docs/zh-TW/skills.md#skills-in-cowork-and-cloud-sessions)，但[自行託管環境中的部分執行緒](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#how-each-session’s-config-is-assembled)除外。提交到儲存庫 `.claude/skills/` 的 skill 不會在雲端執行緒中載入。
* 外掛程式：在**專案設定 > 外掛程式**中新增它們；它們載入到每個新雲端執行緒。儲存庫在其 `.claude/settings.json` 中宣告的外掛程式[不會在雲端執行緒中載入](https://code.claude.com/docs/zh-TW/cloud-environments.md#what-carries-over-from-your-setup)。
* MCP 伺服器：雲端執行緒從您的 claude.ai 帳戶上的連接器獲取其 MCP 工具，這些是您在 [claude.ai/customize/connectors](https://claude.ai/customize/connectors) 連接一次的 MCP 伺服器。每個雲端執行緒可以使用所有它們，無需每個專案的設定。專案對話本身沒有連接器，因此將需要連接器的工作作為雲端執行緒的任務傳送。[連接器如何到達 Claude Code](https://code.claude.com/docs/zh-TW/mcp.md#how-connectors-reach-claude-code) 列出雲端工作階段的規則和關閉連接器的設定。
* 命令列工具和套件：在環境的[設定指令碼](https://code.claude.com/docs/zh-TW/cloud-environments.md#setup-scripts)中安裝它們。

要查看執行中的雲端執行緒在 claude.ai/code 有哪些連接器，請開啟執行緒並從其訊息框旁邊的 **+** 功能表中選擇**連接器**。關閉連接器會將其從該執行緒中移除，並將其儲存為您的帳戶預設值，因此新執行緒和 claude.ai 聊天在您重新開啟它之前開始時沒有它。執行緒在您傳送給它的下一條訊息後取得您新增或重新連接的連接器。

## Project 設定參考

您在 claude.ai/code 或桌面應用程式中更改 project 設定，而不是在 `settings.json` 中。從 project 側邊欄功能表中的 **Settings** 或 project 標題中的齒輪圖示打開 **Project settings**。

設定在您更改時保存；您正在編輯的文本欄位，例如目標或指示，顯示 **Save changes** 和 **Discard**，直到您離開它。對指示、儲存庫、plugins 和 **Project settings** 中環境的更改到達新執行緒，而不是已在執行的執行緒。

| 設定 | 部分 | 它控制什麼 |
| :- | :- | :- |
| 名稱、圖示和目標 | General | project 在側邊欄中的名稱和圖示，以及其一行目標 |
| Coordinator 模型和努力 | General | project 對話中 Claude 的模型和 [努力級別](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level) |
| Thread 模型和努力 | General | 執行緒的模型和努力級別 |
| Project 指示 | Memory | [常設規則](#give-a-project-standing-context) 每個新執行緒接收 |
| Project 儲存庫 | Environment | 新執行緒克隆的儲存庫 |
| 雲端環境 | Environment | 新執行緒執行的 [雲端環境](#choose-an-environment-for-threads) |
| Plugins | Plugins | 加載到每個新執行緒中的 plugins |
| Usage | Usage | 按執行緒和模型的 [令牌使用](#usage-and-cost) |
| Memory | Memory | project 的 [記憶檔案](#give-a-project-standing-context) |
| Restart Claude | General | 當 [Claude 在那裡停止回應](#claude-hasnt-responded) 時重新啟動 project 對話 |
| Pause、Archive、Delete | General | 停止、隱藏或移除 project；請參閱 [暫停、存檔或刪除 project](#pause-archive-or-delete-a-project) |

### 暫停、存檔或刪除 project

所有三個控制都在 **Project settings > General** 的底部：

* **Pause**：立即停止所有內容。每個執行中的執行緒和對話都被中斷，沒有新執行緒啟動，排程任務不執行，project 在您恢復它之前不接受訊息。點擊相同位置或 project 訊息框上方的橫幅中的 **Resume**；暫停的執行緒在您之後發送訊息時繼續。
* **Archive**：從側邊欄隱藏 project 並存檔其執行緒，這停止任何執行中或監視 pull request 的執行緒。project 存檔時，project 中的排程任務不執行。要帶回 project，從 Projects 頁面打開它並點擊 **Unarchive**。其執行緒保持存檔，直到您從工作階段清單中單獨取消存檔它們。
* **Delete**：永久移除 project 及其執行緒、其記憶和其檔案，並關閉 project 的排程任務。這無法撤銷。執行緒推送到 GitHub 的分支和 pull request 不受影響。

## 使用和成本

Project 使用計入與您其他 Claude Code 工作階段相同的 [方案限制](https://code.claude.com/docs/zh-TW/errors.md#youve-hit-your-session-limit)，project 無法自己超過這些限制。

到達您方案限制的執行緒等待並在限制重置時自己繼續，因此您留下執行的工作在您的下一個使用視窗中開始使用，無需來自您的訊息。[執行緒達到使用限制](#usage-limit-reached) 涵蓋了您看到的內容、如何停止它，以及不等待的一種情況。

工作僅在您為帳戶打開 [使用信用](https://code.claude.com/docs/zh-TW/costs.md#add-usage-credits-to-your-subscription) 時才超過您的方案限制。執行緒無法為您打開它們。

### 什麼使用您的方案

Project 比單個工作階段更快地使用您的限制，特別是在 Pro 方案上，您應該期望在執行一個的日子裡更快到達您的限制。project 的這些部分使用您的方案：

* **執行中的執行緒**：每個都是一個完整的工作階段，多個可以同時執行。沒有固定數字；Claude 會依工作需要啟動相應數量的執行緒，您 [要求](#tune-how-claude-runs-a-project) 的限制是偏好而不是上限。強制執行的限制是每天跨您的 projects 500 個新執行緒。
* **對話**：Claude 使用自己的令牌讀取執行緒報告的內容並決定下一步做什麼。
* **執行緒監視提取請求**：空閒執行緒在 CI 失敗或審查評論到達其提取請求時喚醒並再次使用您的方案。要停止它，在執行緒中要求它停止監視提取請求。

沒有執行中的執行緒、沒有監視的提取請求和沒有新訊息的 project 在它閒置時不使用您的方案，存檔的 project 也不使用。

### 查看並減少 project 的使用

在 **Project settings** 中打開 **Usage** 以查看按執行緒和模型的令牌使用，以及多少進入 project 對話。要降低它：

* 在 Pro、Max 和 Ultra 方案限制內，[快取生命週期](https://code.claude.com/docs/zh-TW/prompt-caching.md#cache-lifetime) 為一小時。閒置超過該時間的執行緒在收到後續工作時，會先重新讀取其整個對話，然後才執行任何操作。對於新工作，請要求 Claude 啟動新執行緒，這可能比恢復大型舊執行緒使用更少。
* 對於不需要最大模型的工作，[為執行緒、對話或兩者選擇較小的模型或較低的努力級別](#choose-models-and-let-claude-manage-context)。
* 要求 Claude 在 project 對話中一次執行更少的執行緒，或自己回答小問題而不是啟動執行緒。

## Projects 與其他 Claude Code 功能的關係

幾個 Claude Code 功能讓多個工作階段同時工作，因此平行執行工作本身不是 project 的用途。在 project 中，Claude 啟動並跟蹤工作階段而不是您，每個都從相同的指示開始。以下是每個相鄰功能如何連接到 project：

* **Claude Tag**：[Claude Tag](https://claude.com/docs/claude-tag/overview) 是您團隊 Slack 頻道中的 Claude，在 Team 和 Enterprise 方案上。頻道中的任何人都可以給它工作，頻道中的每個人都看到並引導它，它使用管理員為該頻道設定的連接。

  Projects 適用於 Pro、Max 和 Ultra。project 只屬於您：您是唯一能傳送工作給它或查看其執行緒的人，它使用您自己的 GitHub 存取權限和連接器。[Claude Tag 與 Cowork 和 Claude Code 的不同之處](https://claude.com/docs/claude-tag/concepts/how-it-works#how-claude-tag-differs-from-cowork-and-claude-code) 有並排比較。
* **雲端工作階段**：每個執行緒是一個 [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，除非您要求 Claude 在您的機器上執行它。無論哪種方式，Claude 啟動並追蹤它而不是您。您也可以將自己啟動的雲端工作階段的工作帶入 project：在該工作階段的側邊欄選單中選擇 [**Continue in project**](#start-from-an-existing-cloud-session)。
* **排程任務**：當您在 project 中要求排程工作時，Claude 會建立一個[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)，在該 project 中作為執行緒執行，並出現在其 **Scheduled tasks** 標籤上。您在 project 外建立的排程任務會繼續獨立運作。
* **Remote Control**：[Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 連接 claude.ai 到在您機器上執行的 Claude Code 工作階段。當您在 project 中要求 Claude 在您的電腦上執行執行緒時，project [使用 Remote Control 來執行它](#run-a-thread-on-your-own-computer)。
* **本機工作階段和 agent 檢視**：您在終端機、IDE 或桌面應用程式的本機環境中自行啟動的工作階段不會屬於您的 projects，不過您可以[將其工作帶入某個 project](#start-from-an-existing-cloud-session)。[Agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md) 是用於並排追蹤多個本機工作階段的畫面，您仍然自己啟動每個工作階段並給它其任務。
* **Worktrees**：[worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 給每個本機工作階段其自己的儲存庫工作副本。雲端執行緒不需要它們：每個執行緒將其儲存庫克隆到其自己的雲端沙箱中，並在自己的分支上工作。
* **代理團隊**：[代理團隊](https://code.claude.com/docs/zh-TW/agent-teams.md) 是一個工作階段，為單個任務啟動隊友工作階段，在您的機器上或在雲端工作階段內，並以該任務結束。
* **Subagents**：[subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 在一個工作階段內執行，在其自己的內容視窗中執行側面任務，並將摘要返回到該工作階段。project 的執行緒是 Claude 啟動的完整工作階段，並向 project 對話報告，執行緒仍然可以為其自己的側面任務使用 subagents。
* **claude.ai 聊天和 Cowork 中的 Projects**：[早期 Projects 體驗](https://support.claude.com/en/articles/9517075-what-are-projects)，它對話和參考檔案進行分組，沒有執行緒或協調者。那些 projects 保持今天的工作方式，直到重新設計的體驗到達它們。

[平行執行代理](https://code.claude.com/docs/zh-TW/agents.md) 並排比較這些選項。

## 限制

* Projects 在 claude.ai/code、桌面應用程式和 Claude 行動應用程式中可用，不在終端機 CLI、VS Code 擴充功能或 JetBrains 外掛中，也不通過 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry。
* Project 執行緒是 [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，或通過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 在您自己的機器上的工作階段，兩種情況下 Anthropic 都是模型提供者。[安全](https://code.claude.com/docs/zh-TW/security.md) 和 [資料使用](https://code.claude.com/docs/zh-TW/data-usage.md) 涵蓋了雲端工作階段如何隔離以及保留什麼，[連線和安全](https://code.claude.com/docs/zh-TW/remote-control.md#connection-and-security) 涵蓋了您機器上的執行緒如何連線以及儲存什麼。
* 您無法將自己在機器上啟動的工作階段新增到 project，但您可以[將其工作帶入 project](#start-from-an-existing-cloud-session)。Project 通過 [Remote Control 在您的機器上執行執行緒](#run-a-thread-on-your-own-computer)到達您的機器，該部分列出了它需要的內容。
* 雲端執行緒的沙箱在回合之間暫停，並在執行緒繼續時恢復。如果沙箱無法恢復，執行緒從新克隆繼續，因此未提交的變更可能會遺失。在長任務上，要求 Claude 提交並推送進行中的工作。
* project 屬於一個使用者。您無法與另一個使用者共享 project 或其執行緒，執行緒記錄沒有其他雲端工作階段具有的共享選項。在測試版期間，projects 沒有組織級控制。
* 執行緒屬於啟動它的一個 project。您無法將執行緒移動或複製到另一個 project，或將其移出以獨立存在。[**Continue in project**](#start-from-an-existing-cloud-session) 僅以另一種方式進行：它將雲端工作階段的工作帶入 project。您無法將兩個 projects 合併為一個。

## 故障排除

對於 **New project** 對話框中的 GitHub 設定提示，請參閱 [設定 GitHub 存取](#set-up-github-access)。

### 執行緒看起來卡住了

Claude 不發佈執行緒採取的每一步，因此顯示為執行中且 project 對話中沒有新訊息的執行緒通常仍在工作。新雲端執行緒也在 Claude 開始之前配置其 [雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)，因此其第一次更新需要片刻。打開執行緒讀取其記錄。如果執行緒正在等待權限提示，在那裡回答它。

### 執行緒猜測或停滯而不是詢問

當多個執行緒回來假設了錯誤的內容、解決了缺失的存取或停止了「被阻止」，原因通常是 project 設定中的相同間隙，而不是每個任務的問題。在修復任何內容之前排序哪些執行緒是健全的：

1. 在對話中要求 Claude：「對於每個打開的執行緒，列出您要求它做什麼、它假設或無法到達的內容，以及它正在等待什麼。」Claude 讀取每個執行緒並在對話中回答。
2. 對於從錯誤假設開始的執行緒，從 **Overview** 打開執行緒並從其功能表標記為已解決，或在其訊息框中告訴它改為做什麼。其分支和任何提取請求保留在 GitHub 上，直到您刪除它們。
3. 在 [project 指示](#give-a-project-standing-context) 或 [環境](#choose-an-environment-for-threads) 中修復間隙一次，然後在再次發送其餘工作作為新執行緒之前發送一個執行緒。

### Claude 還沒有回應

當 Claude 執行但其回覆未到達 project 時，project 對話顯示「Claude hasn't responded」橫幅。點擊橫幅上的 **Restart Claude**，或前往 **Project settings > General** 並在 **Restart Claude** 行中點擊 **Restart**。Claude 重新連接到對話；它正在寫的任何回覆都丟失，執行緒不受影響。

### 儲存庫存取錯誤

三條訊息意味著執行緒或 project 無法到達其儲存庫之一。project 的雲端執行緒需要 [GitHub 先決條件](#check-the-prerequisites)，即使您的其他雲端工作階段克隆相同儲存庫而沒有麻煩。

* **「Couldn't start the session — Claude doesn't have GitHub access to this project's repository」**，在執行緒啟動之前報告，當 Claude GitHub App 未安裝在該儲存庫上、已暫停或未連結到您連接的 GitHub 帳戶時。
* **「Unable to access your repository」**，由執行緒報告，當其克隆失敗時：GitHub 拒絕克隆、在 project 具有的名稱下找不到儲存庫，或執行緒被要求啟動的分支不存在。
* **「Claude can't access」** 儲存庫，在您在 **New project** 對話框或 **Project settings** 中保存儲存庫時顯示。訊息繼續帶有安裝連結和重新連接連結。如果 Claude GitHub App 不在該儲存庫上，使用安裝連結，如果它是，使用重新連接連結，因為 GitHub App 可以在 GitHub 上安裝而不連結到您連接到 Claude 的帳戶。如果訊息說 GitHub App 已暫停或不包括此儲存庫，請遵循其連結到 GitHub 以修復它。

要修復任何一個，點擊訊息提供的按鈕，例如 **Install GitHub App** 或 **Select repositories on GitHub**，然後 **Check again**。當受阻的原因在 GitHub 組織一側時，例如尚未批准應用程式的所有者或排除 Claude 的 IP 允許清單，訊息改為顯示 **See how to fix** 連結。如果沒有按鈕，請遵循 [設定 GitHub 存取](#set-up-github-access)，然後發送另一條訊息重試。

### 執行緒達到使用限制

當執行緒或 project 對話達到您方案的五小時或每週上限時，它會自行持續重試，並在上限重置時繼續。由排程任務啟動的執行緒不會等待：其回合會因上限錯誤而停止，您需在上限重置後再發送訊息給它。

在執行緒等待時，它會顯示 **Service is busy**，並帶有「Claude is still retrying and will continue automatically.」您不需要做任何事情，工作就會繼續。如果您寧願它不使用您的下一個用量時段，請點擊執行緒中的 **Stop**，或 [暫停 project](#pause-archive-or-delete-a-project) 以擱置每個執行緒。[用量上限錯誤](https://code.claude.com/docs/zh-TW/errors.md#youve-hit-your-session-limit) 解釋了這些上限以及何時重置。

### 需要額外的使用信用

執行緒或 project 對話發出了您的方案僅使用使用信用涵蓋的請求，例如對您的方案不包括的模型或上下文大小的請求，並且使用信用未為您的帳戶打開。[將使用信用添加到您的訂閱](https://code.claude.com/docs/zh-TW/costs.md#add-usage-credits-to-your-subscription) 涵蓋了誰可以在每個方案上打開或購買它們。一旦信用可用，發送另一條訊息重試。

### 與您的資料夾失去聯繫

在您的電腦上執行的執行緒在該處的 Claude Code 工作階段停止回應時顯示此訊息，通常是因為電腦進入睡眠狀態或桌面應用程式或 `claude remote-control` 退出。喚醒電腦。如果桌面應用程式或 `claude remote-control` 不再在那裡執行，請重新啟動它：

* **桌面應用程式**：重新打開應用程式並確認 **Settings > Code** 或 **Settings > Claude Code** 下的 **Use this computer from your phone and claude.ai** 仍然開啟
* **終端機**：在同一資料夾中再次執行 `claude remote-control`

### 其他訊息

這些訊息命名它們自己的原因。表格為每個提供下一步。

| 訊息 | 要做什麼 |
| :- | :- |
| 「Unable to connect to repository」，帶有「Claude couldn't reach GitHub to fetch your repository」 | 等待片刻，然後發送另一條訊息重試 |
| 「Unable to connect to repository」，帶有「Claude couldn't access your repository or environment」 | 您的 GitHub 帳戶需要對儲存庫的推送存取，環境必須仍然存在。在 **Project settings > Environment** 中檢查兩者，然後重試 |
| 「Couldn't show the setup proposal」 | 您打開的應用程式比 Claude 發送的 **Setup recommendations** 更舊。刷新頁面或重新啟動桌面應用程式，或要求 Claude 再次提議設定 |
| 「The project's environment was removed」 | 在 **Project settings > Environment** 中選擇不同的環境；更改適用於新執行緒 |
| 「Setup script failed」 | 點擊錯誤上的 **Edit setup script**，在環境中修復指令碼，然後發送另一條訊息。[設定指令碼失敗](https://code.claude.com/docs/zh-TW/web-quickstart.md#setup-script-failed) 列出常見原因 |
| 「Claude ran out of context on this turn」 | 執行緒填滿了其上下文視窗。如果訊息說執行緒在新工作階段中繼續，它自己進行；否則在 project 對話中要求 Claude 為剩餘工作啟動新執行緒 |
| 「Couldn't start in」後面跟著您的資料夾名稱 | 您允許執行緒在您的電腦上執行，但工作階段無法在那裡啟動。當訊息下的一行給出原因時，修復它，然後要求 Claude 再次執行任務 |
| 「Claude is out of date on your device」 | 您選擇執行執行緒的電腦具有比 v2.1.280 更舊的 Claude Code 版本。在那裡更新 Claude Code，或如果那是連接資料夾的內容，請更新桌面應用程式，然後要求 Claude 再次執行任務 |
| 「Reached the turn limit」 | 執行緒達到了 [`CLAUDE_CODE_MAX_TURNS`](https://code.claude.com/docs/zh-TW/env-vars) 設定的代理回合上限。發送另一條訊息繼續，或在設定它的地方提高或移除該變數 |

## 相關資源

* [在雲端使用 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)：每個執行緒後面的雲端工作階段如何工作，包括 GitHub 存取選項和提取請求上的 auto-fix
* [設定雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)：變更雲端執行緒可在網路上存取的內容、為其提供環境變數和網路密鑰，以及使用設定指令碼安裝工具
* [使用排程任務自動化工作](https://code.claude.com/docs/zh-TW/routines.md)：排程任務的排程、觸發器和管理，包括 Claude 從 project 建立的排程任務
* [使用代理檢視管理多個代理](https://code.claude.com/docs/zh-TW/agent-view.md)：當工作需要只有您的機器才能到達的工具或服務時，在您自己的機器上執行和跟蹤多個工作階段
* [Projects 重新設計：從資料夾到對話](https://claude.com/blog/projects-redesigned)：啟動公告，帶有使 project 成為與 Claude 對話的思考

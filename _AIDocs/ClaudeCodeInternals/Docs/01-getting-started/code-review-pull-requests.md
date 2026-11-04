<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/code-review-pull-requests | lastmod: 2026-10-24 | section: Getting started / Code review and pull requests -->
> 來源：https://code.claude.com/docs/zh-TW/code-review-pull-requests（官方 zh-TW，lastmod 2026-10-24）｜分類：Getting started › Code review and pull requests｜EN 摘要：Read Code Review findings on your GitHub pull request, respond to or dismiss them, and request a review with `@claude review`.

# 在 pull request 上閱讀與請求審查

> 在您的 GitHub pull request 上閱讀 Code Review 的發現項目、回應或駁回這些項目，並使用 `@claude review` 請求審查。

Code Review 是一項託管服務，由您 Claude 組織中的 Owner 為一組 GitHub 儲存庫啟用。啟用後，Claude 會審查這些儲存庫中的 pull request，並將其發現項目以行內留言、審查內文中的摘要，以及名為 **Claude Code Review** 的 check run 形式發佈。審查永遠不會核准或阻擋您的 pull request，且 check run 的結論永遠不會是失敗。

Owner 可針對每個儲存庫控制[審查的執行時機](https://code.claude.com/docs/zh-TW/code-review-setup.md#set-when-reviews-run)以及[審查的深入程度](https://code.claude.com/docs/zh-TW/code-review-setup.md#set-the-default-review-level)。

> [!NOTE]
>
> 如果您的方案不包含 Code Review，您仍可從 Claude Code 工作階段讓 Claude 審查您的分支：請參閱[使用 `/code-review` 在本機審查](https://code.claude.com/docs/zh-TW/code-review-local)。

## 嚴重性等級

Claude 會將每個發現項目以行內留言形式發佈在相關的程式碼行上，並以三種嚴重性等級之一加以標示：

| 標示 | 嚴重性 | 意義 |
| :- | :- | :- |
| 🔴 | Important | 應在合併前修正的錯誤 |
| 🟡 | Nit | 小問題，值得修正但不構成阻擋 |
| 🟣 | Pre-existing | 存在於程式碼庫中、但並非由此 PR 引入的錯誤 |

當審查記錄了其推理過程時，該發現項目會有一個收合的 **Why this was flagged** 區段。展開即可閱讀 Claude 指出此問題的原因，以及它如何驗證該問題。

若要變更 Claude 在您的儲存庫中指出的內容或其嚴重性排序方式，請參閱[自訂 Code Review](https://code.claude.com/docs/zh-TW/code-review-customize.md)。

## 回應發現項目

除非您儲存庫本身的規則有所要求，否則您可以不回應發現項目就直接合併。如果其分支保護[要求解決對話](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-conversation-resolution-before-merging)，請在合併前解決每個發現項目的討論串。

若要清除發現項目，請解決其討論串或推送修正。

* **不修改程式碼而駁回**：在 GitHub 上自行解決該討論串。僅回覆並不會駁回發現項目。
* **修正問題**：修改程式碼並推送。pull request 的下一次審查若判定問題已修正，就會解決先前的討論串，無論該審查是在您推送時自動執行，還是由您請求執行。
* **說明或提出異議**：回覆該留言。Claude 不會立即回應，且回覆不會啟動審查。pull request 的下一次審查會讀取對先前發現項目的回覆，並可能解決該討論串或發佈一則後續回覆。如果同類型的發現項目不斷出現，請請維護者在 [`REVIEW.md`](https://code.claude.com/docs/zh-TW/code-review-customize#choose-what-to-write-in-review-md) 中新增規則。

若要在不推送的情況下取得下一次審查，請以[頂層 pull request 留言](#comment-commands)的形式留言 `@claude review`。

## Check run 輸出

**Claude Code Review** check run 上的 **Details** 連結會以單一表格開啟依嚴重性排序的發現項目，包括 GitHub 未接受其行內留言的任何發現項目：

| 嚴重性 | 檔案:行 | 問題 |
| - | - | - |
| 🔴 Important | `src/auth/session.ts:142` | Token 重新整理與登出發生競爭，導致過時的工作階段仍保持作用中 |
| 🟡 Nit | `src/auth/session.ts:88` | `parseExpiry` 在輸入格式錯誤時會無聲地傳回 0 |

具有行號但未以行內留言形式發佈的發現項目，會以註解形式出現在 **Files changed** 分頁中的相關程式碼行上。Important 發現項目以紅色顯示、nit 以黃色顯示，pre-existing 錯誤則以灰色顯示。

Check run 的結論為 neutral；在某些未變更任何檔案並[保留先前結果](#when-a-push-keeps-the-earlier-result)的推送之後，結論則為 skipped。其結論永遠不會是失敗，因此已完成的審查不會使必要檢查失敗。如果您沒有看到發現項目，或審查未執行，請參閱[疑難排解 Code Review](https://code.claude.com/docs/zh-TW/code-review-troubleshooting.md)。

### 推送保留先前結果的情況

如果推送後 check run 具有以下其中一個標題，表示 Code Review 保留了先前審查的結果，而非啟動新的審查：

* **Code review skipped — no new changes**：先前審查中沒有任何 [Important](#severity-levels) 發現項目仍未解決，因此不需要新的審查
* **Code review not repeated — earlier findings still open**：若要啟動新的審查，請推送針對未解決之 Important 發現項目的修正，或[解決其討論串](#respond-to-findings)後再次推送

在 github.com 上，當以下兩個條件皆成立時，Code Review 可以保留結果：

* 該 pull request 仍新增和移除相同的行，例如在空提交、乾淨合併基礎分支或乾淨 rebase 之後
* 自該次審查以來，沒有人解決任何 Important 發現項目的討論串

若要在不變更程式碼的情況下取得審查，請留言 [`@claude review`](#comment-commands) 或在 check run 上按一下 **Re-run**。

### 從指令碼讀取結果

若要從您自己的 CI 控管合併或發佈摘要，請使用 `gh` 和 jq 剖析 Details 文字的最後一行。該行是一則 HTML 註解，以 JSON 格式存放嚴重性計數：

```text theme={null}
<!-- bughunter-severity: {"nit":1,"normal":2,"pre_existing":0} -->
```

其上方的各行可能包含來自 pull request 的檔案名稱。如果您以自己的方式剖析該文字，請僅從最後一行取得計數，如同這些步驟中的命令所做的一樣。

**1. 找出 check run ID**

從您的 shell 列出該提交的 check run，並取得 `Claude Code Review` 執行的 `id`。將 `OWNER` 和 `REPO` 替換為您的儲存庫擁有者和名稱，並將 `<commit-sha>` 替換為 pull request 的 head 提交：

```bash theme={null}
gh api repos/OWNER/REPO/commits/<commit-sha>/check-runs --jq '.check_runs[] | {id, name}'
```

如果該提交有多次 `Claude Code Review` 執行，例如在 **Re-run** 之後，GitHub 只會列出最新的一次。

**2. 讀取嚴重性計數**

從該 check run 的 `output.text` 欄位讀取計數，該欄位存放 Details 文字。將 `CHECK_RUN_ID` 替換為該 ID：

```bash theme={null}
gh api repos/OWNER/REPO/check-runs/CHECK_RUN_ID --jq '
  (.output.text | split("\n") | last
    | scan("^<!-- bughunter-severity: (.*) -->$")[0] | fromjson)?
  // error("no severity line")'
```

這會印出一個 JSON 物件，其中包含每種嚴重性的計數，且鍵依字母順序排列，例如 `{"nit": 1, "normal": 2, "pre_existing": 0}`。除了[保留先前結果](#when-a-push-keeps-the-earlier-result)的 check run 之外，這些計數包含 pull request 先前審查中、其討論串仍未解決的發現項目。

在標題為 `Code review skipped — no new changes` 的情況下，計數不包含先前審查中仍未解決的 nit 和 pre-existing 發現項目。此時先前審查中沒有任何 Important 發現項目仍未解決。

**3. 依結果採取行動**

讓您的指令碼依序處理以下情況：

* **標題以 `Code review not repeated` 開頭**：Code Review [保留了先前的結果](#when-a-push-keeps-the-earlier-result)，其中的 Important 發現項目仍未解決，且該 check run 沒有嚴重性行。請在讀取計數之前先使用 `gh api repos/OWNER/REPO/check-runs/CHECK_RUN_ID --jq .output.title` 讀取標題。如果您想控管合併，請讓該作業失敗。
* **標題以 `no new changes` 結尾**：讓該作業通過，無須讀取計數
* **`normal` 大於零**：如果您想控管合併，請讓該作業失敗。`normal` 鍵存放的是 Important 發現項目的計數，因此表示 Claude 至少發現了一個值得在合併前修正的錯誤。若只要印出該計數，請在結尾的單引號前加上 `| .normal`。
* **缺少該行**：該命令會印出包含 `no severity line` 的錯誤而非計數，並以非零狀態結束。請將其視為沒有判定結果，而非零個發現項目。失敗、逾時、被取消或被較新審查取代的審查，其 check run 不會有這一行，而某些已完成的審查也沒有。

## 請求審查

如果您的 pull request 是草稿或來自 fork，自動審查會略過它，因此請[使用留言命令請求審查](#review-drafts-and-pull-requests-from-forks)。若要讓您的 pull request 獲得審查，請執行下列其中一項：

* **開啟或標記為就緒**：在設定為 **Once after PR creation** 或 **After every push** 的儲存庫中，當您開啟或重新開啟 pull request，或將草稿標記為可供審查時，就會啟動審查。
* **留言命令**：在 pull request 上發佈 [`@claude review`](#comment-commands)。
* **推送提交**：在設定為 **After every push** 的儲存庫中，或在您已使用 `@claude review always` 訂閱的 pull request 上，推送會啟動審查。如果您的 pull request 在推送後仍新增和移除相同的行，Code Review 可能會改為[保留先前的結果](#when-a-push-keeps-the-earlier-result)。
* **點擊 Re-run**：在非來自 fork 的 pull request 上，審查失敗或逾時後，可從 check run [再次執行](https://code.claude.com/docs/zh-TW/code-review-troubleshooting.md#retrigger-a-failed-or-timed-out-review)。在非來自 fork 的 pull request 上，您也可以在某次推送[保留了先前的結果](#when-a-push-keeps-the-earlier-result)之後點擊 **Re-run**。
* **等待自動重試**：工作階段被中斷的審查會自動重試一次。[Check run 的摘要](https://code.claude.com/docs/zh-TW/code-review-troubleshooting.md#retrigger-a-failed-or-timed-out-review)會說明何時正在進行重試。

### 留言命令

在 pull request 上以留言形式發佈下列其中一個命令：

| 命令 | 作用 | 使用時機 |
| :- | :- | :- |
| `@claude review` | 啟動單次審查，不會讓 PR 訂閱未來的推送 | 您現在想要一次審查，例如在設定為 **Manual** 的儲存庫中的 pull request 上，或在其他模式下立即再進行一次審查 |
| `@claude review always` | 啟動審查，並讓該 PR 從此訂閱由推送觸發的審查 | 您希望後續的推送都會啟動審查，例如在設定為 **Manual** 的儲存庫中處理高優先順序的 PR 時 |
| `@claude review once` | 與 `@claude review` 相同：啟動單次審查而不訂閱 | 與 `@claude review` 相同的情況 |
| `@claude review stop` | 結束 PR 對由推送觸發之審查的訂閱，不會啟動審查，也不會取消已在執行的審查。Claude 會以留言回覆，而非 check run。 | 您在設定為 **Manual** 或 **Once after PR creation** 的儲存庫中，已使用 `@claude review always` 訂閱某個 PR，且不再希望每次推送都啟動審查 |
| `@claude review off` 或 `@claude review pause` | 與 `@claude review stop` 相同 | 與 `@claude review stop` 相同的情況 |

在設定為 **After every push** 的儲存庫中，您無法透過留言停止審查，因為在該處無論是否有訂閱，推送都會啟動審查。若要在該處讓推送不再對某個 pull request 啟動審查，請將其轉換為[草稿](#review-drafts-and-pull-requests-from-forks)。當您再次將其標記為可供審查時，就會啟動審查。

若要讓任何留言命令生效，必須同時符合下列所有條件：

* 以新的頂層 pull request 留言形式發佈，而不是差異行上的行內留言，也不是審查的內文。編輯先前的留言不算數。
* 將整個命令放在留言開頭的同一行。命令之後可以接其他文字。如果 `always` 或 `stop` 拼錯或位於後面的行，Claude 會將該留言視為單純的 `@claude review`，並啟動單次審查。大小寫不影響。
* 您需要具備儲存庫的 write、maintain 或 admin 權限。Claude 會向 GitHub 檢查每位留言者的權限，而來自 bot 的留言不會啟動審查。
* Pull request 必須處於開啟狀態。

當啟動審查的命令被接受後，pull request 上會出現一個標題為 **Code review queued...** 的 **Claude Code Review** check run。審查開始時，標題會變更為 **Code review in progress...**。Claude 也可能以 👀 回應您的留言，但即使沒有啟動審查，該回應也可能出現，因此請改以 check run 為準。

如果 pull request 的最新提交上已有審查正在執行，新的請求不會啟動第二次審查。

> [!NOTE]
>
> 在 2026 年 7 月的更新之前，`@claude review` 會讓 PR 訂閱由推送觸發的審查。如果您依賴該行為，請改為留言 `@claude review always`。

### 後續審查涵蓋的範圍

自行啟動的後續審查（例如在推送之後）會著重於自上次審查以來的變更，並發佈較少的 [nit 和 pre-existing 發現項目](#severity-levels)。若要查看它是否因此省略了某些發現項目，請在審查內文中尋找計算其數量的句子：

* **自上次審查以來未變更之程式碼上的發現項目**：該句子以「outside the scope of this re-review and not posted」結尾
* **Nit 和 pre-existing 發現項目**：該句子以「found and not posted」結尾

若要取得不省略任何這些項目的審查，請留言 [`@claude review`](#comment-commands)。它會再次涵蓋整個 pull request。

### 審查草稿與來自 fork 的 pull request

自動審查會略過這兩者，因此請使用留言命令請求審查：

* **草稿 pull request**：留言命令可在草稿上執行，因此您可以在將 pull request 標記為就緒之前請求審查。對草稿的推送不會啟動審查，即使在 `@claude review always` 之後也一樣。訂閱會在您將 pull request 標記為就緒後生效。
* **來自 fork 的 pull request**：無論儲存庫的 **Review runs** 設定為何，Claude 都不會自動審查來自 fork 的 pull request。若要啟動審查，請在 pull request 上留言 `@claude review`。[留言命令的條件](#comment-commands)仍然適用，且您需要的 write 存取權限是針對基礎儲存庫，而非 fork。

在來自 fork 的 pull request 上，`@claude review always` 也可以使用，但不會讓 pull request 訂閱之後推送的審查。在該處點擊 check run 上的 **Re-run** 不會啟動審查。

### 搭配 Claude Code GitHub Action 使用 Code Review

如果儲存庫也以互動模式執行 [Claude Code GitHub Action](https://code.claude.com/docs/zh-TW/github-actions.md)，並使用其預設的 `@claude` 觸發詞，`@claude review` 留言也會啟動該 Action。若要將兩者區隔開來，請將該 Action 的 `trigger_phrase` 輸入設定為不同的詞語。

## 相關資源

* [疑難排解 Code Review](https://code.claude.com/docs/zh-TW/code-review-troubleshooting.md)：未啟動、失敗或因預算而被略過的審查
* [Code Review](https://code.claude.com/docs/zh-TW/code-review.md)：此服務是什麼，以及審查如何執行
* [設定 Code Review](https://code.claude.com/docs/zh-TW/code-review-setup.md)：供 Owner 使用，啟用 Code Review 並選擇審查的執行時機與等級
* [自訂 Code Review](https://code.claude.com/docs/zh-TW/code-review-customize.md)：使用 `REVIEW.md` 和 `CLAUDE.md` 變更 Claude 指出的內容
* [Code Review 費用與使用量](https://code.claude.com/docs/zh-TW/code-review-costs.md)：審查如何計費，以及支出上限的設定位置
* [使用 `/code-review` 在本機審查](https://code.claude.com/docs/zh-TW/code-review-local)：從 Claude Code 工作階段對您的分支執行審查

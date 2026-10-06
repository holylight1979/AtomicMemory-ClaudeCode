# 原子記憶系統 — AI 安裝 runbook

> **讀者**：替使用者跑安裝的 Claude Code。照順序做，一步一個指令。人類請看 [Install.md](Install.md)。
> 安裝、升級、驗證全由 `tools/install.py` 完成；你的工作是**跑指令、讀輸出、原樣轉述**。
> 本檔與安裝器輸出不一致時，以安裝器輸出為準，並回報「runbook 需更新」。

## 0. 執行守則

1. **一步一個指令**。每步做完用一句話告訴使用者「做了什麼、結果如何、下一步是什麼」。
2. **只轉述，不發明**。`--check`／`--verify` 的每一行（`OK`／`缺`／`PASS`／`DEGRADED`／`FAIL`）已寫明少了什麼功能、怎麼補；照輸出轉述，不要自己推測原因或補充降級說明。
3. **不覆蓋使用者設定**。不要手動複製檔案進 `~/.claude`，也不要手改 `settings.json`、`workflow/config.json`、`USER*.md`、`IDENTITY*.md`；合併與備份由安裝器做。
4. **缺套件不自行安裝**。不跑 `pip install`、`npm i`、`ollama pull`；把輸出裡的補裝指令列給使用者，由使用者決定。缺項不影響安裝主流程，先裝完再補。
5. **帳號密碼不主動寫入**任何檔案。需要時請使用者自己填。
6. **來源必須是 `git clone`**。下載的壓縮檔不能用（安裝器會報錯）。
7. **指令結束碼不是 0 就停**。把完整輸出貼給使用者並等指示；不要在 `~/.claude` 內自己下 `git checkout`／`reset`／`stash`／`pull` 來繞過。

指令以 bash 寫（Windows 的 Claude Code 用 Git Bash 執行；`$HOME` 在 PowerShell 也成立）。找不到 `python` 時改用 `python3`，以下同。

## 1. 安裝

`<URL>` 是使用者給的版控庫 clone 網址；沒給就問，不要猜。不管 `~/.claude` 存不存在，步驟都一樣（不存在時安裝器會建立它）。**不要直接把版控庫 clone 成 `~/.claude`**。

### 步驟 1：把版控庫 clone 到家目錄下的暫存資料夾

只有在 `$HOME/atomic-memory-src` 已經是這個版控庫的 clone 時才跳過；clone 在別的位置不算，照本步重新 clone。

```bash
git clone -c core.longpaths=true <URL> "$HOME/atomic-memory-src"
```

### 步驟 2：安裝前自檢（唯讀）

```bash
python "$HOME/atomic-memory-src/tools/install.py" --check
```

### 步驟 3：安裝

```bash
python "$HOME/atomic-memory-src/tools/install.py" --apply
```

### 每一步怎麼判讀

| 步驟 | 算成功 | 要停下來問使用者 |
|------|--------|------------------|
| clone | `$HOME/atomic-memory-src/tools/install.py` 存在 | clone 失敗（網址、權限、網路）；`atomic-memory-src` 已存在且不是這個版控庫 |
| `--check` | 結束碼 0。把每一行整理成表轉述：`OK` 的項目、`缺` 的項目（少什麼功能＋補裝指令）。有缺項仍可繼續安裝 | 結束碼 2（Python 低於 3.10 或沒有 git）：請使用者補裝後重跑，不要往下 |
| `--apply` | 結束碼 0，輸出末尾有「請重開 Claude Code」（備份清單只在第一次接管時出現，重跑時沒有是正常的） | 結束碼 3（`~/.claude` 已是另一個版控庫，安裝器沒有動任何東西）；結束碼 1（其他失敗）。中途失敗修好原因後**重跑同一條 `--apply`** 即可，它會從中斷處接續 |

### 步驟 4：第一次回報，並請使用者重開

`--apply` 成功後向使用者回報這四件事，內容都取自 `--apply` 的輸出：

1. 備份放在哪個資料夾、備份了哪些檔。
2. 原本的 `CLAUDE.md` 內容已不再載入；想保留的部分請貼進 `USER-{帳號}.md`（輸出有點名時才提）。
3. `--apply` 末尾列出的選配缺項與各自的補裝指令（見 §2）。
4. 「請完全關閉並重開 Claude Code（VS Code 用 Reload Window），然後把下面這段貼給我」：

```
請執行 python ~/.claude/tools/install.py --verify，把結果逐項告訴我。
```

### 步驟 5：重開後驗證（唯讀）

```bash
python "$HOME/.claude/tools/install.py" --verify
```

- 結束碼 0＝沒有 `FAIL`，安裝完成。結束碼 1＝有 `FAIL`：這一步不適用守則 7 的「停下貼完整輸出」，照下面的格式回報即可。
- 回報格式：一句結論（「安裝完成」或「尚有 N 項 FAIL」）→ `FAIL` 項目與輸出給的修法 → `DEGRADED` 項目（少了什麼功能、怎麼補）→ 輸出末尾的三層記憶現況（根層 atom 數、公司層接上沒）。`PASS` 只報數量。
- 有 `FAIL`：照輸出給的修法告訴使用者，等指示；不要自己改檔。
- 全部通過：刪掉暫存資料夾 `rm -rf "$HOME/atomic-memory-src"`。

## 2. 選配項（使用者想要才做）

- **Ollama 模型**（本地萃取與向量嵌入）：指令以 `--check` 輸出為準，請使用者自己跑 `ollama pull …`。
- **向量套件**：指令以 `--apply`／`--check` 輸出為準（要裝進 hook 用的那支 Python，輸出會寫出完整指令），請使用者自己跑。
- **公司層記憶**：請使用者對 Claude Code 說「接上公司記憶」（`/org` skill）。說明 → [TECH.md](TECH.md) §4.4。
- **多子專案佈局**（把 Claude 開在子專案也接上專案根的記憶）：`python ~/.claude/tools/project-tree.py claim --root <專案根>`。說明 → TECH.md §4.6。
- **其他 AI 客戶端查記憶**（Codex／Gemini CLI／Antigravity，不裝 hooks）：`python ~/.claude/tools/ai-client-setup.py`。說明 → TECH.md §5.8。
- **遠端 Ollama backend、MCP 註冊細節、各依賴缺了會怎樣、疑難排解** → TECH.md §9。
- **關掉某個功能** → TECH.md §12「功能開關」。
- **多台電腦／多人同時寫記憶的索引合併**（自動，不需安裝）→ [_AIDocs/MultiMachineMemorySync.md](_AIDocs/MultiMachineMemorySync.md)。

## 3. 升級

```bash
python "$HOME/.claude/tools/install.py" --upgrade
```

- 結束碼 0 → 請使用者重開 Claude Code，再跑步驟 5 的 `--verify`。
- 結束碼 1 → 原樣轉述輸出後停下。安裝器會嘗試把設定檔還原，逐檔印「已還原」或「還原失敗」；有還原失敗的檔，輸出會寫出使用者版本存在哪裡，一併轉述。它說「有未解衝突」或「rebase／merge 進行中」時，請使用者決定怎麼處理。
- 不要用手動 `git pull` 取代這條指令：安裝器管理的機器上，`settings.json` 與 `workflow/config.json` 的使用者設定要靠它重新合併。

## 4. 移除

移除會刪檔，**先向使用者列出要刪的清單並取得確認**；使用者自己放進這些資料夾的檔案請他先移出。

1. `~/.claude/settings.json`：刪掉 `hooks`，以及指向 `tools/statusline.py` 的 `statusLine`。想還原安裝前的版本，原檔在 `~/.claude/backups/install-<時間戳>/`。
2. `~/.claude.json`：刪掉 `mcpServers` 內的 `workflow-guardian`。
3. 刪除 `~/.claude/` 下的 `hooks`、`lib`、`tools`、`skills`、`rules`、`memory`、`workflow`、`_AIDocs`、`Logs`、`templates`、`prompts`、`verify`，以及 `.git`（它讓 `~/.claude` 成為本系統的版控庫，不刪的話 git 會把上面的刪除視為未提交的變更）。
4. `~/.claude/CLAUDE.md`：安裝時被換成只匯入本系統啟動檔的版本。備份資料夾裡有原檔就放回來，沒有就刪掉。
5. 暫存資料夾 `$HOME/atomic-memory-src` 還在就一併刪除。

Claude Code 本體沒有被修改過，做完上述即回到原生狀態。

## 5. 深度參考

- [README.md](README.md) — 這套系統是什麼
- [TECH.md](TECH.md) — 架構、流程、依賴與降級、設定鍵
- [_AIDocs/_INDEX.md](_AIDocs/_INDEX.md) — 知識庫索引

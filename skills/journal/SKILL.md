---
name: journal
description: 工作日誌產出：從 atoms + git log + transcript 聚合產出日誌
---

# /journal — 工作日誌產出

> 從 episodic atoms + workflow state 自動彙整工作日誌（日報 / 週報）。
> 全域 Skill，適用任何專案。

---

## 使用方式

```
/journal                              # 今天的日報
/journal 2026-04-07                   # 指定日期的日報
/journal week                         # 本週週報
/journal week 2026-04-07              # 含該日期的那週週報
/journal month                        # 本月月報
/journal month 2026-04                # 指定月份月報
/journal range 2026-04-01 2026-04-15  # 任意區間（逐日產日報，跳過無記錄日）
```

---

## Step 1: 執行聚合腳本

用 Bash tool 執行：

```bash
python ~/.claude/tools/journal-aggregate.py $ARGUMENTS
```

- 存檔至主路徑（預設 `~/.claude/journals/`）下的固定子目錄：日報 `日報/YYYY-MM-DD.md`、週報 `週報/week-YYYY-WNN.md`、月報 `月報/month-YYYY-MM.md`；啟動時冪等遷移平鋪舊檔
- range 模式逐日產生日報（跳過無記錄日；只有 VCS commits、無 session 記錄的日子也算有記錄）
- VCS commits 自動拉取（git / svn），用於「做了什麼」結構列；log 以 bytes 抓回 UTF-8 decode，避開 cp950 中文訊息解碼失敗
- LLM 速覽：若本機 Ollama 可達（`127.0.0.1:11434`），自動產 2-4 句段落總結；不可達則跳過
- 產出版面 `## 總覽` = `### 自動分析`（LLM）+ `### 我的增補`（重產時整段保留使用者手寫內容）+ `### 統計`
- 腳本自動清理舊日報：主路徑保留 60 天、鏡射目的地（`CLAUDE_JOURNAL_DIRS` 第 2 個起）保留 14 天

## 環境變數（選填）

| Env var | 用途 | 預設 |
|---------|------|------|
| `CLAUDE_JOURNAL_DIRS` | 儲存路徑（多路徑以 `;` 分隔，第一個為主、其餘複製） | `~/.claude/journals/` |
| `CLAUDE_JOURNAL_OBSIDIAN_DIR` | 舊版鏡射目的地（向後相容，`CLAUDE_JOURNAL_DIRS` 未設時視為單一主路徑） | 不鏡射 |
| `CLAUDE_JOURNAL_VCS_ROOTS` | 額外候選 repo 路徑（`;` 分隔），補足無 session 記錄日的 commits 來源 | 無 |
| `CLAUDE_JOURNAL_AUTHOR` | VCS commits 過濾的作者名 | 該 repo `git config user.name` → OS USERNAME |
| `CLAUDE_JOURNAL_LLM_MODEL` | Ollama 模型名 | `qwen3:1.7b` |

個人設定放 `~/.claude/settings.local.json`（gitignore）：

```json
{
  "env": {
    "CLAUDE_JOURNAL_OBSIDIAN_DIR": "C:\\Users\\YOUR_NAME\\Obsidian\\工作日誌"
  }
}
```

## Step 2: 檢視產出

1. 讀取腳本的 stdout 輸出
2. 如果內容為「無記錄」，告知使用者並結束
3. 否則將內容展示給使用者

## Step 3: 詢問是否調整

問使用者：

> 「日誌已產出。要調整內容嗎？例如：補充說明、改格式、匯出成其他形式。」

- 使用者要求修改 → 用 Edit tool 直接修改對應的 md 檔
- 使用者滿意 → 結束

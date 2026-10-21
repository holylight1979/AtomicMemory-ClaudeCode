# 所有資產必須遵循固定目錄結構-如-b5-kit-merge-scripts

- Scope: global
- Audience: programmer
- Author: holylight
- Source: session:61b12d8f 2026-10-14
- Quote: 「補充：留下的東西搬進 workflow/inbox/ 底下的固定子目錄，B5 驗收工具組放 workflow/inbox/b5-kit/（含 b5_tokens.py.txt），通用合併腳本放 workflow/inbox/merge-scripts/。搬之前先跑 git check-ignore -v workflow/inbox/x，要有命中才搬（改名軌會在 .gitignore 加這一行）…」
- Confidence: [臨]
- Trigger: workflow/inbox, git check-ignore, .gitignore
- Created-at: 2026-10-14

## 知識

- [臨] 所有資產必須遵循固定目錄結構（如 b5-kit, merge-scripts），且搬移前需執行 git check-ignore 檢查，並更新 .gitignore；同時排除 ~/.claude/projects 下的 C--b5-q* 對話紀錄。
- <!-- src: 61b12d8f-1ccd-480a-a32c-a09578eff9ca-2 -->

## 行動

- （依知識內容判斷）


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-21 | 退役移入 _distant/：同一則一次性搬檔訊息拆出的重複卡，「所有資產必須」是擴寫。出處：LLM切入點自評-2026-10-21.md 建議退役清單 #14（組G E34） | memory-audit --delete |

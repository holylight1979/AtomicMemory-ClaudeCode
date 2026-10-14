# 建立固定的專案檔案目錄結構-如-b5-kit-merge-scripts-並

- Scope: global
- Audience: programmer
- Author: holylight
- Source: session:61b12d8f 2026-10-14
- Quote: 「補充：留下的東西搬進 workflow/inbox/ 底下的固定子目錄，B5 驗收工具組放 workflow/inbox/b5-kit/（含 b5_tokens.py.txt），通用合併腳本放 workflow/inbox/merge-scripts/。搬之前先跑 git check-ignore -v workflow/inbox/x，要有命中才搬（改名軌會在 .gitignore 加這一行）…」
- Confidence: [臨]
- Trigger: workflow/inbox, git check-ignore, 文件結構
- Created-at: 2026-10-14

## 知識

- [臨] 建立固定的專案檔案目錄結構（如 b5-kit, merge-scripts），並規定所有搬遷操作必須先執行 git check-ignore 檢查，且需排除 ~/.claude/projects 下的特定對話紀錄。
- <!-- src: 61b12d8f-1ccd-480a-a32c-a09578eff9ca-3 -->

## 行動

- （依知識內容判斷）

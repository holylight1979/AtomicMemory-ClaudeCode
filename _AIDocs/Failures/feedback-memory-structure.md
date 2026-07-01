# feedback-memory-structure

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 寫入記憶, atom 設計, atom 顆粒, 指標型, scope 敏感, GUID硬編碼, 環境相依, gitignore, git rm, memory path, _staging
- Created-at: 2026-05-26
- Related: feedback-tooling-reliability, v5-overhaul-audit-2026-05, feedback-rigor-standards, feedback-live-檔與記憶不留版本操作脈絡歷史歸專門檔

## 知識

- [臨] 專案層寫入 `{project}/.claude/memory/`，禁寫 `~/.claude/projects/{slug}/memory/` (原子記憶專案自治層覆寫)
- [臨] atom 拆為「指標型顆粒」：印象段→指標、行動段 ≥ 3 條、禁知識描述堆際
- [臨] 硬編碼環境相依值（fileID/GUID/port/路徑）不進 atom；記「查什麼」不記「值是什麼」
- [臨] gitignored 檔走 Path.unlink() / fs 操作；tracked 檔走 git rm（不要 git rm gitignored）

## 行動

- 專案層 .claude/memory/
- atom 指標型設計
- 硬編碼不進 atom
- gitignored fs unlink / tracked git rm

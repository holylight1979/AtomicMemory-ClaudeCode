# commit指令拆解要照shell解引號跳脫與here-string-拆不準要擋不能無聲-git不收黏接的-Cpath

- Scope: global
- Author: holylight
- Source: commit:bb8fb836 2026-10-20（track-g2-pathspec-fix）
- Confidence: [臨]
- Trigger: _vcs_segments, _scan_segments, commit 指令拆解, here-string, pathspec 被切掉, SmellGate 無聲放行, 多行 -m, 跳脫引號, 2>&1, _commit_shape_problem, git -C 累加
- Created-at: 2026-10-20
- Related: worktree隔離session的bash守門拒絕任何含git字樣的指令-codex的skip-git-repo-check與pytest參數檔名都中-改寫成worktree內的python啟動器再跑
- Quote: 「track-g2-pathspec-fix：你是工作軌 track-g2-pathspec-fix，總控台是 claude-12 [08791c]（送信一律帶這個識別碼，另有一個同名 session 不是總控台）。第一步用 EnterWorktree 切進 C:\Users\holylight\.claude-wt\g2-pathspec-fix（分支 g2-pathspec-fix，已存在，不…」

## 知識

- [臨] PreToolUse 的閘要知道「這次 commit 真的提交什麼」，拆指令只要有一處不懂 shell 語意，`-- <路徑>` 就會被切到另一段、commit 段看成只提交（空的）暫存區 → 無聲放行。實踩：舊 `_vcs_segments` 照換行／分號切段，PowerShell here-string `@'…'@` 與雙引號多行 `-m` 加 pathspec 整條放行（驗收題 A）。
- [臨] 拆指令要照工具的 shell 解：只在引號外切段；Bash 引號外 `\` 與雙引號裡 `\" \\ \$ \`` 是跳脫，PowerShell 引號外與雙引號裡的反引號是跳脫，兩套不能混用（混用會在另一個 shell 把訊息裡的 `;` 當分段）；`2>&1`、`&>` 的 & 不是分隔；PowerShell here-string 到行首 `'@`／`"@` 才結束。
- [臨] 拆不準要擋並說原因（引號／here-string 沒閉合、落點 cd／-C 是變數、commit／add 段有引號外展開含 Bash `{1..3}`、路徑會被展開）；判斷 token 是不是路徑要用 project-smells 同一份文法（把會展開的 token 換成記號再交 commit_options／add_specs／svn_commit_args），單引號裡的 `$` 是字面檔名（Remix `users.$id.tsx`）照查。
- [臨] 實測：git 不收黏接的 `-Cpath`（unknown option，exit 129），只收 `-C <path>`；多個 -C 與 cd 之後的相對 -C 都相對前一個落點累加。守門：hooks/verify/verify_smell_gate.py。

## 行動

- 改 commit 前的閘或拆指令函式：每種訊息寫法（多行 -m、here-string、-F、多個 -m）配有無 pathspec、Bash 與 PowerShell 各跑一次
- 拆不出要提交什麼就 deny 並說寫法，不回 None

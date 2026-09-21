# detect_atom_use 標註集評估報告

- 標註集：`C:\Users\holylight\.claude\tools\memory-eval\usage_labels.jsonl`（57 筆；labeler=ai-agent-2026-09-21，AI 判定未人工複核）
- 正類：adopted；負類：其餘（cited／rejected／unknown／corrected）
- 標籤分布：{'adopted': 10, 'cited': 9, 'corrected': 9, 'rejected': 9, 'unknown': 20}；origin：{'real': 38, 'synthetic': 19}；form：{'ok': 29, 'cold': 16, 'redundant': 3, 'skip': 7, 'fallback': 2}
- DF 母體：標註集內全部 57 筆 atom_text（去重後 40 種送出形式）用 `build_atom_df` 建；小語料——DF 比例門檻的意義是「出現在超過 ratio×57 筆 atom_text 的 token 視為過泛」。
- atom 比對文字：實際送出形式（全文／節錄／路標／cold 行）。
- embedding tiebreak：關閉（不呼叫 Ollama）。
- 現行參數（workflow/config.json usefulness）：rare_token_min=2、lexical_overlap_min=0.18、未接 DF。

## 參數對照表（主設定）

| 參數 | TP | FP | FN | TN | precision | recall | F1 | 判 used 佔比 | adopted used | cited used | corrected used | rejected used | unknown used |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rare≥2 / cont≥0.18 / DF 無（現行） | 10 | 45 | 0 | 2 | 0.18 | 1.00 | 0.31 | 55/57 | 10/10 | 9/9 | 9/9 | 9/9 | 18/20 |
| rare≥2 / cont≥0.18 / DF 0.5 | 10 | 44 | 0 | 3 | 0.19 | 1.00 | 0.31 | 54/57 | 10/10 | 9/9 | 9/9 | 9/9 | 17/20 |
| rare≥2 / cont≥0.18 / DF 0.1 | 8 | 37 | 2 | 10 | 0.18 | 0.80 | 0.29 | 45/57 | 8/10 | 9/9 | 9/9 | 8/9 | 11/20 |
| rare≥2 / cont≥0.3 / DF 無 | 10 | 45 | 0 | 2 | 0.18 | 1.00 | 0.31 | 55/57 | 10/10 | 9/9 | 9/9 | 9/9 | 18/20 |
| rare≥2 / cont≥0.3 / DF 0.5 | 10 | 44 | 0 | 3 | 0.19 | 1.00 | 0.31 | 54/57 | 10/10 | 9/9 | 9/9 | 9/9 | 17/20 |
| rare≥2 / cont≥0.3 / DF 0.1 | 8 | 36 | 2 | 11 | 0.18 | 0.80 | 0.30 | 44/57 | 8/10 | 9/9 | 9/9 | 8/9 | 10/20 |
| rare≥3 / cont≥0.18 / DF 無 | 10 | 44 | 0 | 3 | 0.19 | 1.00 | 0.31 | 54/57 | 10/10 | 9/9 | 9/9 | 9/9 | 17/20 |
| rare≥3 / cont≥0.18 / DF 0.5 | 10 | 43 | 0 | 4 | 0.19 | 1.00 | 0.32 | 53/57 | 10/10 | 9/9 | 9/9 | 9/9 | 16/20 |
| rare≥3 / cont≥0.18 / DF 0.1 | 7 | 33 | 3 | 14 | 0.17 | 0.70 | 0.28 | 40/57 | 7/10 | 9/9 | 7/9 | 8/9 | 9/20 |
| rare≥3 / cont≥0.3 / DF 無 | 10 | 44 | 0 | 3 | 0.19 | 1.00 | 0.31 | 54/57 | 10/10 | 9/9 | 9/9 | 9/9 | 17/20 |
| rare≥3 / cont≥0.3 / DF 0.5 | 10 | 43 | 0 | 4 | 0.19 | 1.00 | 0.32 | 53/57 | 10/10 | 9/9 | 9/9 | 9/9 | 16/20 |
| rare≥3 / cont≥0.3 / DF 0.1 | 7 | 30 | 3 | 17 | 0.19 | 0.70 | 0.30 | 37/57 | 7/10 | 9/9 | 7/9 | 7/9 | 7/20 |

## 變體 A：atom 比對文字改為整檔（鏡像現行 Stop 讀 atom_path）

| 參數 | TP | FP | FN | TN | precision | recall | F1 | 判 used 佔比 | adopted used | cited used | corrected used | rejected used | unknown used |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rare≥2 / cont≥0.18 / DF 無（現行） | 10 | 47 | 0 | 0 | 0.18 | 1.00 | 0.30 | 57/57 | 10/10 | 9/9 | 9/9 | 9/9 | 20/20 |
| rare≥2 / cont≥0.18 / DF 0.5 | 10 | 46 | 0 | 1 | 0.18 | 1.00 | 0.30 | 56/57 | 10/10 | 9/9 | 9/9 | 9/9 | 19/20 |
| rare≥2 / cont≥0.18 / DF 0.1 | 8 | 31 | 2 | 16 | 0.21 | 0.80 | 0.33 | 39/57 | 8/10 | 7/9 | 6/9 | 7/9 | 11/20 |
| rare≥2 / cont≥0.3 / DF 無 | 10 | 47 | 0 | 0 | 0.18 | 1.00 | 0.30 | 57/57 | 10/10 | 9/9 | 9/9 | 9/9 | 20/20 |
| rare≥2 / cont≥0.3 / DF 0.5 | 10 | 46 | 0 | 1 | 0.18 | 1.00 | 0.30 | 56/57 | 10/10 | 9/9 | 9/9 | 9/9 | 19/20 |
| rare≥2 / cont≥0.3 / DF 0.1 | 8 | 31 | 2 | 16 | 0.21 | 0.80 | 0.33 | 39/57 | 8/10 | 7/9 | 6/9 | 7/9 | 11/20 |
| rare≥3 / cont≥0.18 / DF 無 | 10 | 46 | 0 | 1 | 0.18 | 1.00 | 0.30 | 56/57 | 10/10 | 9/9 | 9/9 | 9/9 | 19/20 |
| rare≥3 / cont≥0.18 / DF 0.5 | 10 | 46 | 0 | 1 | 0.18 | 1.00 | 0.30 | 56/57 | 10/10 | 9/9 | 9/9 | 9/9 | 19/20 |
| rare≥3 / cont≥0.18 / DF 0.1 | 5 | 25 | 5 | 22 | 0.17 | 0.50 | 0.25 | 30/57 | 5/10 | 5/9 | 5/9 | 5/9 | 10/20 |
| rare≥3 / cont≥0.3 / DF 無 | 10 | 46 | 0 | 1 | 0.18 | 1.00 | 0.30 | 56/57 | 10/10 | 9/9 | 9/9 | 9/9 | 19/20 |
| rare≥3 / cont≥0.3 / DF 0.5 | 10 | 46 | 0 | 1 | 0.18 | 1.00 | 0.30 | 56/57 | 10/10 | 9/9 | 9/9 | 9/9 | 19/20 |
| rare≥3 / cont≥0.3 / DF 0.1 | 5 | 25 | 5 | 22 | 0.17 | 0.50 | 0.25 | 30/57 | 5/10 | 5/9 | 5/9 | 5/9 | 10/20 |

## 變體 B：送出形式去除路標 (full: Read …) 路徑段

| 參數 | TP | FP | FN | TN | precision | recall | F1 | 判 used 佔比 | adopted used | cited used | corrected used | rejected used | unknown used |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rare≥2 / cont≥0.18 / DF 無（現行） | 10 | 43 | 0 | 4 | 0.19 | 1.00 | 0.32 | 53/57 | 10/10 | 9/9 | 9/9 | 9/9 | 16/20 |
| rare≥2 / cont≥0.18 / DF 0.5 | 10 | 42 | 0 | 5 | 0.19 | 1.00 | 0.32 | 52/57 | 10/10 | 9/9 | 9/9 | 9/9 | 15/20 |
| rare≥2 / cont≥0.18 / DF 0.1 | 8 | 36 | 2 | 11 | 0.18 | 0.80 | 0.30 | 44/57 | 8/10 | 9/9 | 9/9 | 8/9 | 10/20 |
| rare≥2 / cont≥0.3 / DF 無 | 10 | 42 | 0 | 5 | 0.19 | 1.00 | 0.32 | 52/57 | 10/10 | 9/9 | 9/9 | 9/9 | 15/20 |
| rare≥2 / cont≥0.3 / DF 0.5 | 10 | 41 | 0 | 6 | 0.20 | 1.00 | 0.33 | 51/57 | 10/10 | 9/9 | 9/9 | 9/9 | 14/20 |
| rare≥2 / cont≥0.3 / DF 0.1 | 8 | 36 | 2 | 11 | 0.18 | 0.80 | 0.30 | 44/57 | 8/10 | 9/9 | 9/9 | 8/9 | 10/20 |
| rare≥3 / cont≥0.18 / DF 無 | 10 | 41 | 0 | 6 | 0.20 | 1.00 | 0.33 | 51/57 | 10/10 | 9/9 | 9/9 | 9/9 | 14/20 |
| rare≥3 / cont≥0.18 / DF 0.5 | 10 | 40 | 0 | 7 | 0.20 | 1.00 | 0.33 | 50/57 | 10/10 | 9/9 | 9/9 | 9/9 | 13/20 |
| rare≥3 / cont≥0.18 / DF 0.1 | 7 | 32 | 3 | 15 | 0.18 | 0.70 | 0.29 | 39/57 | 7/10 | 9/9 | 7/9 | 8/9 | 8/20 |
| rare≥3 / cont≥0.3 / DF 無 | 10 | 37 | 0 | 10 | 0.21 | 1.00 | 0.35 | 47/57 | 10/10 | 9/9 | 9/9 | 8/9 | 11/20 |
| rare≥3 / cont≥0.3 / DF 0.5 | 10 | 36 | 0 | 11 | 0.22 | 1.00 | 0.36 | 46/57 | 10/10 | 9/9 | 9/9 | 8/9 | 10/20 |
| rare≥3 / cont≥0.3 / DF 0.1 | 7 | 30 | 3 | 17 | 0.19 | 0.70 | 0.30 | 37/57 | 7/10 | 9/9 | 7/9 | 7/9 | 7/20 |

## 變體 C：corrected 也算正類（主設定的比對文字）

| 參數 | TP | FP | FN | TN | precision | recall | F1 | 判 used 佔比 | adopted used | cited used | corrected used | rejected used | unknown used |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rare≥2 / cont≥0.18 / DF 無（現行） | 19 | 36 | 0 | 2 | 0.35 | 1.00 | 0.51 | 55/57 | 10/10 | 9/9 | 9/9 | 9/9 | 18/20 |
| rare≥2 / cont≥0.18 / DF 0.5 | 19 | 35 | 0 | 3 | 0.35 | 1.00 | 0.52 | 54/57 | 10/10 | 9/9 | 9/9 | 9/9 | 17/20 |
| rare≥2 / cont≥0.18 / DF 0.1 | 17 | 28 | 2 | 10 | 0.38 | 0.89 | 0.53 | 45/57 | 8/10 | 9/9 | 9/9 | 8/9 | 11/20 |
| rare≥2 / cont≥0.3 / DF 無 | 19 | 36 | 0 | 2 | 0.35 | 1.00 | 0.51 | 55/57 | 10/10 | 9/9 | 9/9 | 9/9 | 18/20 |
| rare≥2 / cont≥0.3 / DF 0.5 | 19 | 35 | 0 | 3 | 0.35 | 1.00 | 0.52 | 54/57 | 10/10 | 9/9 | 9/9 | 9/9 | 17/20 |
| rare≥2 / cont≥0.3 / DF 0.1 | 17 | 27 | 2 | 11 | 0.39 | 0.89 | 0.54 | 44/57 | 8/10 | 9/9 | 9/9 | 8/9 | 10/20 |
| rare≥3 / cont≥0.18 / DF 無 | 19 | 35 | 0 | 3 | 0.35 | 1.00 | 0.52 | 54/57 | 10/10 | 9/9 | 9/9 | 9/9 | 17/20 |
| rare≥3 / cont≥0.18 / DF 0.5 | 19 | 34 | 0 | 4 | 0.36 | 1.00 | 0.53 | 53/57 | 10/10 | 9/9 | 9/9 | 9/9 | 16/20 |
| rare≥3 / cont≥0.18 / DF 0.1 | 14 | 26 | 5 | 12 | 0.35 | 0.74 | 0.47 | 40/57 | 7/10 | 9/9 | 7/9 | 8/9 | 9/20 |
| rare≥3 / cont≥0.3 / DF 無 | 19 | 35 | 0 | 3 | 0.35 | 1.00 | 0.52 | 54/57 | 10/10 | 9/9 | 9/9 | 9/9 | 17/20 |
| rare≥3 / cont≥0.3 / DF 0.5 | 19 | 34 | 0 | 4 | 0.36 | 1.00 | 0.53 | 53/57 | 10/10 | 9/9 | 9/9 | 9/9 | 16/20 |
| rare≥3 / cont≥0.3 / DF 0.1 | 14 | 23 | 5 | 15 | 0.38 | 0.74 | 0.50 | 37/57 | 7/10 | 9/9 | 7/9 | 7/9 | 7/20 |

## 現行參數：各標籤／各形式被判 used 的比例

| 標籤 | 判 used / 總數 |
|---|---|
| adopted | 10/10 |
| cited | 9/9 |
| corrected | 9/9 |
| rejected | 9/9 |
| unknown | 18/20 |

| 送出形式 | 判 used / 總數 |
|---|---|
| cold | 15/16 |
| fallback | 2/2 |
| ok | 28/29 |
| redundant | 3/3 |
| skip | 7/7 |

## 明細：rare≥2 / cont≥0.18 / DF 無

### FP（45 筆：負類被判 used）

| id | label | form | origin | shared | containment | 共享 token |
|---|---|---|---|---|---|---|
| r-corr-01 | corrected | ok | real | 12 | 0.13 | commit verify 回合 完成 成後 收尾 最終 測試 結果 自動 裁判 驗證 |
| r-corr-02 | corrected | ok | real | 15 | 0.082 | feedback prompt session 專案 我的 拍板 既有 有真 案層 每個 決策 的需 真的 自己 還沒 |
| r-corr-03 | corrected | ok | real | 4 | 0.138 | prompt session 判斷 動提 |
| r-corr-04 | corrected | ok | real | 13 | 0.116 | hotfix runtime shader tslg_hotfix 不能 修側 復用 新增 既有 熱修 程式 能新 貼圖 |
| r-corr-05 | corrected | ok | real | 6 | 0.032 | trigger 一次 不是 假設 測試 自動 |
| r-cite-01 | cited | skip | real | 17 | 0.68 | aidocs claude users 先實 制被 前先 卡死 好機 實證 審查 小故 拔前 故障 機制 被小 過重 障卡 |
| r-cite-02 | cited | ok | real | 10 | 0.075 | commit staging 了哪 前不 口令 哪些 報告 工作 發現 驗證 |
| r-cite-03 | cited | ok | real | 4 | 0.024 | class gameobject hotfix hotfix-migration-rules |
| r-unk-01 | unknown | cold | real | 7 | 0.438 | aidocs claude holylight tools users 動化 自動 |
| r-unk-02 | unknown | cold | real | 4 | 0.5 | claude holylight users 工作 |
| r-unk-03 | unknown | ok | real | 7 | 0.067 | profile windows 一個 使用 測試 用者 目錄 |
| r-unk-04 | unknown | cold | real | 4 | 0.571 | claude holylight tools users |
| r-unk-05 | unknown | skip | real | 5 | 0.556 | claude holylight users 工作 版控 |
| r-unk-06 | unknown | ok | real | 14 | 0.133 | windows 一個 不要 任何 使用 參數 截斷 正的 用者 目錄 真的 確認 程式 路徑 |
| r-unk-07 | unknown | skip | real | 4 | 0.444 | claude users 架構 決策 |
| r-unk-08 | unknown | ok | real | 4 | 0.333 | claude context tokens users |
| r-unk-09 | unknown | fallback | real | 3 | 0.079 | trigger 自動 萃取 |
| r-unk-10 | unknown | cold | real | 6 | 0.188 | claude holylight users 一次 呼叫 第一 |
| r-unk-11 | unknown | cold | real | 10 | 0.278 | claude context extraction friction holylight related users wg_core wg_extraction wg_friction |
| r-unk-14 | unknown | ok | real | 15 | 0.116 | claude readme skills system tools 任何 修改 子記 專案 憶系 文件 相依 知識 編碼 開發 |
| r-unk-15 | unknown | ok | real | 12 | 0.103 | claude commit fast-forward github gitlab message origin 內容 同時 完成 版控 自己 |
| r-unk-16 | unknown | cold | real | 6 | 0.545 | claude holylight related users 並行 工作 |
| r-unk-17 | unknown | cold | real | 5 | 0.263 | claude holylight users write write_text |
| r-unk-18 | unknown | ok | real | 2 | 0.043 | trigger 避免 |
| r-unk-19 | unknown | cold | real | 9 | 0.257 | claude headless-edge holylight users 實證 彈視 會被 視窗 驗證 |
| r-unk-20 | unknown | skip | real | 10 | 0.312 | claude users 一次 前預 動手 回合 工具 手前 行為 預告 |
| s-cite-01 | cited | cold | synthetic | 23 | 0.852 | claude feedback holylight users 使用 告使 四要 報告 尾報 收尾 段細 片段 用者 白話 細節 綜觀 者視 要素 視角 觀非 角四 話綜 非片 |
| s-cite-02 | cited | cold | synthetic | 9 | 0.391 | aidocs claude heredoc holylight tools write 反斜 斜線 腳本 |
| s-cite-03 | cited | ok | synthetic | 15 | 0.208 | demo-net-10-file-based-app dotnet dotnet-run file-based 單檔 專案 建專 拋棄 支援 棄式 檔跑 直接 行動 跑拋 適合 |
| s-cite-04 | cited | ok | synthetic | 26 | 0.186 | guard-aec-hud-stop session 一次 不看 再查 判死 原因 只證 因落 在渲 心跳 性改 改看 數不 明正 查一 正在 死原 活性 渲染 看心 窗活 線數 證明 跳只 連線 |
| s-cite-05 | cited | skip | synthetic | 6 | 0.5 | realm 分區 區機 機制 疇分 範疇 |
| s-cite-06 | cited | ok | synthetic | 6 | 0.047 | aidocs changelog claude feedback-memory-system-doc-sync 任何 同步 |
| s-rej-01 | rejected | skip | synthetic | 5 | 0.556 | claude workflow-svn 作流 工作 流規 |
| s-rej-02 | rejected | cold | synthetic | 29 | 0.829 | claude headless-edge 使用 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 被順 視窗 躍桌 關掉 面彈 順手 驗會 |
| s-rej-03 | rejected | ok | synthetic | 8 | 0.076 | appdata dotnet profile specialfolder users 測試 隔離 離測 |
| s-rej-04 | rejected | ok | synthetic | 9 | 0.129 | codex codex-exec sandbox skip-git-repo-check unelevated windows windows.sandbox 三旗 旗標 |
| s-rej-05 | rejected | redundant | synthetic | 6 | 0.055 | commit feedback 一體 使用 用者 自己 |
| s-rej-06 | rejected | ok | synthetic | 10 | 0.071 | 不看 心跳 性改 改看 數不 活性 看心 窗活 線數 連線 |
| s-rej-07 | rejected | cold | synthetic | 4 | 0.25 | claude electron electron-uia-automation tools |
| s-rej-08 | rejected | skip | synthetic | 4 | 0.222 | claude gitlab push-commit push-url |
| s-rej-09 | rejected | fallback | synthetic | 5 | 0.132 | budget embedding fallback ollama toolchain-ollama |
| s-corr-01 | corrected | cold | synthetic | 35 | 1.0 | claude headless-edge holylight users 使用 先查 前景 在使 實證 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 與實 被順 視窗 證與 躍桌 關掉 面彈 順手 驗會 驗證 |
| s-corr-02 | corrected | cold | synthetic | 9 | 0.474 | claude holylight newline python users windows windows-python-write-text write write_text |
| s-corr-03 | corrected | ok | synthetic | 14 | 0.1 | alive 不看 判死 原因 因落 心跳 性改 改看 死原 活性 看心 窗活 線數 連線 |
| s-corr-04 | corrected | ok | synthetic | 6 | 0.083 | dotnet file-based 單檔 專案 建專 直接 |

### FN（0 筆：正類被判 not used）

（無）

## 明細：rare≥2 / cont≥0.18 / DF 0.5

### FP（44 筆：負類被判 used）

| id | label | form | origin | shared | containment | 共享 token |
|---|---|---|---|---|---|---|
| r-corr-01 | corrected | ok | real | 12 | 0.135 | commit verify 回合 完成 成後 收尾 最終 測試 結果 自動 裁判 驗證 |
| r-corr-02 | corrected | ok | real | 15 | 0.084 | feedback prompt session 專案 我的 拍板 既有 有真 案層 每個 決策 的需 真的 自己 還沒 |
| r-corr-03 | corrected | ok | real | 4 | 0.154 | prompt session 判斷 動提 |
| r-corr-04 | corrected | ok | real | 13 | 0.119 | hotfix runtime shader tslg_hotfix 不能 修側 復用 新增 既有 熱修 程式 能新 貼圖 |
| r-corr-05 | corrected | ok | real | 5 | 0.027 | 一次 不是 假設 測試 自動 |
| r-cite-01 | cited | skip | real | 16 | 0.667 | aidocs users 先實 制被 前先 卡死 好機 實證 審查 小故 拔前 故障 機制 被小 過重 障卡 |
| r-cite-02 | cited | ok | real | 10 | 0.077 | commit staging 了哪 前不 口令 哪些 報告 工作 發現 驗證 |
| r-cite-03 | cited | ok | real | 4 | 0.025 | class gameobject hotfix hotfix-migration-rules |
| r-unk-01 | unknown | cold | real | 6 | 0.4 | aidocs holylight tools users 動化 自動 |
| r-unk-02 | unknown | cold | real | 3 | 0.429 | holylight users 工作 |
| r-unk-03 | unknown | ok | real | 7 | 0.069 | profile windows 一個 使用 測試 用者 目錄 |
| r-unk-04 | unknown | cold | real | 3 | 0.5 | holylight tools users |
| r-unk-05 | unknown | skip | real | 4 | 0.5 | holylight users 工作 版控 |
| r-unk-06 | unknown | ok | real | 14 | 0.137 | windows 一個 不要 任何 使用 參數 截斷 正的 用者 目錄 真的 確認 程式 路徑 |
| r-unk-07 | unknown | skip | real | 3 | 0.375 | users 架構 決策 |
| r-unk-08 | unknown | ok | real | 3 | 0.273 | context tokens users |
| r-unk-09 | unknown | fallback | real | 2 | 0.057 | 自動 萃取 |
| r-unk-10 | unknown | cold | real | 5 | 0.161 | holylight users 一次 呼叫 第一 |
| r-unk-11 | unknown | cold | real | 9 | 0.257 | context extraction friction holylight related users wg_core wg_extraction wg_friction |
| r-unk-14 | unknown | ok | real | 13 | 0.104 | readme skills system tools 任何 修改 子記 專案 憶系 文件 相依 編碼 開發 |
| r-unk-15 | unknown | ok | real | 11 | 0.097 | commit fast-forward github gitlab message origin 內容 同時 完成 版控 自己 |
| r-unk-16 | unknown | cold | real | 5 | 0.5 | holylight related users 並行 工作 |
| r-unk-17 | unknown | cold | real | 4 | 0.222 | holylight users write write_text |
| r-unk-19 | unknown | cold | real | 8 | 0.235 | headless-edge holylight users 實證 彈視 會被 視窗 驗證 |
| r-unk-20 | unknown | skip | real | 9 | 0.29 | users 一次 前預 動手 回合 工具 手前 行為 預告 |
| s-cite-01 | cited | cold | synthetic | 22 | 0.846 | feedback holylight users 使用 告使 四要 報告 尾報 收尾 段細 片段 用者 白話 細節 綜觀 者視 要素 視角 觀非 角四 話綜 非片 |
| s-cite-02 | cited | cold | synthetic | 8 | 0.364 | aidocs heredoc holylight tools write 反斜 斜線 腳本 |
| s-cite-03 | cited | ok | synthetic | 15 | 0.217 | demo-net-10-file-based-app dotnet dotnet-run file-based 單檔 專案 建專 拋棄 支援 棄式 檔跑 直接 行動 跑拋 適合 |
| s-cite-04 | cited | ok | synthetic | 26 | 0.19 | guard-aec-hud-stop session 一次 不看 再查 判死 原因 只證 因落 在渲 心跳 性改 改看 數不 明正 查一 正在 死原 活性 渲染 看心 窗活 線數 證明 跳只 連線 |
| s-cite-05 | cited | skip | synthetic | 6 | 0.545 | realm 分區 區機 機制 疇分 範疇 |
| s-cite-06 | cited | ok | synthetic | 5 | 0.04 | aidocs changelog feedback-memory-system-doc-sync 任何 同步 |
| s-rej-01 | rejected | skip | synthetic | 4 | 0.5 | workflow-svn 作流 工作 流規 |
| s-rej-02 | rejected | cold | synthetic | 28 | 0.824 | headless-edge 使用 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 被順 視窗 躍桌 關掉 面彈 順手 驗會 |
| s-rej-03 | rejected | ok | synthetic | 8 | 0.078 | appdata dotnet profile specialfolder users 測試 隔離 離測 |
| s-rej-04 | rejected | ok | synthetic | 9 | 0.134 | codex codex-exec sandbox skip-git-repo-check unelevated windows windows.sandbox 三旗 旗標 |
| s-rej-05 | rejected | redundant | synthetic | 6 | 0.056 | commit feedback 一體 使用 用者 自己 |
| s-rej-06 | rejected | ok | synthetic | 10 | 0.073 | 不看 心跳 性改 改看 數不 活性 看心 窗活 線數 連線 |
| s-rej-07 | rejected | cold | synthetic | 3 | 0.2 | electron electron-uia-automation tools |
| s-rej-08 | rejected | skip | synthetic | 3 | 0.176 | gitlab push-commit push-url |
| s-rej-09 | rejected | fallback | synthetic | 5 | 0.143 | budget embedding fallback ollama toolchain-ollama |
| s-corr-01 | corrected | cold | synthetic | 34 | 1.0 | headless-edge holylight users 使用 先查 前景 在使 實證 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 與實 被順 視窗 證與 躍桌 關掉 面彈 順手 驗會 驗證 |
| s-corr-02 | corrected | cold | synthetic | 8 | 0.444 | holylight newline python users windows windows-python-write-text write write_text |
| s-corr-03 | corrected | ok | synthetic | 14 | 0.102 | alive 不看 判死 原因 因落 心跳 性改 改看 死原 活性 看心 窗活 線數 連線 |
| s-corr-04 | corrected | ok | synthetic | 6 | 0.087 | dotnet file-based 單檔 專案 建專 直接 |

### FN（0 筆：正類被判 not used）

（無）

## 明細：rare≥2 / cont≥0.18 / DF 0.1

### FP（37 筆：負類被判 used）

| id | label | form | origin | shared | containment | 共享 token |
|---|---|---|---|---|---|---|
| r-corr-01 | corrected | ok | real | 7 | 0.09 | verify 回合 完成 成後 最終 結果 裁判 |
| r-corr-02 | corrected | ok | real | 10 | 0.062 | 我的 拍板 既有 有真 案層 每個 決策 的需 真的 還沒 |
| r-corr-03 | corrected | ok | real | 2 | 0.091 | 判斷 動提 |
| r-corr-04 | corrected | ok | real | 12 | 0.118 | hotfix runtime shader tslg_hotfix 不能 修側 復用 新增 既有 熱修 能新 貼圖 |
| r-corr-05 | corrected | ok | real | 2 | 0.012 | 不是 假設 |
| r-cite-01 | cited | skip | real | 12 | 0.632 | 先實 制被 卡死 好機 審查 小故 拔前 故障 機制 被小 過重 障卡 |
| r-cite-02 | cited | ok | real | 6 | 0.059 | staging 了哪 前不 哪些 報告 發現 |
| r-cite-03 | cited | ok | real | 4 | 0.026 | class gameobject hotfix hotfix-migration-rules |
| r-unk-03 | unknown | ok | real | 2 | 0.025 | profile 目錄 |
| r-unk-06 | unknown | ok | real | 5 | 0.062 | 參數 正的 目錄 真的 路徑 |
| r-unk-07 | unknown | skip | real | 2 | 0.4 | 架構 決策 |
| r-unk-10 | unknown | cold | real | 2 | 0.08 | 呼叫 第一 |
| r-unk-11 | unknown | cold | real | 5 | 0.185 | extraction friction wg_core wg_extraction wg_friction |
| r-unk-14 | unknown | ok | real | 10 | 0.089 | readme skills system 修改 子記 憶系 文件 相依 編碼 開發 |
| r-unk-15 | unknown | ok | real | 7 | 0.069 | fast-forward github gitlab message origin 同時 完成 |
| r-unk-16 | unknown | cold | real | 1 | 0.2 | 並行 |
| r-unk-17 | unknown | cold | real | 2 | 0.182 | write write_text |
| r-unk-19 | unknown | cold | real | 3 | 0.111 | headless-edge 彈視 會被 |
| r-unk-20 | unknown | skip | real | 7 | 0.28 | 前預 動手 回合 工具 手前 行為 預告 |
| s-cite-01 | cited | cold | synthetic | 16 | 1.0 | 告使 四要 報告 尾報 段細 片段 白話 細節 綜觀 者視 要素 視角 觀非 角四 話綜 非片 |
| s-cite-02 | cited | cold | synthetic | 5 | 0.294 | heredoc write 反斜 斜線 腳本 |
| s-cite-03 | cited | ok | synthetic | 12 | 0.19 | demo-net-10-file-based-app dotnet-run file-based 單檔 建專 拋棄 支援 棄式 檔跑 直接 跑拋 適合 |
| s-cite-04 | cited | ok | synthetic | 23 | 0.192 | guard-aec-hud-stop 再查 判死 原因 只證 因落 在渲 心跳 性改 改看 數不 明正 查一 正在 死原 活性 渲染 看心 窗活 線數 證明 跳只 連線 |
| s-cite-05 | cited | skip | synthetic | 6 | 0.75 | realm 分區 區機 機制 疇分 範疇 |
| s-cite-06 | cited | ok | synthetic | 3 | 0.027 | changelog feedback-memory-system-doc-sync 同步 |
| s-rej-01 | rejected | skip | synthetic | 2 | 1.0 | workflow-svn 流規 |
| s-rej-02 | rejected | cold | synthetic | 25 | 0.926 | headless-edge 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 窗做 者活 被順 躍桌 關掉 面彈 順手 驗會 |
| s-rej-03 | rejected | ok | synthetic | 5 | 0.062 | appdata profile specialfolder 隔離 離測 |
| s-rej-04 | rejected | ok | synthetic | 8 | 0.131 | codex codex-exec sandbox skip-git-repo-check unelevated windows.sandbox 三旗 旗標 |
| s-rej-06 | rejected | ok | synthetic | 9 | 0.075 | 心跳 性改 改看 數不 活性 看心 窗活 線數 連線 |
| s-rej-07 | rejected | cold | synthetic | 2 | 0.2 | electron electron-uia-automation |
| s-rej-08 | rejected | skip | synthetic | 3 | 0.231 | gitlab push-commit push-url |
| s-rej-09 | rejected | fallback | synthetic | 4 | 0.125 | embedding fallback ollama toolchain-ollama |
| s-corr-01 | corrected | cold | synthetic | 27 | 1.0 | headless-edge 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 窗做 者活 與實 被順 證與 躍桌 關掉 面彈 順手 驗會 |
| s-corr-02 | corrected | cold | synthetic | 5 | 0.455 | newline python windows-python-write-text write write_text |
| s-corr-03 | corrected | ok | synthetic | 13 | 0.108 | alive 判死 原因 因落 心跳 性改 改看 死原 活性 看心 窗活 線數 連線 |
| s-corr-04 | corrected | ok | synthetic | 4 | 0.063 | file-based 單檔 建專 直接 |

### FN（2 筆：正類被判 not used）

| id | label | form | origin | shared | containment | method | 共享 token |
|---|---|---|---|---|---|---|---|
| r-adopt-05 | adopted | redundant | real | 1 | 0.012 | lexical | 檔案 |
| r-adopt-09 | adopted | redundant | real | 1 | 0.012 | lexical | 上版 |

## 明細：rare≥2 / cont≥0.3 / DF 無

### FP（45 筆：負類被判 used）

| id | label | form | origin | shared | containment | 共享 token |
|---|---|---|---|---|---|---|
| r-corr-01 | corrected | ok | real | 12 | 0.13 | commit verify 回合 完成 成後 收尾 最終 測試 結果 自動 裁判 驗證 |
| r-corr-02 | corrected | ok | real | 15 | 0.082 | feedback prompt session 專案 我的 拍板 既有 有真 案層 每個 決策 的需 真的 自己 還沒 |
| r-corr-03 | corrected | ok | real | 4 | 0.138 | prompt session 判斷 動提 |
| r-corr-04 | corrected | ok | real | 13 | 0.116 | hotfix runtime shader tslg_hotfix 不能 修側 復用 新增 既有 熱修 程式 能新 貼圖 |
| r-corr-05 | corrected | ok | real | 6 | 0.032 | trigger 一次 不是 假設 測試 自動 |
| r-cite-01 | cited | skip | real | 17 | 0.68 | aidocs claude users 先實 制被 前先 卡死 好機 實證 審查 小故 拔前 故障 機制 被小 過重 障卡 |
| r-cite-02 | cited | ok | real | 10 | 0.075 | commit staging 了哪 前不 口令 哪些 報告 工作 發現 驗證 |
| r-cite-03 | cited | ok | real | 4 | 0.024 | class gameobject hotfix hotfix-migration-rules |
| r-unk-01 | unknown | cold | real | 7 | 0.438 | aidocs claude holylight tools users 動化 自動 |
| r-unk-02 | unknown | cold | real | 4 | 0.5 | claude holylight users 工作 |
| r-unk-03 | unknown | ok | real | 7 | 0.067 | profile windows 一個 使用 測試 用者 目錄 |
| r-unk-04 | unknown | cold | real | 4 | 0.571 | claude holylight tools users |
| r-unk-05 | unknown | skip | real | 5 | 0.556 | claude holylight users 工作 版控 |
| r-unk-06 | unknown | ok | real | 14 | 0.133 | windows 一個 不要 任何 使用 參數 截斷 正的 用者 目錄 真的 確認 程式 路徑 |
| r-unk-07 | unknown | skip | real | 4 | 0.444 | claude users 架構 決策 |
| r-unk-08 | unknown | ok | real | 4 | 0.333 | claude context tokens users |
| r-unk-09 | unknown | fallback | real | 3 | 0.079 | trigger 自動 萃取 |
| r-unk-10 | unknown | cold | real | 6 | 0.188 | claude holylight users 一次 呼叫 第一 |
| r-unk-11 | unknown | cold | real | 10 | 0.278 | claude context extraction friction holylight related users wg_core wg_extraction wg_friction |
| r-unk-14 | unknown | ok | real | 15 | 0.116 | claude readme skills system tools 任何 修改 子記 專案 憶系 文件 相依 知識 編碼 開發 |
| r-unk-15 | unknown | ok | real | 12 | 0.103 | claude commit fast-forward github gitlab message origin 內容 同時 完成 版控 自己 |
| r-unk-16 | unknown | cold | real | 6 | 0.545 | claude holylight related users 並行 工作 |
| r-unk-17 | unknown | cold | real | 5 | 0.263 | claude holylight users write write_text |
| r-unk-18 | unknown | ok | real | 2 | 0.043 | trigger 避免 |
| r-unk-19 | unknown | cold | real | 9 | 0.257 | claude headless-edge holylight users 實證 彈視 會被 視窗 驗證 |
| r-unk-20 | unknown | skip | real | 10 | 0.312 | claude users 一次 前預 動手 回合 工具 手前 行為 預告 |
| s-cite-01 | cited | cold | synthetic | 23 | 0.852 | claude feedback holylight users 使用 告使 四要 報告 尾報 收尾 段細 片段 用者 白話 細節 綜觀 者視 要素 視角 觀非 角四 話綜 非片 |
| s-cite-02 | cited | cold | synthetic | 9 | 0.391 | aidocs claude heredoc holylight tools write 反斜 斜線 腳本 |
| s-cite-03 | cited | ok | synthetic | 15 | 0.208 | demo-net-10-file-based-app dotnet dotnet-run file-based 單檔 專案 建專 拋棄 支援 棄式 檔跑 直接 行動 跑拋 適合 |
| s-cite-04 | cited | ok | synthetic | 26 | 0.186 | guard-aec-hud-stop session 一次 不看 再查 判死 原因 只證 因落 在渲 心跳 性改 改看 數不 明正 查一 正在 死原 活性 渲染 看心 窗活 線數 證明 跳只 連線 |
| s-cite-05 | cited | skip | synthetic | 6 | 0.5 | realm 分區 區機 機制 疇分 範疇 |
| s-cite-06 | cited | ok | synthetic | 6 | 0.047 | aidocs changelog claude feedback-memory-system-doc-sync 任何 同步 |
| s-rej-01 | rejected | skip | synthetic | 5 | 0.556 | claude workflow-svn 作流 工作 流規 |
| s-rej-02 | rejected | cold | synthetic | 29 | 0.829 | claude headless-edge 使用 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 被順 視窗 躍桌 關掉 面彈 順手 驗會 |
| s-rej-03 | rejected | ok | synthetic | 8 | 0.076 | appdata dotnet profile specialfolder users 測試 隔離 離測 |
| s-rej-04 | rejected | ok | synthetic | 9 | 0.129 | codex codex-exec sandbox skip-git-repo-check unelevated windows windows.sandbox 三旗 旗標 |
| s-rej-05 | rejected | redundant | synthetic | 6 | 0.055 | commit feedback 一體 使用 用者 自己 |
| s-rej-06 | rejected | ok | synthetic | 10 | 0.071 | 不看 心跳 性改 改看 數不 活性 看心 窗活 線數 連線 |
| s-rej-07 | rejected | cold | synthetic | 4 | 0.25 | claude electron electron-uia-automation tools |
| s-rej-08 | rejected | skip | synthetic | 4 | 0.222 | claude gitlab push-commit push-url |
| s-rej-09 | rejected | fallback | synthetic | 5 | 0.132 | budget embedding fallback ollama toolchain-ollama |
| s-corr-01 | corrected | cold | synthetic | 35 | 1.0 | claude headless-edge holylight users 使用 先查 前景 在使 實證 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 與實 被順 視窗 證與 躍桌 關掉 面彈 順手 驗會 驗證 |
| s-corr-02 | corrected | cold | synthetic | 9 | 0.474 | claude holylight newline python users windows windows-python-write-text write write_text |
| s-corr-03 | corrected | ok | synthetic | 14 | 0.1 | alive 不看 判死 原因 因落 心跳 性改 改看 死原 活性 看心 窗活 線數 連線 |
| s-corr-04 | corrected | ok | synthetic | 6 | 0.083 | dotnet file-based 單檔 專案 建專 直接 |

### FN（0 筆：正類被判 not used）

（無）

## 明細：rare≥2 / cont≥0.3 / DF 0.5

### FP（44 筆：負類被判 used）

| id | label | form | origin | shared | containment | 共享 token |
|---|---|---|---|---|---|---|
| r-corr-01 | corrected | ok | real | 12 | 0.135 | commit verify 回合 完成 成後 收尾 最終 測試 結果 自動 裁判 驗證 |
| r-corr-02 | corrected | ok | real | 15 | 0.084 | feedback prompt session 專案 我的 拍板 既有 有真 案層 每個 決策 的需 真的 自己 還沒 |
| r-corr-03 | corrected | ok | real | 4 | 0.154 | prompt session 判斷 動提 |
| r-corr-04 | corrected | ok | real | 13 | 0.119 | hotfix runtime shader tslg_hotfix 不能 修側 復用 新增 既有 熱修 程式 能新 貼圖 |
| r-corr-05 | corrected | ok | real | 5 | 0.027 | 一次 不是 假設 測試 自動 |
| r-cite-01 | cited | skip | real | 16 | 0.667 | aidocs users 先實 制被 前先 卡死 好機 實證 審查 小故 拔前 故障 機制 被小 過重 障卡 |
| r-cite-02 | cited | ok | real | 10 | 0.077 | commit staging 了哪 前不 口令 哪些 報告 工作 發現 驗證 |
| r-cite-03 | cited | ok | real | 4 | 0.025 | class gameobject hotfix hotfix-migration-rules |
| r-unk-01 | unknown | cold | real | 6 | 0.4 | aidocs holylight tools users 動化 自動 |
| r-unk-02 | unknown | cold | real | 3 | 0.429 | holylight users 工作 |
| r-unk-03 | unknown | ok | real | 7 | 0.069 | profile windows 一個 使用 測試 用者 目錄 |
| r-unk-04 | unknown | cold | real | 3 | 0.5 | holylight tools users |
| r-unk-05 | unknown | skip | real | 4 | 0.5 | holylight users 工作 版控 |
| r-unk-06 | unknown | ok | real | 14 | 0.137 | windows 一個 不要 任何 使用 參數 截斷 正的 用者 目錄 真的 確認 程式 路徑 |
| r-unk-07 | unknown | skip | real | 3 | 0.375 | users 架構 決策 |
| r-unk-08 | unknown | ok | real | 3 | 0.273 | context tokens users |
| r-unk-09 | unknown | fallback | real | 2 | 0.057 | 自動 萃取 |
| r-unk-10 | unknown | cold | real | 5 | 0.161 | holylight users 一次 呼叫 第一 |
| r-unk-11 | unknown | cold | real | 9 | 0.257 | context extraction friction holylight related users wg_core wg_extraction wg_friction |
| r-unk-14 | unknown | ok | real | 13 | 0.104 | readme skills system tools 任何 修改 子記 專案 憶系 文件 相依 編碼 開發 |
| r-unk-15 | unknown | ok | real | 11 | 0.097 | commit fast-forward github gitlab message origin 內容 同時 完成 版控 自己 |
| r-unk-16 | unknown | cold | real | 5 | 0.5 | holylight related users 並行 工作 |
| r-unk-17 | unknown | cold | real | 4 | 0.222 | holylight users write write_text |
| r-unk-19 | unknown | cold | real | 8 | 0.235 | headless-edge holylight users 實證 彈視 會被 視窗 驗證 |
| r-unk-20 | unknown | skip | real | 9 | 0.29 | users 一次 前預 動手 回合 工具 手前 行為 預告 |
| s-cite-01 | cited | cold | synthetic | 22 | 0.846 | feedback holylight users 使用 告使 四要 報告 尾報 收尾 段細 片段 用者 白話 細節 綜觀 者視 要素 視角 觀非 角四 話綜 非片 |
| s-cite-02 | cited | cold | synthetic | 8 | 0.364 | aidocs heredoc holylight tools write 反斜 斜線 腳本 |
| s-cite-03 | cited | ok | synthetic | 15 | 0.217 | demo-net-10-file-based-app dotnet dotnet-run file-based 單檔 專案 建專 拋棄 支援 棄式 檔跑 直接 行動 跑拋 適合 |
| s-cite-04 | cited | ok | synthetic | 26 | 0.19 | guard-aec-hud-stop session 一次 不看 再查 判死 原因 只證 因落 在渲 心跳 性改 改看 數不 明正 查一 正在 死原 活性 渲染 看心 窗活 線數 證明 跳只 連線 |
| s-cite-05 | cited | skip | synthetic | 6 | 0.545 | realm 分區 區機 機制 疇分 範疇 |
| s-cite-06 | cited | ok | synthetic | 5 | 0.04 | aidocs changelog feedback-memory-system-doc-sync 任何 同步 |
| s-rej-01 | rejected | skip | synthetic | 4 | 0.5 | workflow-svn 作流 工作 流規 |
| s-rej-02 | rejected | cold | synthetic | 28 | 0.824 | headless-edge 使用 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 被順 視窗 躍桌 關掉 面彈 順手 驗會 |
| s-rej-03 | rejected | ok | synthetic | 8 | 0.078 | appdata dotnet profile specialfolder users 測試 隔離 離測 |
| s-rej-04 | rejected | ok | synthetic | 9 | 0.134 | codex codex-exec sandbox skip-git-repo-check unelevated windows windows.sandbox 三旗 旗標 |
| s-rej-05 | rejected | redundant | synthetic | 6 | 0.056 | commit feedback 一體 使用 用者 自己 |
| s-rej-06 | rejected | ok | synthetic | 10 | 0.073 | 不看 心跳 性改 改看 數不 活性 看心 窗活 線數 連線 |
| s-rej-07 | rejected | cold | synthetic | 3 | 0.2 | electron electron-uia-automation tools |
| s-rej-08 | rejected | skip | synthetic | 3 | 0.176 | gitlab push-commit push-url |
| s-rej-09 | rejected | fallback | synthetic | 5 | 0.143 | budget embedding fallback ollama toolchain-ollama |
| s-corr-01 | corrected | cold | synthetic | 34 | 1.0 | headless-edge holylight users 使用 先查 前景 在使 實證 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 與實 被順 視窗 證與 躍桌 關掉 面彈 順手 驗會 驗證 |
| s-corr-02 | corrected | cold | synthetic | 8 | 0.444 | holylight newline python users windows windows-python-write-text write write_text |
| s-corr-03 | corrected | ok | synthetic | 14 | 0.102 | alive 不看 判死 原因 因落 心跳 性改 改看 死原 活性 看心 窗活 線數 連線 |
| s-corr-04 | corrected | ok | synthetic | 6 | 0.087 | dotnet file-based 單檔 專案 建專 直接 |

### FN（0 筆：正類被判 not used）

（無）

## 明細：rare≥2 / cont≥0.3 / DF 0.1

### FP（36 筆：負類被判 used）

| id | label | form | origin | shared | containment | 共享 token |
|---|---|---|---|---|---|---|
| r-corr-01 | corrected | ok | real | 7 | 0.09 | verify 回合 完成 成後 最終 結果 裁判 |
| r-corr-02 | corrected | ok | real | 10 | 0.062 | 我的 拍板 既有 有真 案層 每個 決策 的需 真的 還沒 |
| r-corr-03 | corrected | ok | real | 2 | 0.091 | 判斷 動提 |
| r-corr-04 | corrected | ok | real | 12 | 0.118 | hotfix runtime shader tslg_hotfix 不能 修側 復用 新增 既有 熱修 能新 貼圖 |
| r-corr-05 | corrected | ok | real | 2 | 0.012 | 不是 假設 |
| r-cite-01 | cited | skip | real | 12 | 0.632 | 先實 制被 卡死 好機 審查 小故 拔前 故障 機制 被小 過重 障卡 |
| r-cite-02 | cited | ok | real | 6 | 0.059 | staging 了哪 前不 哪些 報告 發現 |
| r-cite-03 | cited | ok | real | 4 | 0.026 | class gameobject hotfix hotfix-migration-rules |
| r-unk-03 | unknown | ok | real | 2 | 0.025 | profile 目錄 |
| r-unk-06 | unknown | ok | real | 5 | 0.062 | 參數 正的 目錄 真的 路徑 |
| r-unk-07 | unknown | skip | real | 2 | 0.4 | 架構 決策 |
| r-unk-10 | unknown | cold | real | 2 | 0.08 | 呼叫 第一 |
| r-unk-11 | unknown | cold | real | 5 | 0.185 | extraction friction wg_core wg_extraction wg_friction |
| r-unk-14 | unknown | ok | real | 10 | 0.089 | readme skills system 修改 子記 憶系 文件 相依 編碼 開發 |
| r-unk-15 | unknown | ok | real | 7 | 0.069 | fast-forward github gitlab message origin 同時 完成 |
| r-unk-17 | unknown | cold | real | 2 | 0.182 | write write_text |
| r-unk-19 | unknown | cold | real | 3 | 0.111 | headless-edge 彈視 會被 |
| r-unk-20 | unknown | skip | real | 7 | 0.28 | 前預 動手 回合 工具 手前 行為 預告 |
| s-cite-01 | cited | cold | synthetic | 16 | 1.0 | 告使 四要 報告 尾報 段細 片段 白話 細節 綜觀 者視 要素 視角 觀非 角四 話綜 非片 |
| s-cite-02 | cited | cold | synthetic | 5 | 0.294 | heredoc write 反斜 斜線 腳本 |
| s-cite-03 | cited | ok | synthetic | 12 | 0.19 | demo-net-10-file-based-app dotnet-run file-based 單檔 建專 拋棄 支援 棄式 檔跑 直接 跑拋 適合 |
| s-cite-04 | cited | ok | synthetic | 23 | 0.192 | guard-aec-hud-stop 再查 判死 原因 只證 因落 在渲 心跳 性改 改看 數不 明正 查一 正在 死原 活性 渲染 看心 窗活 線數 證明 跳只 連線 |
| s-cite-05 | cited | skip | synthetic | 6 | 0.75 | realm 分區 區機 機制 疇分 範疇 |
| s-cite-06 | cited | ok | synthetic | 3 | 0.027 | changelog feedback-memory-system-doc-sync 同步 |
| s-rej-01 | rejected | skip | synthetic | 2 | 1.0 | workflow-svn 流規 |
| s-rej-02 | rejected | cold | synthetic | 25 | 0.926 | headless-edge 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 窗做 者活 被順 躍桌 關掉 面彈 順手 驗會 |
| s-rej-03 | rejected | ok | synthetic | 5 | 0.062 | appdata profile specialfolder 隔離 離測 |
| s-rej-04 | rejected | ok | synthetic | 8 | 0.131 | codex codex-exec sandbox skip-git-repo-check unelevated windows.sandbox 三旗 旗標 |
| s-rej-06 | rejected | ok | synthetic | 9 | 0.075 | 心跳 性改 改看 數不 活性 看心 窗活 線數 連線 |
| s-rej-07 | rejected | cold | synthetic | 2 | 0.2 | electron electron-uia-automation |
| s-rej-08 | rejected | skip | synthetic | 3 | 0.231 | gitlab push-commit push-url |
| s-rej-09 | rejected | fallback | synthetic | 4 | 0.125 | embedding fallback ollama toolchain-ollama |
| s-corr-01 | corrected | cold | synthetic | 27 | 1.0 | headless-edge 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 窗做 者活 與實 被順 證與 躍桌 關掉 面彈 順手 驗會 |
| s-corr-02 | corrected | cold | synthetic | 5 | 0.455 | newline python windows-python-write-text write write_text |
| s-corr-03 | corrected | ok | synthetic | 13 | 0.108 | alive 判死 原因 因落 心跳 性改 改看 死原 活性 看心 窗活 線數 連線 |
| s-corr-04 | corrected | ok | synthetic | 4 | 0.063 | file-based 單檔 建專 直接 |

### FN（2 筆：正類被判 not used）

| id | label | form | origin | shared | containment | method | 共享 token |
|---|---|---|---|---|---|---|---|
| r-adopt-05 | adopted | redundant | real | 1 | 0.012 | lexical | 檔案 |
| r-adopt-09 | adopted | redundant | real | 1 | 0.012 | lexical | 上版 |

## 明細：rare≥3 / cont≥0.18 / DF 無

### FP（44 筆：負類被判 used）

| id | label | form | origin | shared | containment | 共享 token |
|---|---|---|---|---|---|---|
| r-corr-01 | corrected | ok | real | 12 | 0.13 | commit verify 回合 完成 成後 收尾 最終 測試 結果 自動 裁判 驗證 |
| r-corr-02 | corrected | ok | real | 15 | 0.082 | feedback prompt session 專案 我的 拍板 既有 有真 案層 每個 決策 的需 真的 自己 還沒 |
| r-corr-03 | corrected | ok | real | 4 | 0.138 | prompt session 判斷 動提 |
| r-corr-04 | corrected | ok | real | 13 | 0.116 | hotfix runtime shader tslg_hotfix 不能 修側 復用 新增 既有 熱修 程式 能新 貼圖 |
| r-corr-05 | corrected | ok | real | 6 | 0.032 | trigger 一次 不是 假設 測試 自動 |
| r-cite-01 | cited | skip | real | 17 | 0.68 | aidocs claude users 先實 制被 前先 卡死 好機 實證 審查 小故 拔前 故障 機制 被小 過重 障卡 |
| r-cite-02 | cited | ok | real | 10 | 0.075 | commit staging 了哪 前不 口令 哪些 報告 工作 發現 驗證 |
| r-cite-03 | cited | ok | real | 4 | 0.024 | class gameobject hotfix hotfix-migration-rules |
| r-unk-01 | unknown | cold | real | 7 | 0.438 | aidocs claude holylight tools users 動化 自動 |
| r-unk-02 | unknown | cold | real | 4 | 0.5 | claude holylight users 工作 |
| r-unk-03 | unknown | ok | real | 7 | 0.067 | profile windows 一個 使用 測試 用者 目錄 |
| r-unk-04 | unknown | cold | real | 4 | 0.571 | claude holylight tools users |
| r-unk-05 | unknown | skip | real | 5 | 0.556 | claude holylight users 工作 版控 |
| r-unk-06 | unknown | ok | real | 14 | 0.133 | windows 一個 不要 任何 使用 參數 截斷 正的 用者 目錄 真的 確認 程式 路徑 |
| r-unk-07 | unknown | skip | real | 4 | 0.444 | claude users 架構 決策 |
| r-unk-08 | unknown | ok | real | 4 | 0.333 | claude context tokens users |
| r-unk-09 | unknown | fallback | real | 3 | 0.079 | trigger 自動 萃取 |
| r-unk-10 | unknown | cold | real | 6 | 0.188 | claude holylight users 一次 呼叫 第一 |
| r-unk-11 | unknown | cold | real | 10 | 0.278 | claude context extraction friction holylight related users wg_core wg_extraction wg_friction |
| r-unk-14 | unknown | ok | real | 15 | 0.116 | claude readme skills system tools 任何 修改 子記 專案 憶系 文件 相依 知識 編碼 開發 |
| r-unk-15 | unknown | ok | real | 12 | 0.103 | claude commit fast-forward github gitlab message origin 內容 同時 完成 版控 自己 |
| r-unk-16 | unknown | cold | real | 6 | 0.545 | claude holylight related users 並行 工作 |
| r-unk-17 | unknown | cold | real | 5 | 0.263 | claude holylight users write write_text |
| r-unk-19 | unknown | cold | real | 9 | 0.257 | claude headless-edge holylight users 實證 彈視 會被 視窗 驗證 |
| r-unk-20 | unknown | skip | real | 10 | 0.312 | claude users 一次 前預 動手 回合 工具 手前 行為 預告 |
| s-cite-01 | cited | cold | synthetic | 23 | 0.852 | claude feedback holylight users 使用 告使 四要 報告 尾報 收尾 段細 片段 用者 白話 細節 綜觀 者視 要素 視角 觀非 角四 話綜 非片 |
| s-cite-02 | cited | cold | synthetic | 9 | 0.391 | aidocs claude heredoc holylight tools write 反斜 斜線 腳本 |
| s-cite-03 | cited | ok | synthetic | 15 | 0.208 | demo-net-10-file-based-app dotnet dotnet-run file-based 單檔 專案 建專 拋棄 支援 棄式 檔跑 直接 行動 跑拋 適合 |
| s-cite-04 | cited | ok | synthetic | 26 | 0.186 | guard-aec-hud-stop session 一次 不看 再查 判死 原因 只證 因落 在渲 心跳 性改 改看 數不 明正 查一 正在 死原 活性 渲染 看心 窗活 線數 證明 跳只 連線 |
| s-cite-05 | cited | skip | synthetic | 6 | 0.5 | realm 分區 區機 機制 疇分 範疇 |
| s-cite-06 | cited | ok | synthetic | 6 | 0.047 | aidocs changelog claude feedback-memory-system-doc-sync 任何 同步 |
| s-rej-01 | rejected | skip | synthetic | 5 | 0.556 | claude workflow-svn 作流 工作 流規 |
| s-rej-02 | rejected | cold | synthetic | 29 | 0.829 | claude headless-edge 使用 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 被順 視窗 躍桌 關掉 面彈 順手 驗會 |
| s-rej-03 | rejected | ok | synthetic | 8 | 0.076 | appdata dotnet profile specialfolder users 測試 隔離 離測 |
| s-rej-04 | rejected | ok | synthetic | 9 | 0.129 | codex codex-exec sandbox skip-git-repo-check unelevated windows windows.sandbox 三旗 旗標 |
| s-rej-05 | rejected | redundant | synthetic | 6 | 0.055 | commit feedback 一體 使用 用者 自己 |
| s-rej-06 | rejected | ok | synthetic | 10 | 0.071 | 不看 心跳 性改 改看 數不 活性 看心 窗活 線數 連線 |
| s-rej-07 | rejected | cold | synthetic | 4 | 0.25 | claude electron electron-uia-automation tools |
| s-rej-08 | rejected | skip | synthetic | 4 | 0.222 | claude gitlab push-commit push-url |
| s-rej-09 | rejected | fallback | synthetic | 5 | 0.132 | budget embedding fallback ollama toolchain-ollama |
| s-corr-01 | corrected | cold | synthetic | 35 | 1.0 | claude headless-edge holylight users 使用 先查 前景 在使 實證 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 與實 被順 視窗 證與 躍桌 關掉 面彈 順手 驗會 驗證 |
| s-corr-02 | corrected | cold | synthetic | 9 | 0.474 | claude holylight newline python users windows windows-python-write-text write write_text |
| s-corr-03 | corrected | ok | synthetic | 14 | 0.1 | alive 不看 判死 原因 因落 心跳 性改 改看 死原 活性 看心 窗活 線數 連線 |
| s-corr-04 | corrected | ok | synthetic | 6 | 0.083 | dotnet file-based 單檔 專案 建專 直接 |

### FN（0 筆：正類被判 not used）

（無）

## 明細：rare≥3 / cont≥0.18 / DF 0.5

### FP（43 筆：負類被判 used）

| id | label | form | origin | shared | containment | 共享 token |
|---|---|---|---|---|---|---|
| r-corr-01 | corrected | ok | real | 12 | 0.135 | commit verify 回合 完成 成後 收尾 最終 測試 結果 自動 裁判 驗證 |
| r-corr-02 | corrected | ok | real | 15 | 0.084 | feedback prompt session 專案 我的 拍板 既有 有真 案層 每個 決策 的需 真的 自己 還沒 |
| r-corr-03 | corrected | ok | real | 4 | 0.154 | prompt session 判斷 動提 |
| r-corr-04 | corrected | ok | real | 13 | 0.119 | hotfix runtime shader tslg_hotfix 不能 修側 復用 新增 既有 熱修 程式 能新 貼圖 |
| r-corr-05 | corrected | ok | real | 5 | 0.027 | 一次 不是 假設 測試 自動 |
| r-cite-01 | cited | skip | real | 16 | 0.667 | aidocs users 先實 制被 前先 卡死 好機 實證 審查 小故 拔前 故障 機制 被小 過重 障卡 |
| r-cite-02 | cited | ok | real | 10 | 0.077 | commit staging 了哪 前不 口令 哪些 報告 工作 發現 驗證 |
| r-cite-03 | cited | ok | real | 4 | 0.025 | class gameobject hotfix hotfix-migration-rules |
| r-unk-01 | unknown | cold | real | 6 | 0.4 | aidocs holylight tools users 動化 自動 |
| r-unk-02 | unknown | cold | real | 3 | 0.429 | holylight users 工作 |
| r-unk-03 | unknown | ok | real | 7 | 0.069 | profile windows 一個 使用 測試 用者 目錄 |
| r-unk-04 | unknown | cold | real | 3 | 0.5 | holylight tools users |
| r-unk-05 | unknown | skip | real | 4 | 0.5 | holylight users 工作 版控 |
| r-unk-06 | unknown | ok | real | 14 | 0.137 | windows 一個 不要 任何 使用 參數 截斷 正的 用者 目錄 真的 確認 程式 路徑 |
| r-unk-07 | unknown | skip | real | 3 | 0.375 | users 架構 決策 |
| r-unk-08 | unknown | ok | real | 3 | 0.273 | context tokens users |
| r-unk-10 | unknown | cold | real | 5 | 0.161 | holylight users 一次 呼叫 第一 |
| r-unk-11 | unknown | cold | real | 9 | 0.257 | context extraction friction holylight related users wg_core wg_extraction wg_friction |
| r-unk-14 | unknown | ok | real | 13 | 0.104 | readme skills system tools 任何 修改 子記 專案 憶系 文件 相依 編碼 開發 |
| r-unk-15 | unknown | ok | real | 11 | 0.097 | commit fast-forward github gitlab message origin 內容 同時 完成 版控 自己 |
| r-unk-16 | unknown | cold | real | 5 | 0.5 | holylight related users 並行 工作 |
| r-unk-17 | unknown | cold | real | 4 | 0.222 | holylight users write write_text |
| r-unk-19 | unknown | cold | real | 8 | 0.235 | headless-edge holylight users 實證 彈視 會被 視窗 驗證 |
| r-unk-20 | unknown | skip | real | 9 | 0.29 | users 一次 前預 動手 回合 工具 手前 行為 預告 |
| s-cite-01 | cited | cold | synthetic | 22 | 0.846 | feedback holylight users 使用 告使 四要 報告 尾報 收尾 段細 片段 用者 白話 細節 綜觀 者視 要素 視角 觀非 角四 話綜 非片 |
| s-cite-02 | cited | cold | synthetic | 8 | 0.364 | aidocs heredoc holylight tools write 反斜 斜線 腳本 |
| s-cite-03 | cited | ok | synthetic | 15 | 0.217 | demo-net-10-file-based-app dotnet dotnet-run file-based 單檔 專案 建專 拋棄 支援 棄式 檔跑 直接 行動 跑拋 適合 |
| s-cite-04 | cited | ok | synthetic | 26 | 0.19 | guard-aec-hud-stop session 一次 不看 再查 判死 原因 只證 因落 在渲 心跳 性改 改看 數不 明正 查一 正在 死原 活性 渲染 看心 窗活 線數 證明 跳只 連線 |
| s-cite-05 | cited | skip | synthetic | 6 | 0.545 | realm 分區 區機 機制 疇分 範疇 |
| s-cite-06 | cited | ok | synthetic | 5 | 0.04 | aidocs changelog feedback-memory-system-doc-sync 任何 同步 |
| s-rej-01 | rejected | skip | synthetic | 4 | 0.5 | workflow-svn 作流 工作 流規 |
| s-rej-02 | rejected | cold | synthetic | 28 | 0.824 | headless-edge 使用 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 被順 視窗 躍桌 關掉 面彈 順手 驗會 |
| s-rej-03 | rejected | ok | synthetic | 8 | 0.078 | appdata dotnet profile specialfolder users 測試 隔離 離測 |
| s-rej-04 | rejected | ok | synthetic | 9 | 0.134 | codex codex-exec sandbox skip-git-repo-check unelevated windows windows.sandbox 三旗 旗標 |
| s-rej-05 | rejected | redundant | synthetic | 6 | 0.056 | commit feedback 一體 使用 用者 自己 |
| s-rej-06 | rejected | ok | synthetic | 10 | 0.073 | 不看 心跳 性改 改看 數不 活性 看心 窗活 線數 連線 |
| s-rej-07 | rejected | cold | synthetic | 3 | 0.2 | electron electron-uia-automation tools |
| s-rej-08 | rejected | skip | synthetic | 3 | 0.176 | gitlab push-commit push-url |
| s-rej-09 | rejected | fallback | synthetic | 5 | 0.143 | budget embedding fallback ollama toolchain-ollama |
| s-corr-01 | corrected | cold | synthetic | 34 | 1.0 | headless-edge holylight users 使用 先查 前景 在使 實證 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 與實 被順 視窗 證與 躍桌 關掉 面彈 順手 驗會 驗證 |
| s-corr-02 | corrected | cold | synthetic | 8 | 0.444 | holylight newline python users windows windows-python-write-text write write_text |
| s-corr-03 | corrected | ok | synthetic | 14 | 0.102 | alive 不看 判死 原因 因落 心跳 性改 改看 死原 活性 看心 窗活 線數 連線 |
| s-corr-04 | corrected | ok | synthetic | 6 | 0.087 | dotnet file-based 單檔 專案 建專 直接 |

### FN（0 筆：正類被判 not used）

（無）

## 明細：rare≥3 / cont≥0.18 / DF 0.1

### FP（33 筆：負類被判 used）

| id | label | form | origin | shared | containment | 共享 token |
|---|---|---|---|---|---|---|
| r-corr-01 | corrected | ok | real | 7 | 0.09 | verify 回合 完成 成後 最終 結果 裁判 |
| r-corr-02 | corrected | ok | real | 10 | 0.062 | 我的 拍板 既有 有真 案層 每個 決策 的需 真的 還沒 |
| r-corr-04 | corrected | ok | real | 12 | 0.118 | hotfix runtime shader tslg_hotfix 不能 修側 復用 新增 既有 熱修 能新 貼圖 |
| r-cite-01 | cited | skip | real | 12 | 0.632 | 先實 制被 卡死 好機 審查 小故 拔前 故障 機制 被小 過重 障卡 |
| r-cite-02 | cited | ok | real | 6 | 0.059 | staging 了哪 前不 哪些 報告 發現 |
| r-cite-03 | cited | ok | real | 4 | 0.026 | class gameobject hotfix hotfix-migration-rules |
| r-unk-06 | unknown | ok | real | 5 | 0.062 | 參數 正的 目錄 真的 路徑 |
| r-unk-07 | unknown | skip | real | 2 | 0.4 | 架構 決策 |
| r-unk-11 | unknown | cold | real | 5 | 0.185 | extraction friction wg_core wg_extraction wg_friction |
| r-unk-14 | unknown | ok | real | 10 | 0.089 | readme skills system 修改 子記 憶系 文件 相依 編碼 開發 |
| r-unk-15 | unknown | ok | real | 7 | 0.069 | fast-forward github gitlab message origin 同時 完成 |
| r-unk-16 | unknown | cold | real | 1 | 0.2 | 並行 |
| r-unk-17 | unknown | cold | real | 2 | 0.182 | write write_text |
| r-unk-19 | unknown | cold | real | 3 | 0.111 | headless-edge 彈視 會被 |
| r-unk-20 | unknown | skip | real | 7 | 0.28 | 前預 動手 回合 工具 手前 行為 預告 |
| s-cite-01 | cited | cold | synthetic | 16 | 1.0 | 告使 四要 報告 尾報 段細 片段 白話 細節 綜觀 者視 要素 視角 觀非 角四 話綜 非片 |
| s-cite-02 | cited | cold | synthetic | 5 | 0.294 | heredoc write 反斜 斜線 腳本 |
| s-cite-03 | cited | ok | synthetic | 12 | 0.19 | demo-net-10-file-based-app dotnet-run file-based 單檔 建專 拋棄 支援 棄式 檔跑 直接 跑拋 適合 |
| s-cite-04 | cited | ok | synthetic | 23 | 0.192 | guard-aec-hud-stop 再查 判死 原因 只證 因落 在渲 心跳 性改 改看 數不 明正 查一 正在 死原 活性 渲染 看心 窗活 線數 證明 跳只 連線 |
| s-cite-05 | cited | skip | synthetic | 6 | 0.75 | realm 分區 區機 機制 疇分 範疇 |
| s-cite-06 | cited | ok | synthetic | 3 | 0.027 | changelog feedback-memory-system-doc-sync 同步 |
| s-rej-01 | rejected | skip | synthetic | 2 | 1.0 | workflow-svn 流規 |
| s-rej-02 | rejected | cold | synthetic | 25 | 0.926 | headless-edge 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 窗做 者活 被順 躍桌 關掉 面彈 順手 驗會 |
| s-rej-03 | rejected | ok | synthetic | 5 | 0.062 | appdata profile specialfolder 隔離 離測 |
| s-rej-04 | rejected | ok | synthetic | 8 | 0.131 | codex codex-exec sandbox skip-git-repo-check unelevated windows.sandbox 三旗 旗標 |
| s-rej-06 | rejected | ok | synthetic | 9 | 0.075 | 心跳 性改 改看 數不 活性 看心 窗活 線數 連線 |
| s-rej-07 | rejected | cold | synthetic | 2 | 0.2 | electron electron-uia-automation |
| s-rej-08 | rejected | skip | synthetic | 3 | 0.231 | gitlab push-commit push-url |
| s-rej-09 | rejected | fallback | synthetic | 4 | 0.125 | embedding fallback ollama toolchain-ollama |
| s-corr-01 | corrected | cold | synthetic | 27 | 1.0 | headless-edge 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 窗做 者活 與實 被順 證與 躍桌 關掉 面彈 順手 驗會 |
| s-corr-02 | corrected | cold | synthetic | 5 | 0.455 | newline python windows-python-write-text write write_text |
| s-corr-03 | corrected | ok | synthetic | 13 | 0.108 | alive 判死 原因 因落 心跳 性改 改看 死原 活性 看心 窗活 線數 連線 |
| s-corr-04 | corrected | ok | synthetic | 4 | 0.063 | file-based 單檔 建專 直接 |

### FN（3 筆：正類被判 not used）

| id | label | form | origin | shared | containment | method | 共享 token |
|---|---|---|---|---|---|---|---|
| r-adopt-05 | adopted | redundant | real | 1 | 0.012 | lexical | 檔案 |
| r-adopt-09 | adopted | redundant | real | 1 | 0.012 | lexical | 上版 |
| r-adopt-10 | adopted | ok | real | 2 | 0.038 | lexical | status 不會 |

## 明細：rare≥3 / cont≥0.3 / DF 無

### FP（44 筆：負類被判 used）

| id | label | form | origin | shared | containment | 共享 token |
|---|---|---|---|---|---|---|
| r-corr-01 | corrected | ok | real | 12 | 0.13 | commit verify 回合 完成 成後 收尾 最終 測試 結果 自動 裁判 驗證 |
| r-corr-02 | corrected | ok | real | 15 | 0.082 | feedback prompt session 專案 我的 拍板 既有 有真 案層 每個 決策 的需 真的 自己 還沒 |
| r-corr-03 | corrected | ok | real | 4 | 0.138 | prompt session 判斷 動提 |
| r-corr-04 | corrected | ok | real | 13 | 0.116 | hotfix runtime shader tslg_hotfix 不能 修側 復用 新增 既有 熱修 程式 能新 貼圖 |
| r-corr-05 | corrected | ok | real | 6 | 0.032 | trigger 一次 不是 假設 測試 自動 |
| r-cite-01 | cited | skip | real | 17 | 0.68 | aidocs claude users 先實 制被 前先 卡死 好機 實證 審查 小故 拔前 故障 機制 被小 過重 障卡 |
| r-cite-02 | cited | ok | real | 10 | 0.075 | commit staging 了哪 前不 口令 哪些 報告 工作 發現 驗證 |
| r-cite-03 | cited | ok | real | 4 | 0.024 | class gameobject hotfix hotfix-migration-rules |
| r-unk-01 | unknown | cold | real | 7 | 0.438 | aidocs claude holylight tools users 動化 自動 |
| r-unk-02 | unknown | cold | real | 4 | 0.5 | claude holylight users 工作 |
| r-unk-03 | unknown | ok | real | 7 | 0.067 | profile windows 一個 使用 測試 用者 目錄 |
| r-unk-04 | unknown | cold | real | 4 | 0.571 | claude holylight tools users |
| r-unk-05 | unknown | skip | real | 5 | 0.556 | claude holylight users 工作 版控 |
| r-unk-06 | unknown | ok | real | 14 | 0.133 | windows 一個 不要 任何 使用 參數 截斷 正的 用者 目錄 真的 確認 程式 路徑 |
| r-unk-07 | unknown | skip | real | 4 | 0.444 | claude users 架構 決策 |
| r-unk-08 | unknown | ok | real | 4 | 0.333 | claude context tokens users |
| r-unk-09 | unknown | fallback | real | 3 | 0.079 | trigger 自動 萃取 |
| r-unk-10 | unknown | cold | real | 6 | 0.188 | claude holylight users 一次 呼叫 第一 |
| r-unk-11 | unknown | cold | real | 10 | 0.278 | claude context extraction friction holylight related users wg_core wg_extraction wg_friction |
| r-unk-14 | unknown | ok | real | 15 | 0.116 | claude readme skills system tools 任何 修改 子記 專案 憶系 文件 相依 知識 編碼 開發 |
| r-unk-15 | unknown | ok | real | 12 | 0.103 | claude commit fast-forward github gitlab message origin 內容 同時 完成 版控 自己 |
| r-unk-16 | unknown | cold | real | 6 | 0.545 | claude holylight related users 並行 工作 |
| r-unk-17 | unknown | cold | real | 5 | 0.263 | claude holylight users write write_text |
| r-unk-19 | unknown | cold | real | 9 | 0.257 | claude headless-edge holylight users 實證 彈視 會被 視窗 驗證 |
| r-unk-20 | unknown | skip | real | 10 | 0.312 | claude users 一次 前預 動手 回合 工具 手前 行為 預告 |
| s-cite-01 | cited | cold | synthetic | 23 | 0.852 | claude feedback holylight users 使用 告使 四要 報告 尾報 收尾 段細 片段 用者 白話 細節 綜觀 者視 要素 視角 觀非 角四 話綜 非片 |
| s-cite-02 | cited | cold | synthetic | 9 | 0.391 | aidocs claude heredoc holylight tools write 反斜 斜線 腳本 |
| s-cite-03 | cited | ok | synthetic | 15 | 0.208 | demo-net-10-file-based-app dotnet dotnet-run file-based 單檔 專案 建專 拋棄 支援 棄式 檔跑 直接 行動 跑拋 適合 |
| s-cite-04 | cited | ok | synthetic | 26 | 0.186 | guard-aec-hud-stop session 一次 不看 再查 判死 原因 只證 因落 在渲 心跳 性改 改看 數不 明正 查一 正在 死原 活性 渲染 看心 窗活 線數 證明 跳只 連線 |
| s-cite-05 | cited | skip | synthetic | 6 | 0.5 | realm 分區 區機 機制 疇分 範疇 |
| s-cite-06 | cited | ok | synthetic | 6 | 0.047 | aidocs changelog claude feedback-memory-system-doc-sync 任何 同步 |
| s-rej-01 | rejected | skip | synthetic | 5 | 0.556 | claude workflow-svn 作流 工作 流規 |
| s-rej-02 | rejected | cold | synthetic | 29 | 0.829 | claude headless-edge 使用 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 被順 視窗 躍桌 關掉 面彈 順手 驗會 |
| s-rej-03 | rejected | ok | synthetic | 8 | 0.076 | appdata dotnet profile specialfolder users 測試 隔離 離測 |
| s-rej-04 | rejected | ok | synthetic | 9 | 0.129 | codex codex-exec sandbox skip-git-repo-check unelevated windows windows.sandbox 三旗 旗標 |
| s-rej-05 | rejected | redundant | synthetic | 6 | 0.055 | commit feedback 一體 使用 用者 自己 |
| s-rej-06 | rejected | ok | synthetic | 10 | 0.071 | 不看 心跳 性改 改看 數不 活性 看心 窗活 線數 連線 |
| s-rej-07 | rejected | cold | synthetic | 4 | 0.25 | claude electron electron-uia-automation tools |
| s-rej-08 | rejected | skip | synthetic | 4 | 0.222 | claude gitlab push-commit push-url |
| s-rej-09 | rejected | fallback | synthetic | 5 | 0.132 | budget embedding fallback ollama toolchain-ollama |
| s-corr-01 | corrected | cold | synthetic | 35 | 1.0 | claude headless-edge holylight users 使用 先查 前景 在使 實證 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 與實 被順 視窗 證與 躍桌 關掉 面彈 順手 驗會 驗證 |
| s-corr-02 | corrected | cold | synthetic | 9 | 0.474 | claude holylight newline python users windows windows-python-write-text write write_text |
| s-corr-03 | corrected | ok | synthetic | 14 | 0.1 | alive 不看 判死 原因 因落 心跳 性改 改看 死原 活性 看心 窗活 線數 連線 |
| s-corr-04 | corrected | ok | synthetic | 6 | 0.083 | dotnet file-based 單檔 專案 建專 直接 |

### FN（0 筆：正類被判 not used）

（無）

## 明細：rare≥3 / cont≥0.3 / DF 0.5

### FP（43 筆：負類被判 used）

| id | label | form | origin | shared | containment | 共享 token |
|---|---|---|---|---|---|---|
| r-corr-01 | corrected | ok | real | 12 | 0.135 | commit verify 回合 完成 成後 收尾 最終 測試 結果 自動 裁判 驗證 |
| r-corr-02 | corrected | ok | real | 15 | 0.084 | feedback prompt session 專案 我的 拍板 既有 有真 案層 每個 決策 的需 真的 自己 還沒 |
| r-corr-03 | corrected | ok | real | 4 | 0.154 | prompt session 判斷 動提 |
| r-corr-04 | corrected | ok | real | 13 | 0.119 | hotfix runtime shader tslg_hotfix 不能 修側 復用 新增 既有 熱修 程式 能新 貼圖 |
| r-corr-05 | corrected | ok | real | 5 | 0.027 | 一次 不是 假設 測試 自動 |
| r-cite-01 | cited | skip | real | 16 | 0.667 | aidocs users 先實 制被 前先 卡死 好機 實證 審查 小故 拔前 故障 機制 被小 過重 障卡 |
| r-cite-02 | cited | ok | real | 10 | 0.077 | commit staging 了哪 前不 口令 哪些 報告 工作 發現 驗證 |
| r-cite-03 | cited | ok | real | 4 | 0.025 | class gameobject hotfix hotfix-migration-rules |
| r-unk-01 | unknown | cold | real | 6 | 0.4 | aidocs holylight tools users 動化 自動 |
| r-unk-02 | unknown | cold | real | 3 | 0.429 | holylight users 工作 |
| r-unk-03 | unknown | ok | real | 7 | 0.069 | profile windows 一個 使用 測試 用者 目錄 |
| r-unk-04 | unknown | cold | real | 3 | 0.5 | holylight tools users |
| r-unk-05 | unknown | skip | real | 4 | 0.5 | holylight users 工作 版控 |
| r-unk-06 | unknown | ok | real | 14 | 0.137 | windows 一個 不要 任何 使用 參數 截斷 正的 用者 目錄 真的 確認 程式 路徑 |
| r-unk-07 | unknown | skip | real | 3 | 0.375 | users 架構 決策 |
| r-unk-08 | unknown | ok | real | 3 | 0.273 | context tokens users |
| r-unk-10 | unknown | cold | real | 5 | 0.161 | holylight users 一次 呼叫 第一 |
| r-unk-11 | unknown | cold | real | 9 | 0.257 | context extraction friction holylight related users wg_core wg_extraction wg_friction |
| r-unk-14 | unknown | ok | real | 13 | 0.104 | readme skills system tools 任何 修改 子記 專案 憶系 文件 相依 編碼 開發 |
| r-unk-15 | unknown | ok | real | 11 | 0.097 | commit fast-forward github gitlab message origin 內容 同時 完成 版控 自己 |
| r-unk-16 | unknown | cold | real | 5 | 0.5 | holylight related users 並行 工作 |
| r-unk-17 | unknown | cold | real | 4 | 0.222 | holylight users write write_text |
| r-unk-19 | unknown | cold | real | 8 | 0.235 | headless-edge holylight users 實證 彈視 會被 視窗 驗證 |
| r-unk-20 | unknown | skip | real | 9 | 0.29 | users 一次 前預 動手 回合 工具 手前 行為 預告 |
| s-cite-01 | cited | cold | synthetic | 22 | 0.846 | feedback holylight users 使用 告使 四要 報告 尾報 收尾 段細 片段 用者 白話 細節 綜觀 者視 要素 視角 觀非 角四 話綜 非片 |
| s-cite-02 | cited | cold | synthetic | 8 | 0.364 | aidocs heredoc holylight tools write 反斜 斜線 腳本 |
| s-cite-03 | cited | ok | synthetic | 15 | 0.217 | demo-net-10-file-based-app dotnet dotnet-run file-based 單檔 專案 建專 拋棄 支援 棄式 檔跑 直接 行動 跑拋 適合 |
| s-cite-04 | cited | ok | synthetic | 26 | 0.19 | guard-aec-hud-stop session 一次 不看 再查 判死 原因 只證 因落 在渲 心跳 性改 改看 數不 明正 查一 正在 死原 活性 渲染 看心 窗活 線數 證明 跳只 連線 |
| s-cite-05 | cited | skip | synthetic | 6 | 0.545 | realm 分區 區機 機制 疇分 範疇 |
| s-cite-06 | cited | ok | synthetic | 5 | 0.04 | aidocs changelog feedback-memory-system-doc-sync 任何 同步 |
| s-rej-01 | rejected | skip | synthetic | 4 | 0.5 | workflow-svn 作流 工作 流規 |
| s-rej-02 | rejected | cold | synthetic | 28 | 0.824 | headless-edge 使用 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 被順 視窗 躍桌 關掉 面彈 順手 驗會 |
| s-rej-03 | rejected | ok | synthetic | 8 | 0.078 | appdata dotnet profile specialfolder users 測試 隔離 離測 |
| s-rej-04 | rejected | ok | synthetic | 9 | 0.134 | codex codex-exec sandbox skip-git-repo-check unelevated windows windows.sandbox 三旗 旗標 |
| s-rej-05 | rejected | redundant | synthetic | 6 | 0.056 | commit feedback 一體 使用 用者 自己 |
| s-rej-06 | rejected | ok | synthetic | 10 | 0.073 | 不看 心跳 性改 改看 數不 活性 看心 窗活 線數 連線 |
| s-rej-07 | rejected | cold | synthetic | 3 | 0.2 | electron electron-uia-automation tools |
| s-rej-08 | rejected | skip | synthetic | 3 | 0.176 | gitlab push-commit push-url |
| s-rej-09 | rejected | fallback | synthetic | 5 | 0.143 | budget embedding fallback ollama toolchain-ollama |
| s-corr-01 | corrected | cold | synthetic | 34 | 1.0 | headless-edge holylight users 使用 先查 前景 在使 實證 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 用者 窗做 者活 與實 被順 視窗 證與 躍桌 關掉 面彈 順手 驗會 驗證 |
| s-corr-02 | corrected | cold | synthetic | 8 | 0.444 | holylight newline python users windows windows-python-write-text write write_text |
| s-corr-03 | corrected | ok | synthetic | 14 | 0.102 | alive 不看 判死 原因 因落 心跳 性改 改看 死原 活性 看心 窗活 線數 連線 |
| s-corr-04 | corrected | ok | synthetic | 6 | 0.087 | dotnet file-based 單檔 專案 建專 直接 |

### FN（0 筆：正類被判 not used）

（無）

## 明細：rare≥3 / cont≥0.3 / DF 0.1

### FP（30 筆：負類被判 used）

| id | label | form | origin | shared | containment | 共享 token |
|---|---|---|---|---|---|---|
| r-corr-01 | corrected | ok | real | 7 | 0.09 | verify 回合 完成 成後 最終 結果 裁判 |
| r-corr-02 | corrected | ok | real | 10 | 0.062 | 我的 拍板 既有 有真 案層 每個 決策 的需 真的 還沒 |
| r-corr-04 | corrected | ok | real | 12 | 0.118 | hotfix runtime shader tslg_hotfix 不能 修側 復用 新增 既有 熱修 能新 貼圖 |
| r-cite-01 | cited | skip | real | 12 | 0.632 | 先實 制被 卡死 好機 審查 小故 拔前 故障 機制 被小 過重 障卡 |
| r-cite-02 | cited | ok | real | 6 | 0.059 | staging 了哪 前不 哪些 報告 發現 |
| r-cite-03 | cited | ok | real | 4 | 0.026 | class gameobject hotfix hotfix-migration-rules |
| r-unk-06 | unknown | ok | real | 5 | 0.062 | 參數 正的 目錄 真的 路徑 |
| r-unk-07 | unknown | skip | real | 2 | 0.4 | 架構 決策 |
| r-unk-11 | unknown | cold | real | 5 | 0.185 | extraction friction wg_core wg_extraction wg_friction |
| r-unk-14 | unknown | ok | real | 10 | 0.089 | readme skills system 修改 子記 憶系 文件 相依 編碼 開發 |
| r-unk-15 | unknown | ok | real | 7 | 0.069 | fast-forward github gitlab message origin 同時 完成 |
| r-unk-19 | unknown | cold | real | 3 | 0.111 | headless-edge 彈視 會被 |
| r-unk-20 | unknown | skip | real | 7 | 0.28 | 前預 動手 回合 工具 手前 行為 預告 |
| s-cite-01 | cited | cold | synthetic | 16 | 1.0 | 告使 四要 報告 尾報 段細 片段 白話 細節 綜觀 者視 要素 視角 觀非 角四 話綜 非片 |
| s-cite-02 | cited | cold | synthetic | 5 | 0.294 | heredoc write 反斜 斜線 腳本 |
| s-cite-03 | cited | ok | synthetic | 12 | 0.19 | demo-net-10-file-based-app dotnet-run file-based 單檔 建專 拋棄 支援 棄式 檔跑 直接 跑拋 適合 |
| s-cite-04 | cited | ok | synthetic | 23 | 0.192 | guard-aec-hud-stop 再查 判死 原因 只證 因落 在渲 心跳 性改 改看 數不 明正 查一 正在 死原 活性 渲染 看心 窗活 線數 證明 跳只 連線 |
| s-cite-05 | cited | skip | synthetic | 6 | 0.75 | realm 分區 區機 機制 疇分 範疇 |
| s-cite-06 | cited | ok | synthetic | 3 | 0.027 | changelog feedback-memory-system-doc-sync 同步 |
| s-rej-01 | rejected | skip | synthetic | 2 | 1.0 | workflow-svn 流規 |
| s-rej-02 | rejected | cold | synthetic | 25 | 0.926 | headless-edge 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 窗做 者活 被順 躍桌 關掉 面彈 順手 驗會 |
| s-rej-03 | rejected | ok | synthetic | 5 | 0.062 | appdata profile specialfolder 隔離 離測 |
| s-rej-04 | rejected | ok | synthetic | 8 | 0.131 | codex codex-exec sandbox skip-git-repo-check unelevated windows.sandbox 三旗 旗標 |
| s-rej-06 | rejected | ok | synthetic | 9 | 0.075 | 心跳 性改 改看 數不 活性 看心 窗活 線數 連線 |
| s-rej-08 | rejected | skip | synthetic | 3 | 0.231 | gitlab push-commit push-url |
| s-rej-09 | rejected | fallback | synthetic | 4 | 0.125 | embedding fallback ollama toolchain-ollama |
| s-corr-01 | corrected | cold | synthetic | 27 | 1.0 | headless-edge 先查 前景 在使 實驗 彈視 或先 手關 掉污 數據 景視 會被 染數 查前 桌面 污染 活躍 窗做 者活 與實 被順 證與 躍桌 關掉 面彈 順手 驗會 |
| s-corr-02 | corrected | cold | synthetic | 5 | 0.455 | newline python windows-python-write-text write write_text |
| s-corr-03 | corrected | ok | synthetic | 13 | 0.108 | alive 判死 原因 因落 心跳 性改 改看 死原 活性 看心 窗活 線數 連線 |
| s-corr-04 | corrected | ok | synthetic | 4 | 0.063 | file-based 單檔 建專 直接 |

### FN（3 筆：正類被判 not used）

| id | label | form | origin | shared | containment | method | 共享 token |
|---|---|---|---|---|---|---|---|
| r-adopt-05 | adopted | redundant | real | 1 | 0.012 | lexical | 檔案 |
| r-adopt-09 | adopted | redundant | real | 1 | 0.012 | lexical | 上版 |
| r-adopt-10 | adopted | ok | real | 2 | 0.038 | lexical | status 不會 |

## 人工複核優先（標註者自 flag）

| id | label | review_flag |
|---|---|---|
| r-adopt-01 | adopted | 證據在 8,000 字元上限之外：現行 Stop 會漏判，門檻校準要連取文長度一起看 |
| r-adopt-02 | adopted | cold 一行的標題本身就是配方；算不算「用到 atom」需人工裁定 |
| r-corr-05 | corrected | 行為由使用者「你能否現在進行測試」驅動，是否歸功於 atom 可議 |
| r-cite-01 | cited | 可辯稱 adopted（把結論當審查原則）；路標 containment 0.76 是本集最高 |
| r-unk-14 | unknown | rescue 命中（讀檔）≠ 採用；Phase 2「rescue 只作使用佐證」的邊界案例 |
| r-unk-15 | unknown | rescue-log 判 used、我判 unknown；'git push' 這種 token 該不該進 rescue 詞表 |
| r-unk-16 | unknown | 行為與 atom 一致但只有 cold 行：人工需決定「同題多顆」怎麼歸功 |
| r-unk-18 | unknown | 門檻邊界案例：rare_token_min 2→3 會把它翻成 not used |
| r-unk-19 | unknown | 事實上是「查證後反其道而行」，介於 unknown 與 rejected 之間 |


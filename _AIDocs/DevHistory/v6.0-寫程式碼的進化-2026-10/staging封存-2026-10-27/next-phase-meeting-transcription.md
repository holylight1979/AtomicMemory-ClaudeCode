# next-phase：會議會後轉錄 → 摘要 → 入庫（＋補 Antigravity 文件）

> 本檔絕對路徑：`C:\Users\holylight\.claude\memory\_staging\next-phase-meeting-transcription.md`
> 專案根：`C:\Users\holylight\.claude`（原子記憶系統根層 repo，branch `main`）
> 人稱約定：[使用者]＝holylight；[AI]＝接手本檔的 Claude Code session；[同事]＝TSLG／SGI 專案成員。
> 前一份交接：`memory/_staging/next-phase-zhongtai-followup.md`。

## ⚠ 關鍵約束（先讀，逐字沿用）

- 根層 commit 一律等 [使用者] 單獨送一則「上GIT」才做，commit＋push 一氣；每步做完、驗完，列「改了哪些檔＋驗了什麼／沒驗什麼」問一次「上GIT？」；沒口令前**不碰 git**。
- 選擇性 staging 逐檔列路徑，**禁 `git add -A`**；只提交自己的檔，別的 session 的改動不動。
- 已 push 的 commit 不改寫（origin 雙 push URL：GitHub＋公司 GitLab，GitLab main 擋 force）。
- 全量 `python run_verify.py --json` 已從流程拔掉，不跑（全量改增量待補）；收尾只跑宣告的驗證範圍，偶發紅先單檔重跑再判。
- 背景 vcs-sync 會自動 commit 記憶層（atom／索引）——那是系統行為，不算「碰 git」；程式與文件仍等口令。
- Bash heredoc 含反斜線或大段中文時改用 Write 寫檔再跑。

## 狀態（2026-10-06 session a380adef）

**Step 0–3 全部做完、驗完；程式與文件尚未 commit，等 [使用者] 送「上GIT」。**
做法見 `_AIDocs/_CHANGELOG.md` 2026-10-06 條、`TECH.md` §6.6；驗收清單（全項打勾）`.claude/verify/done/acceptance-meeting-transcription.md`。

### Step 0 答案（[使用者] 拍板）
1. 錄音來源：音檔（m4a／mp3／wav），ffmpeg 統一轉。
2. 辨識機器：192.168.199.130（rdchat）。→ 實作走它的 Ollama `gemma4:e4b`（`/api/show` 標 `audio`），**不裝 faster-whisper**（22 port 開著但 ssh banner 逾時；Ollama 現成模型零安裝）。
3. 存放層：專案 `shared`，`--project <專案根>` 指定。原 Q2（公司層預開「會議決議」Lv1）因此不需拍板。

### 工作樹現況（`git status --short`，全是本 session 的）
```
 M Install-forAI.md              ← 選配項補 Antigravity
 M README.md                     ← Antigravity＋會議整理一句
 M TECH.md                       ← §6.6 新段、目錄樹一行、§5.8 Antigravity、skill-count marker
 M _AIDocs/Architecture.md       ← skill-count marker（hook 自動）
 M _AIDocs/DocIndex-System.md    ← ai-client-setup 補 Antigravity、meeting-transcribe 條目、marker
 M _AIDocs/_CHANGELOG.md         ← 2026-10-06 一條
 M _AIDocs/_INDEX.md             ← skill-count marker（hook 自動）
 M lib/atom_io.py                ← VALID_SOURCES + tool:meeting-transcribe
 M skills/_skill_index.json      ← 22→23（hook 自動）
?? skills/meeting/
?? tools/meeting-transcribe.py
?? tools/verify/verify_meeting_transcribe.py
```
兩顆 local atom（`ollama-gemma4-e4b-音訊輸入走images欄位-…`、`verify用importlib載入tools腳本-…`）已由背景 harvest 自動 commit（4770374、2575483）。

### 已驗（命令與結果）
- `python tools/meeting-transcribe.py --check` → 可以跑（ffmpeg、rdchat-direct gemma4:e4b audio OK）。
- 真 GPU 路徑：5 分鐘合成會議（三種 TTS 聲音，m4a／mp3 各一次）`--dry-run --json` → 2 段、31–35s、決議 5／待辦 8／未決 2，範疇落專案自訂 Lv1（UI演出／網路登入）正確。
- 真寫 atom：分得出 → `shared/<Lv1>/`；分不出 → `shared/_pending_review/`；無標題 → 回錯不吞。
- `pytest tools/verify/verify_meeting_transcribe.py` 16 passed；`hooks/verify/verify_no_window_spawn.py` PASS；`tools/skill-index.py --check` 23 無 drift；doc counts 13 passed；`normalize-eol.py --root --check` 無殘留。
- （歷史紀錄，全量拔掉之前跑的；之後不再跑）全量 `python run_verify.py --json`（15:27 單獨跑一份）→ total 2256、passed 2254、failed 0、errors 0、skipped 2、940s。

## 未解問題（每條可被回答）
- Q1：真人錄音的錯字率可接受嗎？（目前只測 TTS 合成音；`--glossary` 校正後仍有「美術→美數」類漏網）→ 第一場真實會議跑 `/meeting` 後看逐字稿再定。
- Q2：gemma4:e4b 一次吃 565s「同一段重複 8 次」的音檔，輸出被壓成一遍——是模型去重還是截斷？**待確認、勿據此鎖死設計**；生產切 180s 一段已避開，若要加長段才需驗。
- Q3：帶 `auth` 的 Ollama backend 要不要支援音訊路徑？（現況 config 沒有這種 backend，先不做。）

## 留給 [使用者] 的手動事項
- 送「上GIT」（本 session 會依上表逐檔列路徑 staging）。
- 通知 [同事]：更新 `~/.claude`、重啟、說「接上公司記憶」。
- 請美術把 `Install-forAI.md` 那段話貼給 Codex（repo 網址佔位字要先換成實際網址）；企劃用 Antigravity 同一段話。
- 清 TSLG 本機亂碼空資料夾：`svn revert "C:\TSLG\.claude\memory\shared\UIºt¥X"`（前兩份交接留下、未確認是否已做）。
- 第一場真實會議：`/meeting <音檔> 人名 …` 跑完看逐字稿錯字率，決定要不要換辨識模型。

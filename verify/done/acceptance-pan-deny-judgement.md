---
task_slug: pan-deny-judgement
session_id: c3305e50-26fe-44cf-9aec-825707b03c10
created_at: 2026-08-06
source: multifile
status: done
---
## 必須發生
- 監控 loop 偵測到 READY 後立即停止（cron job 刪除）
- 以「log 最後一筆 at」為截點凍結數據，截點後 entry 不回頭補算
- 四門檻逐條實證判讀：①≥2 相異 sid 有正樣本（探針 sid 至多計 1）②force_release 率 ≤20% ③無未解誤豁免 ④假陰性抽查（≤20 個回合全查）漏偵率 ≤5%
- 產出「翻 / 不翻」終局裁決 + 對應動作
- 刪除 `memory/_staging/pan_deny_ready_check.py`
- 判讀證據落長期文件（DevHistory）、結論落 atom、Architecture 的 mode 敘述與現況一致
- 以使用者視角完整回報裁決結論

## 禁止發生
- 不得偽造 / 模擬 log 樣本
- 無正樣本不得切 deny（硬約束）
- 不重開已裁決的四門檻定義、不改門檻數值
- 未經使用者裁決不動手實作替代資料源（prompt_id 對齊 / PostToolUse 側錄）
- 收尾 staging 用 pathspec，勿 `git add -A`

## 驗證指令
- `git status --short`（確認只有本任務檔案、無誤觸他人改動）
- `python -c "import json;print(json.load(open('workflow/config.json',encoding='utf-8'))['guard']['pre_action_notice']['mode'])"` → 應為 `warn`
- `ls memory/_staging/pan_deny_ready_check.py` → 應不存在
- `ls memory/_staging/next-phase-pan-deny.md` → 應不存在
- `python run_verify.py` → 綠燈數不低於基線 1259

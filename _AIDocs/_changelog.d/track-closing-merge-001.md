## 2026-10-27 收尾三段一次交齊：收尾檢核帶目標對照與知識收割，一次呼叫交完
- **AI 寫程式時會看到的**（守門總開關 v6 開；總開關關時 reconcile 欄不驗、不套用，行為同改動前）：
  - **收尾檢核可帶目標對照**（規則 CLOSING_RECONCILE_IN_REPORT）：`anti_evasion_report` 多一個選填欄 `reconcile`（格式同 need_goal action=reconcile 的 items／turns）。MCP 端同一套驗法（`tools/workflow-guardian-mcp/lib/anti-evasion.js` `aecArgErrors`），PostToolUse 交給同一個入口 `wg_need_goal.apply_op`（`hooks/handlers/post_tool_use._aec_reconcile`；同判法、同回覆、同樣記進目標檔），先套用再把樹附進 HUD 報告；報告記 `reconcile`＝applied／rejected／off／error。跟既有的 `harvest_items`（CLOSING_REPORT_ONE_CALL）一起交＝收尾三段一次交齊，Stop 不再要求另呼叫 need_goal reconcile、knowledge_harvest_report。套不上只少這段：收尾檢核照收，回覆寫明只要補交對照。舊的三支分開交照收。
  - **先提示**：三支工具的說明（`mcp.js`）都寫一次交齊；need_goal 的說明另寫「anti_evasion_report 還沒載入就趁別的工具呼叫同一批先載入」（004 R1 那跑收尾才載入，載入本身多一次呼叫）。MCP js 改了要 Reload 才生效。
  - **沒照做才擋，擋訊息寫缺哪段**（CLOSING_MISSING_PART_HINT）：(f2) 擋下時，本回合交過收尾檢核 → 寫「只補 need_goal reconcile，收尾檢核不用重交」；還沒交 → 寫一次交齊的走法（`stop.closing_reconcile_hint`）。收尾檢核閘的擋訊息、「後面還會擋」預覽的收尾檢核與知識收割兩列也寫一次交齊。判定、擋次不變。
  - **非寫碼回合不要求目標對照**（CLOSING_GOAL_CODING_ONLY）：(f2)(f3) 只在寫碼回合判（`stop._verify_gates` 新參數 `coding`：`handle_stop` 既有的 `_coding`，或本 session 改過程式且本回合交了收尾檢核）；例：續接單匯入的寫碼類舊樹、本 session 沒改程式，宣告完成不再要求完整對照。(f1)(f4) 照舊。知識收割閘沒動（預設交背景、不擋）。
  - **收尾那批認三支**（CLOSING_CALL_ALL_THREE）：`wg_closing_round.closing_call` 多認 knowledge_harvest_report（收尾檢核、need_goal reconcile 照認）；收尾前附著點與第二意見接縫都靠它。
- **關掉／繞過的機制**：非寫碼回合不再要求目標對照 (f2)(f3)；其餘閘的判定與擋次沒動。
- **省多少**（題 B′ 第一回合收尾段；事件帳重播 `_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/v6.0的代價-收尾合一-實測/closing_merge_replay.py`，輸入＝input＋cache_creation＋cache_read）：

  | 跑 | 砍前 | 砍後（嚴格／照新提示提早載入） | 省多少（嚴格／提早載入） |
  |---|---|---|---|
  | 004 R1 | 收尾 2 次呼叫（載入收尾檢核＋對照、收尾檢核），收尾類 Stop 擋 0 | 2／1 次 | 0／7.6 萬 token、10.7 秒 |
  | 004 R2 | 收尾 2 次呼叫（對照、收尾檢核），收尾類 Stop 擋 0 | 1／1 次 | 7.9 萬 token、9.3 秒 |

  同日交叉樣本 CCon-1／2／3：2→1、1→1（那跑本來就把兩支放同一批）、2→1，各省 7.5 萬／0／7.4 萬 token。
- **驗證**：新案例 `hooks/verify/verify_closing_merge.py`、`tools/workflow-guardian-mcp/verify/verify_aec_reconcile.js`；`verify_need_goal.py` 兩支案例的 state 補 `need_goal_code_decl_turn`（舊造法沒有任何寫碼回合訊號，跟真實流程不符；斷言不動）；`verify_release_rules.py` 檔尾把四條規則指到案例檔。合最新 main（a463c5c1）後目標範圍：verify_closing_merge、verify_need_goal、verify_release_rules、verify_closing_round、verify_gate_slimming、verify_gate_trim 共 631 綠；node verify_aec_reconcile.js（WG_CLAUDE_DIR 指暫存根）AEC_RECONCILE_CHECK PASS、smoke_mcp_stdio.js MCP_SMOKE_CHECK PASS、verify_mcp_texts_avoid_evasion_words 3 綠。拿 main f45be4ea 回放新案例：verify_closing_merge 7 紅 3 綠（綠的是舊三支照收、總開關關、案例腳本在，三支守舊行為的）、verify_aec_reconcile.js 8 項全紅。codex 一輪（只收弄壞資料／繞閘，原文 `C:/Users/holylight/.claude-wt/_evidence/track-closing-merge/codex_reply.md`）：審出 1 條【繞閘】採納——本 session 前幾回合改過程式、這回合不改也不說完成，只交不帶 reconcile 的收尾檢核，只看措辭的寫碼回合判法會跳過 (f2)；改成本 session 改過程式又交了收尾檢核也算交付邊界，補會紅案例 test_closing_check_after_earlier_code_edit_still_asks（修補前紅）。
- **已知限制**：省不省得到靠 AI 照說明一次交；分開交照收、不擋。收尾檢核在收尾才載入時，合一後仍要載入一次（嚴格重播 R1 省 0）。

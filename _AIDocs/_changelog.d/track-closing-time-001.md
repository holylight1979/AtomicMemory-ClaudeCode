## 2026-10-27 收尾只跑一輪：拐彎判斷與最該修在收尾前就送到；第二意見背景跑、跑完再接上
- **AI 寫程式時會看到的**（守門總開關 v6 開；三個開關程式內預設開、缺＝開，關了照舊送法，舊送法原處沒動）：
  - **拐彎判斷的量測改完程式就起跑**（規則 READING_PATH_EARLY_START，開關 `reading_path.early_start`；`hooks/wg_reading_path.early_start`，由新模組 `hooks/wg_closing_round.py` 在 PostToolBatch 呼叫）：每批工具跑完看本回合改過的程式檔指紋（只 stat、不起 git），變了就照收尾那套交背景量；量完的結果先存著（`EARLY_NOTE`），Stop 收到新的一批只送新的。原本要等第一次收尾才起跑，第一次收尾沒數據，第二次收尾才擋。
  - **收尾要問的在收尾前最後一個工具回應就送到**（TURN_JUDGMENT_PRE_CLOSE、PICK_ONE_PRE_CLOSE，開關 `pick_one.pre_close`）：交收尾檢核（anti_evasion_report）或完整對照（need_goal reconcile）那批，附上量好的拐彎判斷（到門檻的條目＋那一題）與「順手看到最該修」材料（判準卡照接：`workflow/entrypoints.json` 的 E04、E13 加 `mcp_reply` 路）；附了就記問過，Stop 不再為最該修讓對話續跑一輪，拐彎判斷照舊由 Stop 核對五欄。還有一批在量就不附，留給 Stop。
  - **Stop 的拐彎判斷擋下時，最該修同一則一起問**（PICK_ONE_WITH_TURN_JUDGMENT）：沒走到收尾前附著時，補一次就兩件都寫。
  - **第二意見 start 後不用等**（SECOND_OPINION_BACKGROUND，開關 `second_opinion.auto.background`）：擋訊息改寫「先把收尾其餘的事做完，收尾時還在跑寫等第二意見｜<job_id>」；MCP 端 `second_opinion_start` 的下一步、`second_opinion_result` 的說明改成同一個說法（`tools/workflow-guardian-mcp/lib/second-opinion.js`、`mcp.js`，要 Reload 才生效）。開了的 job（只認這批 start 自己回的 job_id、或收尾等待行寫明的，不掃 job 目錄）跑完而 AI 還沒取回 → 下一批工具回應或收尾提醒一次（SECOND_OPINION_DONE_NOTICE，state `second_opinion_watch`）；收尾寫過在等的 job，取回跑完那一回合照宣告完成判四行，不能靠之後不說完成跳過。
- **語意擴充（不是省）**：完整對照算進「最該修」的交付邊界。新的四跑 AI 都沒交收尾檢核、收尾也沒說完成，照舊規則最該修整回合不問（004 那兩跑是靠交了收尾檢核才問到）；現在交了完整對照就問，CT-3 多付 1.4 千 token、0 輪。
- **省多少**（題 B′ 第一回合，拐彎判斷＋最該修這兩個來源；砍前＝004 R1／R2，砍後＝本分支 hook 與 MCP 的無頭實跑，量尺同 `first_turn_breakdown.py`，輸入＝input＋cache_creation＋cache_read）：

  | 情境 | 砍前 | 砍後 | 省多少 |
  |---|---|---|---|
  | 走到收尾前附著點（004 兩跑都有交收尾檢核；新跑 CT-3 交了完整對照） | 17.4 萬 token；2 輪（擋 1＋續跑 1），Stop 3 次；額外呼叫 37.1 秒（含工具與 hook 41.6） | 0.28 萬（附著段被之後重讀：拐彎判斷 1,443＋最該修 1,405）；0 輪，Stop 2 次（另一次是同步提醒，跟這刀無關）；額外呼叫 0 秒，第一次收尾多寫兩段約 12 秒（推論） | 17.1 萬 token、2 輪、37 秒（扣多寫的約 25 秒） |
  | 沒走到（CT-5：收尾類工具一個都沒交） | 同上 | 拐彎判斷照擋 1 次，6.2 萬、8 秒，擋在第一次收尾；最該修不問（交付邊界沒到，舊碼也不問） | 0（擋點提早，次數不變） |

  第二意見另列（日常互動情境，不混進第一回合帳；無頭跑閘不觸發，004 十跑 0 次）：live 帳 60 次跑完的 job 開到 done 中位數 115.5 秒（p25 88、p75 143），舊提示叫 AI start 後直接呼叫 result 守著等；現在不用等，AI 照做時收尾少等這段（推論，量不到實測）。
- **耗時**：PostToolBatch 新增那段（行程內、離線量 CT-3 的 state）一般批次 1 ms、改了程式檔那批 112 ms＋起背景行程 80 ms、收尾類那批 622 ms（這 0.6 秒原本在 Stop 第一次收尾組最該修材料，搬家）。dispatcher（`hooks/dispatcher.py`，`workflow-guardian.py` 是轉接）沒有 >0.5 秒的段、沒動；Stop 的寫碼查核 0.6 秒沒動，跟著 Stop 次數少一次。
- **驗證**：新案例 `hooks/verify/verify_closing_round.py`（10 案：起跑／同批不重量／量測中又改記 pending／開關關照舊、結果先存 Stop 送一次且新的一批蓋掉舊的、收尾前附著與還在量不附、完整對照也是附著點而 set／verify_scope 不是、最該修收尾前附了 Stop 不再送與開關關照舊、一般批次不附、拐彎判斷擋下併問最該修、第二意見提示與 MCP 兩處說法一致、跑完提醒一次且取過不提醒、收尾在等→Stop 提醒→取回不寫四行照擋、前 8 碼相同的別的 session 的 job 不收）；拿 main 5ccf44d2、64795d98 回放都是 9 紅 1 綠（綠的是「一般批次不附」反例）。`verify_g9_second_opinion` 釘舊提示那案改成明設開關關；另修兩案的基底紅（main 把判準卡接尾從「判準卡（」改成「判準卡：」，兩案還照舊字面切，純 main 上也紅）。`verify_release_rules.py` 檔尾加一支把六條規則指到案例檔。目標範圍 42 支 pytest＋2 支 MCP js（合進 main 64795d98 之後）2184 綠、2 略過。codex 一輪（只收弄壞資料／繞閘）：第一次沙箱起不了子程序、讀不到檔，改把 diff 與新模組全文內嵌重問；審出 1 條【弄壞資料】採納——看守掃 job 目錄只比 session 前 8 碼，會把前 8 碼相同的別的 session 的 job 收進來、提醒取回別人的結果；改成只認這批 start 自己回的 job_id（hook 輸入的 tool_response，沒帶就照 tool_use_id 到本 session transcript 找），補會紅案例（修補前的程式回放只紅這一案）。無頭實跑 CT-1～5（CT-4 被點名打斷作廢），live 未動：五個受測 session id 在 live Logs、workflow、projects 都找不到。證據在 `C:\Users\holylight\.claude-wt\_evidence\track-closing-time\`。
- **已知限制**：收尾前附著靠 AI 交收尾檢核或完整對照；兩樣都不交（CT-5）就退回 Stop 送，拐彎判斷照舊擋一次。PostToolBatch 先寫 state 記「最該修問過」再輸出，hook 若剛好在兩者之間被取消，那一問會沒送到（只提醒、不擋）。

"""prompts.py — Prompt templates for Codex Companion assessments.

All prompts instruct Codex to output structured JSON.
Placeholders use {name} format for str.format().
"""

SANDBOX_CONSTRAINT = """\
【硬性沙盒約束】本任務純讀取與分析。禁止任何 git/edit/write/rm/mv/mkdir/touch \
/cp 等修改型指令；禁止呼叫 npm install/pip install 等下載安裝指令。\
僅允許 cat/grep/rg/Get-Content/Get-ChildItem/Select-String 等讀取指令。\
違反即任務失敗。
"""

OUTPUT_SCHEMA = """\
You MUST respond with a single JSON object (no markdown fences, no extra text):
{
  "status": "ok" | "warning" | "needs_followup",
  "severity": "low" | "medium" | "high",
  "category": "plan_gap" | "missing_evidence" | "laziness" | "architecture_risk" | "completion_risk" | "handoff_gap",
  "summary": "one-line summary in Traditional Chinese",
  "evidence": "the concrete fact you observed that justifies this verdict, in Traditional Chinese (cite tool trace / file path / heuristic flag)",
  "delivery": "ignore" | "inject",
  "confidence": "low" | "medium" | "high",
  "applies_until": "next_prompt" | "until_arch_change",
  "turn_index": 0,
  "corrective_prompt": "optional short corrective instruction for the AI agent, in Traditional Chinese (only if delivery=inject)"
}

Field rules:
- delivery=ignore: 你判斷此 turn 不需要打擾代理人。Claude 端會 SKIP 注入。
  使用時機：work appears coherent / heuristic flag is已被代理人對應處理 / 風險不足以打斷。
- delivery=inject: 確實需要 advisory。Claude 端會把 summary + corrective_prompt 注入下一輪。
  使用時機：發現具體缺漏、宣告與證據不一致、結構性風險未被認知。
- confidence: 你對此判斷的把握。low = 可能 false positive，high = 高度確信。
- applies_until: next_prompt = 此 advisory 一輪用完即丟；until_arch_change = 直到重要結構/設計改動為止仍有效。
- turn_index: 從 prompt 的 Turn Index Reference 段直接抄寫，方便去重與排序。
- 你已**沒有 BLOCK 權**。BLOCK 只屬同步 heuristics（confident_completion_without_evidence）。
"""

PLAN_REVIEW = """\
{sandbox_constraint}

You are a code review companion. An AI agent (Claude) has just created an implementation plan. \
Your job is to find gaps, missing steps, questionable assumptions, and risks that the agent may have overlooked.

## Turn Index Reference
turn_index = {turn_index}
（請在輸出 JSON 的 turn_index 欄位原樣抄寫此整數）

## User's Original Goal
{user_goal}

## Plan Content（實體計畫文件；超長時已頭尾採樣並附中段省略標記）
{plan_content}

## Files Examined by the Agent
{files_examined}

## Heuristic Flags (if any)
{heuristic_flags}

## Instructions
- Focus on what is MISSING (concrete missing steps / verification / edge cases), NOT on demanding more 「out of scope / 不在範圍」elaboration. The agent already follows an anti-evasion contract that lists「不動 / 不在範圍」sections by itself — do not push it to elaborate further unless concrete scope creep risk is observed.
- Check: are there steps that depend on untested assumptions?
- Check: is there a verification/testing step after implementation?
- Check: are edge cases or failure modes considered?
- Check: is the scope appropriate (concrete creep risk only — do not flag "too narrow" unless a critical dependency is genuinely missing)?
- Files Examined lists only files touched via monitored tools (Edit/Write/Bash and plan/handoff triggers). Read/Glob/Grep and sub-agent (`[Agent]`) activity are NOT monitored — do NOT infer the agent failed to examine a file merely because it is absent from this list.
- Be concise and specific. Do not praise or encourage. Only point out problems or confirm "ok".

{output_schema}
"""

TURN_AUDIT = """\
{sandbox_constraint}

You are a code review companion. An AI agent (Claude) has just completed a work turn. \
Your job is to evaluate whether the work was thorough, whether shortcuts were taken, \
and whether the results have sufficient evidence.

## Turn Index Reference
turn_index = {turn_index}
（請在輸出 JSON 的 turn_index 欄位原樣抄寫此整數）

## Session Working Directory
{cwd}

## User's Original Goal
{user_goal}

## Tool Trace (recent actions)
{tool_trace}

## Modified Files
{modified_files}

## Files Examined by the Agent
{files_examined}

## Last Assistant Reply (Tail)
{last_assistant_tail}

## Verification Evidence Found
{verification_evidence}

## Heuristic Triggered (Reference Only)
{heuristic_summary}

## Instructions
- Evaluate: did the agent actually DO what it said it would do? (check tool trace for evidence)
- Evaluate: were there verification steps (tests, builds, manual checks)? Cross-check Last Assistant Reply against Tool Trace — if reply claims "tests passed" but trace has no test command AND Verification Evidence Found is empty, that is a real gap.
- Evaluate: did the agent read necessary files before modifying them? Note: Files Examined lists only files touched via monitored tools (Edit/Write/Bash); Read/Glob/Grep and sub-agent (`[Agent]`) activity are NOT monitored — do NOT infer the agent failed to read a file merely because it is absent from this list.
- Evaluate: any signs of shortcuts (skipped steps, assumed success without checking)?
- Do NOT penalize if the turn was genuinely simple and complete — set delivery=ignore.
- Heuristic Triggered is reference only; do NOT echo it back. Form your own opinion based on the actual artifacts above.
- 不要因為代理人省略「不動 / 不在範圍」聲明就 flag — anti-evasion contract 是代理人端自管的紀律，本 audit 只在「真實偷埋 / 跳步」可見於 tool trace 時才標。
- Be concise. Only flag real issues. Use evidence field to cite the concrete observation (file path / trace step #).

{output_schema}
"""

ARCHITECTURE_REVIEW = """\
{sandbox_constraint}

You are a code review companion. An AI agent (Claude) has created or modified structural files \
(bridge, provider, adapter, service, client, etc.). Your job is to evaluate the design decision.

## Turn Index Reference
turn_index = {turn_index}
（請在輸出 JSON 的 turn_index 欄位原樣抄寫此整數）

## Session Working Directory
{cwd}

## Structural Files Changed
{arch_files}

## Recent Tool Trace
{tool_trace}

## Instructions
- Check: were alternatives considered?
- Check: is the abstraction level appropriate (too much? too little?)
- Check: are failure modes and rollback strategies addressed?
- Check: does this introduce unnecessary coupling?
- If the change is straightforward and appropriate, respond with status "ok"

{output_schema}
"""


HANDOFF_REVIEW = """\
{sandbox_constraint}

You are an adversarial handoff-quality reviewer. An AI agent (Claude) has just written a \
cross-session handoff / next-phase document. The NEXT session will see NONE of the current \
conversation — it has ONLY this document. Your job is to find the gaps that would make the next \
session lose context, drift, or act on wrong assumptions. The author cannot see its own blind \
spots — that is exactly why an independent reviewer exists. （全程繁體中文輸出。）

## Turn Index Reference
turn_index = {turn_index}
（請在輸出 JSON 的 turn_index 欄位原樣抄寫此整數）

## User's Original Goal (if captured)
{user_goal}

## Handoff / Next-Phase Document (the ONLY thing the next session will see)
{handoff_content}

## 對抗式檢核（逐項判「文件是否真的做到」，命中任一實質缺口即 needs_followup）
1. **為何而做**：新 session 讀完知道目標/動機（outcome·why），不只知道「做什麼」？
2. **決策理由**：每個已鎖定決策附一行 why？被否決的 alternative 有寫原因？
3. **未解問題**：獨立成區、每條是「可被回答的具體問句」，而非模糊待辦？
4. **只寫 delta**：本 session 特有/會變/接手必知；通用 SOP 用連結帶過、沒整段重貼稀釋重點？
   （注意：通用規則「沒整段重貼」是優點，**不要**因此 flag。）
5. **load-bearing 逐字保留**：數值/路徑/識別碼原樣保留，沒被改寫成「那個檔/之前的方法」這類斷鏈模糊描述？
6. **假設 vs 已驗證**：未驗證項有標「待確認、勿據此鎖死」？
7. **新舊矛盾顯式裁決**：以 X 為準、作廢 Y，沒並列丟給下游自己猜？
8. **關鍵約束/否定條件放首尾**：沒被埋在中段（lost-in-middle 會被下個 session 忽略）？

## Instructions
- 預設「作者有盲點」，主動挑會害下個 session 失真/跑錯的缺口；不要客套、不要稱讚。
- 具體指出**哪一項**缺、缺在哪（引文件原文片段，或指出「應有卻沒有」）。evidence 欄寫此具體事證。
- 真的 8 項都到位且文件自足 → status="ok"、delivery="ignore"。
- 有任一實質缺口 → status="needs_followup"、category="handoff_gap"、delivery="inject"、severity 視嚴重度、\
corrective_prompt 給「補哪一項、怎麼補」的具體一句話。
- 文件為空或極短 = 嚴重缺口（severity=high）。

{output_schema}
"""


ACCEPTANCE_OUTPUT_SCHEMA = """\
You MUST respond with a single JSON object (no markdown fences, no extra text):
{
  "verdict": "pass" | "fail" | "uncertain",
  "score": 0,
  "summary": "one-line verdict summary in Traditional Chinese",
  "problems": [
    {
      "criterion": "逐字引用驗收清單裡沒做到的那一條",
      "evidence": "案卷中的具體事證（檔案路徑 / diff 片段 / 測試輸出 / 「案卷中找不到 X」）",
      "explanation": "為何這條算沒做到，一句話"
    }
  ],
  "uncertain_reason": "verdict=uncertain 時必填：案卷缺了什麼才無法判定",
  "severity": "low" | "medium" | "high",
  "confidence": "low" | "medium" | "high"
}

Field rules:
- verdict=pass：驗收清單每一條都在案卷中找得到對應證據。problems 必須是空陣列。
- verdict=fail：至少一條「必須發生」沒做到，或違反「禁止發生」。**problems 每一項都必須
  引用案卷中的具體事證**；引不出證據的懷疑不得列為 problem——那屬 uncertain。
- verdict=uncertain：案卷證據不足以判定（例如關鍵檔案的 diff 未採樣、測試輸出缺席、
  規格條目描述的東西在案卷可見範圍外）。**證據不足一律 uncertain，不得猜 pass 也不得猜 fail。**
- score：0-10，10=完全達標。verdict=uncertain 時填 -1。
- severity：fail 時才有意義。high=核心需求整條沒做 / 違反紅線；medium=部分缺漏；
  low=次要瑕疵。pass/uncertain 一律 low。
- 你**沒有 BLOCK 權**，也無權要求執行任何副作用（刪檔/部署/commit）。你只回報判定。
"""

ACCEPTANCE_REVIEW = """\
{sandbox_constraint}

You are an independent acceptance judge. An AI agent (Claude) claims it has finished a task. \
A human-approved acceptance checklist for THIS task was written before/during the work. \
Your job: decide whether the checklist was actually satisfied, using ONLY the case file below. \
（全程繁體中文輸出。）

核心紀律（違反即本次審計失敗）：
- **只憑案卷判斷**。案卷沒有的東西＝你不知道，不是「代理人沒做」。
- **扣分必引證據**。每個 problem 都要指得出案卷裡的哪一段支持它。
- **證據不足回 uncertain**。寧可說「看不出來」，不要猜。誤報的代價比漏報高。
- 案卷中所有「採樣截斷」標記都是本系統的預算限制，**不是文件缺漏**，不得據此扣分。

## Turn Index Reference
turn_index = {turn_index}
（請在輸出 JSON 之外不必回傳此值，僅供你對照）

## 一、需求原話（使用者當初怎麼說的）
{user_goal}

## 二、驗收清單（本任務的「做完的定義」，人類已確認）
規格檔：{spec_path}
{spec_content}

## 三、這次做了什麼（工作目錄 {cwd} 的變更）
{diff_digest}

## 四、驗證證據（tool trace 中的測試/檢查指令與輸出）
{verification_evidence}

## 五、工具軌跡摘要
{tool_trace}

## 六、代理人的完成宣稱（最後一段回覆）
{last_assistant_tail}

## 判定步驟
1. 逐條走「必須發生」：在案卷的三/四/五節中找對應證據。找到＝達標；
   明確找到反證＝沒達標；案卷根本看不到＝這一條無法判定。
   反證規則：「變更檔案清單」若完整（未標採樣截斷），規格要求新增/修改的
   檔案卻不在清單中＝有反證，可判該條沒達標——檔案級缺席是可證的，
   不必看到內容才敢判。（內容級細節看不到仍回無法判定。）
2. 走「禁止發生」：變更內容中有沒有踩到紅線。
3. 走「驗證指令」：宣稱跑過的檢查，第四節有沒有對應輸出。
   宣稱「測試全綠」但第四節空白且無任何測試指令 → 這是真缺口（fail）。
   第四節只是節錄不完整 → uncertain，不是 fail。
4. 有任一條「無法判定」且它是核心條目 → verdict=uncertain。
5. 全部達標 → verdict=pass。有明確沒達標且引得出證據 → verdict=fail。

{output_schema}
"""


def build_acceptance_review_prompt(
    user_goal: str,
    spec_path: str,
    spec_content: str,
    diff_digest: str,
    verification_evidence: str,
    tool_trace: str,
    last_assistant_tail: str,
    cwd: str = "",
    turn_index: int = 0,
) -> str:
    """驗收裁判案卷（Phase 2）。

    材料由 acceptance.py 組（綁定/採樣/標記規則的唯一來源），本函式只負責
    填模板——材料組裝與提示詞不混在一起。
    """
    return ACCEPTANCE_REVIEW.format(
        sandbox_constraint=SANDBOX_CONSTRAINT,
        turn_index=turn_index,
        cwd=cwd or "(unknown)",
        user_goal=user_goal or "(未擷取到需求原話——若這是判斷關鍵請回 uncertain)",
        spec_path=spec_path or "(unknown)",
        spec_content=spec_content or "(規格檔讀取失敗——無驗收標準可依據，請回 uncertain)",
        diff_digest=diff_digest or "(無變更內容可依據，請回 uncertain)",
        verification_evidence=verification_evidence or "(無驗證證據)",
        tool_trace=tool_trace or "(no trace)",
        last_assistant_tail=last_assistant_tail or "(空——代理人可能靜默結束)",
        output_schema=ACCEPTANCE_OUTPUT_SCHEMA,
    )


def build_handoff_review_prompt(
    handoff_content: str,
    user_goal: str = "",
    turn_index: int = 0,
) -> str:
    """跨 session handoff/next-phase 文件的對抗式自檢（Q2 自檢機制）。

    把 skills/handoff Step 3.5 的 8 問交給獨立 codex 當「他評」checklist，補掉
    「作者自評抓不到自身盲點」的缺口（2026-06 dogfood 實證）。handoff_content 為
    next-phase 檔全文（PostToolUse 偵測 next-phase/handoff 檔寫入時讀入）。
    """
    return HANDOFF_REVIEW.format(
        sandbox_constraint=SANDBOX_CONSTRAINT,
        turn_index=turn_index,
        user_goal=user_goal or "(not captured — 由文件自述的目標判斷)",
        handoff_content=handoff_content or "(空文件 — 這本身就是嚴重缺口)",
        output_schema=OUTPUT_SCHEMA,
    )


def build_plan_review_prompt(
    user_goal: str,
    plan_content: str,
    files_examined: str,
    heuristic_flags: str = "None",
    turn_index: int = 0,
) -> str:
    return PLAN_REVIEW.format(
        sandbox_constraint=SANDBOX_CONSTRAINT,
        turn_index=turn_index,
        user_goal=user_goal or "(not captured)",
        plan_content=plan_content or "(no plan content available)",
        files_examined=files_examined or "(none)",
        heuristic_flags=heuristic_flags,
        output_schema=OUTPUT_SCHEMA,
    )


def build_turn_audit_prompt(
    cwd: str,
    tool_trace: str,
    modified_files: str,
    heuristic_flags: str = "None",
    turn_index: int = 0,
    user_goal: str = "",
    last_assistant_tail: str = "",
    verification_evidence: str = "",
    heuristic_summary: str = "",
    files_examined: str = "",
) -> str:
    """組出 turn-audit 提示。

    段落組成：
      * User's Original Goal — state.user_goal（首個非空 user prompt 前段）
      * Files Examined by the Agent — trace 內監測範圍工具接觸的檔案摘要
        （模板明示 Read/Glob/Grep/Agent 不在監測範圍，防「未讀檔」誤報）
      * Last Assistant Reply (Tail)  — 取自 state.last_assistant_tail
      * Verification Evidence Found  — assessor 抽自 trace 的 verify cmd 摘要
      * Heuristic Triggered (Reference Only) — heuristics.format_for_context 結果
    並把 turn_index 抄入 OUTPUT_SCHEMA 的 turn_index 欄位（codex 直接 echo）。

    `heuristic_flags` 仍保留（向下相容 plan_review 風格），但 turn_audit 場景
    應改用 `heuristic_summary`（語意明確：reference only 而非「Flag」）。
    """
    return TURN_AUDIT.format(
        sandbox_constraint=SANDBOX_CONSTRAINT,
        turn_index=turn_index,
        cwd=cwd or "(unknown)",
        user_goal=user_goal or "(not captured)",
        tool_trace=tool_trace or "(no trace)",
        modified_files=modified_files or "(none)",
        files_examined=files_examined or "(none)",
        last_assistant_tail=last_assistant_tail or "(empty — agent may have exited silently)",
        verification_evidence=verification_evidence or "(none found)",
        heuristic_summary=heuristic_summary or heuristic_flags or "None",
        output_schema=OUTPUT_SCHEMA,
    )


def build_architecture_review_prompt(
    cwd: str,
    arch_files: str,
    tool_trace: str,
    turn_index: int = 0,
) -> str:
    return ARCHITECTURE_REVIEW.format(
        sandbox_constraint=SANDBOX_CONSTRAINT,
        turn_index=turn_index,
        cwd=cwd or "(unknown)",
        arch_files=arch_files or "(none)",
        tool_trace=tool_trace or "(no trace)",
        output_schema=OUTPUT_SCHEMA,
    )

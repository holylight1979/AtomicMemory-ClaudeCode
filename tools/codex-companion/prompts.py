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

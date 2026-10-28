// mcp.js — MCP stdio JSON-RPC transport。buffer 私有於本檔（stdin loop + handleMessage 同檔）。
// handleToolCall lazy-require atom-tools 以化解 mcp<->atom-tools 循環相依。
const { VERSIONS } = require("./paths");
const { crashLog } = require("./log");

// ─── MCP Protocol ───────────────────────────────────────────────────────────

let buffer = "";

process.stdin.setEncoding("utf-8");
process.stdin.on("data", (chunk) => {
  buffer += chunk;
  processBuffer();
});

function processBuffer() {
  // Newline-delimited JSON (Claude Code 2.x transport format)
  let line;
  while ((line = extractLine()) !== null) {
    if (!line.trim()) continue;
    try {
      const parsed = JSON.parse(line);
      handleMessage(parsed);
    } catch (err) {
      crashLog("PARSE_ERROR", err);
      sendError(null, -32700, "Parse error");
    }
  }
}

function extractLine() {
  // Try newline-delimited first (what Claude Code actually sends)
  const nlIdx = buffer.indexOf("\n");
  if (nlIdx !== -1) {
    const line = buffer.slice(0, nlIdx);
    buffer = buffer.slice(nlIdx + 1);
    return line;
  }
  return null;
}

function sendResponse(id, result) {
  const msg = JSON.stringify({ jsonrpc: "2.0", id, result });
  process.stdout.write(msg + "\n");
}

function sendError(id, code, message) {
  const msg = JSON.stringify({ jsonrpc: "2.0", id, error: { code, message } });
  process.stdout.write(msg + "\n");
}

// ─── MCP Message Handler ────────────────────────────────────────────────────

function handleMessage(msg) {
  const { id, method, params } = msg;

  switch (method) {
    case "initialize":
      sendResponse(id, {
        protocolVersion: "2025-11-25",
        capabilities: { tools: { listChanged: false } },
        serverInfo: { name: "workflow-guardian", version: VERSIONS.guardian },
      });
      break;

    case "notifications/initialized":
      break;

    case "tools/list":
      sendResponse(id, { tools: TOOL_DEFINITIONS });
      break;

    case "tools/call":
      handleToolCall(id, params?.name, params?.arguments || {});
      break;

    default:
      if (id !== undefined) {
        sendError(id, -32601, `Method not found: ${method}`);
      }
  }
}

// ─── Tool Definitions ───────────────────────────────────────────────────────

const TOOL_DEFINITIONS = [
  {
    name: "atom_write",
    description:
      "Write or update an atom file with validated format. " +
      "Ensures correct metadata structure, runs write-gate dedup, " +
      "updates MEMORY.md index, and triggers vector indexing. " +
      "V4: supports shared/role/personal scopes; sensitive audience " +
      "(architecture/decision) on shared auto-routes to _pending_review/.",
    inputSchema: {
      type: "object",
      properties: {
        title: { type: "string", description: "Atom title (becomes # heading and filename slug)" },
        scope: {
          type: "string",
          enum: ["global", "shared", "role", "personal", "project", "org"],
          description: "V4 scope. shared=project-wide, role=role-shared (requires `role`), personal=per-user (requires `user` or defaults to current). global=cross-project. org=company layer (sugar: shared under workflow/config.json org_memory root; project_cwd ignored). project (legacy)=transparently mapped to shared. Defaults to shared. REALM GATE: when called from a project working dir, scope=global is REJECTED (all modes, skip_gate cannot bypass) if title/triggers/knowledge/actions mention any project-specific name (the project's top-level folder names, CLAUDE.md / Workspace_Map member names, repo-paths {codes}, absolute paths under the project root, or 「此專案/本專案」) — use scope=shared + project_cwd instead; feedback-* titles then land in <project>/.claude/memory/failures/<domain>/.",
        },
        role: {
          type: "string",
          description: "Role subdir name (e.g. art, programmer, planner). Required when scope=role.",
        },
        user: {
          type: "string",
          description: "Personal subdir owner. Required when scope=personal; falls back to current OS user.",
        },
        cross_project: {
          type: "boolean",
          description: "scope=personal only. true = the user's CROSS-PROJECT personal preference, stored at ~/.claude/memory/personal/<user>/ and visible to that user in every project (default false = personal-in-project at {proj}/.claude/memory/personal/<user>/, visible only in that project). Calls made from ~/.claude itself land cross-project automatically.",
        },
        audience: {
          type: "array", items: { type: "string" },
          description: "Audience tags (multi-role). On scope=shared, presence of 'architecture' or 'decision' auto-routes atom to _pending_review/ with Pending-review-by: management.",
        },
        pending_review_by: {
          type: "string",
          description: "Optional Pending-review-by metadata (e.g. 'management'). Auto-set for sensitive audience on shared.",
        },
        merge_strategy: {
          type: "string", enum: ["ai-assist", "git-only"],
          description: "Optional Merge-strategy metadata. Default ai-assist (omitted from file).",
        },
        realm: {
          type: "string", enum: ["core", "local"],
          description: "V5+ realm (orthogonal to scope; only effective when scope=global). 'core' (default) = cross-project knowledge in memory/, injected in every project. 'local' = ~/.claude-only knowledge routed to _AIDocs/_atoms/<domain>/, injected ONLY when the working dir is under ~/.claude (zero cost in external projects). Use 'local' for memory-system/tooling/brain-world knowledge that is irrelevant outside ~/.claude. The atom keeps scope=global; realm is derived from its path, not stored as a field.",
        },
        domain: {
          type: "string",
          description: "Category path under the layer root: '<Lv1>[/<Lv2>]'. REQUIRED for mode=create when scope=global (non-local realm), for feedback-* titles (Lv1 = failure topic → memory/Failures/<topic>/), and for scope=shared (→ shared/<Lv1>/). Lv1 is a CLOSED list (memory/_meta/taxonomy.json): 版控(vcs) | 工作流(workflow) | 思考與決策(thinking) | 驗證與實證(verify) | dotnet | OS-Windows(windows) | 文字與格式(text) | 設計通則(design) | 行為契約(conduct) | CC與原子記憶契約(cc-memory); EN slug/aliases accepted and snapped to the canonical name (e.g. 'vcs/git' → 版控/Git). Lv2 is free (created on demand). Unknown Lv1 → rejected unless allow_new_category=true. Ignored for append/replace (existing atom located via index). For realm=local this is instead the hierarchical local domain (e.g. 'MemDev' or 'OS/Windows/WSL'; roots World|Tools|MemDev; empty/invalid → 'Else').",
        },
        dry_run: {
          type: "boolean",
          description: "Preview without writing. create: runs the full gate chain (domain/category snap, [臨] rule, write-gate dedup, build+validate, budget) and reports the landing path/category — no file, no index, no conflict-detector side effects. append/replace: locates the existing atom and reports what would change. Default false.",
        },
        allow_new_category: {
          type: "boolean",
          description: "Allow `domain` to open a NEW Lv1 category not in taxonomy.json (still subject to reserved-name / charset checks). Default false. Prefer an existing Lv1; new Lv1s should be rare and deliberate.",
        },
        subdir: {
          type: "string",
          description: "Optional create-target subdir relative to the project memory root (slash-separated, scope=shared only), e.g. 'projects/AI-gen-X' → memory/projects/AI-gen-X/<slug>.md. Supports one-repo-multi-project partition layouts in a single write. Segments are sandboxed (no '..', no '_' prefix, protected dirs like personal/roles rejected). Only affects the create landing spot — append/replace locate the existing file via the index regardless of subfolder.",
        },
        confidence: { type: "string", enum: ["[固]", "[觀]", "[臨]"], description: "Confidence level" },
        triggers: {
          type: "array", items: { type: "string" },
          description: "Trigger keywords for MEMORY.md index",
        },
        knowledge: {
          type: "array", items: { type: "string" },
          description: "Knowledge lines (normally prefixed with [固]/[觀]/[臨]). A single element starting with | (markdown table) or ``` (code fence) is emitted verbatim as a block, no bullet — pass tables/code as their own element.",
        },
        actions: {
          type: "array", items: { type: "string" },
          description: "Action guidelines",
        },
        related: {
          type: "array", items: { type: "string" },
          description: "Related atom names (optional)",
        },
        supersedes: {
          type: "array", items: { type: "string" },
          description: "本顆取代的舊 atom 名（create/replace）。replace 時：不給＝保留原 Supersedes；[]＝清除；非空＝替換。被取代者不再注入但檔案保留。py 端拒：自指、沿既有鏈循環、目標為核心保護名、目標不存在。append 忽略。",
        },
        provenance: {
          type: "string",
          description: "Optional source of this knowledge: file path / URL / commit / session id. Rendered as `- Source:`. replace／append: omit=keep, \"\"=clear, non-empty=replace the whole Source line (append: include the old source in the value if it should stay).",
        },
        depends: {
          type: "array", items: { type: "string" },
          description: "Optional validity dependencies, e.g. [\"path:~/.claude/tools/entrypoint.py\"] (root-layer card) or [\"path:src/entrypoint.py\"] (project card, relative to project root). Cards are shared across machines: never write this machine's absolute path (C:/Users/<me>/...). Rendered as `- Depends:`; path: entries are machine-checked by health-check (missing → stale). replace: omit=keep, []=clear.",
        },
        entry: {
          type: "array", items: { type: "string" },
          description: "這張卡是哪幾個切入點的判準卡，代號查 workflow/entrypoints.json（如 [\"E04\", \"E08\"]）。程式在那個切入點問 LLM 時（擋訊息、deny、MCP 回覆）先把 Entry 命中的卡的知識段接在問句後面。Rendered as `- Entry:`。create 帶 entry 的卡不會被自動分到 local realm（ENTRY_BOUND_STAYS_CORE），scope=global 要給 core 的 domain。replace: omit=keep, []=clear；append 忽略。",
        },
        quote: {
          type: "string",
          description: "觸發這張卡片的使用者原話，單行 ≤200 字；通常由 PostToolUse 自動填，呼叫者不必給。Rendered as `- Quote:`（Source 之後）。replace／append: omit=keep, \"\"=clear, non-empty=replace.",
        },
        status: {
          type: "string",
          description: "Optional one-line current status (e.g. '案結 2026-07-29'). Shown alongside cold/one-line injections so the pointer carries minimal state. Current-state ONLY — no version history / change narrative.",
        },
        kind_hint: {
          type: "string",
          enum: ["pointer", "complement", "ledger", "hub", "plain"],
          description: "選填。宣告這張卡的型：pointer 指標／complement 互補／ledger 現況帳／hub 導讀卡／plain 一般。py 端仍會自判（hub＝kind_hint=hub 或標題含「導讀」或五段齊、ledger 日期數字對），hint 不能讓缺段卡過",
        },
        dedupe: {
          type: "object",
          properties: {
            verdict: { type: "string", enum: ["same", "supersedes", "different"] },
            of: { type: "string" },
            why: { type: "string" },
          },
          description: "去重宣告（create）。寫入閘回「需要宣告」（新內容和既有卡相似，列出候選卡）時才帶著重送：你判斷新內容和其中一張候選卡的關係。same＝同一條，知識段改併入那張卡（走 append；triggers／actions 不併）；supersedes＝取代，寫新卡並以 Supersedes 標那張（舊卡留檔、不再注入）；different＝不同，照常寫新卡。of＝候選卡名原字照抄，也可以是這次去重比對的層（回覆的 searched layers）裡其他存在的卡（不同層同名寫成 <layer>:<卡名>）；why＝一句理由（空白、佔位、純標點會被退回）。沒有命中相似時照宣告走：same／supersedes 的 of 要是那幾層裡存在的卡，different 照常寫並附 note。",
        },
        conflict: {
          type: "array",
          items: {
            type: "object",
            properties: {
              of: { type: "string" },
              verdict: { type: "string", enum: ["conflict", "not_conflict"] },
              why: { type: "string" },
            },
          },
          description: "衝突宣告（scope=shared create）。atom_write 回「衝突待宣告（這次不寫檔）」並列出要宣告的卡（這次向量前幾名）時才帶著重送：名單每張一條，多寫不在名單的會略過、不算錯。判兩張是不是同一件事、同一個範圍，而且不能同時成立；範圍不同各自成立、或一張補充另一張都不是衝突。not_conflict＝照寫；conflict＝落待審報告不寫 shared。of＝卡名原字照抄，why＝一句理由。都會留帳。",
        },
        scope_reason: {
          type: "string",
          description: "範疇理由（scope=global／org）。realm 閘只因字面「此專案／本專案」這類字樣擋下時才帶：一句說明為什麼這段是跨專案的（例：在講這個詞本身）。帶了照寫並留帳；專案專名、專案路徑命中照擋，這欄不放行。",
        },
        mode: {
          type: "string", enum: ["create", "append", "replace"],
          description: "create=new atom, append=add knowledge lines, replace=overwrite knowledge section",
        },
        project_cwd: {
          type: "string",
          description: "Project root path (required for scope=shared/role/personal). For scope=global it feeds the realm gate (project-name scan); omitted → the MCP process cwd (= session cwd) is used.",
        },
        skip_gate: {
          type: "boolean",
          description: "Skip the write-gate QUALITY/DEDUP check only (for [固] or explicit user request). Does NOT skip realm/scope checks: the project-name realm gate for scope=global and the category/domain gate always run.",
        },
        skip_conflict_check: {
          type: "boolean",
          description: "Skip write-time conflict detection (shared scope only). Use only for controlled migrations / tests.",
        },
      },
      required: ["title", "confidence", "triggers", "knowledge", "mode"],
    },
  },
  {
    name: "atom_promote",
    description:
      "Promote an atom's confidence level. " +
      "Eligible when Confirmations (cross-session) ≥4→[觀] / ≥10→[固], OR usefulness Wilson " +
      "lower-bound ≥ promote_lb with n ≥ min_n. ReadHits is exposure-only, not a promotion gate. " +
      "Use execute=false for dry-run. " +
      "When promoting to [固], pass merge_to_preferences=true to append knowledge " +
      "into preferences.md and archive the source atom (global scope only).",
    inputSchema: {
      type: "object",
      properties: {
        atom_name: { type: "string", description: "Atom filename without .md extension" },
        scope: { type: "string", enum: ["global", "project"], description: "Scope to search in" },
        project_cwd: { type: "string", description: "Project root (required for project scope)" },
        execute: { type: "boolean", description: "true=execute promotion, false=dry-run check only" },
        merge_to_preferences: {
          type: "boolean",
          description: "On [觀]→[固] promotion, auto-merge knowledge into preferences.md and archive this atom. global scope only. Default false.",
        },
      },
      required: ["atom_name", "scope", "execute"],
    },
  },
  {
    name: "atom_move",
    description:
      "V5 SoT-correct atom move/reconcile. Updates the single central _atom_index.json (via upsert/delete) and moves the .access.json sidecar with the .md; the _ATOM_INDEX.md mirror is auto-regenerated — it does NOT hand-edit per-folder indexes. " +
      "subcommand='move' relocates an atom to --to (a memory-root OR a subfolder under one — index root is auto-detected; the index scope is always preserved unless explicitly overridden via `scope`). " +
      "subcommand='reconcile' assumes the atom was manually moved to --at and fixes its index path + cross-layer refs. " +
      "Refuses atoms under _AIDocs/_atoms/ (use atom-set-realm) or _AIDocs/Failures/ (title-routed). Cross-root layering: down-refs (global→project) removed, up-refs kept, sibling refs warned. Self-validates via validate_index. Use dry_run=true to preview.",
    inputSchema: {
      type: "object",
      properties: {
        subcommand: { type: "string", enum: ["move", "reconcile"], description: "move=mv + sync JSON SoT + sidecar; reconcile=sync only (atom already at target)" },
        atom: { type: "string", description: "Atom slug (filename without .md)" },
        from: { type: "string", description: "Source dir — atom located via index/slug; index root auto-detected by walking up (required for move)" },
        to: { type: "string", description: "Target folder — a memory-root or any subfolder under one (required for move)" },
        at: { type: "string", description: "Dir at/under the memory-root where the atom now lives (required for reconcile)" },
        scope: { type: "string", description: "Explicitly set the index scope on move (optional). Default: preserve the existing index scope — moves never reset scope on their own; scope_changed in the report is honest." },
        dry_run: { type: "boolean", description: "Preview without applying changes" },
      },
      required: ["subcommand", "atom"],
    },
  },
  {
    name: "atom_edit_meta",
    description:
      "Surgically edit an atom's metadata (Trigger / Related / Tags / Entry) in place — " +
      "no full-file rebuild. Locates <atom_name>.md via py lib/atom_io.locate_atom (single " +
      "authority: global memory/ + memory/Failures/ + _AIDocs/_atoms/; project shared → " +
      "personal(current user) → role when scope=project), then " +
      "delegates to lib/atom_io.edit_metadata through the audit funnel. " +
      "Pass any subset of triggers/related/tags/entry; at least one is required. " +
      "Each provided field fully replaces that field's existing value.",
    inputSchema: {
      type: "object",
      properties: {
        atom_name: { type: "string", description: "Atom filename without .md extension" },
        scope: { type: "string", enum: ["global", "project"], description: "Scope to search in" },
        role: { type: "string", description: "Optional: also try the project's roles/<role>/ layer when scope=project" },
        user: { type: "string", description: "Optional: personal layer owner when scope=project (default current OS user)" },
        triggers: {
          type: "array", items: { type: "string" },
          description: "Replacement Trigger keywords (optional). Replaces the whole Trigger line.",
        },
        related: {
          type: "array", items: { type: "string" },
          description: "Replacement Related atom names (optional). Replaces the whole Related line.",
        },
        tags: {
          type: "array", items: { type: "string" },
          description: "Replacement Tags (optional). Replaces the whole Tags line.",
        },
        entry: {
          type: "array", items: { type: "string" },
          description: "Replacement Entry（切入點代號，查 workflow/entrypoints.json，如 [\"E04\"]；optional）。Replaces the whole Entry line and the index entry field; [] clears.",
        },
        project_cwd: { type: "string", description: "Project root (required for project scope)" },
      },
      required: ["atom_name", "scope"],
    },
  },
  {
    name: "anti_evasion_report",
    description:
      "結構化提交收尾檢核 (a)–(k)；內容走 Anti-Evasion HUD、chat 只留折疊 chip。" +
      "動 core 檔並宣告完成時由 Stop 閘要求。收尾只交這一份：report 寫給讀者的白話全文（做了什麼／驗了什麼／沒做什麼／追蹤項，" +
      "以讀者看得懂為先），給了 report 時 e／f／g 可省；收尾一次交齊：要記的知識放 harvest_items（同 knowledge_harvest_report 的 items），" +
      "不必另呼叫那支；目標對照不要求（交付時程式照收據代填，reconcile 欄選填、有自己的判斷才帶）。其餘欄必填（沒有 (c)）；未發生填「無」（(k) 不接受空字串）。" +
      "順序：先把值得留的知識 atom_write 寫完、再呼叫本 tool——報告是收尾檢核不是待辦清單，" +
      "(d)「尚未寫／見下一動」或 (h)「下一動＝寫 atom」會被 Stop 擋回、要求補寫後重新提交。" +
      "本 tool 只回 chip、不寫 state（one-writer：state/持久化由 Python PostToolUse 獨佔）。",
    inputSchema: {
      type: "object",
      properties: {
        report: { type: "string", description: "收尾全文，寫給沒看執行過程的讀者：做了什麼、驗了什麼（附數字或收據）、沒做什麼、追蹤項；白話、不預設欄位。給了它 e／f／g 可省（寫進這份裡）" },
        harvest_items: { type: "array", description: "知識收割清單（選填，格式同 knowledge_harvest_report 的 items；交了就不必另呼叫那支，(d) 可寫「見收割報告」）", items: { type: "object" } },
        reconcile: {
          type: "object",
          description: "目標對照（選填、不要求：交付時程式照收據代填；有自己的判斷才帶。格式同 need_goal action=reconcile：items 每個還活著的節點 {id, status, evidence?, followup?, note?, same_class?}、turns 選填）；" +
            "判法與回覆跟那支相同",
          properties: {
            items: { type: "array", items: { type: "object" }, description: "同 need_goal reconcile 的 items" },
            turns: { type: "integer", description: "這次拐了幾個彎（選填）" },
          },
        },
        a: { type: "string", description: "缺失發現與修補清單（`- 檔:行 — 改了什麼`）；無則「無」。必寫" },
        b: { type: "string", description: "AI 逃避通報（忽略/偷埋現象）；僅發生時填、否則「無」" },
        d: { type: "string", description: "記憶收錄帳：填之前先掃五個來源——①使用者指正/退回/重申的話（→ feedback）②重試≥2 次或查了才懂的機制/踩坑 ③外查來的事實（帶日期）④我做的取捨/契約/偏好 ⑤既有 atom 被證錯或要補的。逐項 `- <項目> → 已寫入 atom <名>`（atom_write 已完成）或 `- <項目> → 不寫（一句理由）`；判定不寫也要留痕。⛔ 不接受「尚未寫／待補／見下一動」——那是把記憶推給下一回合，會被拒收並擋 Stop；值得寫就在呼叫本 tool 之前寫完。本回合已交過收割報告（knowledge_harvest_report）可只填「見收割報告」。無則「無」。必寫" },
        e: { type: "string", description: "未告知決策＋未驗證假設：擅自的取捨（默默選了方案、跳過步驟、動了請求之外的檔）與做事時依賴但未驗證的假設；使用者沒看執行過程就不會知道的事都算。無則「無」" },
        f: { type: "string", description: "靜默狀態改變：對話輸出沒交代的環境副作用——安裝套件、改 config、重啟服務、建排程/cron、仍在跑的背景程序或 agent。無則「無」" },
        g: { type: "string", description: "版控收尾：本 session 改動哪些已 commit（hash 一句）、哪些未上及理由（併發 session 進度／待拍板／隱私）。無改動則「無」" },
        h: { type: "string", description: "收尾判定：單句——「可關閉」或「下一動＝…」。下一動只列使用者要做的事（重啟驗證、拍板）；寫 atom／補測試／commit 是你自己能做的，先做完再提交。必寫" },
        i: { type: "string", description: "衍生暫存清單：一行一路徑 `<路徑> — <備註>`（絕對或相對 cwd，可 glob）。只列「你自己產生的暫存／中間產物、此刻尚存、留給使用者裁決」的（scratchpad 腳本、.bak、一次性 log、undo 檔）；已刪的不列、純說明不列（預設完工即刪）。⛔ 絕不列正式產出：改了還沒 commit 的 code／doc／atom／索引／CHANGELOG 屬 (a)(b)/(g) 未同步事項，不是暫存——這些路徑會被拒收並回警。Python 端解析進 per-session 殘檔帳本，HUD 以 exists() 列尚存者供保留/刪除。無則「無」。必寫" },
        j_evidence_path: { type: "string", description: "證據持久路徑：本回合驗證收據的持久位置，一行一路徑（絕對路徑）。本 session 跑過哨兵驗證（Bash／PowerShell 輸出 `<NAME>_CHECK PASS|FAIL|DONE`）時填「無」或留空即可：系統自動帶入本 session 收據帳本的絕對路徑（帳本在資料根，不必自己找）；要另附驗證輸出檔／報告檔才填它們，填了就用你填的，Stop 對帳閘會查 exists()，不存在會擋。沒有收據填「無」。必寫" },
        k_followups: { type: "string", description: "追蹤項：還沒做完、之後要追的事，一行一項 `[<部位>] <要追什麼>` 或 `<部位>｜<要追什麼>`（Python 端只寫進追蹤帳本 workflow/tracking/<slug>.jsonl，不寫病灶文件；有部位的，之後碰到那個部位時接在導讀卡末段【未結追蹤項】送出，沒部位的在開場列出）。跟帳上已記的（本 session 的 need_goal followup、PickOne、先前的 k）是同一件 → 行尾加「｜同追蹤項：<那筆裡連續至少 8 字>」，系統換成新說法、不另記一筆；字面相同的自動不重記。沒有寫「無」；⛔ 不接受空字串（Stop 會擋）。必寫" },
      },
      required: ["a", "b", "d", "h", "i", "j_evidence_path", "k_followups"],
    },
  },
  {
    name: "knowledge_harvest_report",
    description:
      "階段完工知識收割回報：宣告完成時由 Stop 閘（KnowledgeHarvest）要求呼叫。" +
      "順序：先把本場值得留的知識用 atom_write（create/append/replace、supersedes）寫完、無用 atom 用 atom_retire 退役，" +
      "再呼叫本 tool 列出每一項盤點結果。掃六個來源：①使用者指正/退回/重申 ②重試≥2 次或查了才懂的機制/坑 " +
      "③外查事實（帶日期）④我做的取捨/契約/偏好 ⑤既有 atom 被證錯或要補 ⑥本場證實無用且無人引用的 atom。" +
      "判準：只寫「從程式碼/文件讀不出來、之後會重查或重犯」的；一次性事實不寫（action=skip 附 reason 留痕）。" +
      "action≠skip 必填 atom 與 path，path 必須是 atom_write/atom_retire 結果最後一行 receipt 的絕對路徑（retired 填退役前路徑）；" +
      "items=[] 表示本場無值得寫的（照樣要呼叫）。收尾要交收尾檢核時，改放進 anti_evasion_report 的 harvest_items 一次交，不必另呼叫本 tool。" +
      "本 tool 只回 chip、不寫 state（one-writer：items 與本 session receipt 的逐項核對、state/ledger 由 Python PostToolUse 獨佔；核不過會以 Harvest-Pending 擋一次要求補）。",
    inputSchema: {
      type: "object",
      properties: {
        items: {
          type: "array",
          description: "盤點清單；本場無值得寫的給 []。",
          items: {
            type: "object",
            properties: {
              source: {
                type: "string",
                enum: ["correction", "mechanism", "external_fact", "decision", "atom_fix", "atom_retire"],
                description: "知識來源：correction=使用者指正；mechanism=機制/踩坑；external_fact=外查事實；decision=取捨/契約/偏好；atom_fix=既有 atom 修正；atom_retire=退役",
              },
              summary: { type: "string", description: "一句話說這條知識是什麼" },
              action: {
                type: "string",
                enum: ["created", "appended", "replaced", "superseded", "retired", "skip"],
                description: "已做的動作（呼叫本 tool 前已完成）；skip=判定不寫",
              },
              atom: { type: "string", description: "atom 名（action≠skip 必填）" },
              path: { type: "string", description: "receipt 回的絕對路徑（action≠skip 必填；retired 填 old_path）" },
              scope: { type: "string", enum: ["global", "shared", "personal", "role", "local", "org"], description: "落點層" },
              reason: { type: "string", description: "action=skip 必填：一句為何不寫" },
              route: {
                type: "string",
                enum: ["part_doc", "global", "org", "local", "shared", "candidate_global"],
                description: "選填。萃取路由：part_doc=有部位→該部位病灶文件＋卡一行指標（必帶 part）；global=去專案細節後跨專案；org=全公司；local=只在記憶系統；shared=專案；candidate_global=realm 拒後先落 shared 標候選全域。global／candidate_global 的 summary 不得帶專案名（先 atom_io_cli action=scrub）",
              },
              candidate_global: { type: "boolean", description: "選填。這條其實是跨專案通則、只因 realm 閘先落 shared" },
              part: { type: "string", description: "選填。部位名（route=part_doc 必填）" },
            },
            required: ["source", "summary", "action"],
          },
        },
        note: { type: "string", description: "選填：整場補充說明" },
      },
      required: ["items"],
    },
  },
  {
    name: "atom_retire",
    description:
      "退役一顆無用／錯誤且無人引用的 atom：連同 _atom_index.json 條目、向量索引、MEMORY.md 目錄列一起清掉，" +
      "檔案搬到 _distant/<yyyy_mm>/（可還原：memory-audit --restore）。" +
      "護欄全在任何異動之前（py 單源）：[固] 拒（改用 atom_write supersedes 取代）；核心保護名拒（保護清單載入失敗也拒）；" +
      "被其他 atom 的 Related/Supersedes 引用拒（掃描含 personal 層）；不存在 → 明確錯誤不算成功。" +
      "索引／向量／搬移任一步失敗 → 回錯誤並列已完成與未完成步驟。" +
      "結果最後一行為 receipt（op=retire、old_path、new_path、index_ok），knowledge_harvest_report 的 retired 項填其 old_path。" +
      "本 tool 不寫 state（one-writer：receipt 由 Python PostToolUse 記帳）。",
    inputSchema: {
      type: "object",
      properties: {
        atom_name: { type: "string", description: "Atom 檔名（不含 .md）" },
        scope: {
          type: "string", enum: ["global", "shared", "personal", "role", "local", "org"],
          description: "atom 所在層：global=~/.claude/memory/（含 Failures/）；local=~/.claude/_AIDocs/_atoms/；shared/personal/role=專案層（需 project_cwd）；org=公司層（config org_memory 根的 shared，免 project_cwd）",
        },
        project_cwd: { type: "string", description: "專案根（scope=shared/personal/role 必填）" },
        role: { type: "string", description: "scope=role 的角色子夾" },
        user: { type: "string", description: "scope=personal 的擁有者（預設現用 OS 使用者）" },
        reason: { type: "string", description: "必填：為何退役（寫進 audit／merge history）" },
        dry_run: { type: "boolean", description: "只跑護欄與定位、不異動；回預計搬移路徑" },
      },
      required: ["atom_name", "scope", "reason"],
    },
  },
  {
    name: "memory_search",
    description:
      "一句話查原子記憶（唯讀）。走與 hook 注入同一條檢索管線：候選池（global + 本專案 shared + 本人 role/personal，" +
      "scope 可見性已收窄）→ trigger / BM25 / vector → RRF 融合排序。回 schema_version=1 的穩定結構：" +
      "results[{name, path, rel_path, scope, source, score, excerpt, author, audience, tags, status, provenance}] 與 warnings（同名跨層遮蔽、向量路關閉等）；" +
      "provenance＝該 atom 的 `- Source:` 行原值（空字串表示無）。" +
      "format=table（預設，人讀）| json（給程式／其他 AI）。不寫 state、不留 receipt。",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "要查的問題或關鍵字（必填）" },
        cwd: { type: "string", description: "以哪個專案目錄的視角查（決定專案層候選池）；預設 server 行程 cwd" },
        top_k: { type: "integer", description: "最多回幾筆（預設 8）" },
        format: { type: "string", enum: ["table", "json"], description: "回覆格式：table（預設）或 json（原始 JSON 字串）" },
      },
      required: ["query"],
    },
  },
  {
    name: "atom_source",
    description:
      "查一張 atom 的來源：Source 指標＋Quote 原句；transcript 還在則回該 uuid 前後各 1 則原文（state=live），" +
      "否則回 Quote（quote_only），都沒有回出處與『原對話已逾保留期』（unrecoverable）。唯讀，不寫 state、不留 receipt。",
    inputSchema: {
      type: "object",
      properties: {
        atom: { type: "string", description: "atom 名（不含 .md）或絕對路徑（必填）" },
        cwd: { type: "string", description: "專案根，用於定位專案層 atom；預設 server 行程 cwd" },
        format: { type: "string", enum: ["table", "json"], description: "回覆格式：table（預設）或 json（原始 JSON 字串）" },
      },
      required: ["atom"],
    },
  },
  {
    name: "second_opinion_start",
    description:
      "啟動第二意見（另一家模型 Codex 拿同材料獨立作答）。同步打包材料→雜湊→replay-guard pre，20 秒內回三行 " +
      "`job_id: <id>` / `hash: <sha256>` / `status: started|blocked|failed`；started 才在背景跑 codex（60～300 s），" +
      "之後用 second_opinion_result({job_id}) 取結果。mode=independent 不收 draft（獨立作答不能看到己方答案，帶了直接拒）；" +
      "mode=review 必須帶 draft（拿目標逐段評草稿：是這裡／不是這段）。replay-guard pre 非 PASS → blocked 不 spawn；" +
      "codex 探針起不來 → failed、不退 claude。模型名經 ~/.codex/models_cache.json 精確比對（預設 gpt-6-astra）。" +
      "不碰 state；job 目錄 workflow/second-opinion/<ts>-<sid8>-<kind>/。",
    inputSchema: {
      type: "object",
      properties: {
        kind: { type: "string", enum: ["diagnose", "evaluate", "stage-review"], description: "diagnose=診斷根因與風險；evaluate=評估做法是否達標／有無更簡單等價寫法；stage-review=階段交付審查" },
        part: { type: "string", description: "部位名（對 <root>/.claude/overview-map.md 的部位欄；找部位卡與病灶文件用）" },
        cwd: { type: "string", description: "專案內路徑（取 diff、找表、找帳本的起點）" },
        mode: { type: "string", enum: ["independent", "review"], description: "independent=同材料獨立作答（不給 draft）；review=拿目標逐段評草稿（必給 draft）" },
        question: { type: "string", description: "要它回答的問題或要達成的目標（必填）" },
        draft: { type: "string", description: "我方草稿／結論。只有 mode=review 收；independent 帶了直接拒" },
        sealed: { type: "array", items: { type: "string" }, description: "選填：封存答案關鍵字（回放實驗用）；提示詞或材料含任一個 → blocked" },
      },
      required: ["kind", "part", "cwd", "mode", "question"],
    },
  },
  {
    name: "second_opinion_result",
    description:
      "取第二意見結果：`status: running|done|failed|blocked`＋done 時三段「結論／證據／反例或未解」（超 20KB 截斷並附完整路徑）。" +
      "跑完了馬上回；還在跑會等到有結果再回（每次最多等約 100 秒，還在跑就再呼叫一次），所以可以先做收尾其餘的事、要結果時再呼叫，不用另開背景等待。" +
      "running 超過 timeout_s＋90 s 仍無更新 → 回 failed（背景子程序中斷不會永遠 running）。唯讀、不碰 state。",
    inputSchema: {
      type: "object",
      properties: {
        job_id: { type: "string", description: "second_opinion_start 回的 job_id（必填）" },
      },
      required: ["job_id"],
    },
  },
  {
    name: "project_smells",
    description:
      "專案壞味道候選池：回前 N 筆 [{rank, path, category, reason, source, age_days}]，category 只收 " +
      "hotspot|size|complexity|duplication|coupling|stale|custom。來源讀 <專案根>/.claude/overview-hub.json：" +
      "smells_report（報告檔；超過 smells_max_age_days 預設 7 只在表頭加一行 stale、資料照回）→ smells_cmd（逾時 smells_timeout_s 預設 20 回錯誤附指示）" +
      "→ 都沒有走 builtin（檔案大小＋近 60 天 git fix 熱點，代理量非判決）。無 reason 的列丟棄並回 dropped 數；" +
      "未知類別要在 smells_category_map 映射，沒映射的列丟棄並列出名稱。唯讀、不碰 state；回應 ≤25KB。",
    inputSchema: {
      type: "object",
      properties: {
        part: { type: "string", description: "部位名（過濾報告的 part 欄；builtin 以 <root>/<part> 為掃描範圍）（必填）" },
        cwd: { type: "string", description: "專案內路徑，往上找 .claude/overview-hub.json（必填）" },
        top_n: { type: "integer", description: "最多回幾筆（預設 overview-hub.json 的 candidate_top_n，再預設 5）" },
      },
      required: ["part", "cwd"],
    },
  },
  {
    name: "need_goal",
    description:
      "需求目標樹：先寫「真正要達成什麼」，工作中長子目標，收尾對照；action＝set｜add｜update｜reconcile｜read｜verify_scope。" +
      "set＝任務開始寫樹根 goal（整個需求一句、使用者的語言、只寫目標不寫手段），子目標同次放 items，要改程式帶 kind=code；被糾正時改這棵樹，真的換事才 new_task=true。" +
      "set／update 可一起交 locate=[{part, lines}]（定位行）與 data_files=[{path, why}]（改資料檔的宣告）。" +
      "也可不呼叫工具：先發不寫檔的 Bash，`目標｜<整個需求一句>`、`子目標｜<一件>` 行放它開頭的 `#` 註解，接著改檔，hook 讀走；回覆文字要早一則（同一則接著呼叫工具的文字 hook 讀不到）。" +
      "add＝再長的子目標；update＝改節點；reconcile＝完整對照（選用，每個活著的節點交終點結論＋證據，可放 anti_evasion_report 的 reconcile 欄）；read＝回目前的樹；verify_scope＝宣告驗證範圍。" +
      "寫碼類任務沒有樹不能改程式；本 tool 只驗參數、不寫檔。",
    inputSchema: {
      type: "object",
      properties: {
        action: { type: "string", enum: ["set", "add", "update", "reconcile", "read", "verify_scope"] },
        goal: { type: "string", description: "set：樹根一句" },
        new_task: { type: "boolean" },
        kind: { type: "string", enum: ["code", "knowledge"] },
        why: { type: "string" },
        import_from: { type: "string", description: "set：續接單路徑" },
        locate: {
          type: "array",
          description: "定位四行隨樹一起交，不必另發註解指令；lines＝定位｜部位／根因層／前例／批判",
          items: {
            type: "object",
            properties: { part: { type: "string" }, lines: { type: "array", items: { type: "string" } } },
            required: ["part", "lines"],
          },
        },
        parent: { type: "string", description: "add：父節點，省略＝樹根" },
        items: {
          type: "array",
          description: "set／add：[{text, clarity?, origin?, quote?}]；update：[{id, text?, status?, clarity?, origin?, quote?, why?}]；" +
            "reconcile：[{id, status(終點), evidence?, followup?, note?, same_class?}]；" +
            "verify_scope：[{target(測試檔／節點／資料夾／指令), why, inputs?(還讀的非程式檔), depends?(用到的程式檔), case_for?(驗的改過程式檔)}]",
          items: {
            type: "object",
            properties: {
              status: { type: "string", enum: ["todo", "doing", "done", "partial", "none", "dropped"] },
              clarity: { type: "string", enum: ["clear", "open"] },
              origin: { type: "string", enum: ["user", "inferred", "grown"] },
              quote: { type: "string", description: "標 origin=user 時引用的使用者原話子句（至少 6 字，或整句）" },
              evidence: {
                type: "array",
                description: "[{kind: receipt|case|file|atom, ref(receipt 寫 latest 或 R<號>), level: measured|read|inferred, covers?}]",
                items: { type: "object" },
              },
              same_class: { type: "string" },
              inputs: { type: "array", items: { type: "string" } },
              depends: { type: "array", items: { type: "string" } },
              case_for: { type: "array", items: { type: "string" } },
            },
          },
        },
        no_case: { type: "array", description: "verify_scope：[{path, reason}] 不需要新案例的改過程式檔", items: { type: "object" } },
        reviews: {
          type: "array",
          description: "verify_scope：[{leak, verdict: missed|unrelated, root_cause?, next_time?, reason?}] 範圍漏判逐筆檢討",
          items: { type: "object" },
        },
        turns: { type: "integer" },
        form: { type: "string", enum: ["full", "compact", "handoff"] },
        data_files: {
          type: "array",
          description: "資料檔宣告隨樹一起交，不必另發註解指令",
          items: { type: "object", properties: { path: { type: "string" }, why: { type: "string" } }, required: ["path", "why"] },
        },
      },
      required: ["action"],
    },
  },
];

// ─── Tool Handlers ──────────────────────────────────────────────────────────

function handleToolCall(id, toolName, args) {
  const { toolAtomWrite, toolAtomPromote, toolAtomMove, toolAtomEditMeta, toolAtomRetire, toolMemorySearch, toolAtomSource } = require("./atom-tools");
  switch (toolName) {
    case "memory_search":
      return toolMemorySearch(id, args).catch(e => sendToolResult(id, `memory_search error: ${e.message}`, true));
    case "atom_source":
      return toolAtomSource(id, args).catch(e => sendToolResult(id, `atom_source error: ${e.message}`, true));
    case "atom_retire":
      return toolAtomRetire(id, args).catch(e => sendToolResult(id, `atom_retire error: ${e.message}`, true));
    case "knowledge_harvest_report":
      // one-writer：只驗 schema、回 chip；receipt 核對／state／ledger 由 Python PostToolUse 獨佔。
      return require("./harvest").toolKnowledgeHarvestReport(id, args)
        .catch(e => sendToolResult(id, `knowledge_harvest_report error: ${e.message}`, true));
    case "second_opinion_start":
      // 不碰 state；同步 spawn prepare（20 s）→ started 才 detached 跑 execute（codex）。
      return require("./second-opinion").toolSecondOpinionStart(id, args)
        .catch(e => sendToolResult(id, `second_opinion_start error: ${e.message}`, true));
    case "second_opinion_result":
      return require("./second-opinion").toolSecondOpinionResult(id, args)
        .catch(e => sendToolResult(id, `second_opinion_result error: ${e.message}`, true));
    case "project_smells":
      // 唯讀：spawn tools/project-smells.py --json（25 s timeout+kill）。
      return require("./project-smells").toolProjectSmells(id, args)
        .catch(e => sendToolResult(id, `project_smells error: ${e.message}`, true));
    case "need_goal":
      // one-writer：只驗參數、回 chip；目標檔與編號由 Python PostToolUse（wg_need_goal.apply_op）獨佔。
      return require("./need-goal").toolNeedGoal(id, args)
        .catch(e => sendToolResult(id, `need_goal error: ${e.message}`, true));
    case "atom_write":
      return toolAtomWrite(id, args).catch(e => sendToolResult(id, `atom_write error: ${e.message}`, true));
    case "atom_promote":
      // toolAtomPromote 為 async，需 .catch 包 throw（與 atom_write/atom_move 一致）
      return toolAtomPromote(id, args).catch(e => sendToolResult(id, `atom_promote error: ${e.message}`, true));
    case "atom_move":
      return toolAtomMove(id, args).catch(e => sendToolResult(id, `atom_move error: ${e.message}`, true));
    case "atom_edit_meta":
      return toolAtomEditMeta(id, args).catch(e => sendToolResult(id, `atom_edit_meta error: ${e.message}`, true));
    case "anti_evasion_report":
      // one-writer：只回 chip、不碰 state（state/持久化/HUD 由 Python PostToolUse 獨佔）。
      return require("./anti-evasion").toolAntiEvasionReport(id, args)
        .catch(e => sendToolResult(id, `anti_evasion_report error: ${e.message}`, true));
    default:
      sendError(id, -32601, `Unknown tool: ${toolName}`);
  }
}

function sendToolResult(id, text, isError = false) {
  sendResponse(id, {
    content: [{ type: "text", text }],
    ...(isError && { isError: true }),
  });
}

module.exports = {
  sendResponse, sendError, sendToolResult, handleMessage, handleToolCall, TOOL_DEFINITIONS,
};

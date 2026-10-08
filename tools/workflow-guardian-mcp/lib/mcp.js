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
          description: "Optional source of this knowledge: file path / URL / commit / session id. Rendered as `- Source:`. replace: omit=keep, \"\"=clear, non-empty=replace.",
        },
        depends: {
          type: "array", items: { type: "string" },
          description: "Optional validity dependencies, e.g. [\"path:C:/abs/entrypoint.py\"]. Rendered as `- Depends:`; path: entries are machine-checked by health-check (missing → stale). replace: omit=keep, []=clear.",
        },
        quote: {
          type: "string",
          description: "觸發這張卡片的使用者原話，單行 ≤200 字；通常由 PostToolUse 自動填，呼叫者不必給。Rendered as `- Quote:`（Source 之後）。replace: omit=keep, \"\"=clear, non-empty=replace.",
        },
        status: {
          type: "string",
          description: "Optional one-line current status (e.g. '案結 2026-07-29'). Shown alongside cold/one-line injections so the pointer carries minimal state. Current-state ONLY — no version history / change narrative.",
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
      "Surgically edit an atom's metadata (Trigger / Related / Tags) in place — " +
      "no full-file rebuild. Locates <atom_name>.md via py lib/atom_io.locate_atom (single " +
      "authority: global memory/ + memory/Failures/ + _AIDocs/_atoms/; project shared → " +
      "personal(current user) → role when scope=project), then " +
      "delegates to lib/atom_io.edit_metadata through the audit funnel. " +
      "Pass any subset of triggers/related/tags; at least one is required. " +
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
        project_cwd: { type: "string", description: "Project root (required for project scope)" },
      },
      required: ["atom_name", "scope"],
    },
  },
  {
    name: "anti_evasion_report",
    description:
      "結構化提交收尾檢核 (a)–(i)；內容走 Anti-Evasion HUD、chat 只留折疊 chip。" +
      "動 core 檔並宣告完成時由 Stop 閘要求。九參都 required；未發生填「無」。" +
      "順序：先把值得留的知識 atom_write 寫完、再呼叫本 tool——報告是收尾檢核不是待辦清單，" +
      "(d)「尚未寫／見下一動」或 (h)「下一動＝寫 atom」會被 Stop 擋回、要求補寫後重新提交。" +
      "本 tool 只回 chip、不寫 state（one-writer：state/持久化由 Python PostToolUse 獨佔）。",
    inputSchema: {
      type: "object",
      properties: {
        a: { type: "string", description: "缺失發現與修補清單（`- 檔:行 — 改了什麼`）；無則「無」。必寫" },
        b: { type: "string", description: "AI 逃避通報（忽略/偷埋現象）；僅發生時填、否則「無」" },
        c: { type: "string", description: "Token 累積警示（Auto-Handoff 預警則附接續 prompt）；僅發生時填、否則「無」" },
        d: { type: "string", description: "記憶收錄帳：填之前先掃五個來源——①使用者指正/退回/重申的話（→ feedback）②重試≥2 次或查了才懂的機制/踩坑 ③外查來的事實（帶日期）④我做的取捨/契約/偏好 ⑤既有 atom 被證錯或要補的。逐項 `- <項目> → 已寫入 atom <名>`（atom_write 已完成）或 `- <項目> → 不寫（一句理由）`；判定不寫也要留痕。⛔ 不接受「尚未寫／待補／見下一動」——那是把記憶推給下一回合，會被拒收並擋 Stop；值得寫就在呼叫本 tool 之前寫完。無則「無」。必寫" },
        e: { type: "string", description: "未告知決策＋未驗證假設：擅自的取捨（默默選了方案、跳過步驟、動了請求之外的檔）與做事時依賴但未驗證的假設；使用者沒看執行過程就不會知道的事都算。無則「無」" },
        f: { type: "string", description: "靜默狀態改變：對話輸出沒交代的環境副作用——安裝套件、改 config、重啟服務、建排程/cron、仍在跑的背景程序或 agent。無則「無」" },
        g: { type: "string", description: "版控收尾：本 session 改動哪些已 commit（hash 一句）、哪些未上及理由（併發 session 進度／待拍板／隱私）。無改動則「無」" },
        h: { type: "string", description: "收尾判定：單句——「可關閉」或「下一動＝…」。下一動只列使用者要做的事（重啟驗證、拍板）；寫 atom／補測試／commit 是你自己能做的，先做完再提交。必寫" },
        i: { type: "string", description: "衍生暫存清單：一行一路徑 `<路徑> — <備註>`（絕對或相對 cwd，可 glob）。只列「你自己產生的暫存／中間產物、此刻尚存、留給使用者裁決」的（scratchpad 腳本、.bak、一次性 log、undo 檔）；已刪的不列、純說明不列（預設完工即刪）。⛔ 絕不列正式產出：改了還沒 commit 的 code／doc／atom／索引／CHANGELOG 屬 (a)(b)/(g) 未同步事項，不是暫存——這些路徑會被拒收並回警。Python 端解析進 per-session 殘檔帳本，HUD 以 exists() 列尚存者供保留/刪除。無則「無」。必寫" },
      },
      required: ["a", "b", "c", "d", "e", "f", "g", "h", "i"],
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
      "items=[] 表示本場無值得寫的（照樣要呼叫）。" +
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

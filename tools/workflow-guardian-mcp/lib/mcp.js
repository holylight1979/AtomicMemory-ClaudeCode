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
          enum: ["global", "shared", "role", "personal", "project"],
          description: "V4 scope. shared=project-wide, role=role-shared (requires `role`), personal=per-user (requires `user` or defaults to current). global=cross-project. project (legacy)=transparently mapped to shared. Defaults to shared. REALM GATE: when called from a project working dir, scope=global is REJECTED (all modes, skip_gate cannot bypass) if title/triggers/knowledge/actions mention any project-specific name (the project's top-level folder names, CLAUDE.md / Workspace_Map member names, repo-paths {codes}, absolute paths under the project root, or 「此專案/本專案」) — use scope=shared + project_cwd instead; feedback-* titles then land in <project>/.claude/memory/failures/<domain>/.",
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
      "本 tool 只回 chip、不寫 state（one-writer：state/持久化由 Python PostToolUse 獨佔）。",
    inputSchema: {
      type: "object",
      properties: {
        a: { type: "string", description: "缺失發現與修補清單（`- 檔:行 — 改了什麼`）；無則「無」。必寫" },
        b: { type: "string", description: "AI 逃避通報（忽略/偷埋現象）；僅發生時填、否則「無」" },
        c: { type: "string", description: "Token 累積警示（Auto-Handoff 預警則附接續 prompt）；僅發生時填、否則「無」" },
        d: { type: "string", description: "記憶收錄帳：本 session 值得留給日後的知識/經驗逐項列——`- <項目> → 已寫入 atom <名>` 或 `- <項目> → 不寫（一句理由）`。涵蓋：尚未紀錄的踩坑、帶日期戳的外查資料、個人/團隊偏好或契約、既有 atom 更新/重分類、重點歸納。判定不寫也要留痕。無則「無」。必寫" },
        e: { type: "string", description: "未告知決策＋未驗證假設：擅自的取捨（默默選了方案、跳過步驟、動了請求之外的檔）與做事時依賴但未驗證的假設；使用者沒看執行過程就不會知道的事都算。無則「無」" },
        f: { type: "string", description: "靜默狀態改變：對話輸出沒交代的環境副作用——安裝套件、改 config、重啟服務、建排程/cron、仍在跑的背景程序或 agent。無則「無」" },
        g: { type: "string", description: "版控收尾：本 session 改動哪些已 commit（hash 一句）、哪些未上及理由（併發 session 進度／待拍板／隱私）。無改動則「無」" },
        h: { type: "string", description: "收尾判定：單句——「可關閉」或「下一動＝…」。必寫" },
        i: { type: "string", description: "衍生暫存清單：一行一路徑 `<路徑> — <備註>`（絕對或相對 cwd，可 glob）。只列「你自己產生的暫存／中間產物、此刻尚存、留給使用者裁決」的（scratchpad 腳本、.bak、一次性 log、undo 檔）；已刪的不列、純說明不列（預設完工即刪）。⛔ 絕不列正式產出：改了還沒 commit 的 code／doc／atom／索引／CHANGELOG 屬 (a)(b)/(g) 未同步事項，不是暫存——這些路徑會被拒收並回警。Python 端解析進 per-session 殘檔帳本，HUD 以 exists() 列尚存者供保留/刪除。無則「無」。必寫" },
      },
      required: ["a", "b", "c", "d", "e", "f", "g", "h", "i"],
    },
  },
];

// ─── Tool Handlers ──────────────────────────────────────────────────────────

function handleToolCall(id, toolName, args) {
  const { toolAtomWrite, toolAtomPromote, toolAtomMove, toolAtomEditMeta } = require("./atom-tools");
  switch (toolName) {
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

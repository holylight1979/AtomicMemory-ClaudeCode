/**
 * Workflow Guardian MCP Server + HTTP Dashboard
 *
 * MCP stdio server (JSON-RPC): lets Claude query/update workflow state
 * HTTP server (port 3848): serves dashboard UI for the user
 *
 * Zero npm dependencies. Node.js 18+.
 */

const fs = require("fs");
const path = require("path");
const http = require("http");
const https = require("https");
const { exec } = require("child_process");
const worldChat = require("./world-chat");   // 腦內世界生物 LLM 對話代理（同進程模組）

// ─── Crash protection & logging ─────────────────────────────────────────────

const CLAUDE_DIR = path.join(require("os").homedir(), ".claude");
const WORKFLOW_DIR = path.join(CLAUDE_DIR, "workflow");
const CRASH_LOG = path.join(WORKFLOW_DIR, "guardian-crash.log");

// Hard cap so a crash loop can never fill the disk again. Root cause of the
// 2026-05 114GB guardian-crash incident: a non-Claude host (Codex) launched
// this MCP over stdio, the process threw on every event-loop tick, the
// uncaughtException handler logged-and-continued (no exit), and
// guardian-crash.log grew unbounded. The Python SessionStart rotation does not
// cover non-Claude hosts, so the writer itself must enforce a ceiling.
const CRASH_LOG_MAX_BYTES = 5 * 1024 * 1024;
let _crashLogging = false;
function crashLog(label, err) {
  if (_crashLogging) return;          // re-entry guard: prevent EPIPE cascade
  _crashLogging = true;
  try {
    const ts = new Date().toISOString();
    const msg = `[${ts}] ${label}: ${err?.stack || err}\n`;
    let oversized = false;
    try { oversized = fs.statSync(CRASH_LOG).size > CRASH_LOG_MAX_BYTES; } catch {}
    try {
      if (oversized) {
        // Cap hit: truncate to a single notice instead of appending forever.
        fs.writeFileSync(CRASH_LOG, `[${ts}] crash log hit ${CRASH_LOG_MAX_BYTES}B cap; truncated. Last: ${label}\n`);
      } else {
        fs.appendFileSync(CRASH_LOG, msg);
      }
    } catch {}
    try { process.stderr.write(`[workflow-guardian] ${label}: ${err?.message || err}\n`); } catch {}
  } finally {
    _crashLogging = false;
  }
}

// Break runaway loops: after too many fatal errors in one process, exit so the
// host restarts cleanly instead of spinning at ~95% CPU and appending forever.
// Recoverable crashLog callers (parse errors, index funnel) are NOT counted —
// only the truly-fatal global handlers below.
let _fatalCount = 0;
const FATAL_MAX_BEFORE_EXIT = 20;
function onFatal(label, err) {
  crashLog(label, err);
  if (++_fatalCount >= FATAL_MAX_BEFORE_EXIT) {
    try { process.stderr.write(`[workflow-guardian] ${_fatalCount} fatal errors; exiting to avoid runaway loop\n`); } catch {}
    process.exit(1);
  }
}

process.on("uncaughtException", (err) => { onFatal("UncaughtException", err); });
process.on("unhandledRejection", (reason) => { onFatal("UnhandledRejection", reason); });
// Actually exit on termination signals. Previously these logged but did NOT
// exit, leaving orphan node processes that could not be shut down normally.
process.on("SIGTERM", () => { crashLog("SIGTERM", "Process received SIGTERM"); process.exit(0); });
process.on("SIGINT", () => { crashLog("SIGINT", "Process received SIGINT"); process.exit(0); });
const MEMORY_DIR = path.join(CLAUDE_DIR, "memory");
// V5+ feedback-* 路由常數（MIRROR: lib/atom_locations.py — keep in sync）
const FAILURES_DIR = path.join(CLAUDE_DIR, "_AIDocs", "Failures");
const FAILURES_REL = "_AIDocs/Failures";
const FEEDBACK_TITLE_PREFIX = "feedback-";
// V5+ local realm（範疇限定）：本地知識物理落 _AIDocs/_atoms/<domain>/，索引仍在 memory/_atom_index.json。
// realm 由 index path 前綴推導（不存欄位）；注入閘門只在 cwd∈~/.claude 才納入。
// MIRROR: lib/atom_locations.py:LOCAL_ATOMS_* / local_write_target — keep in sync.
const LOCAL_ATOMS_DIR = path.join(CLAUDE_DIR, "_AIDocs", "_atoms");
const LOCAL_ATOMS_REL = "_AIDocs/_atoms";
const LOCAL_REALM_DOMAINS = new Set(["World", "Tools", "MemDev"]);
const LOCAL_REALM_DEFAULT_DOMAIN = "Else";
// 階層 domain 路徑最大深度（MIRROR: lib/atom_locations.py:LOCAL_REALM_MAX_DEPTH）。
const LOCAL_REALM_MAX_DEPTH = 7;
// V5+ realm 分類器（MIRROR: lib/atom_locations.py:classify_realm / CORE_PROTECTED_* /
// LOCAL_REALM_LEXICON — keep in sync；parity test_17 守漂移）。設計守則見 py 端註解：
// 核心保護硬擋 → 實例詞庫 → 安全預設 core；只掃 name + triggers，絕不用記憶系統通用詞。
const LOCAL_REALM_CORE_PROTECTED_PREFIXES = [
  "decisions", "workflow-", "toolchain", "feedback-", "memory-pipeline-", "atom-",
];
const LOCAL_REALM_CORE_PROTECTED_EXACT = new Set([
  "preferences", "cognitive-patterns", "goal-driven-verify-loopkarpathy-吸收",
]);
const LOCAL_REALM_LEXICON = {
  "腦內世界": "World", "world.html": "World", "reconcile-render": "World",
  "環境演化": "World", "env-layer": "World",
  "gdoc": "Tools", "harvester": "Tools", "electron-uia": "Tools",
  "electron 自動化": "Tools", "codex": "Tools", "logs_2.sqlite": "Tools", "反編譯": "Tools",
  "guardian-dashboard": "MemDev", "孤兒佔埠": "MemDev", "eaddrinuse": "MemDev",
};
const LOCAL_REALM_NAME_WEIGHT = 10;
const LOCAL_REALM_TRIGGER_WEIGHT = 1;

/** Realm 分類器（安全預設 core，僅高信心判 local）。回 {realm, domain, matched, protected}。
 *  只掃 name + triggers。MIRROR: lib/atom_locations.py:classify_realm — keep in sync. */
function classifyRealm(name, triggers) {
  const nm = (name || "").trim().toLowerCase();
  // 1) 核心保護硬擋（先於詞庫）
  if (LOCAL_REALM_CORE_PROTECTED_EXACT.has(nm) ||
      LOCAL_REALM_CORE_PROTECTED_PREFIXES.some(p => nm.startsWith(p))) {
    return { realm: "core", domain: null, matched: [], protected: true };
  }
  // 2) 實例詞庫掃描（name 權重 > trigger 權重，domain 消歧）
  const trigBlob = (triggers || []).map(t => (t || "").toLowerCase()).join(" ");
  const scores = {};
  const matched = [];
  for (const [term, dom] of Object.entries(LOCAL_REALM_LEXICON)) {
    let hit = 0;
    if (nm.includes(term)) hit += LOCAL_REALM_NAME_WEIGHT;
    if (trigBlob.includes(term)) hit += LOCAL_REALM_TRIGGER_WEIGHT;
    if (hit) { scores[dom] = (scores[dom] || 0) + hit; matched.push(term); }
  }
  if (Object.keys(scores).length === 0) {
    return { realm: "core", domain: null, matched: [], protected: false };
  }
  // 平手 → 依 sorted(LOCAL_REALM_DOMAINS) 固定序首位（對拍 py max(sorted, key)）
  const domsSorted = [...LOCAL_REALM_DOMAINS].sort();
  let bestDom = domsSorted[0];
  for (const d of domsSorted) {
    if ((scores[d] || 0) > (scores[bestDom] || 0)) bestDom = d;
  }
  // Domain 段字元集 guard（base lexicon 恆過；防污染詞庫的亂碼 domain 流出 —
  // 2026-06-12 韓文實案）。MIRROR: lib/atom_locations.py:classify_realm → _clean_segment。
  // 注意：須自足於 test_17 eval block（不得引用 cleanRealmSegment，定義在 block 外）。
  const segBad = (sg) => {
    const t = sg.replace(/\s+/g, " ").trim();
    return !t || t[0] === "_" || t[0] === "." || /[<>:"|?*]/.test(t) ||
           !/^[\x20-\x7E㐀-䶿一-鿿]+$/.test(t);
  };
  if (bestDom.split("/").filter(sg => sg.trim()).some(segBad)) {
    bestDom = LOCAL_REALM_DEFAULT_DOMAIN;
  }
  return {
    realm: "local", domain: bestDom,
    matched: [...new Set(matched)].sort(), protected: false,
  };
}
const TOOLS_DIR = path.join(CLAUDE_DIR, "tools");
const CONFIG_PATH = path.join(WORKFLOW_DIR, "config.json");
const REGISTRY_PATH = path.join(MEMORY_DIR, "project-registry.json");
const VERSION_PATH = path.join(CLAUDE_DIR, "version.json");
const DASHBOARD_PORT = loadConfig().dashboard_port || 3848;

function loadVersions() {
  try { return JSON.parse(fs.readFileSync(VERSION_PATH, "utf-8")); }
  catch { return { guardian: "0.0.0", atom_memory: "?" }; }
}
const VERSIONS = loadVersions();

function loadRegistry() {
  try {
    return JSON.parse(fs.readFileSync(REGISTRY_PATH, "utf-8"));
  } catch {
    return { projects: {} };
  }
}

/** Returns [{slug, memDir}] for all registered projects that have .claude/memory/ */
function getRegistryMemDirs() {
  const reg = loadRegistry();
  const results = [];
  for (const [slug, info] of Object.entries(reg.projects || {})) {
    if (!info.root) continue;
    const newMem = path.join(info.root, ".claude", "memory");
    if (fs.existsSync(newMem)) {
      results.push({ slug, memDir: newMem });
    }
  }
  return results;
}

function loadConfig() {
  try {
    return JSON.parse(fs.readFileSync(CONFIG_PATH, "utf-8"));
  } catch {
    return {};
  }
}

// ─── State File I/O ─────────────────────────────────────────────────────────

function listStatePaths() {
  try {
    return fs
      .readdirSync(WORKFLOW_DIR)
      .filter((f) => f.startsWith("state-") && f.endsWith(".json"))
      .map((f) => path.join(WORKFLOW_DIR, f));
  } catch {
    return [];
  }
}

function resolveSessionId(prefix) {
  // Support prefix matching: "3c7a47d0" → full UUID
  // Direct hit: exact filename exists → fast path
  const directPath = path.join(WORKFLOW_DIR, `state-${prefix}.json`);
  try { if (fs.existsSync(directPath)) return prefix; } catch {}

  // Prefix search: enumerate state files
  const ids = listStatePaths().map((p) =>
    path.basename(p).replace("state-", "").replace(".json", "")
  );
  const matches = ids.filter((id) => id.startsWith(prefix));
  if (matches.length === 1) return matches[0];
  if (matches.length === 0) return null;
  // Ambiguous: return null (caller handles error)
  return null;
}

function readState(sessionId) {
  const p = path.join(WORKFLOW_DIR, `state-${sessionId}.json`);
  try {
    return JSON.parse(fs.readFileSync(p, "utf-8"));
  } catch {
    return null;
  }
}

function writeState(sessionId, state) {
  state.last_updated = new Date().toISOString();
  const p = path.join(WORKFLOW_DIR, `state-${sessionId}.json`);
  const tmp = p + ".tmp";
  try {
    fs.mkdirSync(WORKFLOW_DIR, { recursive: true });
    fs.writeFileSync(tmp, JSON.stringify(state, null, 2), "utf-8");
    fs.renameSync(tmp, p);
  } catch {
    try { fs.unlinkSync(tmp); } catch {}
  }
}

function deleteState(sessionId) {
  const p = path.join(WORKFLOW_DIR, `state-${sessionId}.json`);
  try {
    fs.unlinkSync(p);
    return true;
  } catch {
    return false;
  }
}

function deriveSessionName(cwd) {
  if (!cwd) return "unknown";
  // Normalize path separators and extract last meaningful directory
  const parts = cwd.replace(/\\/g, "/").replace(/\/+$/, "").split("/").filter(Boolean);
  return parts[parts.length - 1] || "unknown";
}

function listAllSessions() {
  const cfg = loadConfig().cleanup || {};
  const DONE_TTL_MS    = cfg.ended_ttl_ms          || 60 * 1000;          // 1 min
  const ORPHAN_DONE_MS = cfg.orphan_done_ttl_ms     || 30 * 60 * 1000;    // 30 min
  const ORPHAN_WORK_MS = cfg.orphan_working_ttl_ms  || 24 * 60 * 60 * 1000; // 24 hr

  return listStatePaths().map((p) => {
    try {
      const state = JSON.parse(fs.readFileSync(p, "utf-8"));
      const sid = state.session?.id || path.basename(p).replace("state-", "").replace(".json", "");
      const now = Date.now();

      // ── Auto-cleanup (3-tier) ─────────────────────────────────────
      const safeTs = (v) => { const t = new Date(v).getTime(); return isNaN(t) ? 0 : t; };

      // Tier 1: ended_at is set → clean after 1 min
      if (state.ended_at) {
        const endedAge = now - safeTs(state.ended_at);
        if (endedAge > DONE_TTL_MS) {
          process.stderr.write(`[guardian] cleanup: ended session ${sid.slice(0,8)} (${Math.round(endedAge/60000)}min)\n`);
          try { fs.unlinkSync(p); } catch {}
          return null;
        }
      }

      // Tier 2: phase=done but no ended_at (orphan) → clean after 30 min
      if (!state.ended_at && state.phase === "done") {
        const lu = safeTs(state.last_updated);
        if (lu && (now - lu) > ORPHAN_DONE_MS) {
          process.stderr.write(`[guardian] cleanup: orphan-done ${sid.slice(0,8)} (${Math.round((now-lu)/60000)}min idle)\n`);
          try { fs.unlinkSync(p); } catch {}
          return null;
        }
      }

      // Tier 3: not done, no ended_at, no activity for 24h → dead session
      if (!state.ended_at && state.phase !== "done") {
        const ref = safeTs(state.last_updated) || safeTs(state.session?.started_at);
        if (ref && (now - ref) > ORPHAN_WORK_MS) {
          process.stderr.write(`[guardian] cleanup: stale-working ${sid.slice(0,8)} (${Math.round((now-ref)/3600000)}h idle)\n`);
          try { fs.unlinkSync(p); } catch {}
          return null;
        }
      }

      // ── Build session info ────────────────────────────────────────
      const startedAt = state.session?.started_at || "";
      const ageMs = startedAt ? now - new Date(startedAt).getTime() : 0;
      return {
        session_id: sid,
        name: deriveSessionName(state.session?.cwd),
        phase: state.phase || "unknown",
        project: state.session?.cwd || "",
        started_at: startedAt,
        modified_files_count: (state.modified_files || []).length,
        knowledge_queue_count: (state.knowledge_queue || []).length,
        sync_pending: state.sync_pending || false,
        age_minutes: Math.round(ageMs / 60000),
        ended: !!state.ended_at,
        muted: !!state.muted,
        merged_into: state.merged_into || null,
        skip_vector_init: !!state._skip_vector_init,
      };
    } catch {
      return null;
    }
  }).filter(Boolean);
}

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

// V5 P2 (2026-05-26): 4 internal IPC tools removed from MCP surface
// (workflow_status / workflow_signal / memory_queue_add / memory_queue_flush).
// Reason: these are hook-internal state ops that should not appear in Claude's
// tool menu. Replacements:
//   - workflow_status     → 由 SessionStart hook 自動注入 state 摘要
//   - workflow_signal     → Stop gate 自動偵測 git/svn clean 標 sync_completed
//   - memory_queue_*      → 由 wg_extraction extract-worker 全自動處理
// The toolXxx() handler functions below are kept temporarily as dead code
// (until P6 Wave 5 cleanup) so the file structure stays stable.
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
          description: "V4 scope. shared=project-wide, role=role-shared (requires `role`), personal=per-user (requires `user` or defaults to current). global=cross-project. project (legacy)=transparently mapped to shared. Defaults to shared.",
        },
        role: {
          type: "string",
          description: "Role subdir name (e.g. art, programmer, planner). Required when scope=role.",
        },
        user: {
          type: "string",
          description: "Personal subdir owner. Required when scope=personal; falls back to current OS user.",
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
          description: "Hierarchical sub-path for realm=local atoms (slash-separated, max depth 7, e.g. 'Tools' or 'OS/Windows/WSL'). Lv1 roots: World (brain-world) | Tools (external tools / env troubleshooting) | MemDev (memory-system / Guardian dev), or a new root. Go deeper only when a NARROW topic has large known content volume. Empty/invalid → 'Else' (catch-all).",
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
        mode: {
          type: "string", enum: ["create", "append", "replace"],
          description: "create=new atom, append=add knowledge lines, replace=overwrite knowledge section",
        },
        project_cwd: {
          type: "string",
          description: "Project root path (required for scope=shared/role/personal)",
        },
        skip_gate: {
          type: "boolean",
          description: "Skip write-gate quality check (for [固] or explicit user request)",
        },
        skip_conflict_check: {
          type: "boolean",
          description: "Skip V4 Phase 5 write-time conflict detection (shared scope only). Use only for controlled migrations / tests.",
        },
      },
      required: ["title", "confidence", "triggers", "knowledge", "mode"],
    },
  },
  {
    name: "atom_promote",
    description:
      "Promote an atom's confidence level. " +
      "Checks dual thresholds: [臨]→[觀] Conf≥4 or RH≥20, [觀]→[固] Conf≥10 or RH≥50. " +
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
      "Atomic atom move/reconcile across memory layers. " +
      "subcommand='move' moves atom from --from to --to (both memory-root dirs) and syncs _ATOM_INDEX/MEMORY.md/inbound refs. " +
      "subcommand='reconcile' assumes atom already lives at --at and cleans stale state elsewhere. " +
      "Enforces layering: down-refs (global→project) removed automatically, up-refs (project→global) kept, " +
      "sibling cross-project refs reported as warnings. Use dry_run=true to preview.",
    inputSchema: {
      type: "object",
      properties: {
        subcommand: { type: "string", enum: ["move", "reconcile"], description: "move=full mv + sync; reconcile=sync only (atom already at target)" },
        atom: { type: "string", description: "Atom slug (filename without .md)" },
        from: { type: "string", description: "Source memory root dir (required for move)" },
        to: { type: "string", description: "Target memory root dir (required for move)" },
        at: { type: "string", description: "Current memory root where atom lives (required for reconcile)" },
        dry_run: { type: "boolean", description: "Preview without applying changes" },
      },
      required: ["subcommand", "atom"],
    },
  },
  {
    name: "atom_edit_meta",
    description:
      "Surgically edit an atom's metadata (Trigger / Related / Tags) in place — " +
      "no full-file rebuild. Locates <atom_name>.md via the same scope resolution as " +
      "atom_promote (global memory, project layers, _AIDocs/Failures for feedback-*), then " +
      "delegates to lib/atom_io.edit_metadata through the audit funnel. " +
      "Pass any subset of triggers/related/tags; at least one is required. " +
      "Each provided field fully replaces that field's existing value.",
    inputSchema: {
      type: "object",
      properties: {
        atom_name: { type: "string", description: "Atom filename without .md extension" },
        scope: { type: "string", enum: ["global", "project"], description: "Scope to search in" },
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
];

// ─── Tool Handlers ──────────────────────────────────────────────────────────

function handleToolCall(id, toolName, args) {
  switch (toolName) {
    // V5 P2: workflow_status / workflow_signal / memory_queue_add / memory_queue_flush
    // no longer exposed in TOOL_DEFINITIONS — they fall through to default error.
    case "atom_write":
      return toolAtomWrite(id, args).catch(e => sendToolResult(id, `atom_write error: ${e.message}`, true));
    case "atom_promote":
      // S3.2: toolAtomPromote 改 async，需 .catch 包 throw（與 atom_write/atom_move 一致）
      return toolAtomPromote(id, args).catch(e => sendToolResult(id, `atom_promote error: ${e.message}`, true));
    case "atom_move":
      return toolAtomMove(id, args).catch(e => sendToolResult(id, `atom_move error: ${e.message}`, true));
    case "atom_edit_meta":
      return toolAtomEditMeta(id, args).catch(e => sendToolResult(id, `atom_edit_meta error: ${e.message}`, true));
    default:
      sendError(id, -32601, `Unknown tool: ${toolName}`);
  }
}

function toolWorkflowStatus(id, args) {
  if (args.session_id) {
    const resolved = resolveSessionId(args.session_id);
    if (!resolved) {
      return sendToolResult(id, `No state found for session ${args.session_id}`);
    }
    const state = readState(resolved);
    if (!state) {
      return sendToolResult(id, `No state found for session ${args.session_id}`);
    }
    const modFiles = (state.modified_files || [])
      .map((m) => `  - ${m.path} (${m.tool} @ ${m.at})`)
      .join("\n");
    const kqItems = (state.knowledge_queue || [])
      .map((q) => `  - ${q.classification} ${q.content}`)
      .join("\n");
    const text = [
      `## Session ${args.session_id}`,
      `- Phase: ${state.phase}`,
      `- CWD: ${state.session?.cwd || "?"}`,
      `- Started: ${state.session?.started_at || "?"}`,
      `- Sync pending: ${state.sync_pending}`,
      `- Stop blocked: ${state.stop_blocked_count || 0}x`,
      "",
      `### Modified files (${(state.modified_files || []).length})`,
      modFiles || "  (none)",
      "",
      `### Knowledge queue (${(state.knowledge_queue || []).length})`,
      kqItems || "  (none)",
    ].join("\n");
    return sendToolResult(id, text);
  }

  // List all sessions
  const sessions = listAllSessions();
  if (sessions.length === 0) {
    return sendToolResult(id, "No active workflow sessions.");
  }
  const lines = sessions.map(
    (s) =>
      `- **${s.session_id.slice(0, 8)}** | ${s.phase} | files: ${s.modified_files_count} | knowledge: ${s.knowledge_queue_count} | ${s.age_minutes}min${s.ended ? " (ended)" : ""}`
  );
  return sendToolResult(id, "## Active Sessions\n" + lines.join("\n"));
}

function toolWorkflowSignal(id, args) {
  const { session_id, signal } = args;
  const resolved = resolveSessionId(session_id);
  if (!resolved) {
    return sendToolResult(id, `No state found for session ${session_id}`, true);
  }
  const state = readState(resolved);
  if (!state) {
    return sendToolResult(id, `No state found for session ${session_id}`, true);
  }

  switch (signal) {
    case "sync_started":
      state.phase = "syncing";
      break;
    case "sync_completed":
      state.phase = "done";
      state.sync_pending = false;
      state.knowledge_queue = [];
      state.modified_files = [];
      state.ended_at = new Date().toISOString();
      break;
    case "reset":
      state.phase = "working";
      state.sync_pending = false;
      state.stop_blocked_count = 0;
      state.remind_count = 0;
      state.muted = false;
      break;
    case "mute":
      state.muted = true;
      break;
  }

  writeState(resolved, state);
  return sendToolResult(id, `Signal '${signal}' applied. Phase: ${state.phase}`);
}

function toolMemoryQueueAdd(id, args) {
  const { session_id, content, classification, trigger_context } = args;
  const resolved = resolveSessionId(session_id);
  if (!resolved) {
    return sendToolResult(id, `No state found for session ${session_id}`, true);
  }
  const state = readState(resolved);
  if (!state) {
    return sendToolResult(id, `No state found for session ${session_id}`, true);
  }

  state.knowledge_queue = state.knowledge_queue || [];
  state.knowledge_queue.push({
    content,
    classification: classification || "[臨]",
    context: trigger_context || "",
    at: new Date().toISOString(),
  });
  state.sync_pending = true;
  writeState(resolved, state);

  return sendToolResult(
    id,
    `Added to knowledge queue (${state.knowledge_queue.length} items): ${classification} ${content.slice(0, 60)}`
  );
}

function toolMemoryQueueFlush(id, args) {
  const { session_id } = args;
  const resolved = resolveSessionId(session_id);
  if (!resolved) {
    return sendToolResult(id, `No state found for session ${session_id}`, true);
  }
  const state = readState(resolved);
  if (!state) {
    return sendToolResult(id, `No state found for session ${session_id}`, true);
  }

  const count = (state.knowledge_queue || []).length;
  state.knowledge_queue = [];
  writeState(resolved, state);

  return sendToolResult(id, `Flushed ${count} knowledge queue items.`);
}

// ─── Atom Write/Promote Helpers ────────────────────────────────────────────

/** Convert title to a safe filename slug (lowercase, hyphens, no special chars) */
function slugify(title) {
  return title
    .toLowerCase()
    .replace(/[\s_]+/g, "-")
    .replace(/[^a-z0-9\u4e00-\u9fff\u3400-\u4dbf-]/g, "")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    || "untitled";
}

/** Detect an existing atom file in memDir whose name normalizes to the SAME slug
 *  but differs literally — e.g. a legacy underscore atom "client_il.md" when the
 *  incoming slug is "client-il" (slugify maps _→-). Without this guard, mode=create
 *  silently FORKS a near-duplicate atom that no append/replace path can ever reach.
 *  Returns the colliding filename (e.g. "client_il.md") or null. */
function findSeparatorVariant(memDir, slug) {
  let entries;
  try { entries = fs.readdirSync(memDir); } catch { return null; }
  for (const name of entries) {
    if (!name.endsWith(".md")) continue;
    const base = name.slice(0, -3);
    if (base === slug) continue;             // exact name handled by existsSync
    if (slugify(base) === slug) return name; // separator-variant collision
  }
  return null;
}

/** Build atom file content from structured parameters.
 *  V4: scopeLabel may be plain "shared"/"global" or composite "role:art"/"personal:alice".
 *  Optional metadata (audience/author/pending_review_by/merge_strategy/created_at)
 *  written only when present, in SPEC §4 order. */
function isBlockKnowledge(item) {
  // 表格列（| 開頭）或程式碼 fence（三反引號開頭）→ 原樣輸出 block。對拍 atom_spec.py
  const s = item.replace(/^\s+/, "");
  return s.startsWith("|") || s.startsWith("```");
}

function renderKnowledgeLines(knowledge) {
  // block-aware 渲染 ## 知識 區行清單。對拍 lib/atom_spec.py:render_knowledge_lines（須 byte-identical）
  const out = [];
  for (const k of knowledge) {
    if (isBlockKnowledge(k)) {
      if (out.length && out[out.length - 1] !== "") out.push("");
      out.push(...k.split("\n"));
      out.push("");
    } else {
      out.push(k.startsWith("- ") ? k : `- ${k}`);
    }
  }
  while (out.length && out[out.length - 1] === "") out.pop();
  return out;
}

function buildAtomContent({
  title,
  scope,
  confidence,
  triggers,
  knowledge,
  actions,
  related,
  audience,
  author,
  pendingReviewBy,
  mergeStrategy,
  createdAt,
  today,
}) {
  const _today = today || new Date().toISOString().slice(0, 10);
  const lines = [`# ${title}`, ""];
  lines.push(`- Scope: ${scope}`);
  if (audience && audience.length > 0) {
    lines.push(`- Audience: ${audience.join(", ")}`);
  }
  if (author) {
    lines.push(`- Author: ${author}`);
  }
  lines.push(`- Confidence: ${confidence}`);
  lines.push(`- Trigger: ${triggers.join(", ")}`);
  // Wave 2: Last-used / Confirmations / ReadHits 移到 <atom>.access.json，不再寫 .md
  if (pendingReviewBy) {
    lines.push(`- Pending-review-by: ${pendingReviewBy}`);
  }
  if (mergeStrategy && mergeStrategy !== "ai-assist") {
    lines.push(`- Merge-strategy: ${mergeStrategy}`);
  }
  lines.push(`- Created-at: ${createdAt || _today}`);
  if (related && related.length > 0) {
    lines.push(`- Related: ${related.join(", ")}`);
  }
  lines.push("", "## 知識", "");
  for (const line of renderKnowledgeLines(knowledge)) {
    lines.push(line);
  }
  lines.push("", "## 行動", "");
  if (actions && actions.length > 0) {
    for (const a of actions) {
      lines.push(a.startsWith("- ") ? a : `- ${a}`);
    }
  } else {
    lines.push("- （依知識內容判斷）");
  }
  lines.push("");
  return lines.join("\n");
}

/** Validate atom content structure. Returns null if valid, error string if invalid. */
function validateAtomContent(content) {
  if (content.includes("---\n") && content.indexOf("---\n") < 5) {
    return "YAML frontmatter (---) is forbidden in atom files";
  }
  if (!content.match(/^# .+/m)) {
    return "Missing # title heading";
  }
  if (!content.includes("## 知識")) {
    return "Missing ## 知識 section";
  }
  if (!content.includes("## 行動")) {
    return "Missing ## 行動 section";
  }
  const confMatch = content.match(/^- Confidence:\s*(.+)$/m);
  if (!confMatch || !["[固]", "[觀]", "[臨]"].includes(confMatch[1].trim())) {
    return "Missing or invalid Confidence metadata";
  }
  return null;
}

// V4: project root marker walk (mirrors hooks/wg_paths.find_project_root)
function findProjectRoot(cwd) {
  if (!cwd) return null;
  let p = path.resolve(cwd);
  for (let i = 0; i < 4; i++) {
    if (fs.existsSync(path.join(p, ".claude", "memory", "MEMORY.md"))) return p;
    if (fs.existsSync(path.join(p, "_AIDocs"))) return p;
    if (fs.existsSync(path.join(p, ".git")) || fs.existsSync(path.join(p, ".svn"))) return p;
    const parent = path.dirname(p);
    if (parent === p) break;
    p = parent;
  }
  return null;
}

// Mirrors wg_roles.get_current_user (env override + os user).
function getCurrentUser() {
  if (process.env.CLAUDE_USER) return process.env.CLAUDE_USER;
  try { return require("os").userInfo().username; } catch { return "unknown"; }
}

// SPEC 7.4 first-version sensitive audience set.
const SENSITIVE_AUDIENCE = new Set(["architecture", "decision"]);
function isSensitiveAudience(audience) {
  if (!Array.isArray(audience)) return false;
  return audience.some(a => SENSITIVE_AUDIENCE.has(String(a).trim().toLowerCase()));
}

/** Resolve the memory directory for a given scope.
 *  V4: shared / role / personal land in project subdirs;
 *  legacy "project" maps to "shared"; "global" unchanged.
 *  Returns { dir, error } — caller checks error.
 */
function resolveMemDir(scope, projectCwd, opts = {}) {
  scope = scope || "shared";

  // ─── S3.2 P3+P4: cwd-scope mismatch 防護 ────────────────────────────────
  // 防止「在專案 root 下用 scope=global 寫個人/專案知識到全域」與
  // 「在 ~/.claude 下用 scope=shared/role/personal 落到不存在的 V4 子層」。
  // force_global escape hatch 給 migration / 測試使用。
  const normCwd = (s) => {
    if (!s) return "";
    try { return path.resolve(s).toLowerCase(); }
    catch { return String(s).toLowerCase(); }
  };
  const claudeDirNorm = normCwd(CLAUDE_DIR);
  const cwdNorm = normCwd(projectCwd);
  const isUnderClaudeDir = cwdNorm && (
    cwdNorm === claudeDirNorm ||
    cwdNorm.startsWith(claudeDirNorm + path.sep.toLowerCase()) ||
    cwdNorm.startsWith(claudeDirNorm + "/")
  );

  if (scope === "global" && !opts.force_global) {
    // P3: 若 cwd 落在某個專案 root（非 ~/.claude）→ 拒絕（避免污染 global）
    if (cwdNorm && !isUnderClaudeDir) {
      const projRoot = findProjectRoot(projectCwd);
      if (projRoot && normCwd(projRoot) !== claudeDirNorm) {
        return { error:
          `scope=global rejected: cwd=${projectCwd} is inside project root=${projRoot}; ` +
          `use scope=shared/role/personal for project knowledge, or pass force_global=true`,
        };
      }
    }
  }

  if ((scope === "shared" || scope === "role" || scope === "personal") && isUnderClaudeDir) {
    // P4: ~/.claude 本身沒有 V4 sub-scope 結構（已被 P1 防護擋住）
    return { error:
      `scope=${scope} rejected: cwd=${projectCwd} is under ~/.claude itself; ` +
      `use scope=global for cross-project knowledge`,
    };
  }
  // ─── /S3.2 P3+P4 ────────────────────────────────────────────────────────

  if (scope === "global") {
    fs.mkdirSync(MEMORY_DIR, { recursive: true });
    return { dir: MEMORY_DIR, base: MEMORY_DIR };
  }

  // Legacy: scope=project returns root memory dir (no V4 subdir).
  // atom_write should pre-map project→shared via callers; here we keep legacy
  // root-dir behavior for atom_promote / readers that still pass "project".
  if (scope === "project" && projectCwd) {
    const projMem = path.join(projectCwd, ".claude", "memory");
    if (fs.existsSync(projMem)) return { dir: projMem, base: projMem };
    const norm = projectCwd.replace(/\\/g, "/").replace(/\/+$/, "");
    const slug = norm.replace(/[^a-zA-Z0-9]/g, "-").replace(/-+/g, "-");
    const projDir = path.join(CLAUDE_DIR, "projects", slug, "memory");
    if (fs.existsSync(projDir)) return { dir: projDir, base: projDir };
    return { dir: projMem, base: projMem };
  }

  if (scope === "role" && !opts.role) {
    return { error: "scope=role requires 'role' parameter (e.g., 'art', 'programmer')" };
  }
  if (scope !== "shared" && scope !== "role" && scope !== "personal") {
    return { error: `Unknown scope: ${scope}` };
  }

  const root = findProjectRoot(projectCwd || "");
  if (!root) {
    return { error: `No project root found for scope=${scope} (need .git/.svn/_AIDocs/.claude/memory/MEMORY.md marker under ${projectCwd || "(no cwd)"})` };
  }
  // ~/.claude itself is global memory; reject V4 sub-scopes there
  try {
    if (path.resolve(root) === path.resolve(CLAUDE_DIR)) {
      return { error: `cwd is ~/.claude itself; use scope=global for cross-project knowledge` };
    }
  } catch {}

  const base = path.join(root, ".claude", "memory");
  let dir;
  if (scope === "shared") dir = path.join(base, "shared");
  else if (scope === "role") dir = path.join(base, "roles", opts.role);
  else dir = path.join(base, "personal", opts.user);

  fs.mkdirSync(dir, { recursive: true });
  return { dir, base };
}

/** 已註冊 Failures atom（非 feedback- 前綴，如 cognitive-patterns / memory-pipeline-*）。
 *  MIRROR: lib/atom_locations.py:failures_atom_stems ∈ is_failures_routed_title。
 *  缺此判定時這些 atom 的 append/replace 會在 memory/ 找不到檔（2026-06-12 缺口修補）。 */
function isRegisteredFailuresStem(slug) {
  try {
    const data = JSON.parse(
      fs.readFileSync(path.join(MEMORY_DIR, "_atom_index.json"), "utf-8"));
    return (data.atoms || []).some(
      (a) => (a.path || "").startsWith(FAILURES_REL + "/") &&
        path.basename(a.path, ".md") === slug);
  } catch {
    return false;
  }
}

/** V5+ feedback-* 路由疊加。將 resolveMemDir 結果改寫為 _AIDocs/Failures/ 目的地。
 *  索引仍在 memory/_atom_index.json（單一索引來源）。
 *  MIRROR: lib/atom_locations.py:failures_write_target — keep in sync.
 *  Returns: { memDir, baseDir, indexDir, indexRoot, routedToFailures }.
 */
function applyFeedbackRouting(resolved, slug, scope) {
  // 預設沿用既有語意：indexDir = baseDir, indexRoot = baseDir 的父目錄
  let memDir = resolved.dir;
  let baseDir = resolved.base;
  let indexDir = baseDir;
  let indexRoot = path.dirname(baseDir);
  let routedToFailures = false;
  if (scope === "global" &&
      (slug.startsWith(FEEDBACK_TITLE_PREFIX) || isRegisteredFailuresStem(slug))) {
    fs.mkdirSync(FAILURES_DIR, { recursive: true });
    memDir = FAILURES_DIR;
    baseDir = FAILURES_DIR;
    indexDir = MEMORY_DIR;
    indexRoot = CLAUDE_DIR;
    routedToFailures = true;
  }
  return { memDir, baseDir, indexDir, indexRoot, routedToFailures };
}

/** 單段正規化（path-traversal 最後防線）。MIRROR: lib/atom_locations.py:_clean_segment。
 *  非法（空 / 含分隔 / `_`·`.` 前綴 / 不安全字元 / 非 CJK·ASCII 字元）→ ""
 *  （caller 截斷/退 fail-safe）。字元集 guard：LLM 生成 domain 視為不可信輸入，
 *  跨文字系統字元（Hangul「자동화」實案 2026-06-12）穿透 snap 防線 → 整段拒。
 *  MIRROR: lib/atom_locations.py:_SEG_ALLOWED_RE（parity test_22）。 */
function cleanRealmSegment(seg) {
  const s = (seg || "").replace(/\s+/g, " ").trim();
  if (!s || s.includes("/") || s.includes("\\")) return "";
  if (s[0] === "_" || s[0] === ".") return "";
  if (/[<>:"|?*]/.test(s)) return "";
  // 字元集 guard regex 內聯（test_22 eval block 自足性：不得引用函式外 const）
  if (!/^[\x20-\x7E㐀-䶿一-鿿]+$/.test(s)) return "";
  return s;
}

/** V5+ local-realm 路由：本地範疇 atom 物理落 _AIDocs/_atoms/<domain_path>/。
 *  realm 由 index path 前綴推導（不存欄位）。索引仍在 memory/_atom_index.json。
 *  domain 支援多段階層路徑（"OS/Windows/WSL"，mkdir-p 全鏈）；空/全非法 → DEFAULT。
 *  每段過 cleanRealmSegment 防寫到樹外。MIRROR: lib/atom_locations.py:local_write_target。
 *  Returns: { memDir, baseDir, indexDir, indexRoot }.
 */
function applyLocalRouting(domain) {
  const dom = (domain || "").trim() || LOCAL_REALM_DEFAULT_DOMAIN;
  let segs = dom.split("/").map(cleanRealmSegment).filter(Boolean).slice(0, LOCAL_REALM_MAX_DEPTH);
  if (segs.length === 0) segs = [LOCAL_REALM_DEFAULT_DOMAIN];  // fail-safe，永不寫到樹外
  const memDir = path.join(LOCAL_ATOMS_DIR, ...segs);
  fs.mkdirSync(memDir, { recursive: true });
  return { memDir, baseDir: memDir, indexDir: MEMORY_DIR, indexRoot: CLAUDE_DIR };
}

/** Find atom index path for a given scope (V3.2: prefer _ATOM_INDEX.md) */
function resolveMemoryIndex(memDir) {
  const atomIdx = path.join(memDir, "_ATOM_INDEX.md");
  if (fs.existsSync(atomIdx)) return atomIdx;
  return path.join(memDir, "MEMORY.md");  // fallback
}

/** V4 Phase 5: Run conflict-detector --mode=write-check.
 *  Returns Promise<{verdict, matches, detector_model, skipped, skip_reason, scope}>.
 *  Fail-open: on script error resolves to verdict=ok+skipped=true (do not block writes
 *  when detector infra is down). Longer timeout than write-gate (LLM is slower). */
function execConflictDetector(content, scope, projectCwd) {
  return new Promise((resolve) => {
    const scriptPath = path.join(TOOLS_DIR, "memory-conflict-detector.py");
    if (!fs.existsSync(scriptPath)) {
      return resolve({ verdict: "ok", matches: [], detector_model: "n/a",
                       skipped: true, skip_reason: "detector script missing", scope });
    }
    const args = ["--mode=write-check",
                  "--scope", scope,
                  "--content", content];
    if (projectCwd) {
      args.push("--project-cwd", projectCwd);
    }
    const cp = require("child_process").spawn("python", [scriptPath, ...args], {
      windowsHide: true,
    });
    let out = "", err = "";
    const timer = setTimeout(() => {
      try { cp.kill(); } catch {}
    }, 60000);  // 60s — vector + 3 LLM calls
    cp.stdout.on("data", d => { out += d.toString(); });
    cp.stderr.on("data", d => { err += d.toString(); });
    cp.on("close", () => {
      clearTimeout(timer);
      try {
        const parsed = JSON.parse(out.trim().split("\n").pop());
        resolve(parsed);
      } catch (e) {
        try { process.stderr.write(`[conflict-detector] parse error: ${e.message} stderr=${err.slice(0, 200)}\n`); } catch {}
        resolve({ verdict: "ok", matches: [], detector_model: "n/a",
                  skipped: true, skip_reason: "detector parse/exec error", scope });
      }
    });
    cp.on("error", (e) => {
      clearTimeout(timer);
      try { process.stderr.write(`[conflict-detector] spawn error: ${e.message}\n`); } catch {}
      resolve({ verdict: "ok", matches: [], detector_model: "n/a",
                skipped: true, skip_reason: "detector spawn error", scope });
    });
  });
}

/** V4 Phase 5: TSV append to {baseDir}/_merge_history.log. SPEC §10.
 *  baseDir is {proj}/.claude/memory/ (so log sits alongside shared/ roles/ personal/). */
function appendMergeHistory(baseDir, action, atom, scope, by, detail) {
  try {
    const safe = s => String(s || "-").replace(/[\t\n\r]/g, " ").trim() || "-";
    const line = [new Date().toISOString(), action, atom, scope, by, detail]
      .map(safe).join("\t") + "\n";
    fs.appendFileSync(path.join(baseDir, "_merge_history.log"), line, "utf-8");
  } catch (e) {
    try { process.stderr.write(`[merge_history] ${e.message}\n`); } catch {}
  }
}

/** V4 Phase 5: render CONTRADICT report (non-atom) for _pending_review/{slug}.conflict.md. */
function buildConflictReport({ slug, incomingTitle, incomingContent, matches, detectorModel, author }) {
  const lines = [
    `# Write-time conflict: ${incomingTitle || slug}`,
    "",
    `- Detected-at: ${new Date().toISOString()}`,
    `- Incoming-author: ${author || "-"}`,
    `- Detector: ${detectorModel || "n/a"}`,
    `- Pending-review-by: management`,
    "",
    "## Incoming knowledge",
    "",
    "```",
    (incomingContent || "").slice(0, 4000),
    "```",
    "",
    "## Conflicting existing atoms",
    "",
  ];
  for (const m of matches || []) {
    lines.push(`- **${m.atom_name}** (layer=\`${m.layer}\`, similarity=${(m.similarity || 0).toFixed(3)}, class=${m.classification})`);
    if (m.fact_preview) lines.push(`  preview: ${m.fact_preview.replace(/\n/g, " ")}`);
  }
  lines.push(
    "",
    "## Resolution",
    "",
    "管理職 `/conflict-review`：",
    "1. 編輯既有 atom 或 incoming — 以消解事實衝突",
    "2. 若 incoming 有獨立價值 → approve（搬草稿到 `shared/`）",
    "3. 若 incoming 錯誤 → reject（僅刪本報告，既有 atom 不動）",
    "",
  );
  return lines.join("\n");
}

/** Run write-gate Python script for dedup check. Returns Promise<{action, reason}> */
function execWriteGate(content, classification) {
  return new Promise((resolve) => {
    const scriptPath = path.join(TOOLS_DIR, "memory-write-gate.py");
    if (!fs.existsSync(scriptPath)) {
      return resolve({ action: "add", reason: "write-gate script not found, allowing" });
    }
    // Escape content for CLI: use stdin via echo pipe
    const escaped = JSON.stringify({ content, classification });
    const cmd = `echo ${escaped.replace(/"/g, '\\"')} | python "${scriptPath.replace(/\\/g, "/")}"`;
    exec(cmd, { timeout: 15000 }, (err, stdout) => {
      if (err || !stdout) {
        return resolve({ action: "add", reason: "write-gate unavailable, allowing" });
      }
      try {
        const result = JSON.parse(stdout.trim());
        resolve(result);
      } catch {
        resolve({ action: "add", reason: "write-gate parse error, allowing" });
      }
    });
  });
}

/** V5 P3b: Upsert atom entry to _atom_index.json (SoT) via funnel.
 *  Auto-regenerates _ATOM_INDEX.md mirror via lib/atom_index_json.upsert_atom. */
async function appendToIndex(memDir, atomName, relPath, triggers) {
  const r = await funnelWriteIndex(memDir, atomName, relPath, triggers, "mcp");
  if (!r.ok) crashLog("appendToIndex funnel (json)", r.error);
}

/** Trigger vector service re-index (fire and forget) */
function triggerVectorReindex() {
  try {
    const url = "http://127.0.0.1:3849/reindex";
    const req = http.request(url, { method: "POST", timeout: 3000 }, () => {});
    req.on("error", () => {}); // ignore
    req.end();
  } catch {}
}

/** Regenerate MEMORY.md from _ATOM_INDEX (fire and forget).
 *  Only touches global memory — project layers don't have sync-memory-index hookup yet. */
function syncMemoryIndex() {
  try {
    const script = path.join(TOOLS_DIR, "sync-memory-index.py");
    if (!fs.existsSync(script)) return;
    const cp = require("child_process").spawn("python", [script, "--write"], {
      windowsHide: true, detached: true, stdio: "ignore",
    });
    cp.on("error", () => {});
    cp.unref();
  } catch {}
}

/** Parse atom metadata from file content. Returns {confidence, confirmations, ...} */
function parseAtomMeta(content) {
  const meta = {};
  const re = /^- ([\w-]+):\s*(.+)$/gm;
  let m;
  while ((m = re.exec(content)) !== null) {
    const key = m[1].toLowerCase();
    const val = m[2].trim();
    switch (key) {
      case "confidence": meta.confidence = val; break;
      case "scope": meta.scope = val; break;
      case "trigger": meta.triggers = val; break;
      case "related": meta.related = val; break;
      // Wave 2: confirmations / readhits / last-used 從 <atom>.access.json 讀（見 readAtomAccess）
    }
  }
  const titleMatch = content.match(/^# (.+)$/m);
  if (titleMatch) meta.title = titleMatch[1];
  return meta;
}

/** Wave 2: 讀 <atom>.access.json 旁路檔（同步 fs，不 spawn 子程序）。 */
function readAtomAccess(atomPath) {
  try {
    const accessPath = atomPath.replace(/\.md$/, ".access.json");
    if (!fs.existsSync(accessPath)) return {};
    const raw = JSON.parse(fs.readFileSync(accessPath, "utf-8"));
    let confirmations = raw.confirmations;
    if (Array.isArray(confirmations)) confirmations = confirmations.length;
    return {
      confirmations: parseInt(confirmations, 10) || 0,
      readhits: parseInt(raw.read_hits, 10) || 0,
      usefulHits: Number(raw.useful_hits != null ? raw.useful_hits : 1),  // α (v3, Laplace prior 1)
      usedFail: Number(raw.used_fail != null ? raw.used_fail : 1),        // β
      lastUsed: raw.last_used || null,
      lastPromotedAt: raw.last_promoted_at || null,
    };
  } catch {
    return {};
  }
}

// ─── Phase 2 (#2): 效用 Wilson 下界（SYNC: lib/atom_access.py wilson_lower_bound /
//     usefulness_stats / usefulness_promote_eligible —— py↔js 鏡像，改一邊要改另一邊）。
function wilsonLowerBound(successes, n, z) {
  if (n <= 0) return 0.0;
  const phat = successes / n;
  const denom = 1.0 + (z * z) / n;
  const centre = phat + (z * z) / (2.0 * n);
  const margin = z * Math.sqrt((phat * (1.0 - phat) + (z * z) / (4.0 * n)) / n);
  const lb = (centre - margin) / denom;
  return Math.max(0.0, Math.min(1.0, lb));
}

/** access(α,β) → succ/fail/n/mean/lowerBound（prior=1 → succ=α−1, fail=β−1）。 */
function usefulnessStats(access, z) {
  const PRIOR = 1;
  const alpha = Number(access.usefulHits != null ? access.usefulHits : PRIOR);
  const beta = Number(access.usedFail != null ? access.usedFail : PRIOR);
  const succ = Math.max(0, alpha - PRIOR);
  const fail = Math.max(0, beta - PRIOR);
  const n = succ + fail;
  return {
    alpha, beta, successes: succ, failures: fail, n,
    mean: n > 0 ? succ / n : 0.0,
    lowerBound: wilsonLowerBound(succ, n, z),
  };
}

// world.html「戰力星級」資料源（v2）：把 <atom>.access.json 的遙測併進 /api/atoms 的
// atom 物件。access.json 為 Wave-2 權威來源（counts/last_used 不在 .md），故覆寫同名 .md 欄位。
const POWER_WILSON_Z = 1.96;
function enrichAtomWithAccess(atom, filePath) {
  const acc = readAtomAccess(filePath);
  if (acc.confirmations != null) atom.confirmations = acc.confirmations;
  if (acc.readhits != null) atom.read_hits = acc.readhits;
  if (acc.lastUsed) atom.last_used = acc.lastUsed;      // Wave-2 權威，覆寫 .md
  atom.useful_hits = acc.usefulHits != null ? acc.usefulHits : 1;  // α (Laplace prior 1)
  atom.used_fail = acc.usedFail != null ? acc.usedFail : 1;        // β
  const stats = usefulnessStats(acc, POWER_WILSON_Z);
  atom.power = Math.round(stats.lowerBound * 1000) / 1000;  // 戰力 = Wilson 下界 0..1
  atom.power_mean = Math.round(stats.mean * 1000) / 1000;
  atom.power_n = stats.n;                                   // 樣本數（succ+fail）
  if (atom.last_used) {
    const lu = new Date(atom.last_used);
    if (!isNaN(lu.getTime())) atom.days_since_used = Math.floor((Date.now() - lu.getTime()) / 86400000);
  }
}

/** Wave 2: spawn `python -m lib.atom_access <subcommand>` 對 access 旁路檔做寫入。 */
function spawnAtomAccess(subcommand, args) {
  return new Promise((resolve) => {
    let cp;
    try {
      cp = require("child_process").spawn(
        "python", ["-m", "lib.atom_access", subcommand, ...args],
        { cwd: CLAUDE_DIR, windowsHide: true,
          env: { ...process.env, PYTHONIOENCODING: "utf-8" } },
      );
    } catch (e) {
      return resolve({ ok: false, error: `spawn failed: ${e.message}` });
    }
    let out = "", err = "";
    cp.stdout.on("data", (d) => { out += d.toString("utf-8"); });
    cp.stderr.on("data", (d) => { err += d.toString("utf-8"); });
    cp.on("close", (code) => {
      try {
        resolve(out ? JSON.parse(out) : { ok: code === 0 });
      } catch (e) {
        resolve({ ok: false, error: `cli parse fail: ${e.message} stderr=${err.slice(0, 200)}` });
      }
    });
    cp.on("error", (e) => resolve({ ok: false, error: `spawn error: ${e.message}` }));
  });
}

// ─── S3.2: Atom Funnel Bridge (spawn lib/atom_io_cli) ─────────────────────

/** Spawn `python -m lib.atom_io_cli` to perform atom write through the
 *  centralized funnel (audit log + audit-id + uniform error contract).
 *  Returns Promise<{ok, error, audit_id, path}>.
 *  All atomic writes from MCP go through this so PreToolUse strict gate
 *  (S3.3) can verify every write has an audit log entry.
 */
function spawnAtomCli(action, payload) {
  return new Promise((resolve) => {
    let cp;
    try {
      cp = require("child_process").spawn(
        "python", ["-m", "lib.atom_io_cli"],
        {
          cwd: CLAUDE_DIR,
          windowsHide: true,
          env: { ...process.env, PYTHONIOENCODING: "utf-8" },
        }
      );
    } catch (e) {
      return resolve({ ok: false, error: `spawn failed: ${e.message}` });
    }
    let out = "", err = "";
    cp.stdout.on("data", (d) => { out += d.toString("utf-8"); });
    cp.stderr.on("data", (d) => { err += d.toString("utf-8"); });
    cp.on("close", () => {
      try {
        resolve(JSON.parse(out));
      } catch (e) {
        resolve({ ok: false, error: `cli parse fail: ${e.message} stderr=${err.slice(0, 200)}` });
      }
    });
    cp.on("error", (e) => resolve({ ok: false, error: `spawn error: ${e.message}` }));
    try {
      cp.stdin.write(JSON.stringify({ action, ...payload }));
      cp.stdin.end();
    } catch (e) {
      resolve({ ok: false, error: `stdin write failed: ${e.message}` });
    }
  });
}

/** Atomic write through funnel: routes raw content via lib.atom_io.write_raw. */
function funnelWriteRaw(filePath, content, source, op) {
  return spawnAtomCli("write_raw", {
    file_path: filePath, content, source, op: op || "raw",
  });
}

/** Index full overwrite through funnel. */
function funnelWriteIndexFull(indexPath, content, source) {
  return spawnAtomCli("write_index_full", {
    index_path: indexPath, content, source,
  });
}

/** V5 P3b: Single-atom upsert via lib.atom_io.write_index → _atom_index.json. */
function funnelWriteIndex(baseDir, slug, relPath, triggers, source) {
  return spawnAtomCli("write_index", {
    base_dir: baseDir, slug, rel_path: relPath,
    triggers, source,
  });
}


// Flat-legacy write fallback: atoms created under V3 layout sit at
// <baseDir>/{slug}.md instead of <baseDir>/shared/{slug}.md. Read path
// (hooks/wg_core.py:386-396 _is_legacy_atom) already supports both layers
// for injection; write path mirrors that compat for append/replace so users
// aren't blocked while a project's V3→V5 layout migration is still pending.
// Only triggers for scope=shared, only when V5 path is absent AND legacy path exists.
function flatLegacyFallback(scope, baseDir, slug, expectedPath) {
  if (scope !== "shared") return null;
  if (fs.existsSync(expectedPath)) return null;
  const candidate = path.join(baseDir, slug + ".md");
  if (!fs.existsSync(candidate)) return null;
  try {
    process.stderr.write(
      `[atom_write] flat-legacy fallback: writing to ${candidate} ` +
      `(V5 expects ${expectedPath} — project pending migration)\n`
    );
  } catch {}
  return candidate;
}

// ─── Atom Write Handler ────────────────────────────────────────────────────

async function toolAtomWrite(id, args) {
  let {
    title, scope, confidence, triggers, knowledge, actions, related, mode,
    project_cwd, skip_gate, skip_conflict_check,
    role, user, audience, pending_review_by, merge_strategy,
    realm, domain,
  } = args;

  // Validate core required fields (scope now optional, defaults to shared)
  if (!title || !confidence || !triggers || !knowledge || !mode) {
    return sendToolResult(id, "Missing required parameters (title, confidence, triggers, knowledge, mode)", true);
  }

  // V4: default scope, transparent legacy mapping
  if (!scope) scope = "shared";
  if (scope === "project") {
    try { process.stderr.write(`[atom_write] scope=project is deprecated; mapped to shared\n`); } catch {}
    scope = "shared";
  }

  // V4 personal default user
  if (scope === "personal" && !user) user = getCurrentUser();

  // Resolve target memory dir (write target + base for index)
  const resolved = resolveMemDir(scope, project_cwd, { role, user });
  if (resolved.error) {
    return sendToolResult(id, `atom_write: ${resolved.error}`, true);
  }
  const slug = slugify(title);
  // V5+ feedback-* routing 集中到 applyFeedbackRouting（對拍 lib/atom_locations.py）
  let { memDir, baseDir, indexDir, indexRoot, routedToFailures } =
    applyFeedbackRouting(resolved, slug, scope);

  // V5+ realm 自動分類（無顯式 realm 時跑分類器；計畫 Phase3「掛兩處」之 server.js 側）。
  // 顯式 realm（含 "core"）優先、不覆寫；核心保護硬擋、安全預設 core。跑於所有 global
  // 非-feedback 寫入（非只 create）——因 8 顆 allowlist 的 slug 皆含 lexicon 詞（name 權重），
  // append/replace 任意 triggers 都穩定判 local → 找得到已遷移的 local 檔（防 append 回歸）。
  if (realm === undefined && !routedToFailures && scope === "global") {
    const rc = classifyRealm(slug, triggers);
    if (rc.realm === "local") {
      realm = "local";
      if (!domain) domain = rc.domain;
      try { process.stderr.write(
        `[atom_write] auto-realm: ${slug} → local/${domain} (matched: ${rc.matched.join(",")})\n`); } catch {}
    }
  }

  // V5+ local-realm routing（與 feedback 互斥；realm 與 scope 正交，只在 global 生效）
  // 對拍 lib/atom_io._resolve_target 的 realm=="local" 分支。
  let routedToLocal = false;
  if (!routedToFailures && scope === "global" && realm === "local") {
    ({ memDir, baseDir, indexDir, indexRoot } = applyLocalRouting(domain));
    routedToLocal = true;
  }

  // SPEC 7.4: sensitive audience on shared → auto-pending
  let pendingReviewBy = pending_review_by || null;
  if (scope === "shared" && isSensitiveAudience(audience)) {
    memDir = path.join(baseDir, "shared", "_pending_review");
    fs.mkdirSync(memDir, { recursive: true });
    if (!pendingReviewBy) pendingReviewBy = "management";
  }

  // V4 metadata: scope label (composite for role/personal)
  let scopeLabel = scope;
  if (scope === "role") scopeLabel = `role:${role}`;
  else if (scope === "personal") scopeLabel = `personal:${user}`;

  // V4 Phase 5: filePath/relPath may be recomputed after conflict-detector reroute
  let filePath = path.join(memDir, slug + ".md");
  let relPath = path.relative(indexRoot, filePath).replace(/\\/g, "/");

  const author = getCurrentUser();
  const today = new Date().toISOString().slice(0, 10);

  // ── Mode: create ──
  if (mode === "create") {
    if (fs.existsSync(filePath)) {
      return sendToolResult(id, `Atom already exists: ${slug}.md — use mode=append or mode=replace`, true);
    }
    // Guard: slug collides with a separator-variant of an existing atom (e.g. legacy
    // underscore "client_il.md" vs slug "client-il"). Creating would fork a near-dup.
    const variant = findSeparatorVariant(memDir, slug);
    if (variant) {
      return sendToolResult(id,
        `Slug collision: "${variant}" already exists and normalizes to the same slug "${slug}".\n` +
        `Creating "${slug}.md" would fork a near-duplicate atom.\n` +
        `→ Use mode=append/replace on the existing atom, or rename "${variant}" to the hyphen convention first.`,
        true);
    }

    // 原子記憶語意契約：新 atom 必須 [臨]
    if (confidence !== "[臨]") {
      return sendToolResult(id,
        `New atom must start at [臨] (confidence=${confidence} rejected).\n` +
        `Reason: [觀]/[固] reflect cross-session stability; first-write cannot assert that.\n` +
        `Knowledge items inside should also use [臨] prefix.\n` +
        `Promotion: Confirmations (cross-session) ≥4→[觀] ≥10→[固]; ReadHits (injection) ≥20/≥50 auxiliary.`,
        true);
    }

    if (!skip_gate) {
      const gateResult = await execWriteGate(knowledge.join("\n"), confidence);
      if (gateResult.action === "skip") {
        return sendToolResult(id, `Write-gate rejected: ${gateResult.reason}`, true);
      }
      if (gateResult.action === "update" && gateResult.dedup_match) {
        return sendToolResult(id,
          `Write-gate: similar to existing atom "${gateResult.dedup_match.atom_name}" ` +
          `(score=${gateResult.dedup_match.score}). Use mode=append on that atom instead.`, true);
      }
    }

    // ─── V4 Phase 5: write-time conflict detection (SPEC §7.1) ───
    // Only shared scope. skip_conflict_check honored for migrations/tests.
    if (scope === "shared" && !skip_conflict_check) {
      const cr = await execConflictDetector(knowledge.join("\n"), "shared", project_cwd);
      if (cr.verdict === "contradict") {
        const pendingDir = path.join(baseDir, "shared", "_pending_review");
        fs.mkdirSync(pendingDir, { recursive: true });
        const reportPath = path.join(pendingDir, slug + ".conflict.md");
        const report = buildConflictReport({
          slug, incomingTitle: title, incomingContent: knowledge.join("\n"),
          matches: cr.matches, detectorModel: cr.detector_model, author,
        });
        fs.writeFileSync(reportPath + ".tmp", report, "utf-8");
        fs.renameSync(reportPath + ".tmp", reportPath);
        appendMergeHistory(baseDir, "pending-create", slug, scopeLabel, author,
          `contradict vs ${(cr.matches[0] || {}).atom_name || "?"} sim=${((cr.matches[0] || {}).similarity || 0).toFixed(3)}`);
        return sendToolResult(id,
          `BLOCKED by conflict detector — CONTRADICT vs "${(cr.matches[0] || {}).atom_name || "?"}".\n` +
          `Report written: ${reportPath}\n` +
          `Atom NOT written to shared/. Awaiting management review (/conflict-review).`,
          false  // not isError — pending is normal flow
        );
      }
      if (cr.verdict === "extend_overlap") {
        // Reroute to _pending_review/ as atom draft (still full atom format)
        memDir = path.join(baseDir, "shared", "_pending_review");
        fs.mkdirSync(memDir, { recursive: true });
        if (!pendingReviewBy) pendingReviewBy = "management";
        filePath = path.join(memDir, slug + ".md");
        relPath = path.relative(indexRoot, filePath).replace(/\\/g, "/");
        appendMergeHistory(baseDir, "pending-create", slug, scopeLabel, author,
          `extend_overlap vs ${(cr.matches[0] || {}).atom_name || "?"} sim=${((cr.matches[0] || {}).similarity || 0).toFixed(3)}`);
      }
    }

    // 2026-06-12 parity 方案 B：內容構造統一 spawn py funnel（lib.atom_io_cli "build"，
    // 含 validate）；js buildAtomContent 退役為 test_13 parity fixture。
    const br = await spawnAtomCli("build", {
      title, scope: scopeLabel, confidence, triggers, knowledge, actions, related,
      audience, author, pending_review_by: pendingReviewBy, merge_strategy, created_at: today,
    });
    if (!br.ok) {
      return sendToolResult(id, `Validation failed: ${br.error}`, true);
    }
    const content = (br.extra || {}).content;

    fs.mkdirSync(memDir, { recursive: true });
    // S3.2: 走 lib.atom_io.write_raw funnel（atomic write + audit log）
    const wr = await funnelWriteRaw(filePath, content, "mcp", "atom_create");
    if (!wr.ok) {
      return sendToolResult(id, `funnel write_raw failed: ${wr.error}`, true);
    }

    // Wave 2: 同步建立 <atom>.access.json 旁路檔（first_seen=today）
    await spawnAtomAccess("init", [filePath, "--first-seen", today, "--source", "mcp"]);
    await spawnAtomAccess("set", [filePath, "--field", "last_used",
                                  "--value", today, "--source", "mcp"]);

    await appendToIndex(indexDir, slug, relPath, triggers);
    triggerVectorReindex();
    if (scopeLabel === "global") syncMemoryIndex();

    return sendToolResult(id,
      `Created atom: ${slug}.md (${confidence}, scope=${scopeLabel})\n` +
      `Path: ${filePath}\n` +
      `Author: ${author}\n` +
      (pendingReviewBy ? `Pending-review-by: ${pendingReviewBy} (sensitive audience auto-routed)\n` : "") +
      `Triggers: ${triggers.join(", ")}\n` +
      `MEMORY.md index updated.`
    );
  }

  // ── Mode: append ──
  if (mode === "append") {
    const legacyPath = flatLegacyFallback(scope, baseDir, slug, filePath);
    if (legacyPath) {
      filePath = legacyPath;
      relPath = path.relative(indexRoot, filePath).replace(/\\/g, "/");
    }
    if (!fs.existsSync(filePath) && scopeLabel === "global") {
      // find-fallback：local（_AIDocs/_atoms/）與 feedback-*（_AIDocs/Failures/）物理居 memory/ 外，
      // 鏡像 promote/edit_meta 的遞迴 fallback；否則 scope=global 的 local atom append 報 not-found。
      const found = findAtomFileRecursive(FAILURES_DIR, slug) || findAtomFileRecursive(LOCAL_ATOMS_DIR, slug);
      if (found) {
        filePath = found;
        relPath = path.relative(indexRoot, filePath).replace(/\\/g, "/");
      }
    }
    if (!fs.existsSync(filePath)) {
      return sendToolResult(id, `Atom not found: ${slug}.md — use mode=create first`, true);
    }

    // 2026-06-12 parity 方案 B：拼接+validate+落檔統一 spawn py（lib.atom_io.append_atom_file）
    // —— 退役 js readFileSync 自拼 splice（CRLF 混寫面，見 lib/atom_io.py:_atomic_write 註解）。
    // Wave 2: Last-used 不在 .md，append 後改寫 access.json（下方 spawnAtomAccess）。
    const wr = await spawnAtomCli("append", { file_path: filePath, knowledge, source: "mcp" });
    if (!wr.ok) {
      return sendToolResult(id, `funnel append failed: ${wr.error}`, true);
    }

    // Wave 2: 同步刷 access.json last_used
    await spawnAtomAccess("set", [filePath, "--field", "last_used",
                                  "--value", today, "--source", "mcp"]);

    triggerVectorReindex();

    return sendToolResult(id,
      `Appended ${knowledge.length} knowledge lines to ${slug}.md\n` +
      `Last-used updated.`
    );
  }

  // ── Mode: replace ──
  if (mode === "replace") {
    const legacyPath = flatLegacyFallback(scope, baseDir, slug, filePath);
    if (legacyPath) {
      filePath = legacyPath;
      relPath = path.relative(indexRoot, filePath).replace(/\\/g, "/");
    }
    // Guard: replace = overwrite an EXISTING atom. If the target is absent, this was a
    // silent upsert that birthed a brand-new atom bypassing the create [臨] gate. Refuse.
    if (!fs.existsSync(filePath) && scopeLabel === "global") {
      // find-fallback（同 append）：local / feedback-* 物理居 memory/ 外。
      const found = findAtomFileRecursive(FAILURES_DIR, slug) || findAtomFileRecursive(LOCAL_ATOMS_DIR, slug);
      if (found) {
        filePath = found;
        relPath = path.relative(indexRoot, filePath).replace(/\\/g, "/");
      }
    }
    if (!fs.existsSync(filePath)) {
      const variant = findSeparatorVariant(memDir, slug);
      return sendToolResult(id,
        `Atom not found: ${slug}.md — mode=replace requires an existing atom.\n` +
        (variant
          ? `(A separator-variant "${variant}" exists — rename it to "${slug}.md" first, or append to it.)\n`
          : "") +
        `To add a NEW atom use mode=create (new atoms must start at [臨]).`,
        true);
    }
    // Wave 2: Confirmations / ReadHits 在 access.json，replace 不需保留（檔本就分離）
    // 仍保留 Author / Created-at（屬知識性 metadata）
    let prevAuthor = author;
    let prevCreatedAt = today;
    if (fs.existsSync(filePath)) {
      try {
        const old = fs.readFileSync(filePath, "utf-8");
        const am = old.match(/^- Author:\s*(.+)$/m);
        if (am) prevAuthor = am[1].trim();
        const cm = old.match(/^- Created-at:\s*(.+)$/m);
        if (cm) prevCreatedAt = cm[1].trim();
      } catch {}
    }

    // 2026-06-12 parity 方案 B：同 create，內容構造 spawn py funnel "build"（含 validate）
    const br = await spawnAtomCli("build", {
      title, scope: scopeLabel, confidence, triggers, knowledge, actions, related,
      audience, author: prevAuthor, pending_review_by: pendingReviewBy,
      merge_strategy, created_at: prevCreatedAt,
    });
    if (!br.ok) {
      return sendToolResult(id, `Validation failed: ${br.error}`, true);
    }
    const content = (br.extra || {}).content;

    fs.mkdirSync(memDir, { recursive: true });
    // S3.2: 走 lib.atom_io.write_raw funnel
    const wr = await funnelWriteRaw(filePath, content, "mcp", "atom_replace");
    if (!wr.ok) {
      return sendToolResult(id, `funnel write_raw failed: ${wr.error}`, true);
    }

    // Wave 2: 刷 access.json last_used（access 計數自動保留）
    await spawnAtomAccess("set", [filePath, "--field", "last_used",
                                  "--value", today, "--source", "mcp"]);

    await appendToIndex(indexDir, slug, relPath, triggers);
    triggerVectorReindex();
    if (scopeLabel === "global") syncMemoryIndex();

    // 讀 access 給訊息顯示保留的計數
    const accAfter = readAtomAccess(filePath);
    return sendToolResult(id,
      `Replaced atom: ${slug}.md (${confidence}, preserved conf=${accAfter.confirmations || 0} rh=${accAfter.readhits || 0}, author=${prevAuthor})\n` +
      `MEMORY.md index updated.`
    );
  }

  return sendToolResult(id, `Unknown mode: ${mode}. Use create/append/replace.`, true);
}

// ─── Atom Promote Handler ──────────────────────────────────────────────────

// Locate <atom_name>.md anywhere under memDir; needed because feedback/ etc.
// are valid atom subdirs (mirrors lib/atom_spec.SKIP_DIRS exclusions).
function findAtomFileRecursive(memDir, atomName) {
  const target = atomName + ".md";
  const SKIP = new Set([
    "_reference", "_archived", "_pending_review", "_staging",
    "templates", "wisdom", "_drafts", "episodic", "_meta",
  ]);
  const queue = [memDir];
  while (queue.length) {
    const cur = queue.shift();
    let entries;
    try { entries = fs.readdirSync(cur, { withFileTypes: true }); } catch { continue; }
    for (const e of entries) {
      const full = path.join(cur, e.name);
      if (e.isDirectory()) {
        if (SKIP.has(e.name) || e.name.startsWith("_archive")) continue;
        queue.push(full);
      } else if (e.isFile() && e.name === target) {
        return full;
      }
    }
  }
  return null;
}

async function toolAtomPromote(id, args) {
  const { atom_name, scope, project_cwd, execute, role, user, merge_to_preferences } = args;

  const resolved = resolveMemDir(scope, project_cwd, { role, user });
  if (resolved.error) {
    return sendToolResult(id, `atom_promote: ${resolved.error}`, true);
  }
  const memDir = resolved.dir;
  let filePath = path.join(memDir, atom_name + ".md");

  if (!fs.existsSync(filePath)) {
    // Fallback: recursive lookup (atom may live in feedback/ or other subdir)
    let found = findAtomFileRecursive(memDir, atom_name);
    // V5+: feedback-* atoms 居 _AIDocs/Failures/，不在 memDir 樹下，需額外掃
    if (!found && scope === "global" && atom_name.startsWith(FEEDBACK_TITLE_PREFIX)) {
      found = findAtomFileRecursive(FAILURES_DIR, atom_name);
    }
    // V5+: local-realm atoms 居 _AIDocs/_atoms/<domain>/（scope=global 但不在 memory/ 樹下）
    if (!found && scope === "global") {
      found = findAtomFileRecursive(LOCAL_ATOMS_DIR, atom_name);
    }
    if (!found) {
      return sendToolResult(id, `Atom not found: ${atom_name}.md in ${scope} scope`, true);
    }
    filePath = found;
  }

  let content = fs.readFileSync(filePath, "utf-8");
  if (content.charCodeAt(0) === 0xFEFF) content = content.slice(1);

  const meta = parseAtomMeta(content);
  if (!meta.confidence) {
    return sendToolResult(id, `Cannot parse confidence from ${atom_name}.md`, true);
  }

  // Determine promotion path (v3 dual-field)
  // SYNC: memory/decisions.md — promotion thresholds
  const THRESHOLDS = {
    "[臨]": { next: "[觀]", confirmations: 4, readhits: 20 },
    "[觀]": { next: "[固]", confirmations: 10, readhits: 50 },
    "[固]": null, // already max
  };

  const path_info = THRESHOLDS[meta.confidence];
  if (!path_info) {
    return sendToolResult(id,
      `${atom_name} is already at ${meta.confidence} — no promotion available.`
    );
  }

  const { next, confirmations: reqConf, readhits: reqRH } = path_info;
  // Wave 2: 計數從 <atom>.access.json 讀，不再 parseAtomMeta（meta.confidence 仍從 .md 抽）
  const access = readAtomAccess(filePath);
  const confirmations = access.confirmations || 0;
  const readhits = access.readhits || 0;

  // Phase 2 (#2): 晉升 = 真實 Confirmations 主軌 OR 效用 Wilson 下界。
  // ReadHits 降為純曝光計數，不再參與晉升（取代 Phase 0 readhits 輔助門）。
  // SYNC: lib/atom_access.py usefulness_promote_eligible + wg_atoms.py:_self_iterate_atoms。
  const uconf = (loadConfig().usefulness) || {};
  const promoteLb = Number(uconf.promote_lb != null ? uconf.promote_lb : 0.6);
  const minN = Number(uconf.min_n != null ? uconf.min_n : 3);
  const wilsonZ = Number(uconf.wilson_z != null ? uconf.wilson_z : 1.96);
  const ustat = usefulnessStats(access, wilsonZ);
  const utilEligible = ustat.n >= minN && ustat.lowerBound >= promoteLb;

  let eligible = confirmations >= reqConf;
  let method = "confirmations";
  if (!eligible && utilEligible) {
    eligible = true;
    method = "usefulness";
  }

  const utilLine =
    `  Usefulness: lb=${ustat.lowerBound.toFixed(3)} (α=${ustat.alpha}, β=${ustat.beta}, n=${ustat.n})` +
    ` — need lb≥${promoteLb} & n≥${minN}\n`;

  if (!eligible) {
    return sendToolResult(id,
      `## Dry-run: ${atom_name}\n` +
      `Current: ${meta.confidence}\n` +
      `  Confirmations: ${confirmations}/${reqConf}\n` +
      utilLine +
      `  ReadHits: ${readhits} (純曝光，不參與晉升)\n` +
      `Required: Confirmations ≥ ${reqConf} OR (Usefulness lb ≥ ${promoteLb} AND n ≥ ${minN})\n` +
      `Deficit: ${Math.max(0, reqConf - confirmations)} conf / lb ${Math.max(0, promoteLb - ustat.lowerBound).toFixed(3)}`
    );
  }

  // Eligible for promotion
  if (!execute) {
    return sendToolResult(id,
      `## Dry-run: ${atom_name}\n` +
      `Current: ${meta.confidence}\n` +
      `  Confirmations: ${confirmations}/${reqConf}\n` +
      utilLine +
      `Eligible via: ${method} → ${next}\n` +
      `Set execute=true to apply.`
    );
  }

  // Execute promotion
  // Wave 2: Last-used 不在 .md，只改 Confidence + 知識條目層級的 [臨]/[觀]
  const updated = content
    .replace(/^- Confidence:\s*.+$/m, `- Confidence: ${next}`);

  // Also update individual knowledge lines: [臨] → [觀] etc.
  const finalContent = updated.replace(
    new RegExp(`- \\${meta.confidence.replace(/[[\]]/g, "\\$&")}`, "g"),
    `- ${next}`
  );

  // S3.2: 走 lib.atom_io.write_raw funnel
  const wrPromote = await funnelWriteRaw(filePath, finalContent, "mcp", "atom_promote");
  if (!wrPromote.ok) {
    return sendToolResult(id, `funnel write_raw failed: ${wrPromote.error}`, true);
  }

  // Wave 2: 同步寫 access.json 的 last_promoted_at + last_used
  await spawnAtomAccess("record-promotion",
    [filePath, "--target", next, "--source", "mcp"]);

  triggerVectorReindex();

  // Promotion audit log
  try {
    const auditPath = path.join(MEMORY_DIR, "_promotion_audit.jsonl");
    const entry = {
      ts: new Date().toISOString().slice(0, 19),
      action: "manual_promote",
      atom: atom_name,
      from: meta.confidence,
      to: next,
      confirmations,
      readhits,
      method,
      scope,
    };
    fs.appendFileSync(auditPath, JSON.stringify(entry) + "\n");
  } catch {}

  // ─── 方案 c: [觀]→[固] 合併流程 ────────────────────────────────
  // 方案 a（自動提示）：只要晉升為 [固]，一律在回覆裡附上「是否合進 preferences.md」提示，
  // 讓 Claude 引導使用者裁決。
  // 方案 b（自動執行）：當 merge_to_preferences=true，立即把 knowledge 追加到 preferences.md、
  // 歸檔本 atom 到 _archived/，再請 Claude 後續手動移除 _ATOM_INDEX.md 的該行。
  const promotedToStable = next === "[固]";
  let mergeReport = "";
  if (promotedToStable && merge_to_preferences) {
    if (scope !== "global") {
      mergeReport = "\n\n[merge_to_preferences] 已略過：僅支援 global scope。";
    } else {
      try {
        const knowledgeLines = extractKnowledgeLines(finalContent);
        const prefPath = path.join(MEMORY_DIR, "preferences.md");
        const archiveDir = path.join(MEMORY_DIR, "_archived");
        if (!fs.existsSync(archiveDir)) fs.mkdirSync(archiveDir, { recursive: true });
        const today = new Date().toISOString().slice(0, 10);
        const archivePath = path.join(archiveDir, `${today}-${atom_name}.md`);

        let prefText = fs.existsSync(prefPath) ? fs.readFileSync(prefPath, "utf-8") : "";
        if (prefText.charCodeAt(0) === 0xFEFF) prefText = prefText.slice(1);
        const mergeSection =
          `\n\n### 歸檔合併 · ${atom_name} (${today})\n` +
          `> 自 [觀]→[固] 晉升時合併自 \`${path.basename(filePath)}\`\n\n` +
          knowledgeLines.map(l => `- ${l}`).join("\n") + "\n";
        // S3.2: 走 lib.atom_io.write_raw funnel
        const wrPref = await funnelWriteRaw(
          prefPath, prefText.trimEnd() + mergeSection, "mcp", "promote_merge_pref"
        );
        if (!wrPref.ok) throw new Error(`funnel write_raw failed: ${wrPref.error}`);

        fs.renameSync(filePath, archivePath);

        mergeReport =
          `\n\n[merge_to_preferences] 已執行：\n` +
          `  - Appended ${knowledgeLines.length} 行到 preferences.md\n` +
          `  - Archived → ${path.relative(MEMORY_DIR, archivePath)}\n` +
          `  - ⚠ 請手動移除 _ATOM_INDEX.md 中 ${atom_name} 的索引列。`;
      } catch (e) {
        mergeReport = `\n\n[merge_to_preferences] 失敗：${e.message}`;
      }
    }
  }

  const mergeHint = (promotedToStable && !merge_to_preferences)
    ? `\n\n💡 建議：${atom_name} 已達 [固]，若此知識本質為「個人偏好/操作規範」，` +
      `可用 merge_to_preferences=true 重新呼叫，將 knowledge 併入 preferences.md 並歸檔此 atom。`
    : "";

  return sendToolResult(id,
    `Promoted ${atom_name}: ${meta.confidence} → ${next}\n` +
    `Confirmations: ${confirmations} | ReadHits: ${readhits} (via ${method})\n` +
    `Knowledge lines updated to ${next}.` +
    mergeReport +
    mergeHint
  );
}

// ─── Atom Edit-Metadata Handler ────────────────────────────────────────────

/** Spawn inline python that calls lib.atom_io.edit_metadata through the funnel.
 *  list 參數 (triggers/related/tags) 以單一 JSON 字串走 argv 傳入，python 端
 *  json.loads 後展開。沿用 spawnAtomCli/spawnAtomAccess 慣例：cwd=CLAUDE_DIR、
 *  PYTHONIOENCODING=utf-8、windowsHide。回傳 Promise<WriteResult.to_dict()>。
 */
function spawnEditMetadata(filePath, fields) {
  // fields: { triggers?: string[], related?: string[], tags?: string[] }
  const payload = JSON.stringify({ file_path: filePath, ...fields });
  const inline = [
    "import sys, json",
    "from lib.atom_io import edit_metadata",
    "p = json.loads(sys.argv[1])",
    "r = edit_metadata(",
    "    p['file_path'],",
    "    triggers=p.get('triggers'),",
    "    related=p.get('related'),",
    "    tags=p.get('tags'),",
    "    source='mcp',",
    ")",
    "print(json.dumps(r.to_dict(), ensure_ascii=False))",
  ].join("\n");
  return new Promise((resolve) => {
    let cp;
    try {
      cp = require("child_process").spawn(
        "python", ["-c", inline, payload],
        {
          cwd: CLAUDE_DIR,
          windowsHide: true,
          env: { ...process.env, PYTHONIOENCODING: "utf-8" },
        }
      );
    } catch (e) {
      return resolve({ ok: false, error: `spawn failed: ${e.message}` });
    }
    let out = "", err = "";
    cp.stdout.on("data", (d) => { out += d.toString("utf-8"); });
    cp.stderr.on("data", (d) => { err += d.toString("utf-8"); });
    cp.on("close", () => {
      try {
        resolve(JSON.parse(out.trim()));
      } catch (e) {
        resolve({ ok: false, error: `cli parse fail: ${e.message} stderr=${err.slice(0, 300)}` });
      }
    });
    cp.on("error", (e) => resolve({ ok: false, error: `spawn error: ${e.message}` }));
  });
}

async function toolAtomEditMeta(id, args) {
  const { atom_name, scope, project_cwd, role, user, triggers, related, tags } = args;

  if (!atom_name || !scope) {
    return sendToolResult(id, "atom_edit_meta: atom_name and scope are required", true);
  }

  // At least one metadata field must be provided.
  const fields = {};
  const changed = [];
  if (Array.isArray(triggers)) { fields.triggers = triggers; changed.push("trigger"); }
  if (Array.isArray(related))  { fields.related = related;   changed.push("related"); }
  if (Array.isArray(tags))     { fields.tags = tags;         changed.push("tags"); }
  if (changed.length === 0) {
    return sendToolResult(id,
      "atom_edit_meta: at least one of triggers / related / tags must be provided (array of string).",
      true);
  }

  // Path resolution — mirror toolAtomPromote exactly (global/project + feedback-*).
  const resolved = resolveMemDir(scope, project_cwd, { role, user });
  if (resolved.error) {
    return sendToolResult(id, `atom_edit_meta: ${resolved.error}`, true);
  }
  const memDir = resolved.dir;
  let filePath = path.join(memDir, atom_name + ".md");

  if (!fs.existsSync(filePath)) {
    let found = findAtomFileRecursive(memDir, atom_name);
    if (!found && scope === "global" && atom_name.startsWith(FEEDBACK_TITLE_PREFIX)) {
      found = findAtomFileRecursive(FAILURES_DIR, atom_name);
    }
    // V5+: local-realm atoms 居 _AIDocs/_atoms/<domain>/（scope=global 但不在 memory/ 樹下）
    if (!found && scope === "global") {
      found = findAtomFileRecursive(LOCAL_ATOMS_DIR, atom_name);
    }
    if (!found) {
      return sendToolResult(id, `Atom not found: ${atom_name}.md in ${scope} scope`, true);
    }
    filePath = found;
  }

  const result = await spawnEditMetadata(filePath, fields);
  if (!result.ok) {
    return sendToolResult(id, `atom_edit_meta failed: ${result.error || "(unknown error)"}`, true);
  }

  triggerVectorReindex();

  return sendToolResult(id,
    `Edited metadata for ${atom_name}.md (fields: ${changed.join(", ")})\n` +
    `audit_id: ${result.audit_id || "(none)"}`
  );
}

// ─── Atom Move Handler ─────────────────────────────────────────────────────

function toolAtomMove(id, args) {
  const { subcommand, atom, dry_run } = args;
  if (!subcommand || !atom) {
    return Promise.resolve(sendToolResult(id, "atom_move: subcommand and atom are required", true));
  }
  const scriptPath = path.join(TOOLS_DIR, "atom-move.py");
  if (!fs.existsSync(scriptPath)) {
    return Promise.resolve(sendToolResult(id, `atom_move: script not found at ${scriptPath}`, true));
  }
  const argv = [scriptPath, subcommand, atom];
  if (subcommand === "move") {
    if (!args.from || !args.to) {
      return Promise.resolve(sendToolResult(id, "atom_move move: --from and --to required", true));
    }
    argv.push("--from", args.from, "--to", args.to);
  } else if (subcommand === "reconcile") {
    if (!args.at) {
      return Promise.resolve(sendToolResult(id, "atom_move reconcile: --at required", true));
    }
    argv.push("--at", args.at);
  } else {
    return Promise.resolve(sendToolResult(id, `atom_move: unknown subcommand '${subcommand}'`, true));
  }
  if (dry_run) argv.push("--dry-run");

  return new Promise((resolve) => {
    const cp = require("child_process").spawn("python", argv, { windowsHide: true });
    let out = "", err = "";
    const timer = setTimeout(() => { try { cp.kill(); } catch {} }, 30000);
    cp.stdout.on("data", d => { out += d.toString(); });
    cp.stderr.on("data", d => { err += d.toString(); });
    cp.on("close", (code) => {
      clearTimeout(timer);
      const combined = (out || "") + (err ? ("\n[stderr]\n" + err) : "");
      if (code !== 0) {
        sendToolResult(id, `atom_move exited ${code}\n${combined}`, true);
      } else {
        sendToolResult(id, combined.trim() || "(no output)");
      }
      resolve();
    });
    cp.on("error", (e) => {
      clearTimeout(timer);
      sendToolResult(id, `atom_move spawn error: ${e.message}`, true);
      resolve();
    });
  });
}

function extractKnowledgeLines(content) {
  // 從 atom 檔抓「## 知識」到下個 `## ` 或 EOF 之間，保留以 `- ` 開頭的行（去掉 `- ` 前綴）
  const m = content.match(/^##\s*知識\s*$([\s\S]*?)(?=^##\s|\Z)/m);
  if (!m) return [];
  return m[1]
    .split("\n")
    .map(l => l.trim())
    .filter(l => l.startsWith("- "))
    .map(l => l.slice(2).trim())
    .filter(Boolean);
}

function sendToolResult(id, text, isError = false) {
  sendResponse(id, {
    content: [{ type: "text", text }],
    ...(isError && { isError: true }),
  });
}

// ─── v2.1 API Handlers ──────────────────────────────────────────────────────

function jsonRes(res, code, data) {
  res.writeHead(code, { "Content-Type": "application/json" });
  res.end(JSON.stringify(data));
}

// Build a safe python command (Windows path backslashes must be forward-slashed for exec)
function pyCmd(scriptPath, args) {
  return 'python "' + scriptPath.replace(/\\/g, "/") + '" ' + args;
}

// --- Episodic Atom Parser & API ---

function parseEpisodicAtom(filePath) {
  const content = fs.readFileSync(filePath, "utf-8");
  const atom = {
    filename: path.basename(filePath),
    title: "", confidence: "", type: "", triggers: [],
    last_used: "", created: "", ttl: "", expires_at: "",
    days_until_expiry: null, knowledge_lines: [], full_content: content,
  };
  const titleMatch = content.match(/^#\s+(.+)$/m);
  if (titleMatch) atom.title = titleMatch[1];
  const metaRe = /^-\s+([\w-]+):\s*(.+)$/gm;
  let m;
  while ((m = metaRe.exec(content)) !== null) {
    const key = m[1].toLowerCase(), val = m[2].trim();
    switch (key) {
      case "confidence": atom.confidence = val; break;
      case "type": atom.type = val; break;
      case "trigger": atom.triggers = val.split(",").map(t => t.trim()); break;
      case "last-used": atom.last_used = val; break;
      case "created": atom.created = val; break;
      case "ttl": atom.ttl = val; break;
      case "expires-at":
        atom.expires_at = val;
        const expDate = new Date(val);
        atom.days_until_expiry = Math.ceil((expDate - new Date()) / 86400000);
        break;
    }
  }
  let inKnowledge = false;
  for (const line of content.split("\n")) {
    if (/^##\s+知識/.test(line)) { inKnowledge = true; continue; }
    if (/^##\s+/.test(line) && inKnowledge) break;
    if (inKnowledge && line.trim().startsWith("-")) {
      atom.knowledge_lines.push(line.trim().replace(/^-\s*/, ""));
    }
  }
  return atom;
}

function apiEpisodic(req, res) {
  try {
    const dirsToScan = [MEMORY_DIR];
    // V2.21: scan registry project dirs (new path)
    for (const { memDir } of getRegistryMemDirs()) {
      if (!dirsToScan.includes(memDir)) dirsToScan.push(memDir);
    }
    // Also scan old project-level episodic dirs (fallback for unregistered projects)
    const projectsDir = path.join(CLAUDE_DIR, "projects");
    if (fs.existsSync(projectsDir)) {
      for (const proj of fs.readdirSync(projectsDir)) {
        const projMemDir = path.join(projectsDir, proj, "memory");
        if (fs.existsSync(projMemDir) && !dirsToScan.includes(projMemDir)) dirsToScan.push(projMemDir);
      }
    }
    const atoms = [];
    for (const dir of dirsToScan) {
      const epicDir = path.join(dir, "episodic");
      if (!fs.existsSync(epicDir)) continue;
      try {
        const files = fs.readdirSync(epicDir)
          .filter(f => f.startsWith("episodic-") && f.endsWith(".md"));
        for (const f of files) {
          try { atoms.push(parseEpisodicAtom(path.join(epicDir, f))); }
          catch {}
        }
      } catch {}
    }
    atoms.sort((a, b) => (b.created || "").localeCompare(a.created || ""));
    jsonRes(res, 200, atoms);
  } catch { jsonRes(res, 200, []); }
}

// --- Memory Health API (cached) ---

let healthCache = { data: null, timestamp: 0 };
const HEALTH_CACHE_TTL_MS = 60000;

function apiHealth(req, res, forceRefresh) {
  const now = Date.now();
  if (!forceRefresh && healthCache.data && (now - healthCache.timestamp) < HEALTH_CACHE_TTL_MS) {
    return jsonRes(res, 200, healthCache.data);
  }
  const auditScript = path.join(TOOLS_DIR, "memory-audit.py");
  const healthScript = path.join(TOOLS_DIR, "atom-health-check.py");
  // Run both tools in parallel
  let auditDone = false, healthDone = false;
  let auditData = null, healthData = null;
  let responded = false;
  const tryMerge = () => {
    if (!auditDone || !healthDone || responded) return;
    responded = true;
    const merged = auditData || {};
    if (healthData) {
      merged.broken_refs = healthData.broken_refs || [];
      merged.missing_reverse_refs = healthData.missing_reverse_refs || [];
      merged.stale_atoms = healthData.stale_atoms || [];
    }
    healthCache = { data: merged, timestamp: Date.now() };
    jsonRes(res, 200, merged);
  };
  exec(pyCmd(auditScript, "--json"), { timeout: 30000 }, (err, stdout) => {
    if (stdout) { try { auditData = JSON.parse(stdout); } catch {} }
    auditDone = true;
    tryMerge();
  });
  exec(pyCmd(healthScript, "--report --json"), { timeout: 30000 }, (err, stdout) => {
    if (stdout) { try { healthData = JSON.parse(stdout); } catch {} }
    healthDone = true;
    tryMerge();
  });
}

// --- E2E Test Runner (async jobs) ---

// ── 泛用非同步 Job Runner（test / heal / 其他共用，避免重複貼上 Map+鎖+輪詢+清除）──
//    maxConcurrent=1 即原 testJobs 的單例語意；heal 可配置 N（雲端後端並行）
function makeJobRunner({ maxConcurrent = 1, ttlMs = 300000 } = {}) {
  const jobs = new Map();
  const running = () => { let n = 0; for (const j of jobs.values()) if (j.status === "running") n++; return n; };
  function start(taskFn, meta = {}) {
    if (running() >= maxConcurrent) return { ok: false, reason: "busy", running: running() };
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    const job = { id, status: "running", result: null, startedAt: Date.now(), finishedAt: null, ...meta };
    jobs.set(id, job);
    Promise.resolve().then(() => taskFn(job))
      .then((result) => { if (jobs.has(id)) { job.result = result; job.status = "completed"; } })
      .catch((e) => { if (jobs.has(id)) { job.result = { error: String((e && e.message) || e) }; job.status = "error"; } })
      .finally(() => { if (jobs.has(id)) { job.finishedAt = Date.now(); setTimeout(() => jobs.delete(id), ttlMs); } });
    return { ok: true, id, job };
  }
  function statusRes(res, id) {
    const job = jobs.get(id);
    if (!job) return jsonRes(res, 404, { error: "job not found" });
    jsonRes(res, 200, { job_id: id, status: job.status, elapsed_ms: (job.finishedAt || Date.now()) - job.startedAt, result: job.result });
  }
  return { jobs, start, statusRes, running };
}

// 把子程序 exec 包成 Promise：stdout 能 JSON.parse → resolve；否則 reject（job 標 error）
// 註：腳本測試失敗仍輸出合法 JSON → 視為 completed（保留原 testJobs「非零退出仍解析」語意）
function execJson(cmd, opts = {}) {
  return new Promise((resolve, reject) => {
    exec(cmd, opts, (err, stdout, stderr) => {
      if (stdout) { try { return resolve(JSON.parse(stdout)); } catch { /* fall through */ } }
      if (err) return reject(new Error(err.message + (stderr ? " | " + String(stderr).slice(0, 500) : "")));
      reject(new Error("empty output" + (stderr ? " | " + String(stderr).slice(0, 500) : "")));
    });
  });
}

const testRunner = makeJobRunner({ maxConcurrent: 1, ttlMs: 300000 });
function apiTestRunStart(req, res) {
  const scriptPath = path.join(TOOLS_DIR, "test-memory-v21.py");
  const r = testRunner.start(() => execJson(pyCmd(scriptPath, "--json"), { timeout: 120000 }));
  if (!r.ok) return jsonRes(res, 409, { error: "test already running" });
  jsonRes(res, 202, { job_id: r.id, status: "running" });
}
function apiTestRunStatus(req, res, jobId) { return testRunner.statusRes(res, jobId); }

// ── World Command Bus：Claude/使用者下指令 → 前端輪詢執行 → 回報；snapshot 供讀取世界狀態 ──
function readJsonBody(req, cb) {
  let body = "";
  req.on("data", (ch) => (body += ch));
  req.on("end", () => { try { cb(body ? JSON.parse(body) : {}); } catch { cb(null); } });
}
const worldCommands = [];        // {id, cmd, args, at, status, result}
let worldCmdSeq = 0;
let worldSnapshot = { at: 0, creatures: [] };   // 前端 POST 回填、Claude GET 讀
function apiWorldCommandPost(req, res) {
  readJsonBody(req, (body) => {
    if (!body || !body.cmd) return jsonRes(res, 400, { error: "missing cmd" });
    const id = ++worldCmdSeq;
    worldCommands.push({ id, cmd: body.cmd, args: body.args || {}, at: Date.now(), status: "pending", result: null });
    if (worldCommands.length > 200) worldCommands.splice(0, worldCommands.length - 200);
    jsonRes(res, 200, { id, queued: true });
  });
}
function apiWorldCommandsGet(req, res, sinceStr) {
  const since = parseInt(sinceStr || "0", 10) || 0;
  jsonRes(res, 200, { commands: worldCommands.filter((c) => c.id > since && c.status === "pending"), last_id: worldCmdSeq });
}
function apiWorldResultPost(req, res) {
  readJsonBody(req, (body) => {
    const c = body && worldCommands.find((x) => x.id === body.id);
    if (c) { c.status = body.ok ? "done" : "failed"; c.result = body.observation != null ? body.observation : null; }
    jsonRes(res, 200, { ok: !!c });
  });
}
function apiWorldSnapshot(req, res) {
  if (req.method === "POST") {
    return readJsonBody(req, (body) => {
      if (body && Array.isArray(body.creatures)) worldSnapshot = { at: Date.now(), creatures: body.creatures };
      jsonRes(res, 200, { ok: true });
    });
  }
  const age = worldSnapshot.at ? Math.round((Date.now() - worldSnapshot.at) / 1000) : null;
  jsonRes(res, 200, { ...worldSnapshot, age_seconds: age });
}

// ── World 環境演化狀態（per-region 發展；★獨立於原子記憶系統，只讀寫 workflow/world-dev.json，不碰 memory/）──
const WORLD_DEV_PATH = path.join(WORKFLOW_DIR, "world-dev.json");
function emptyWorldDev() { return { version: 1, updated_at: 0, mode: "slow", regions: {} }; }
function readWorldDev() {
  try { const d = JSON.parse(fs.readFileSync(WORLD_DEV_PATH, "utf-8")); return (d && d.regions) ? d : emptyWorldDev(); }
  catch { return emptyWorldDev(); }
}
let worldDev = readWorldDev();
let worldDevTimer = null;
function flushWorldDev() {                                   // 原子寫，仿 writeState（.tmp→rename）
  worldDevTimer = null;
  worldDev.updated_at = Date.now();
  const tmp = WORLD_DEV_PATH + ".tmp";
  try {
    fs.mkdirSync(WORKFLOW_DIR, { recursive: true });
    fs.writeFileSync(tmp, JSON.stringify(worldDev, null, 2), "utf-8");
    fs.renameSync(tmp, WORLD_DEV_PATH);
  } catch { try { fs.unlinkSync(tmp); } catch {} }
}
function scheduleWorldDevWrite() {                           // debounce 300ms，批次落盤
  if (worldDevTimer) clearTimeout(worldDevTimer);
  worldDevTimer = setTimeout(flushWorldDev, 300);
}
function apiWorldDev(req, res) {
  if (req.method === "POST") {
    return readJsonBody(req, (body) => {
      if (!body || typeof body !== "object") return jsonRes(res, 400, { error: "bad body" });
      if (typeof body.mode === "string") worldDev.mode = body.mode;
      if (body.regions && typeof body.regions === "object") {  // 前端為各 region 真相源 → 整顆 region 物件覆寫
        for (const k of Object.keys(body.regions)) worldDev.regions[k] = body.regions[k];
      }
      if (body.reset === true) worldDev = emptyWorldDev();     // 全清（僅 world-dev.json，不碰 atom）
      scheduleWorldDevWrite();
      jsonRes(res, 200, { ok: true });
    });
  }
  jsonRes(res, 200, worldDev);                                // GET：回完整發展狀態
}

// ── 記憶自癒：spawn atom-heal.py（分級 L1 機械/L2 LLM判斷/L3 喚醒），皆走泛用 healRunner ──
const healRunner = makeJobRunner({ maxConcurrent: (loadConfig().heal || {}).max_concurrent || 1, ttlMs: 300000 });
const ATOM_NAME_RE = /^[\w一-鿿.-]+$/;   // 防 shell 注入：只允許字母數字底線連字號點與 CJK
function healCfg() { return loadConfig().heal || {}; }
function spawnHeal(atom, auto) {
  const script = path.join(TOOLS_DIR, "atom-heal.py");
  const args = `--atom "${atom}" --apply --backend ${healCfg().backend || "ollama"}${auto ? " --auto" : ""} --json`;
  return healRunner.start(() => execJson(pyCmd(script, args), { timeout: healCfg().agent_timeout_ms || 180000 }), { atom });
}
function apiHealStart(req, res, atom, auto) {
  if (healCfg().enabled === false) return jsonRes(res, 503, { error: "heal disabled" });
  if (!ATOM_NAME_RE.test(atom)) return jsonRes(res, 400, { error: "bad atom name" });
  const r = spawnHeal(atom, auto);
  if (!r.ok) return jsonRes(res, 409, { error: "heal busy", running: r.running });
  jsonRes(res, 202, { job_id: r.id, status: "running", atom, auto: !!auto });
}
function apiHealAll(req, res) {
  if (healCfg().enabled === false) return jsonRes(res, 503, { error: "heal disabled" });
  exec(pyCmd(path.join(TOOLS_DIR, "atom-health-check.py"), "--report --json"), { timeout: 30000 }, (err, stdout) => {
    const names = new Set();
    try {
      const h = JSON.parse(stdout);
      (h.broken_refs || []).forEach((b) => names.add(b.atom));
      (h.missing_reverse_refs || []).forEach((r) => names.add(r.atom_a));
    } catch { /* ignore */ }
    const started = [];
    for (const n of names) {
      if (!ATOM_NAME_RE.test(n)) continue;
      const r = spawnHeal(n, false);
      if (r.ok) started.push({ atom: n, job_id: r.id }); else break;   // 並發滿 → 其餘留待下次
    }
    jsonRes(res, 202, { started, count: started.length, pending: Math.max(0, names.size - started.length) });
  });
}
function apiHealReview(req, res) {
  const dir = path.join(CLAUDE_DIR, "memory", "_heal_review");
  const items = [];
  try {
    for (const f of fs.readdirSync(dir)) {
      if (f.endsWith(".json")) { try { items.push(JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8"))); } catch { /* skip */ } }
    }
  } catch { /* dir absent = no pending */ }
  jsonRes(res, 200, { items, count: items.length });
}

// --- Vector Status Proxy ---

function apiVectorStatus(req, res) {
  const cfg = loadConfig();
  const port = cfg.vector_search?.service_port || 3849;
  const proxyReq = http.request(
    { hostname: "127.0.0.1", port, path: "/status", method: "GET", timeout: 5000 },
    (proxyRes) => {
      let body = "";
      proxyRes.on("data", chunk => body += chunk);
      proxyRes.on("end", () => {
        try { jsonRes(res, 200, JSON.parse(body)); }
        catch { jsonRes(res, 502, { error: "invalid response from vector service" }); }
      });
    }
  );
  proxyReq.on("error", () => jsonRes(res, 503, { error: "vector service unreachable", port }));
  proxyReq.on("timeout", () => { proxyReq.destroy(); jsonRes(res, 504, { error: "vector service timeout" }); });
  proxyReq.end();
}

// --- Ollama Backends Status (30s server-side cache) ---

let _ollamaCache = { data: null, ts: 0 };
const OLLAMA_CACHE_TTL = 30000; // 30s

function apiOllamaBackendsStatus(req, res) {
  const now = Date.now();
  if (_ollamaCache.data && (now - _ollamaCache.ts) < OLLAMA_CACHE_TTL) {
    return jsonRes(res, 200, _ollamaCache.data);
  }

  const cfg = loadConfig();
  const backends = cfg.vector_search?.ollama_backends || {};
  const names = Object.keys(backends);
  if (!names.length) return jsonRes(res, 200, { backends: [], cached: false });

  // Read long_die marker
  let longDie = null;
  try {
    const marker = fs.readFileSync(path.join(WORKFLOW_DIR, ".backend_long_die.json"), "utf-8");
    longDie = JSON.parse(marker);
  } catch {}

  // Read auth token for rdchat
  let rdchatToken = null;
  try {
    const tf = fs.readFileSync(path.join(WORKFLOW_DIR, ".rdchat_token.json"), "utf-8");
    rdchatToken = JSON.parse(tf).token;
  } catch {}

  const results = [];
  let pending = names.length;

  function finish() {
    if (--pending > 0) return;
    const payload = { backends: results, long_die: longDie, cached: false, checked_at: now };
    _ollamaCache = { data: { ...payload, cached: true }, ts: now };
    payload.cached = false;
    jsonRes(res, 200, payload);
  }

  for (const name of names) {
    const b = backends[name];
    const entry = {
      name,
      base_url: b.base_url,
      llm_model: b.llm_model || "?",
      embedding_model: b.embedding_model || "?",
      priority: b.priority || 99,
      enabled: b.enabled !== false,
      status: "unknown",
      latency_ms: null,
      long_die: longDie && longDie.backend === name ? longDie : null,
    };

    if (!entry.enabled) {
      entry.status = "disabled";
      results.push(entry);
      finish();
      continue;
    }

    const url = new URL(b.base_url.replace(/\/+$/, "") + "/api/tags");
    const isHttps = url.protocol === "https:";
    const mod = isHttps ? https : http;
    const headers = {};
    if (b.auth && rdchatToken) {
      headers["Authorization"] = "Bearer " + rdchatToken;
    }
    const t0 = Date.now();
    const opts = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname + url.search,
      method: "GET",
      headers,
      timeout: 5000,
      rejectUnauthorized: false,
    };

    const probe = mod.request(opts, (probeRes) => {
      // Drain response body
      probeRes.on("data", () => {});
      probeRes.on("end", () => {
        entry.latency_ms = Date.now() - t0;
        entry.status = probeRes.statusCode === 200 ? "online"
                     : probeRes.statusCode === 401 ? "auth_expired"
                     : "error_" + probeRes.statusCode;
        results.push(entry);
        finish();
      });
    });
    probe.on("error", () => {
      entry.latency_ms = Date.now() - t0;
      entry.status = "offline";
      results.push(entry);
      finish();
    });
    probe.on("timeout", () => {
      probe.destroy();
      entry.latency_ms = Date.now() - t0;
      entry.status = "timeout";
      results.push(entry);
      finish();
    });
    probe.end();
  }
}

// --- Knowledge Queue Aggregation ---

function apiKnowledgeQueue(req, res) {
  const sessions = listAllSessions();
  const items = [];
  for (const s of sessions) {
    if (s.ended) continue;
    const state = readState(s.session_id);
    if (!state) continue;
    for (const kq of (state.knowledge_queue || [])) {
      items.push({ session_id: s.session_id, session_name: s.name, ...kq });
    }
  }
  jsonRes(res, 200, items);
}

// --- Atoms Browser API ---

function apiProjects(req, res) {
  const reg = loadRegistry();
  const projects = [];
  for (const [slug, info] of Object.entries(reg.projects || {})) {
    const proj = {
      slug,
      root: info.root || "",
      last_seen: info.last_seen || "",
      aliases: info.aliases || [],
      has_memory: false,
      atom_count: 0,
      failure_count: 0,
      episodic_count: 0,
    };
    // V2.21: if root itself is the .claude dir, memory is at root/memory/ directly
    const rootNorm = path.resolve(info.root || "");
    const isClaudeDir = rootNorm.toLowerCase() === path.resolve(CLAUDE_DIR).toLowerCase();
    const memDir = isClaudeDir
      ? path.join(rootNorm, "memory")
      : path.join(rootNorm, ".claude", "memory");
    if (fs.existsSync(memDir) && fs.existsSync(path.join(memDir, "MEMORY.md"))) {
      proj.has_memory = true;
      try {
        proj.atom_count = fs.readdirSync(memDir).filter(f =>
          f.endsWith(".md") && f !== "MEMORY.md" && !f.startsWith("_") && !f.startsWith("SPEC_")
        ).length;
      } catch {}
      try {
        const failDir = path.join(memDir, "failures");
        if (fs.existsSync(failDir)) {
          proj.failure_count = fs.readdirSync(failDir).filter(f => f.endsWith(".md") && f !== "_INDEX.md").length;
        }
      } catch {}
      try {
        const epicDir = path.join(memDir, "episodic");
        if (fs.existsSync(epicDir)) {
          proj.episodic_count = fs.readdirSync(epicDir).filter(f => f.endsWith(".md")).length;
        }
      } catch {}
    }
    projects.push(proj);
  }
  projects.sort((a, b) => (b.last_seen || "").localeCompare(a.last_seen || ""));
  jsonRes(res, 200, projects);
}

function apiAtoms(req, res) {
  const atoms = [];
  const seenAtomFiles = new Set();
  const scanDirs = [
    { dir: MEMORY_DIR, layer: "global", scope: "global" },
    { dir: path.join(MEMORY_DIR, "failures"), layer: "failures", scope: "global" },
    { dir: path.join(MEMORY_DIR, "unity"), layer: "unity", scope: "global" },
  ];

  for (const { dir, layer, scope } of scanDirs) {
    if (!fs.existsSync(dir)) continue;
    for (const f of fs.readdirSync(dir)) {
      if (!f.endsWith(".md")) continue;
      if (f === "MEMORY.md" || f.startsWith("SPEC_") || f.startsWith("_")) continue;

      const filePath = path.join(dir, f);
      const fileKey = path.resolve(filePath).toLowerCase();
      if (seenAtomFiles.has(fileKey)) continue;
      seenAtomFiles.add(fileKey);
      try {
        const content = fs.readFileSync(filePath, "utf-8");
        const atom = { name: f.replace(".md", ""), layer, scope, file: f };

        // Parse metadata
        const metaRe = /^-\s+([\w-]+):\s*(.+)$/gm;
        let m;
        while ((m = metaRe.exec(content)) !== null) {
          const key = m[1].toLowerCase(), val = m[2].trim();
          switch (key) {
            case "confidence": atom.confidence = val; break;
            case "last-used": atom.last_used = val; break;
            case "confirmations": atom.confirmations = parseInt(val) || 0; break;
            case "readhits": atom.readhits = parseInt(val) || 0; break;
            case "trigger": atom.triggers = val.split(",").map(t => t.trim()); break;
            case "related": atom.related = val.split(",").map(t => t.trim()); break;
            case "created": atom.created = val; break;
            case "type": atom.type = val; break;
            case "tags": atom.tags = val.split(",").map(t => t.trim()); break;
            case "scope": atom.scope = val; break;
            case "audience": atom.audience = val.split(",").map(t => t.trim()); break;
            case "author": atom.author = val; break;
          }
        }

        // Count knowledge items
        let knowledgeCount = 0;
        let inKnowledge = false;
        for (const line of content.split("\n")) {
          if (/^##\s+知識/.test(line)) { inKnowledge = true; continue; }
          if (/^##\s+/.test(line) && inKnowledge) break;
          if (inKnowledge && /^- \[/.test(line)) knowledgeCount++;
        }
        atom.knowledge_count = knowledgeCount;

        // Line count
        atom.line_count = content.split("\n").length;

        // Days since last used
        if (atom.last_used) {
          const lu = new Date(atom.last_used);
          atom.days_since_used = Math.floor((Date.now() - lu.getTime()) / 86400000);
        }

        // Full content for detail view
        atom.content = content;

        enrichAtomWithAccess(atom, filePath);  // v2: 戰力/遙測
        atoms.push(atom);
      } catch {}
    }
  }

  // Helper: scan a single .md as an atom (used by project + V4 shared/role scans)
  function pushAtomFromFile(filePath, fileName, layerLabel, defaultScope) {
    const fileKey = path.resolve(filePath).toLowerCase();
    if (seenAtomFiles.has(fileKey)) return;
    seenAtomFiles.add(fileKey);
    try {
      const content = fs.readFileSync(filePath, "utf-8");
      if (content.includes("Status: migrated-v2.21")) return;
      const atom = {
        name: fileName.replace(".md", ""),
        layer: layerLabel,
        scope: defaultScope,
        file: fileName,
        content,
      };
      const metaRe = /^-\s+([\w-]+):\s*(.+)$/gm;
      let m2;
      while ((m2 = metaRe.exec(content)) !== null) {
        const key = m2[1].toLowerCase(), val = m2[2].trim();
        switch (key) {
          case "confidence": atom.confidence = val; break;
          case "last-used": atom.last_used = val; break;
          case "confirmations": atom.confirmations = parseInt(val) || 0; break;
          case "readhits": atom.readhits = parseInt(val) || 0; break;
          case "related": atom.related = val.split(",").map(t => t.trim()); break;
          case "trigger": atom.triggers = val.split(",").map(t => t.trim()); break;
          case "scope": atom.scope = val; break;
          case "audience": atom.audience = val.split(",").map(t => t.trim()); break;
          case "author": atom.author = val; break;
        }
      }
      atom.line_count = content.split("\n").length;
      enrichAtomWithAccess(atom, filePath);  // v2: 戰力/遙測
      atoms.push(atom);
    } catch {}
  }

  // Helper: scan a flat memory dir, skip excluded dirs, optionally exclude personal/episodic/_*
  function scanFlatDir(dir, layerLabel, defaultScope) {
    if (!fs.existsSync(dir)) return;
    for (const f of fs.readdirSync(dir)) {
      if (!f.endsWith(".md")) continue;
      if (f === "MEMORY.md" || f.startsWith("_")) continue;
      pushAtomFromFile(path.join(dir, f), f, layerLabel, defaultScope);
    }
  }

  // Helper: V4 shared/ + roles/{r}/ scan for any memory root
  function scanV4ScopeDirs(memRoot, layerPrefix, scopePrefix) {
    const sharedDir = path.join(memRoot, "shared");
    if (fs.existsSync(sharedDir)) {
      scanFlatDir(sharedDir, layerPrefix + "shared", scopePrefix + "shared");
    }
    const rolesDir = path.join(memRoot, "roles");
    if (fs.existsSync(rolesDir)) {
      try {
        for (const role of fs.readdirSync(rolesDir)) {
          const roleDir = path.join(rolesDir, role);
          try {
            if (!fs.statSync(roleDir).isDirectory()) continue;
          } catch { continue; }
          scanFlatDir(roleDir, layerPrefix + "role:" + role, scopePrefix + "role:" + role);
        }
      } catch {}
    }
  }

  // Helper: scan a project memory dir (legacy flat layout) and push atoms
  function scanProjMemDir(projMemDir, slug) {
    const before = atoms.length;
    scanFlatDir(projMemDir, "project:" + slug, "project:" + slug);
    scanV4ScopeDirs(projMemDir, "project:" + slug + ":", "project:" + slug + ":");
    // 路徑即權威：專案 memory 目錄下的 atom 一律歸該 slug。
    // pushAtomFromFile 解析 frontmatter 時會用 bare `Scope:`（project/shared/personal/role:x）
    // 覆寫掉 path-derived 的 composite scope，導致 shared/ 子層 atom 被誤歸 "core" 房
    // （c--projects 全在 shared/ → 整個房間消失）。兩段掃描後統一補正回 project:<slug>[:subscope]。
    for (let i = before; i < atoms.length; i++) {
      const sc = atoms[i].scope || "";
      if (sc === "project:" + slug || sc.startsWith("project:" + slug + ":")) continue;
      if (sc === "project") atoms[i].scope = "project:" + slug;
      else if (sc === "shared" || sc === "personal" || sc.startsWith("role:")) {
        atoms[i].scope = "project:" + slug + ":" + sc;
      }
    }
  }

  // V4: global shared/ + roles/{r}/ scan (本專案目前無此目錄，預留給未來)
  scanV4ScopeDirs(MEMORY_DIR, "", "");

  // V2.21: scan registry project dirs (new path)
  const seenProjDirs = new Set();
  for (const { slug, memDir } of getRegistryMemDirs()) {
    scanProjMemDir(memDir, slug);
    seenProjDirs.add(memDir);
  }

  // Also scan old project memory dirs (fallback for unregistered projects)
  const projectsDir = path.join(CLAUDE_DIR, "projects");
  if (fs.existsSync(projectsDir)) {
    for (const proj of fs.readdirSync(projectsDir)) {
      const projMemDir = path.join(projectsDir, proj, "memory");
      if (seenProjDirs.has(projMemDir)) continue;
      scanProjMemDir(projMemDir, proj);
    }
  }

  atoms.sort((a, b) => (b.last_used || "").localeCompare(a.last_used || ""));
  jsonRes(res, 200, atoms);
}

// ─── Skills (commands/*.md) ──────────────────────────────────────────────────
// 純檔案掃描；提供「全域 + 各 registered project」的 slash command 清單。
const SKILL_CATEGORY_MAP = {
  // V4 / V4.1 共用核心
  "memory-peek": "V4.1", "memory-undo": "V4.1", "memory-session-score": "V4.1",
  "generate-episodic": "V4.1",
  // 記憶維運
  "extract": "記憶維運", "memory-health": "記憶維運", "memory-review": "記憶維運",
  "conflict": "記憶維運", "conflict-review": "記憶維運", "atom-debug": "記憶維運",
  "fix-escalation": "記憶維運",
  // 開發協作
  "handoff": "開發協作", "continue": "開發協作", "resume": "開發協作",
  "init-project": "開發協作", "init-roles": "開發協作", "read-project": "開發協作",
  "upgrade": "開發協作", "consciousness-stream": "開發協作",
  // 工具
  "harvest": "工具", "browse-sprites": "工具", "unity-yaml": "工具",
  "svn-update": "工具", "vector": "工具",
};

function extractSkillDescription(content) {
  const lines = content.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    // 跳過 H1 與空行；找第一個 `> ...` 引言行（這是現行 commands/*.md 的描述慣例）
    if (line.startsWith("> ")) return line.slice(2).trim();
  }
  // fallback：第一個非 H1 / 非空 / 非分隔線的段落
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line || line.startsWith("#") || line.startsWith("---")) continue;
    return line.slice(0, 200);
  }
  return "";
}

function scanCommandsDir(dir, source) {
  const skills = [];
  if (!fs.existsSync(dir)) return skills;
  for (const f of fs.readdirSync(dir)) {
    if (!f.endsWith(".md")) continue;
    const filePath = path.join(dir, f);
    try {
      const stat = fs.statSync(filePath);
      if (!stat.isFile()) continue;
      const content = fs.readFileSync(filePath, "utf-8");
      const name = f.replace(".md", "");
      skills.push({
        name,
        command: "/" + name,
        description: extractSkillDescription(content),
        category: SKILL_CATEGORY_MAP[name] || "其他",
        source,
        file: filePath,
        content,
      });
    } catch {}
  }
  return skills;
}

function apiSkills(req, res) {
  const skills = [];
  const seenFiles = new Set();
  function pushUnique(list) {
    for (const s of list) {
      const key = path.resolve(s.file).toLowerCase();
      if (seenFiles.has(key)) continue;
      seenFiles.add(key);
      skills.push(s);
    }
  }
  // 全域（優先，避免被 registered project 重複撈走）
  pushUnique(scanCommandsDir(path.join(CLAUDE_DIR, "commands"), "global"));
  // 各 registered project
  const reg = loadRegistry();
  for (const [slug, info] of Object.entries(reg.projects || {})) {
    if (!info.root) continue;
    const rootNorm = path.resolve(info.root);
    const projCmdDir = path.join(rootNorm, ".claude", "commands");
    // 若 project root 的 .claude/commands 與 CLAUDE_DIR/commands 是同一目錄（例：root=user home），跳過
    const projCmdNorm = path.resolve(projCmdDir).toLowerCase();
    const globalCmdNorm = path.resolve(path.join(CLAUDE_DIR, "commands")).toLowerCase();
    if (projCmdNorm === globalCmdNorm) continue;
    pushUnique(scanCommandsDir(projCmdDir, "project:" + slug));
  }
  // 排序：分類 → 名稱
  skills.sort((a, b) =>
    a.category.localeCompare(b.category, "zh-Hant") ||
    a.name.localeCompare(b.name)
  );
  jsonRes(res, 200, skills);
}

// ─── MCP Servers ─────────────────────────────────────────────────────────────
// 來源：~/.claude/.mcp.json + 各 registered project .mcp.json + settings.json
function readMcpJson(filePath) {
  if (!fs.existsSync(filePath)) return null;
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf-8"));
  } catch { return null; }
}

function apiMcpServers(req, res) {
  const servers = [];

  // 全域 .mcp.json
  const globalMcp = readMcpJson(path.join(CLAUDE_DIR, ".mcp.json"));
  if (globalMcp && globalMcp.mcpServers) {
    for (const [name, cfg] of Object.entries(globalMcp.mcpServers)) {
      servers.push(buildMcpEntry(name, cfg, "global", path.join(CLAUDE_DIR, ".mcp.json")));
    }
  }

  // settings.json 的 enabled 狀態
  const settings = readMcpJson(path.join(CLAUDE_DIR, "settings.json")) || {};
  const enabledList = settings.enabledMcpjsonServers || [];
  const enableAll = settings.enableAllProjectMcpServers === true;

  // 各 registered project .mcp.json
  const reg = loadRegistry();
  for (const [slug, info] of Object.entries(reg.projects || {})) {
    if (!info.root) continue;
    const rootNorm = path.resolve(info.root);
    const isClaudeDir = rootNorm.toLowerCase() === path.resolve(CLAUDE_DIR).toLowerCase();
    if (isClaudeDir) continue;
    const projMcpPath = path.join(rootNorm, ".mcp.json");
    const projMcp = readMcpJson(projMcpPath);
    if (!projMcp || !projMcp.mcpServers) continue;
    for (const [name, cfg] of Object.entries(projMcp.mcpServers)) {
      const entry = buildMcpEntry(name, cfg, "project:" + slug, projMcpPath);
      // 專案 MCP 的啟用判斷：enableAllProjectMcpServers 或 enabledMcpjsonServers 含名稱
      entry.enabled = enableAll || enabledList.includes(name);
      servers.push(entry);
    }
  }

  servers.sort((a, b) =>
    a.source.localeCompare(b.source) || a.name.localeCompare(b.name)
  );
  jsonRes(res, 200, servers);
}

function buildMcpEntry(name, cfg, source, filePath) {
  return {
    name,
    type: cfg.type || "stdio",
    command: cfg.command || "",
    args: Array.isArray(cfg.args) ? cfg.args : [],
    url: cfg.url || "",
    env_keys: cfg.env ? Object.keys(cfg.env) : [],
    source,
    config_file: filePath,
    enabled: true, // 全域預設啟用；專案的會在 caller 覆寫
  };
}

// ─── HTTP Dashboard ─────────────────────────────────────────────────────────

const DASHBOARD_HTML = `<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>工作流守衛 v${VERSIONS.guardian}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, "Segoe UI", sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }
  h1 { color: #58a6ff; margin-bottom: 4px; font-size: 1.4em; }
  .subtitle { color: #8b949e; font-size: 0.85em; margin-bottom: 12px; }
  .stats { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
  .stat { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 10px 14px; min-width: 100px; }
  .stat-value { font-size: 1.4em; font-weight: bold; color: #58a6ff; }
  .stat-label { font-size: 0.75em; color: #8b949e; }
  .tab-nav { display: flex; gap: 0; border-bottom: 1px solid #30363d; margin-bottom: 16px; }
  .tab-btn { padding: 8px 16px; border: none; background: none; color: #8b949e; cursor: pointer; border-bottom: 2px solid transparent; font-size: 0.9em; font-family: inherit; }
  .tab-btn:hover { color: #c9d1d9; }
  .tab-btn.active { color: #58a6ff; border-bottom-color: #58a6ff; }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }
  .sessions { display: flex; flex-direction: column; gap: 12px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .card-name { font-weight: 600; color: #e6edf3; font-size: 1.05em; }
  .card-id { font-family: monospace; color: #79c0ff; font-size: 0.85em; }
  .badge { padding: 2px 8px; border-radius: 12px; font-size: 0.75em; font-weight: 600; }
  .badge-init { background: #1f6feb33; color: #58a6ff; }
  .badge-working { background: #f0883e33; color: #f0883e; }
  .badge-syncing { background: #d2a82633; color: #d2a826; }
  .badge-done { background: #23863633; color: #3fb950; }
  .badge-merged { background: #a371f733; color: #a371f7; }
  .card-meta { font-size: 0.8em; color: #8b949e; margin-bottom: 8px; }
  .card-stats { display: flex; gap: 16px; font-size: 0.85em; }
  .card-stats span { color: #8b949e; }
  .card-stats strong { color: #c9d1d9; }
  .details { margin-top: 10px; padding-top: 10px; border-top: 1px solid #30363d; font-size: 0.82em; }
  .details summary { cursor: pointer; color: #58a6ff; margin-bottom: 6px; }
  .file-list, .kq-list { list-style: none; padding-left: 8px; }
  .file-list li, .kq-list li { padding: 2px 0; color: #8b949e; font-family: monospace; font-size: 0.9em; }
  .kq-badge { font-weight: bold; }
  .kq-badge-fixed { color: #3fb950; }
  .kq-badge-observe { color: #d2a826; }
  .kq-badge-temp { color: #f0883e; }
  .actions { margin-top: 10px; display: flex; gap: 8px; }
  .btn { padding: 4px 12px; border-radius: 4px; border: 1px solid #30363d; background: #21262d; color: #c9d1d9; cursor: pointer; font-size: 0.8em; font-family: inherit; }
  .btn:hover { background: #30363d; }
  .btn-primary { border-color: #388bfd66; color: #58a6ff; }
  .btn-primary:hover { background: #388bfd22; }
  .btn-success { border-color: #3fb95066; color: #3fb950; }
  .btn-success:hover { background: #3fb95022; }
  .btn-danger { border-color: #f8514966; color: #f85149; }
  .btn-danger:hover { background: #f8514922; }
  .empty { text-align: center; color: #8b949e; padding: 40px; }
  .auto-refresh { font-size: 0.8em; color: #8b949e; }
  .auto-refresh label { cursor: pointer; }
  /* Timeline */
  .timeline { position: relative; padding-left: 28px; border-left: 2px solid #30363d; margin-left: 8px; }
  .timeline-item { position: relative; margin-bottom: 16px; }
  .timeline-dot { position: absolute; left: -35px; top: 10px; width: 12px; height: 12px; border-radius: 50%; border: 2px solid #0d1117; }
  .ttl-green { background: #3fb950; }
  .ttl-yellow { background: #d2a826; }
  .ttl-red { background: #f85149; }
  .ttl-critical { background: #f85149; animation: pulse 1s infinite; }
  .ttl-expired { background: #484f58; }
  @keyframes pulse { 50% { opacity: 0.4; } }
  .timeline-card { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; }
  .timeline-date { font-size: 0.75em; color: #8b949e; }
  .timeline-title { font-weight: 600; color: #e6edf3; margin: 4px 0; }
  .timeline-ttl { font-size: 0.8em; padding: 1px 6px; border-radius: 8px; font-weight: 600; }
  .timeline-knowledge { margin-top: 8px; font-size: 0.82em; color: #8b949e; }
  .timeline-knowledge li { padding: 2px 0; list-style: none; }
  .timeline-full { margin-top: 8px; padding-top: 8px; border-top: 1px solid #30363d; white-space: pre-wrap; font-family: monospace; font-size: 0.78em; color: #8b949e; max-height: 300px; overflow-y: auto; }
  /* Health */
  .health-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; margin-bottom: 16px; }
  .health-stat { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; text-align: center; }
  .health-stat .val { font-size: 1.5em; font-weight: bold; }
  .health-stat .lbl { font-size: 0.75em; color: #8b949e; }
  .issue-table { width: 100%; border-collapse: collapse; font-size: 0.82em; margin-bottom: 16px; }
  .issue-table th { text-align: left; color: #8b949e; padding: 6px 8px; border-bottom: 1px solid #30363d; }
  .issue-table td { padding: 6px 8px; border-bottom: 1px solid #21262d; }
  .level-error { color: #f85149; }
  .level-warning { color: #d2a826; }
  .level-info { color: #58a6ff; }
  .suggest-list { list-style: none; margin-bottom: 16px; }
  .suggest-list li { padding: 6px 0; border-bottom: 1px solid #21262d; font-size: 0.85em; }
  .suggest-arrow { color: #58a6ff; font-weight: bold; }
  .cache-info { font-size: 0.75em; color: #484f58; margin-top: 8px; }
  /* Tests */
  .test-card { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 6px; margin-bottom: 6px; background: #161b22; border: 1px solid #30363d; }
  .test-pass { border-left: 3px solid #3fb950; }
  .test-fail { border-left: 3px solid #f85149; }
  .test-skip { border-left: 3px solid #8b949e; }
  .test-icon { font-size: 1.1em; width: 22px; text-align: center; }
  .test-name { font-weight: 600; color: #e6edf3; flex: 1; }
  .test-duration { font-size: 0.8em; color: #8b949e; }
  .test-msg { font-size: 0.78em; color: #8b949e; font-family: monospace; }
  .test-summary { display: flex; gap: 16px; padding: 12px; background: #161b22; border: 1px solid #30363d; border-radius: 6px; margin-bottom: 12px; font-size: 0.9em; }
  .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #30363d; border-top-color: #58a6ff; border-radius: 50%; animation: spin 0.8s linear infinite; vertical-align: middle; margin-right: 8px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .run-btn { padding: 10px 24px; font-size: 1em; border-radius: 6px; border: 1px solid #3fb95066; background: #23863622; color: #3fb950; cursor: pointer; font-weight: 600; font-family: inherit; }
  .run-btn:hover { background: #23863644; }
  .run-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  /* Vector */
  .vec-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .vec-section { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 14px; }
  .vec-section h3 { font-size: 0.9em; color: #58a6ff; margin-bottom: 8px; }
  .vec-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 0.85em; }
  .vec-row .k { color: #8b949e; }
  .vec-row .v { color: #e6edf3; font-family: monospace; }
  .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .status-online { background: #3fb950; }
  .status-offline { background: #f85149; }
  .status-warn { background: #d2a826; }
  .status-disabled { background: #484f58; }
  .backend-card { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 14px; }
  .backend-card .bc-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  .backend-card .bc-name { font-weight: 600; font-size: 0.95em; }
  .backend-card .bc-tag { font-size: 0.75em; padding: 1px 6px; border-radius: 3px; background: #30363d; color: #8b949e; }
  .backend-card .bc-tag.pri { background: #58a6ff22; color: #58a6ff; }
  .section-title { font-size: 1em; font-weight: 600; color: #e6edf3; margin-bottom: 10px; }
  /* Atoms */
  .atom-table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
  .atom-table th { text-align: left; color: #8b949e; padding: 8px; border-bottom: 2px solid #30363d; cursor: pointer; user-select: none; }
  .atom-table th:hover { color: #58a6ff; }
  .atom-table td { padding: 8px; border-bottom: 1px solid #21262d; }
  .atom-table tr:hover { background: #161b2288; }
  .atom-name { color: #58a6ff; font-weight: 600; cursor: pointer; }
  .atom-name:hover { text-decoration: underline; }
  .atom-layer { font-size: 0.8em; padding: 1px 6px; border-radius: 8px; background: #30363d; color: #8b949e; }
  .atom-conf { font-weight: bold; }
  .conf-fixed { color: #3fb950; }
  .conf-observe { color: #d2a826; }
  .conf-temp { color: #f0883e; }
  .atom-detail { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 16px; margin: 12px 0; white-space: pre-wrap; font-family: monospace; font-size: 0.82em; max-height: 500px; overflow-y: auto; }
  .atom-filter { padding: 6px 12px; background: #161b22; border: 1px solid #30363d; border-radius: 4px; color: #c9d1d9; font-size: 0.9em; margin-bottom: 12px; width: 300px; font-family: inherit; }
  .atom-filter::placeholder { color: #484f58; }
  .atom-stats { display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
  .proj-table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
  .proj-table th { text-align: left; color: #8b949e; padding: 8px; border-bottom: 2px solid #30363d; }
  .proj-table td { padding: 8px; border-bottom: 1px solid #21262d; vertical-align: top; }
  .proj-table tr:hover { background: #161b2288; }
  .proj-root { font-family: monospace; font-size: 0.85em; color: #79c0ff; word-break: break-all; }
  .proj-badge-mem { background: #23863622; color: #3fb950; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; }
  .proj-badge-nomem { background: #30363d; color: #8b949e; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; }
  .proj-alias { font-size: 0.8em; color: #8b949e; }
  .proj-filter-btn { background: none; border: 1px solid #30363d; color: #58a6ff; padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 0.8em; font-family: inherit; }
  .proj-filter-btn:hover { background: #58a6ff22; }
  .hot-cache-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; display: flex; align-items: center; gap: 12px; font-size: 0.85em; }
  .hot-cache-card.has-cache { border-color: #3fb95066; }
  .hot-cache-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .hot-cache-dot.green { background: #3fb950; }
  .hot-cache-dot.gray { background: #484f58; }
  .vector-indicator { display: inline-flex; align-items: center; gap: 4px; cursor: pointer; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; }
  .vector-indicator:hover { background: #30363d; }
  .vector-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
  .vector-dot.ready { background: #3fb950; }
  .vector-dot.not-ready { background: #f85149; }
</style>
</head>
<body>
<div style="display:flex;justify-content:space-between;align-items:baseline;">
  <div><h1>工作流守衛 v${VERSIONS.guardian}</h1><p class="subtitle">記憶與對話監控</p></div>
  <div class="auto-refresh"><label><input type="checkbox" id="autoRefresh" checked> 自動重整 (5秒)</label></div>
</div>

<div class="stats" id="statsBar"></div>
<div id="hotCacheCard" class="hot-cache-card" style="display:none"></div>

<nav class="tab-nav">
  <button class="tab-btn active" data-tab="sessions">對話</button>
  <button class="tab-btn" data-tab="episodic">情境記憶</button>
  <button class="tab-btn" data-tab="health">健康檢查</button>
  <button class="tab-btn" data-tab="atoms">原子記憶 v${VERSIONS.atom_memory}</button>
  <button class="tab-btn" data-tab="projects">已知專案</button>
  <button class="tab-btn" data-tab="tests">測試</button>
  <button class="tab-btn" data-tab="vector">向量服務</button>
  <button class="tab-btn" data-tab="env">環境</button>
</nav>

<div id="panelSessions" class="tab-panel active">
  <div class="sessions" id="sessionList"></div>
</div>

<div id="panelEpisodic" class="tab-panel">
  <div id="episodicContent"></div>
</div>

<div id="panelHealth" class="tab-panel">
  <div id="healthContent"><div class="empty">載入健康資料中...</div></div>
</div>

<div id="panelAtoms" class="tab-panel">
  <div id="atomsContent"><div class="empty">載入原子記憶中...</div></div>
</div>

<div id="panelProjects" class="tab-panel">
  <div id="projectsContent"><div class="empty">載入已知專案中...</div></div>
</div>

<div id="panelTests" class="tab-panel">
  <div id="testsContent">
    <div style="text-align:center;padding:20px;">
      <button class="run-btn" id="runTestsBtn" onclick="startTestRun()">執行端對端測試</button>
    </div>
    <div id="testResults"></div>
  </div>
</div>

<div id="panelVector" class="tab-panel">
  <div id="vectorContent"><div class="empty">載入向量服務狀態中...</div></div>
</div>

<div id="panelEnv" class="tab-panel">
  <div id="envContent"><div class="empty">載入環境資訊中...</div></div>
</div>

<script>
let refreshTimer;
let currentTab = "sessions";
let testJobId = null;
let testPollTimer = null;

function switchTab(name) {
  const btn = document.querySelector('[data-tab="' + name + '"]');
  if (btn) btn.click();
}

// ─── Tab Switching ───

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const prevTab = currentTab;
    currentTab = btn.dataset.tab;
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    document.getElementById("panel" + currentTab.charAt(0).toUpperCase() + currentTab.slice(1)).classList.add("active");
    if (prevTab === "vector" && currentTab !== "vector") stopBackendsPolling();
    refreshCurrentTab();
  });
});

async function refreshCurrentTab() {
  const prevScroll = window.scrollY;
  switch (currentTab) {
    case "sessions": await renderSessions(); break;
    case "episodic": await renderEpisodic(); break;
    case "health": await renderHealth(false); break;
    case "atoms": await renderAtoms(); break;
    case "projects": await renderProjects(); break;
    case "tests": break;
    case "vector": await renderVector(); break;
    case "env": await renderEnv(); break;
  }
  window.scrollTo(0, prevScroll);
}

// ─── Sessions Panel (existing logic) ───

async function fetchSessions() {
  try { const r = await fetch("/api/sessions"); return await r.json(); }
  catch { return []; }
}

async function sendSignal(sid, signal) {
  await fetch("/api/sessions/" + sid + "/signal", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ signal })
  });
  renderSessions();
}

async function deleteSession(sid) {
  if (!confirm("確定要刪除對話 " + sid.slice(0,8) + "?")) return;
  await fetch("/api/sessions/" + sid, { method: "DELETE" });
  renderSessions();
}

function badgeClass(phase) { return "badge badge-" + (phase || "init"); }

function clsBadge(c) {
  if (c === "[固]") return '<span class="kq-badge kq-badge-fixed">[固]</span>';
  if (c === "[觀]") return '<span class="kq-badge kq-badge-observe">[觀]</span>';
  return '<span class="kq-badge kq-badge-temp">[臨]</span>';
}

function esc(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

async function renderSessions() {
  const [sessions, vecReady] = await Promise.all([fetchSessions(), fetchVectorReady()]);
  const active = sessions.filter(s => !s.ended);
  const pending = sessions.filter(s => s.sync_pending && !s.ended);
  const vecHtml = '<div class="stat"><div class="vector-indicator" onclick="switchTab(\\'vector\\')"><span class="vector-dot ' + (vecReady?"ready":"not-ready") + '"></span> Vector</div></div>';
  updateStats(sessions.length, active.length, pending.length, vecHtml);
  renderHotCache();

  if (sessions.length === 0) {
    document.getElementById("sessionList").innerHTML = '<div class="empty">無進行中的對話。</div>';
    return;
  }

  const cards = await Promise.all(sessions.map(async (s) => {
    let detail;
    try { const r = await fetch("/api/sessions/" + s.session_id); detail = await r.json(); }
    catch { detail = {}; }
    const files = detail.modified_files || [];
    const kq = detail.knowledge_queue || [];
    const uniqueFiles = [...new Set(files.map(f => f.path))];
    let fileHtml = "";
    if (uniqueFiles.length > 0) {
      fileHtml = '<details><summary>修改檔案 (' + uniqueFiles.length + ')</summary><ul class="file-list">' +
        uniqueFiles.map(f => "<li>" + esc(f.split(/[\\\\/]/).pop()) + ' <span style="color:#484f58">' + esc(f) + "</span></li>").join("") + "</ul></details>";
    }
    let kqHtml = "";
    if (kq.length > 0) {
      kqHtml = '<details><summary>知識佇列 (' + kq.length + ')</summary><ul class="kq-list">' +
        kq.map(q => "<li>" + clsBadge(q.classification) + " " + esc((q.content||"").slice(0,80)) + "</li>").join("") + "</ul></details>";
    }
    return '<div class="card">' +
      '<div class="card-header"><span class="card-name">' + esc(s.name||"?") + '</span><span class="' + badgeClass(s.phase) + '">' + s.phase + (s.muted?" (已靜音)":"") + '</span></div>' +
      '<div class="card-meta"><span class="card-id">' + s.session_id.slice(0,8) + '</span> &middot; ' + esc(s.project||"?") + ' &middot; ' + s.age_minutes + ' 分鐘' + (s.ended?" &middot; 已結束":"") + (s.merged_into?' &middot; <span style="color:#a371f7">已合併至 '+s.merged_into.slice(0,8)+'</span>':"") + '</div>' +
      '<div class="card-stats"><span>檔案：<strong>' + s.modified_files_count + '</strong></span><span>知識：<strong>' + s.knowledge_queue_count + '</strong></span><span>同步：<strong>' + (s.sync_pending?"待處理":"完成") + '</strong></span></div>' +
      (fileHtml||kqHtml ? '<div class="details">' + fileHtml + kqHtml + '</div>' : '') +
      '<div class="actions">' +
        '<button class="btn" onclick="sendSignal(\\'' + s.session_id + '\\',\\'sync_completed\\')">標記已同步</button>' +
        '<button class="btn" onclick="sendSignal(\\'' + s.session_id + '\\',\\'reset\\')">重置</button>' +
        (s.muted ? '' : '<button class="btn" onclick="sendSignal(\\'' + s.session_id + '\\',\\'mute\\')">靜音</button>') +
        '<button class="btn btn-danger" onclick="deleteSession(\\'' + s.session_id + '\\')">刪除</button>' +
      '</div></div>';
  }));
  document.getElementById("sessionList").innerHTML = cards.join("");
}

// ─── Stats Bar ───

function updateStats(total, active, pending, extra) {
  let html = '<div class="stat"><div class="stat-value">' + total + '</div><div class="stat-label">對話數</div></div>' +
    '<div class="stat"><div class="stat-value">' + active + '</div><div class="stat-label">進行中</div></div>' +
    '<div class="stat"><div class="stat-value">' + pending + '</div><div class="stat-label">待同步</div></div>';
  if (extra) html += extra;
  document.getElementById("statsBar").innerHTML = html;
}

// ─── V3: Hot Cache Card ───

async function renderHotCache() {
  const el = document.getElementById("hotCacheCard");
  try {
    const data = await (await fetch("/api/hot-cache")).json();
    if (data.empty) { el.style.display = "none"; return; }
    const hasUninjected = !data.injected && (data.knowledge||[]).length > 0;
    el.className = "hot-cache-card" + (hasUninjected ? " has-cache" : "");
    el.style.display = "flex";
    const ageMin = Math.round((data.age_seconds||0) / 60);
    const ageStr = ageMin < 1 ? "<1 分鐘" : ageMin + " 分鐘前";
    el.innerHTML =
      '<span class="hot-cache-dot ' + (hasUninjected ? "green" : "gray") + '"></span>' +
      '<span><strong>Hot Cache</strong></span>' +
      '<span>來源: ' + (data.source||"?") + '</span>' +
      '<span>知識: ' + (data.knowledge||[]).length + ' 條</span>' +
      '<span>注入: ' + (data.injected ? "已注入" : "待注入") + '</span>' +
      '<span style="color:#8b949e">' + ageStr + '</span>';
  } catch { el.style.display = "none"; }
}

// ─── V3: Vector Ready Indicator ───

async function fetchVectorReady() {
  try {
    const data = await (await fetch("/api/vector-ready")).json();
    return data.ready;
  } catch { return false; }
}

// ─── Episodic Timeline ───

async function renderEpisodic() {
  const el = document.getElementById("episodicContent");
  try {
    const atoms = await (await fetch("/api/episodic")).json();
    if (!atoms.length) {
      el.innerHTML = '<div class="empty">無情境記憶紀錄。<br><span style="font-size:0.85em">情境記憶在對話結束時自動生成。</span></div>';
      return;
    }
    let html = '<div class="timeline">';
    for (const a of atoms) {
      const d = a.days_until_expiry;
      let dotCls = "ttl-green";
      let ttlLabel = d + "天剩餘";
      let ttlStyle = "background:#3fb95022;color:#3fb950";
      if (d !== null && d <= 0) { dotCls = "ttl-expired"; ttlLabel = "已過期"; ttlStyle = "background:#484f5822;color:#484f58"; }
      else if (d !== null && d <= 3) { dotCls = "ttl-critical"; ttlLabel = d + "天剩餘"; ttlStyle = "background:#f8514922;color:#f85149"; }
      else if (d !== null && d <= 7) { dotCls = "ttl-red"; ttlStyle = "background:#f8514922;color:#f85149"; }
      else if (d !== null && d <= 14) { dotCls = "ttl-yellow"; ttlStyle = "background:#d2a82622;color:#d2a826"; }

      const knLines = (a.knowledge_lines || []).slice(0, 5).map(l => "<li>" + esc(l) + "</li>").join("");
      const moreCount = (a.knowledge_lines||[]).length - 5;
      const hasMore = moreCount > 0;

      html += '<div class="timeline-item"><div class="timeline-dot ' + dotCls + '"></div><div class="timeline-card">' +
        '<div style="display:flex;justify-content:space-between;align-items:center">' +
          '<span class="timeline-date">' + esc(a.created || "?") + '</span>' +
          '<span class="timeline-ttl" style="' + ttlStyle + '">' + ttlLabel + '</span>' +
        '</div>' +
        '<div class="timeline-title">' + esc(a.title) + '</div>' +
        '<div style="font-size:0.78em;color:#8b949e">' + esc(a.triggers.join(", ")) + '</div>' +
        (knLines ? '<ul class="timeline-knowledge">' + knLines + (hasMore ? '<li style="color:#58a6ff">... +' + moreCount + ' 更多</li>' : '') + '</ul>' : '') +
        '<details><summary style="font-size:0.8em;color:#58a6ff;cursor:pointer;margin-top:6px">完整內容</summary>' +
          '<div class="timeline-full">' + esc(a.full_content) + '</div></details>' +
      '</div></div>';
    }
    html += '</div>';
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty">載入情境記憶失敗：' + esc(e.message) + '</div>';
  }
}

// ─── Memory Health ───

let lastHealthData = null;

let _healthInfoVisible = false;
function toggleHealthInfo() {
  _healthInfoVisible = !_healthInfoVisible;
  document.querySelectorAll('.health-info-row').forEach(r => {
    r.style.display = _healthInfoVisible ? '' : 'none';
  });
}

async function renderHealth(force) {
  const el = document.getElementById("healthContent");
  try {
    const url = "/api/health" + (force ? "?force=1" : "");
    el.innerHTML = '<div class="empty"><span class="spinner"></span> 載入健康報告中...</div>';
    const data = await (await fetch(url)).json();
    if (data.error) { el.innerHTML = '<div class="empty">健康檢查失敗：' + esc(data.error) + '</div>'; return; }
    lastHealthData = data;

    const cc = data.confidence_counts || {};
    let html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">' +
      '<span class="section-title">記憶健康報告</span>' +
      '<button class="btn btn-primary" onclick="renderHealth(true)">立即重整</button></div>';

    // Confidence counts
    html += '<div class="health-grid">';
    html += '<div class="health-stat"><div class="val" style="color:#3fb950">' + (cc["[固]"]||0) + '</div><div class="lbl">[固] 確定</div></div>';
    html += '<div class="health-stat"><div class="val" style="color:#d2a826">' + (cc["[觀]"]||0) + '</div><div class="lbl">[觀] 觀察</div></div>';
    html += '<div class="health-stat"><div class="val" style="color:#f0883e">' + (cc["[臨]"]||0) + '</div><div class="lbl">[臨] 臨時</div></div>';
    html += '<div class="health-stat"><div class="val">' + (data.total_atoms||0) + '</div><div class="lbl">原子總數</div></div>';
    html += '<div class="health-stat"><div class="val">' + (data.distant_count||0) + '</div><div class="lbl">疏遠區</div></div>';
    html += '</div>';

    // Issues — grouped by severity
    const issues = data.issues || [];
    const errCount = issues.filter(i => i.level === "error").length;
    const warnCount = issues.filter(i => i.level === "warning").length;
    const infoCount = issues.filter(i => i.level === "info").length;
    if (issues.length) {
      html += '<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">' +
        '<span class="section-title">問題</span>' +
        (errCount ? '<span style="color:#f85149;font-weight:bold">' + errCount + ' error</span>' : '') +
        (warnCount ? '<span style="color:#d2a826;font-weight:bold">' + warnCount + ' warning</span>' : '') +
        (infoCount ? '<span style="color:#8b949e">' + infoCount + ' info</span>' : '') +
        '<button class="btn" style="font-size:0.75em;padding:2px 8px" onclick="toggleHealthInfo()">顯示/隱藏 info</button>' +
        '</div>';
      html += '<table class="issue-table"><tr><th>等級</th><th>分類</th><th>檔案</th><th>訊息</th></tr>';
      for (const i of issues) {
        const hideClass = i.level === "info" ? ' class="health-info-row" style="display:' + (_healthInfoVisible ? '' : 'none') + '"' : '';
        html += '<tr' + hideClass + '><td class="level-' + i.level + '">' + i.level + '</td><td>' + esc(i.category) + '</td><td style="font-family:monospace;font-size:0.85em">' + esc(i.file) + '</td><td>' + esc(i.message) + '</td></tr>';
      }
      html += '</table>';
    } else {
      html += '<div style="color:#3fb950;margin-bottom:12px">✓ 無任何問題</div>';
    }

    // Promotions
    const promos = data.promotions || [];
    if (promos.length) {
      html += '<div class="section-title">晉升候選</div><ul class="suggest-list">';
      for (const p of promos) {
        html += '<li><span style="font-family:monospace">' + esc(p.file) + '</span> ' + p.current + ' <span class="suggest-arrow">&rarr;</span> ' + p.suggested + '<br><span style="color:#8b949e;font-size:0.82em">' + esc(p.reason) + '</span></li>';
      }
      html += '</ul>';
    }

    // Demotions
    const demos = data.demotions || [];
    if (demos.length) {
      html += '<div class="section-title">降級 / 過期警告</div><ul class="suggest-list">';
      for (const d of demos) {
        html += '<li><span style="font-family:monospace">' + esc(d.file) + '</span> ' + d.current + ' <span class="suggest-arrow">&rarr;</span> ' + d.suggested + '<br><span style="color:#8b949e;font-size:0.82em">' + esc(d.reason) + '</span></li>';
      }
      html += '</ul>';
    }

    // Reference integrity
    const brokenRefs = data.broken_refs || [];
    const missingRev = data.missing_reverse_refs || [];
    const staleAtoms = data.stale_atoms || [];
    html += '<div class="section-title">參照完整性</div>';
    if (!brokenRefs.length && !missingRev.length && !staleAtoms.length) {
      html += '<div style="color:#3fb950;margin-bottom:12px">✓ 所有參照完整、無過期 atom</div>';
    } else {
      if (brokenRefs.length) {
        html += '<div style="margin-bottom:8px"><strong style="color:#f85149">斷裂參照 (' + brokenRefs.length + ')</strong></div>';
        html += '<table class="issue-table"><tr><th>來源 Atom</th><th>指向（不存在）</th></tr>';
        for (const r of brokenRefs) { html += '<tr><td>' + esc(r.atom || "") + '</td><td style="color:#f85149">' + esc(r.missing_ref || "") + '</td></tr>'; }
        html += '</table>';
      }
      if (missingRev.length) {
        html += '<div style="margin-bottom:8px"><strong style="color:#d2a826">缺反向參照 (' + missingRev.length + ')</strong></div>';
        html += '<table class="issue-table"><tr><th>說明</th></tr>';
        for (const r of missingRev) { html += '<tr><td style="color:#d2a826">' + esc(r.direction || (r.atom_a + " → " + r.atom_b)) + '</td></tr>'; }
        html += '</table>';
      }
      if (staleAtoms.length) {
        html += '<div style="margin-bottom:8px"><strong style="color:#f0883e">過期 Atom (' + staleAtoms.length + ')</strong></div><ul>';
        for (const s of staleAtoms) { html += '<li>' + esc(s.name || s) + ' — Last-used: ' + esc(s.last_used || "?") + '</li>'; }
        html += '</ul>';
      }
    }

    // Audit stats
    const as = data.audit_stats || {};
    if (as.total_entries) {
      html += '<div class="section-title">審計摘要</div><div class="health-grid">';
      const ba = as.by_action || {};
      for (const [k, v] of Object.entries(ba)) {
        html += '<div class="health-stat"><div class="val">' + v + '</div><div class="lbl">' + k + '</div></div>';
      }
      html += '<div class="health-stat"><div class="val">' + as.total_entries + '</div><div class="lbl">總筆數</div></div>';
      html += '</div>';
    }

    html += '<div class="cache-info">掃描時間：' + esc(data.scan_date || "?") + ' | 層級：' + (data.layers||[]).join(", ") + '</div>';
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty">載入健康資料失敗：' + esc(e.message) + '</div>';
  }
}

// ─── E2E Test Runner ───

async function startTestRun() {
  const btn = document.getElementById("runTestsBtn");
  const el = document.getElementById("testResults");
  btn.disabled = true;
  el.innerHTML = '<div style="text-align:center;padding:16px"><span class="spinner"></span> 測試執行中... <span id="testElapsed">0s</span></div>';
  const startTime = Date.now();
  const elapsedTimer = setInterval(() => {
    const s = ((Date.now() - startTime) / 1000).toFixed(0);
    const te = document.getElementById("testElapsed");
    if (te) te.textContent = s + "s";
  }, 500);

  try {
    const r = await fetch("/api/test-run", { method: "POST" });
    const d = await r.json();
    if (d.error) { el.innerHTML = '<div class="empty">' + esc(d.error) + '</div>'; btn.disabled = false; clearInterval(elapsedTimer); return; }
    testJobId = d.job_id;
    testPollTimer = setInterval(async () => {
      try {
        const sr = await fetch("/api/test-run/" + testJobId);
        const sd = await sr.json();
        if (sd.status !== "running") {
          clearInterval(testPollTimer);
          clearInterval(elapsedTimer);
          testPollTimer = null;
          btn.disabled = false;
          renderTestResults(sd);
        }
      } catch {}
    }, 2000);
  } catch (e) {
    el.innerHTML = '<div class="empty">測試執行失敗：' + esc(e.message) + '</div>';
    btn.disabled = false;
    clearInterval(elapsedTimer);
  }
}

function renderTestResults(job) {
  const el = document.getElementById("testResults");
  if (job.status === "error") {
    const err = job.result || {};
    el.innerHTML = '<div class="empty" style="color:#f85149">測試失敗：' + esc(err.error || "unknown") + (err.stderr ? '<br><pre style="text-align:left;font-size:0.8em;margin-top:8px">' + esc(err.stderr) + '</pre>' : '') + '</div>';
    return;
  }
  const r = job.result || {};
  const results = r.results || [];
  let html = '<div class="test-summary">' +
    '<span style="color:#3fb950;font-weight:600">通過：' + (r.passed||0) + '</span>' +
    '<span style="color:#f85149;font-weight:600">失敗：' + (r.failed||0) + '</span>' +
    '<span style="color:#8b949e">略過：' + (r.skipped||0) + '</span>' +
    '<span style="color:#8b949e">總計：' + (r.total||0) + '</span>' +
    '<span style="color:#8b949e">耗時：' + ((job.elapsed_ms||0)/1000).toFixed(1) + 's</span>' +
  '</div>';
  for (const t of results) {
    const cls = t.skipped ? "test-skip" : (t.passed ? "test-pass" : "test-fail");
    const icon = t.skipped ? "&#9711;" : (t.passed ? "&#10003;" : "&#10007;");
    const iconColor = t.skipped ? "#8b949e" : (t.passed ? "#3fb950" : "#f85149");
    html += '<div class="test-card ' + cls + '">' +
      '<span class="test-icon" style="color:' + iconColor + '">' + icon + '</span>' +
      '<span class="test-name">' + esc(t.name) + '</span>' +
      '<span class="test-duration">' + (t.duration_ms||0).toFixed(0) + 'ms</span>' +
    '</div>';
    if (t.message) {
      html += '<div style="padding:0 14px 6px 48px"><span class="test-msg">' + esc(t.message) + '</span></div>';
    }
  }
  el.innerHTML = html;
}

// ─── Vector Status ───

let _backendsHtml = "";  // cached backend HTML (refreshed independently)
let _backendsTimer = null;

async function fetchBackendsStatus() {
  try {
    const r = await fetch("/api/ollama-backends-status");
    const d = await r.json();
    const bs = (d.backends || []).sort((a,b) => a.priority - b.priority);
    if (!bs.length) { _backendsHtml = ""; return; }

    const statusMap = {
      online: { dot: "status-online", label: "線上", color: "#3fb950" },
      offline: { dot: "status-offline", label: "離線", color: "#f85149" },
      timeout: { dot: "status-offline", label: "逾時", color: "#f85149" },
      auth_expired: { dot: "status-warn", label: "Token 過期", color: "#d2a826" },
      disabled: { dot: "status-disabled", label: "停用", color: "#484f58" },
    };
    const checkedAt = d.checked_at ? new Date(d.checked_at).toLocaleTimeString() : "?";
    const cached = d.cached ? ' <span style="color:#484f58;font-size:0.75em">(快取)</span>' : "";

    let html = '<div style="margin-top:16px"><h3 style="font-size:0.95em;color:#e6edf3;margin-bottom:8px">Ollama 後端' + cached + ' <span style="color:#484f58;font-size:0.75em;font-weight:normal">最後檢查 ' + checkedAt + '</span></h3>';

    // Long DIE warning
    if (d.long_die) {
      html += '<div style="background:#d2a82622;border:1px solid #d2a82644;border-radius:6px;padding:8px 12px;margin-bottom:10px;font-size:0.85em;color:#d2a826">';
      html += '⚠ ' + esc(d.long_die.backend) + ' 長期停用至 ' + esc(d.long_die.until||"?") + '：' + esc(d.long_die.message||"");
      html += '</div>';
    }

    html += '<div class="vec-grid">';
    for (const b of bs) {
      const s = statusMap[b.status] || { dot: "status-warn", label: b.status, color: "#d2a826" };
      const isRemote = !b.base_url.includes("127.0.0.1") && !b.base_url.includes("localhost");
      html += '<div class="backend-card">';
      html += '<div class="bc-header"><span class="status-dot ' + s.dot + '"></span>';
      html += '<span class="bc-name">' + esc(b.name) + '</span>';
      html += '<span class="bc-tag pri">P' + b.priority + '</span>';
      html += '<span class="bc-tag">' + (isRemote ? "遠端" : "本機") + '</span>';
      html += '</div>';
      html += '<div class="vec-row"><span class="k">狀態</span><span class="v" style="color:' + s.color + '">' + s.label;
      if (b.latency_ms != null && b.status === "online") html += ' (' + b.latency_ms + 'ms)';
      html += '</span></div>';
      html += '<div class="vec-row"><span class="k">URL</span><span class="v" style="font-size:0.8em;word-break:break-all">' + esc(b.base_url) + '</span></div>';
      html += '<div class="vec-row"><span class="k">LLM</span><span class="v">' + esc(b.llm_model) + '</span></div>';
      html += '<div class="vec-row"><span class="k">Embedding</span><span class="v">' + esc(b.embedding_model) + '</span></div>';
      if (b.long_die) {
        html += '<div class="vec-row"><span class="k">DIE 狀態</span><span class="v" style="color:#d2a826">長期停用至 ' + esc(b.long_die.until||"?") + '</span></div>';
      }
      html += '</div>';
    }
    html += '</div></div>';
    _backendsHtml = html;
  } catch (e) {
    _backendsHtml = '<div style="margin-top:16px;color:#8b949e;font-size:0.85em">Ollama 後端狀態載入失敗：' + esc(e.message) + '</div>';
  }
}

function startBackendsPolling() {
  if (_backendsTimer) return;
  fetchBackendsStatus();
  _backendsTimer = setInterval(fetchBackendsStatus, 30000);
}
function stopBackendsPolling() {
  if (_backendsTimer) { clearInterval(_backendsTimer); _backendsTimer = null; }
}

async function renderVector() {
  const el = document.getElementById("vectorContent");
  startBackendsPolling();
  try {
    const r = await fetch("/api/vector-status");
    const d = await r.json();
    if (d.error) {
      el.innerHTML = '<div class="card" style="text-align:center;padding:24px"><span class="status-dot status-offline"></span><strong style="color:#f85149">離線</strong><br><span style="color:#8b949e;font-size:0.85em">' + esc(d.error) + '</span></div>' + _backendsHtml;
      return;
    }
    const svc = d.service || {};
    const idx = d.index || {};
    const cfg = d.config || {};
    const job = d.index_job || {};
    const upH = Math.floor((svc.uptime_seconds||0)/3600);
    const upM = Math.floor(((svc.uptime_seconds||0)%3600)/60);

    let html = '<div style="margin-bottom:12px"><span class="status-dot status-online"></span><strong style="color:#3fb950">線上</strong> <span style="color:#8b949e;font-size:0.85em">(' + esc(svc.embedder||"?") + ' on port ' + (svc.port||3849) + ')</span></div>';
    html += '<div class="vec-grid">';

    // Service info
    html += '<div class="vec-section"><h3>服務</h3>';
    html += '<div class="vec-row"><span class="k">運行時間</span><span class="v">' + upH + 'h ' + upM + 'm</span></div>';
    html += '<div class="vec-row"><span class="k">請求次數</span><span class="v">' + (svc.requests_served||0) + '</span></div>';
    html += '<div class="vec-row"><span class="k">嵌入模型</span><span class="v">' + esc(svc.embedder||"?") + '</span></div>';
    html += '</div>';

    // Index info
    html += '<div class="vec-section"><h3>索引</h3>';
    html += '<div class="vec-row"><span class="k">總區塊數</span><span class="v">' + (idx.total_chunks||0) + '</span></div>';
    html += '<div class="vec-row"><span class="k">獨立原子</span><span class="v">' + (idx.unique_atoms||0) + '</span></div>';
    html += '<div class="vec-row"><span class="k">層級數</span><span class="v">' + (idx.layers||[]).length + '</span></div>';
    html += '</div>';

    // Config
    html += '<div class="vec-section"><h3>設定</h3>';
    html += '<div class="vec-row"><span class="k">後端</span><span class="v">' + esc(cfg.embedding_backend||"?") + '</span></div>';
    html += '<div class="vec-row"><span class="k">模型</span><span class="v">' + esc(cfg.embedding_model||"?") + '</span></div>';
    html += '<div class="vec-row"><span class="k">搜尋上限</span><span class="v">' + (cfg.search_top_k||5) + '</span></div>';
    html += '<div class="vec-row"><span class="k">最低分數</span><span class="v">' + (cfg.search_min_score||0.5) + '</span></div>';
    html += '</div>';

    // Index job
    html += '<div class="vec-section"><h3>最近索引任務</h3>';
    if (job.running) {
      html += '<div style="color:#d2a826"><span class="spinner"></span> 索引建立中...</div>';
    } else if (job.result) {
      const jr = job.result;
      html += '<div class="vec-row"><span class="k">發現原子</span><span class="v">' + (jr.atoms_found||0) + '</span></div>';
      html += '<div class="vec-row"><span class="k">已索引原子</span><span class="v">' + (jr.atoms_indexed||0) + '</span></div>';
      html += '<div class="vec-row"><span class="k">區塊數</span><span class="v">' + (jr.total_chunks||0) + '</span></div>';
      html += '<div class="vec-row"><span class="k">耗時</span><span class="v">' + ((jr.elapsed_seconds||0)).toFixed(1) + 's</span></div>';
      html += '<div class="vec-row"><span class="k">類型</span><span class="v">' + (jr.incremental?"增量":"全量") + '</span></div>';
      if (job.finished_at) {
        const fin = new Date(job.finished_at * 1000);
        html += '<div class="vec-row"><span class="k">完成時間</span><span class="v">' + fin.toLocaleString() + '</span></div>';
      }
    } else {
      html += '<div style="color:#8b949e">無近期索引紀錄</div>';
    }
    html += '</div>';

    html += '</div>';
    html += _backendsHtml;
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty">載入向量服務狀態失敗：' + esc(e.message) + '</div>';
  }
}

// ─── Projects Panel ───

async function renderProjects() {
  const el = document.getElementById("projectsContent");
  try {
    const projects = await (await fetch("/api/projects")).json();
    if (!projects.length) {
      el.innerHTML = '<div class="empty">project-registry.json 中無已知專案。</div>';
      return;
    }
    let html = '<p style="color:#8b949e;font-size:0.85em;margin-bottom:12px">來源：project-registry.json（共 ' + projects.length + ' 個專案，動態更新）</p>';
    html += '<table class="proj-table"><thead><tr>';
    html += '<th>Slug / 別名</th><th>根路徑</th><th>記憶層</th><th>Atoms</th><th>Failures</th><th>Episodic</th><th>最後活動</th><th>操作</th>';
    html += '</tr></thead><tbody>';
    for (const p of projects) {
      const memBadge = p.has_memory
        ? '<span class="proj-badge-mem">✓ .claude/memory</span>'
        : '<span class="proj-badge-nomem">未初始化</span>';
      const aliases = (p.aliases || []).length
        ? '<div class="proj-alias">' + p.aliases.map(a => esc(a)).join(', ') + '</div>'
        : '';
      const filterBtn = p.has_memory
        ? '<button class="proj-filter-btn" onclick="filterAtomsByProject(&#39;project:' + p.slug + '&#39;)">查看 Atoms</button>'
        : '';
      html += '<tr>';
      html += '<td><strong>' + esc(p.slug) + '</strong>' + aliases + '</td>';
      html += '<td><span class="proj-root">' + esc(p.root) + '</span></td>';
      html += '<td>' + memBadge + '</td>';
      html += '<td>' + (p.atom_count || 0) + '</td>';
      html += '<td>' + (p.failure_count || 0) + '</td>';
      html += '<td>' + (p.episodic_count || 0) + '</td>';
      html += '<td>' + esc(p.last_seen || '-') + '</td>';
      html += '<td>' + filterBtn + '</td>';
      html += '</tr>';
    }
    html += '</tbody></table>';
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty">載入專案清單失敗：' + esc(e.message) + '</div>';
  }
}

function filterAtomsByProject(layerPrefix) {
  // Switch to atoms tab and filter by project layer
  currentTab = "atoms";
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelector('[data-tab="atoms"]').classList.add("active");
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  document.getElementById("panelAtoms").classList.add("active");
  renderAtoms().then(() => {
    const filterInput = document.getElementById("atomFilter");
    if (filterInput) {
      filterInput.value = layerPrefix;
      filterInput.dispatchEvent(new Event("input"));
    }
  });
}

// ─── Atoms Browser ───

let atomsData = [];
const expandedAtoms = new Set();  // track expanded detail rows across refreshes

async function renderAtoms() {
  const el = document.getElementById("atomsContent");
  const prevFilter = document.getElementById("atomFilter");
  const savedFilter = prevFilter ? prevFilter.value : "";
  try {
    atomsData = await (await fetch("/api/atoms")).json();
    if (!atomsData.length) {
      el.innerHTML = '<div class="empty">無原子記憶。</div>';
      return;
    }
    renderAtomsTable(atomsData);
    if (savedFilter) {
      const fi = document.getElementById("atomFilter");
      if (fi) { fi.value = savedFilter; filterAtoms(savedFilter); }
    } else if (atomSortKey) {
      reapplySort();
    }
  } catch (e) {
    el.innerHTML = '<div class="empty">載入原子記憶失敗：' + esc(e.message) + '</div>';
  }
}

function renderAtomsTable(atoms) {
  const el = document.getElementById("atomsContent");
  const confCounts = {};
  for (const a of atoms) { confCounts[a.confidence] = (confCounts[a.confidence]||0) + 1; }

  let html = '<div class="atom-stats">';
  html += '<div class="stat"><div class="stat-value">' + atoms.length + '</div><div class="stat-label">原子總數</div></div>';
  if (confCounts["[固]"]) html += '<div class="stat"><div class="stat-value" style="color:#3fb950">' + confCounts["[固]"] + '</div><div class="stat-label">[固] 確定</div></div>';
  if (confCounts["[觀]"]) html += '<div class="stat"><div class="stat-value" style="color:#d2a826">' + confCounts["[觀]"] + '</div><div class="stat-label">[觀] 觀察</div></div>';
  if (confCounts["[臨]"]) html += '<div class="stat"><div class="stat-value" style="color:#f0883e">' + confCounts["[臨]"] + '</div><div class="stat-label">[臨] 臨時</div></div>';
  html += '</div>';

  // 收集所有 scope 給下拉選單
  const scopeSet = new Set();
  for (const a of atoms) { if (a.scope) scopeSet.add(a.scope); }
  const scopes = [...scopeSet].sort();

  html += '<div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap">';
  html += '<input id="atomFilter" class="atom-filter" type="text" placeholder="搜尋原子名稱、觸發詞..." oninput="applyAtomFilters()" style="margin-bottom:0">';
  html += '<select id="atomScopeFilter" class="atom-filter" style="width:auto;margin-bottom:0" onchange="applyAtomFilters()">';
  html += '<option value="">所有 scope</option>';
  for (const s of scopes) {
    html += '<option value="' + esc(s) + '">' + esc(s) + '</option>';
  }
  html += '</select>';
  html += '</div>';

  html += '<table class="atom-table" id="atomTable">';
  html += '<thead><tr>' +
    '<th onclick="sortAtoms(\\'name\\')">名稱 &#8597;</th>' +
    '<th onclick="sortAtoms(\\'scope\\')">Scope &#8597;</th>' +
    '<th onclick="sortAtoms(\\'layer\\')">層級 &#8597;</th>' +
    '<th onclick="sortAtoms(\\'confidence\\')">信心 &#8597;</th>' +
    '<th onclick="sortAtoms(\\'confirmations\\')">確認數 &#8597;</th>' +
    '<th onclick="sortAtoms(\\'readhits\\')">讀取數 &#8597;</th>' +
    '<th onclick="sortAtoms(\\'last_used\\')">最後使用 &#8597;</th>' +
    '<th onclick="sortAtoms(\\'knowledge_count\\')">知識數 &#8597;</th>' +
    '<th>行數</th>' +
  '</tr></thead>';
  html += '<tbody id="atomTableBody">';
  html += buildAtomRows(atoms);
  html += '</tbody></table>';
  el.innerHTML = html;
}

function buildAtomRows(atoms) {
  let html = '';
  for (const a of atoms) {
    const confClass = a.confidence === "[固]" ? "conf-fixed" : a.confidence === "[觀]" ? "conf-observe" : "conf-temp";
    const daysAgo = a.days_since_used != null ? a.days_since_used + ' 天前' : '-';
    const audienceTitle = (a.audience||[]).join(", ");
    const authorBadge = a.author ? ' <span style="color:#8b949e;font-size:0.78em">@' + esc(a.author) + '</span>' : '';
    html += '<tr data-name="' + esc(a.name) + '">' +
      '<td><span class="atom-name" onclick="toggleAtomDetail(\\'' + esc(a.name) + '\\')">' + esc(a.name) + '</span>' + authorBadge + '</td>' +
      '<td><span class="atom-layer" title="audience: ' + esc(audienceTitle||"-") + '">' + esc(a.scope||"-") + '</span></td>' +
      '<td><span class="atom-layer">' + esc(a.layer) + '</span></td>' +
      '<td><span class="atom-conf ' + confClass + '">' + esc(a.confidence||"-") + '</span></td>' +
      '<td>' + (a.confirmations||0) + '</td>' +
      '<td>' + (a.readhits||0) + '</td>' +
      '<td title="' + esc(a.last_used||"") + '">' + daysAgo + '</td>' +
      '<td>' + (a.knowledge_count||'-') + '</td>' +
      '<td>' + (a.line_count||'-') + '</td>' +
    '</tr>';
    const detailVis = expandedAtoms.has(a.name) ? '' : 'none';
    html += '<tr id="detail-' + esc(a.name) + '" style="display:' + detailVis + '"><td colspan="9"><div class="atom-detail">' + esc(a.content||"") + '</div></td></tr>';
  }
  return html;
}

function toggleAtomDetail(name) {
  const row = document.getElementById("detail-" + name);
  if (!row) return;
  if (row.style.display === "none") {
    row.style.display = "";
    expandedAtoms.add(name);
  } else {
    row.style.display = "none";
    expandedAtoms.delete(name);
  }
}

let atomSortKey = "last_used";
let atomSortAsc = false;

function applySortToBody(data) {
  const sorted = [...data].sort((a, b) => {
    let va = a[atomSortKey] ?? "", vb = b[atomSortKey] ?? "";
    if (typeof va === "number" && typeof vb === "number") return atomSortAsc ? va - vb : vb - va;
    va = String(va); vb = String(vb);
    return atomSortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
  });
  document.getElementById("atomTableBody").innerHTML = buildAtomRows(sorted);
}

function reapplySort() { applySortToBody(atomsData); }

function sortAtoms(key) {
  if (atomSortKey === key) atomSortAsc = !atomSortAsc;
  else { atomSortKey = key; atomSortAsc = key === "name"; }
  applySortToBody(atomsData);
}

function filterAtoms(query) {
  // 為了向後相容（既有呼叫點用 filterAtoms(saved)），轉呼叫 applyAtomFilters
  const fi = document.getElementById("atomFilter");
  if (fi && typeof query === "string") fi.value = query;
  applyAtomFilters();
}

function applyAtomFilters() {
  const fi = document.getElementById("atomFilter");
  const sf = document.getElementById("atomScopeFilter");
  const q = (fi ? fi.value : "").toLowerCase();
  const scope = sf ? sf.value : "";
  const filtered = atomsData.filter(a => {
    if (scope && (a.scope||"") !== scope) return false;
    if (!q) return true;
    if (a.name.toLowerCase().includes(q)) return true;
    if ((a.triggers||[]).some(t => t.toLowerCase().includes(q))) return true;
    if ((a.related||[]).some(r => r.toLowerCase().includes(q))) return true;
    if ((a.layer||"").toLowerCase().includes(q)) return true;
    if ((a.scope||"").toLowerCase().includes(q)) return true;
    if ((a.author||"").toLowerCase().includes(q)) return true;
    return false;
  });
  applySortToBody(filtered);
}

// ─── Env Tab (Skills + MCP Servers) ───

async function renderEnv() {
  const el = document.getElementById("envContent");
  try {
    const [skills, mcps] = await Promise.all([
      fetch("/api/skills").then(r => r.json()),
      fetch("/api/mcp-servers").then(r => r.json()),
    ]);
    el.innerHTML = renderSkillsSection(skills) + renderMcpSection(mcps);
  } catch (e) {
    el.innerHTML = '<div class="empty">載入環境資訊失敗：' + esc(e.message) + '</div>';
  }
}

function renderSkillsSection(skills) {
  let html = '<div class="section-title">Slash Commands / Skills（' + skills.length + '）</div>';
  if (!skills.length) return html + '<div class="empty">無 commands。</div>';

  // 依分類分組
  const byCat = {};
  for (const s of skills) {
    const cat = s.category || "其他";
    if (!byCat[cat]) byCat[cat] = [];
    byCat[cat].push(s);
  }
  const cats = Object.keys(byCat).sort();

  for (const cat of cats) {
    html += '<details open style="margin-bottom:12px"><summary style="color:#58a6ff;cursor:pointer;padding:6px 0">' + esc(cat) + ' （' + byCat[cat].length + '）</summary>';
    html += '<table class="atom-table">';
    html += '<thead><tr><th>指令</th><th>說明</th><th>來源</th></tr></thead><tbody>';
    for (const s of byCat[cat]) {
      const sourceLabel = s.source === "global" ?
        '<span class="atom-layer">global</span>' :
        '<span class="atom-layer" style="background:#1f6feb33;color:#58a6ff">' + esc(s.source) + '</span>';
      html += '<tr>' +
        '<td><span class="atom-name" onclick="toggleSkillDetail(\\'' + esc(s.name) + '\\')">' + esc(s.command) + '</span></td>' +
        '<td style="color:#c9d1d9">' + esc(s.description||"-") + '</td>' +
        '<td>' + sourceLabel + '</td>' +
      '</tr>';
      html += '<tr id="skill-detail-' + esc(s.name) + '" style="display:none"><td colspan="3"><div class="atom-detail">' + esc(s.content||"") + '</div></td></tr>';
    }
    html += '</tbody></table></details>';
  }
  return html;
}

function toggleSkillDetail(name) {
  const row = document.getElementById("skill-detail-" + name);
  if (!row) return;
  row.style.display = row.style.display === "none" ? "" : "none";
}

function renderMcpSection(mcps) {
  let html = '<div class="section-title" style="margin-top:24px">MCP Servers（' + mcps.length + '）</div>';
  if (!mcps.length) return html + '<div class="empty">無 MCP servers。</div>';

  // 依來源分組
  const bySource = {};
  for (const m of mcps) {
    if (!bySource[m.source]) bySource[m.source] = [];
    bySource[m.source].push(m);
  }
  const sources = Object.keys(bySource).sort();

  for (const src of sources) {
    html += '<details open style="margin-bottom:12px"><summary style="color:#58a6ff;cursor:pointer;padding:6px 0">' + esc(src) + ' （' + bySource[src].length + '）</summary>';
    html += '<table class="atom-table">';
    html += '<thead><tr><th>名稱</th><th>類型</th><th>狀態</th><th>command / url</th><th>env keys</th></tr></thead><tbody>';
    for (const m of bySource[src]) {
      const statusBadge = m.enabled ?
        '<span class="status-dot status-online"></span>啟用' :
        '<span class="status-dot status-disabled"></span>停用';
      const cmdDisplay = m.url ? esc(m.url) :
        (esc(m.command || "-") + (m.args.length ? ' ' + esc(m.args.slice(-1)[0]) : ''));
      html += '<tr>' +
        '<td><strong style="color:#e6edf3">' + esc(m.name) + '</strong></td>' +
        '<td><span class="atom-layer">' + esc(m.type) + '</span></td>' +
        '<td>' + statusBadge + '</td>' +
        '<td style="font-family:monospace;font-size:0.78em;color:#8b949e;word-break:break-all">' + cmdDisplay + '</td>' +
        '<td style="font-size:0.78em;color:#8b949e">' + (m.env_keys.length ? esc(m.env_keys.join(", ")) : '-') + '</td>' +
      '</tr>';
    }
    html += '</tbody></table>';
    html += '<div style="font-size:0.75em;color:#484f58;margin-top:4px">config: ' + esc(bySource[src][0].config_file) + '</div>';
    html += '</details>';
  }
  return html;
}

// ─── Auto Refresh ───

function startAutoRefresh() {
  clearInterval(refreshTimer);
  if (document.getElementById("autoRefresh").checked) {
    refreshTimer = setInterval(refreshCurrentTab, 5000);
  }
}

document.getElementById("autoRefresh").addEventListener("change", startAutoRefresh);
renderSessions();
startAutoRefresh();
</script>
</body>
</html>`;

const httpServer = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${DASHBOARD_PORT}`);
  const pathname = url.pathname;

  // CORS for local dev
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    return res.end();
  }

  // Dashboard
  if (pathname === "/" && req.method === "GET") {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    return res.end(DASHBOARD_HTML);
  }

  // API: list sessions
  if (pathname === "/api/sessions" && req.method === "GET") {
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(JSON.stringify(listAllSessions()));
  }

  // API: get/delete single session
  const sessionMatch = pathname.match(/^\/api\/sessions\/([^/]+)$/);
  if (sessionMatch) {
    const sid = resolveSessionId(sessionMatch[1]) || sessionMatch[1];
    if (req.method === "GET") {
      const state = readState(sid);
      if (!state) {
        res.writeHead(404, { "Content-Type": "application/json" });
        return res.end(JSON.stringify({ error: "not found" }));
      }
      res.writeHead(200, { "Content-Type": "application/json" });
      return res.end(JSON.stringify(state));
    }
    if (req.method === "DELETE") {
      const ok = deleteState(sid);
      res.writeHead(ok ? 200 : 404, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({ ok, deleted: `state-${sid}.json` }));
    }
  }

  // API: send signal
  const signalMatch = pathname.match(/^\/api\/sessions\/([^/]+)\/signal$/);
  if (signalMatch && req.method === "POST") {
    const sid = resolveSessionId(signalMatch[1]) || signalMatch[1];
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      try {
        const { signal } = JSON.parse(body);
        const state = readState(sid);
        if (!state) {
          res.writeHead(404, { "Content-Type": "application/json" });
          return res.end(JSON.stringify({ error: "not found" }));
        }
        switch (signal) {
          case "sync_started":
            state.phase = "syncing";
            break;
          case "sync_completed":
            state.phase = "done";
            state.sync_pending = false;
            state.knowledge_queue = [];
            state.modified_files = [];
            state.ended_at = new Date().toISOString();
            break;
          case "reset":
            state.phase = "working";
            state.sync_pending = false;
            state.stop_blocked_count = 0;
            state.remind_count = 0;
            state.muted = false;
            break;
          case "mute":
            state.muted = true;
            break;
        }
        writeState(sid, state);
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true, state }));
      } catch {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "invalid body" }));
      }
    });
    return;
  }

  // v2.1 API routes
  if (pathname === "/api/episodic" && req.method === "GET") {
    return apiEpisodic(req, res);
  }
  if (pathname === "/api/health" && req.method === "GET") {
    const force = url.searchParams.get("force") === "1";
    return apiHealth(req, res, force);
  }
  if (pathname === "/api/test-run" && req.method === "POST") {
    return apiTestRunStart(req, res);
  }
  const testJobMatch = pathname.match(/^\/api\/test-run\/([^/]+)$/);
  if (testJobMatch && req.method === "GET") {
    return apiTestRunStatus(req, res, testJobMatch[1]);
  }
  // ── World Command Bus 路由 ──
  if (pathname === "/api/world-command" && req.method === "POST") return apiWorldCommandPost(req, res);
  if (pathname === "/api/world-commands" && req.method === "GET") return apiWorldCommandsGet(req, res, url.searchParams.get("since"));
  if (pathname === "/api/world-result" && req.method === "POST") return apiWorldResultPost(req, res);
  if (pathname === "/api/world-snapshot") return apiWorldSnapshot(req, res);
  if (pathname === "/api/world-dev") return apiWorldDev(req, res);
  // ── 記憶自癒路由（先比對固定路徑，再 heal/(.+) 否則被吃掉）──
  if (pathname === "/api/heal-all" && req.method === "POST") return apiHealAll(req, res);
  if (pathname === "/api/heal-review" && req.method === "GET") return apiHealReview(req, res);
  const healJobMatch = pathname.match(/^\/api\/heal-job\/([^/]+)$/);
  if (healJobMatch && req.method === "GET") return healRunner.statusRes(res, healJobMatch[1]);
  const healMatch = pathname.match(/^\/api\/heal\/(.+)$/);
  if (healMatch && req.method === "POST") return apiHealStart(req, res, decodeURIComponent(healMatch[1]), url.searchParams.get("auto") === "1");
  if (pathname === "/api/vector-status" && req.method === "GET") {
    return apiVectorStatus(req, res);
  }
  if (pathname === "/api/ollama-backends-status" && req.method === "GET") {
    return apiOllamaBackendsStatus(req, res);
  }
  if (pathname === "/api/creature-chat" && req.method === "POST") {
    return worldChat.handleCreatureChat(req, res, { loadConfig, jsonRes, WORKFLOW_DIR, fs, path });
  }
  if (pathname === "/api/knowledge-queue" && req.method === "GET") {
    return apiKnowledgeQueue(req, res);
  }
  if (pathname === "/api/atoms" && req.method === "GET") {
    return apiAtoms(req, res);
  }
  if (pathname === "/api/projects" && req.method === "GET") {
    return apiProjects(req, res);
  }
  if (pathname === "/api/skills" && req.method === "GET") {
    return apiSkills(req, res);
  }
  if (pathname === "/api/mcp-servers" && req.method === "GET") {
    return apiMcpServers(req, res);
  }

  // ── V3: Hot Cache status ──
  if (pathname === "/api/hot-cache" && req.method === "GET") {
    const cachePath = path.join(WORKFLOW_DIR, "hot_cache.json");
    try {
      const raw = fs.readFileSync(cachePath, "utf-8");
      const data = JSON.parse(raw);
      data.age_seconds = Math.round(Date.now() / 1000 - (data.timestamp || 0));
      res.writeHead(200, { "Content-Type": "application/json" });
      return res.end(JSON.stringify(data));
    } catch {
      res.writeHead(200, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({ empty: true }));
    }
  }

  // ── V3: Vector Ready indicator ──
  if (pathname === "/api/vector-ready" && req.method === "GET") {
    const flagPath = path.join(WORKFLOW_DIR, "vector_ready.flag");
    const ready = fs.existsSync(flagPath);
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ ready }));
  }

  res.writeHead(404);
  res.end("Not found");
});

// ─── Dashboard port binding with recovery heartbeat ─────────────────────────
// When multiple Claude Code instances exist, only one binds port 3848.
// If that instance dies, a surviving instance must reclaim the port.
const HEARTBEAT_INTERVAL_MS = 15000;
let dashboardHeartbeat = null;

function tryBindDashboard() {
  if (httpServer.listening) return;

  const probe = http.request(
    { hostname: "127.0.0.1", port: DASHBOARD_PORT, path: "/", method: "HEAD", timeout: 500 },
    () => {
      // Port occupied by another instance — keep heartbeat running
      probe.destroy();
    }
  );

  probe.on("error", () => {
    // Connection refused → port is free, attempt to bind
    if (httpServer.listening) return;
    httpServer.listen(DASHBOARD_PORT, "127.0.0.1", () => {
      process.stderr.write(`[workflow-guardian] Dashboard: http://127.0.0.1:${DASHBOARD_PORT}\n`);
      if (dashboardHeartbeat) {
        clearInterval(dashboardHeartbeat);
        dashboardHeartbeat = null;
      }
    });
  });

  probe.on("timeout", () => probe.destroy());
  probe.end();
}

httpServer.on("error", (err) => {
  if (err.code === "EADDRINUSE") {
    process.stderr.write(`[workflow-guardian] Dashboard port ${DASHBOARD_PORT} taken (race), will retry.\n`);
    if (!dashboardHeartbeat) {
      dashboardHeartbeat = setInterval(tryBindDashboard, HEARTBEAT_INTERVAL_MS);
      dashboardHeartbeat.unref();
    }
  } else {
    process.stderr.write(`[workflow-guardian] Dashboard failed: ${err.message}\n`);
  }
});

tryBindDashboard();
setImmediate(() => {
  if (!httpServer.listening && !dashboardHeartbeat) {
    dashboardHeartbeat = setInterval(tryBindDashboard, HEARTBEAT_INTERVAL_MS);
    dashboardHeartbeat.unref();
  }
});

// Keep MCP alive
process.stdin.resume();

// Test/tooling surface: pure content builders (no side effects). Safe to require
// for parity tests; production boots via `node server.js` (require.main === module)
// and is unaffected. See lib/verify/verify_atom_io_equivalence.py:test_13.
module.exports = { buildAtomContent, renderKnowledgeLines, isBlockKnowledge };

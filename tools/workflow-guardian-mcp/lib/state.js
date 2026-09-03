// state.js — workflow/state-*.json 讀寫與會期清理（3-tier auto-cleanup）。
const fs = require("fs");
const path = require("path");
const { WORKFLOW_DIR, loadConfig } = require("./paths");

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

module.exports = {
  listStatePaths, resolveSessionId, readState, writeState, deleteState,
  deriveSessionName, listAllSessions,
};

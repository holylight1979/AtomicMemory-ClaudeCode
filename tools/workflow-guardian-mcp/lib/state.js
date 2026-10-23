// state.js — workflow/state-*.json 讀寫與會期清理（3-tier auto-cleanup）。
const fs = require("fs");
const path = require("path");
const { WORKFLOW_DIR, CODE_DIR, PYTHON_EXE, loadConfig } = require("./paths");

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

/** 改 state 的幾個頂層鍵（規則 STATE_RMW_LOCKED）：跟 hook 守同一把 state-<sid>.lock，鎖裡讀改寫、別人寫過就三方合併、
 *  拿不到鎖留待併帳——Node 沒有 hook 用的那種檔案鎖，整段交 `python -m lib.state_rmw`（hook 同一份 wg_core 實作）。
 *  以前這裡讀整份、改、tmp→rename 整份寫回，會蓋掉 hook 剛寫的那份。回 Promise<{ok, state?, error?}>；失敗也寫 stderr。 */
function applyStateChanges(sessionId, changes) {
  return new Promise((resolve) => {
    let out = "", err = "";
    const done = (res) => {
      if (!res.ok) process.stderr.write(`[guardian] state ${String(sessionId).slice(0, 8)} not updated: ${res.error}\n`);
      resolve(res);
    };
    let cp;
    try {
      cp = require("child_process").spawn(PYTHON_EXE, ["-m", "lib.state_rmw"], {
        cwd: CODE_DIR, env: { ...process.env, PYTHONIOENCODING: "utf-8" }, windowsHide: true,
      });
    } catch (e) {
      return done({ ok: false, error: `spawn failed: ${e.message}` });
    }
    cp.stdout.on("data", (d) => (out += d));
    cp.stderr.on("data", (d) => (err += d));
    cp.on("error", (e) => done({ ok: false, error: `spawn failed: ${e.message}` }));
    cp.on("close", () => {
      if (err.trim()) process.stderr.write(err);   // 合併／待併帳訊號照轉
      try {
        done(JSON.parse(out.trim().split("\n").pop()));
      } catch {
        done({ ok: false, error: `bad reply from lib.state_rmw: ${(out || err).slice(0, 200)}` });
      }
    });
    cp.stdin.end(JSON.stringify({ session_id: sessionId, set: changes }));
  });
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
  listStatePaths, resolveSessionId, readState, applyStateChanges, deleteState,
  deriveSessionName, listAllSessions,
};

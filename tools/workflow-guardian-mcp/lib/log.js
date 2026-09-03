// log.js — crash 記錄與致命錯誤守門（crashLog / onFatal）。全域 process handler 留 server.js 呼叫本檔。
const fs = require("fs");
const path = require("path");
const { WORKFLOW_DIR } = require("./paths");

// ─── Crash protection & logging ─────────────────────────────────────────────

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

module.exports = { crashLog, onFatal };

/**
 * Workflow Guardian MCP Server + HTTP Dashboard — 進入點（entry point）。
 *
 * 職責僅剩：requires/wiring、MCP stdio 轉接（lib/mcp）、HTTP route table、埠自癒、
 *          boot block、parity export 面。業務邏輯已拆入 lib/*（見 lib/_MAP.md）。
 *
 * MCP stdio server (JSON-RPC) + HTTP dashboard (port 3848). Zero npm deps. Node.js 18+.
 */

const fs = require("fs");
const path = require("path");
const http = require("http");
const worldChat = require("./world-chat");   // 腦內世界生物 LLM 對話代理（同進程模組）

const { WORKFLOW_DIR, VERSIONS, loadConfig } = require("./lib/paths");
const { onFatal, crashLog } = require("./lib/log");
const { resolveSessionId, readState, writeState, deleteState, listAllSessions } = require("./lib/state");
const { buildAtomContent, renderKnowledgeLines, isBlockKnowledge } = require("./lib/atom-render");
const dashboardHtml = require("./lib/dashboard-html");
const antiEvasion = require("./lib/anti-evasion");   // Anti-Evasion HUD 唯讀 API + heartbeat
const aecHudHtml = require("./lib/aec-hud-html");     // Anti-Evasion HUD 頁模板
require("./lib/mcp");   // MCP stdio transport：載入即註冊 process.stdin data handler（buffer 私有其內）
const {
  jsonRes,
  apiEpisodic, apiHealth, apiTestRunStart, apiTestRunStatus,
  apiWorldCommandPost, apiWorldCommandsGet, apiWorldResultPost, apiWorldSnapshot, apiWorldDev,
  apiHealAll, apiHealReview, apiHealJobStatus, apiHealStart,
  apiVectorStatus, apiOllamaBackendsStatus, apiKnowledgeQueue,
  apiAtoms, apiProjects, apiSkills, apiMcpServers,
} = require("./lib/http-api");

process.on("uncaughtException", (err) => { onFatal("UncaughtException", err); });
process.on("unhandledRejection", (reason) => { onFatal("UnhandledRejection", reason); });
// Actually exit on termination signals. Previously these logged but did NOT
// exit, leaving orphan node processes that could not be shut down normally.
process.on("SIGTERM", () => { crashLog("SIGTERM", "Process received SIGTERM"); process.exit(0); });
process.on("SIGINT", () => { crashLog("SIGINT", "Process received SIGINT"); process.exit(0); });

// WG_DASHBOARD_PORT env override (testing / running a second isolated instance)
// takes precedence over config; falls back to config then the 3848 default.
const DASHBOARD_PORT = Number(process.env.WG_DASHBOARD_PORT) || loadConfig().dashboard_port || 3848;

// mtime of THIS server.js captured once at process start. A newer instance —
// whose file mtime is greater because server.js was edited after we booted —
// uses this (exposed via /api/whoami · /api/relinquish) to recognize us as
// stale code and ask us to hand off the port. See the port-binding section.
const SELF_MTIME_AT_BOOT = (() => {
  try { return fs.statSync(__filename).mtimeMs; } catch { return 0; }
})();

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
    return res.end(dashboardHtml.render(VERSIONS));
  }

  // API: identify this instance — pid, the server.js file it loaded, and that
  // file's mtime at our boot. Lets a newer instance judge whether the current
  // port holder is stale code, and lets a human verify "is new code live?".
  if (pathname === "/api/whoami" && req.method === "GET") {
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ pid: process.pid, file: __filename, mtime: SELF_MTIME_AT_BOOT }));
  }

  // API: cooperative port hand-off (self-heal). A newer instance running the SAME
  // server.js (requesterFile === our __filename) with fresher code (requesterMtime
  // > our boot-time mtime) asks us to release :3848. We ACK, then exit OURSELVES so
  // it can rebind. No process ever kills another — the stale holder terminates
  // itself; 守好只殺自己人 by construction. A non-guardian process has no such
  // route (404) so nothing outside our own code is ever affected. Localhost-only,
  // same trust model as /api/sessions/:id/signal.
  if (pathname === "/api/relinquish" && req.method === "POST") {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      let reqMtime = NaN, reqFile = "";
      try {
        const j = JSON.parse(body || "{}");
        reqMtime = Number(j.requesterMtime);
        reqFile = String(j.requesterFile || "");
      } catch {}
      const sameFile = !!reqFile &&
        path.resolve(reqFile).toLowerCase() === path.resolve(__filename).toLowerCase();
      const newer = Number.isFinite(reqMtime) && reqMtime > SELF_MTIME_AT_BOOT;
      const relinquishing = sameFile && newer;
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ relinquishing, pid: process.pid, mtime: SELF_MTIME_AT_BOOT }));
      if (relinquishing) {
        process.stderr.write(`[workflow-guardian] Relinquishing port ${DASHBOARD_PORT}: my code (mtime ${SELF_MTIME_AT_BOOT}) is older than requester (${reqMtime}); exiting.\n`);
        // Flush the ACK, stop accepting, then exit so the listening socket frees.
        setTimeout(() => { try { httpServer.close(); } catch {} process.exit(0); }, 200);
      }
    });
    return;
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
  if (healJobMatch && req.method === "GET") return apiHealJobStatus(req, res, healJobMatch[1]);
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

  // ── Hot Cache status ──
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

  // ── Vector Ready indicator ──
  if (pathname === "/api/vector-ready" && req.method === "GET") {
    const flagPath = path.join(WORKFLOW_DIR, "vector_ready.flag");
    const ready = fs.existsSync(flagPath);
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ ready }));
  }

  // ── Anti-Evasion HUD 路由（唯讀；港口持有者供頁 + glob disk 上 Python 落的 report 檔）──
  if (pathname === "/aec/hud" && req.method === "GET") {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    return res.end(aecHudHtml.render());
  }
  if (pathname === "/api/aec/reports" && req.method === "GET") {
    return antiEvasion.apiAecReports(req, res, url.searchParams.get("since"));
  }
  const aecTempMatch = pathname.match(/^\/api\/aec\/tempfiles\/([^/]+)$/);
  if (aecTempMatch && req.method === "GET") {
    return antiEvasion.apiAecTempfiles(req, res, aecTempMatch[1]);
  }
  const aecReportMatch = pathname.match(/^\/api\/aec\/report\/([^/]+)\/(\d+)$/);
  if (aecReportMatch && req.method === "GET") {
    return antiEvasion.apiAecReport(req, res, aecReportMatch[1], aecReportMatch[2]);
  }
  if (pathname === "/api/aec/beat" && req.method === "GET") {
    return antiEvasion.apiAecBeat(req, res);
  }
  if (pathname === "/api/aec/beat-status" && req.method === "GET") {
    return antiEvasion.apiAecBeatStatus(req, res);
  }
  if (pathname === "/api/aec/decision" && req.method === "POST") {
    return antiEvasion.apiAecDecisionPost(req, res);   // HUD (d) 保留/刪除鈕 → 決策落磁碟
  }

  res.writeHead(404);
  res.end("Not found");
});

// ─── Dashboard port binding with recovery heartbeat + stale-orphan reclaim ───
// When multiple Claude Code instances exist, only one binds port 3848.
// If that instance dies, a surviving instance reclaims the port via heartbeat.
//
// Self-heal: an old session's server.js process does NOT exit when the session /
// VS Code closes — it lingers as an orphan holding 3848 and serving STALE code,
// so edited routes never go live (POST /api/<new route> → 404). When we find the
// port held, we ask the holder to hand off via POST /api/relinquish: a holder
// running OUR server.js with OLDER code (its boot-time mtime < this file's current
// mtime) exits ITSELF and we rebind; a peer on current code, or any non-guardian
// process (no such route → not-ok/404), keeps the port and we yield.
// 守好只殺自己人 by construction: we never kill another process — the stale holder
// terminates itself, and only our own code exposes the relinquish contract. Pure
// Node http (no shell / external process spawn), so nothing for AV to flag and it
// works on any platform.
const HEARTBEAT_INTERVAL_MS = 15000;
let dashboardHeartbeat = null;
let _reclaiming = false;

/** If port DASHBOARD_PORT is held by our own stale (old-code) orphan, ask it to
 *  relinquish (it self-exits) and rebind. Otherwise yield. No-op while busy. */
function reclaimStaleOrphan() {
  if (_reclaiming || httpServer.listening) return;
  _reclaiming = true;
  const done = () => { _reclaiming = false; };

  let currentMtime;
  try { currentMtime = fs.statSync(__filename).mtimeMs; }
  catch { return done(); }

  const payload = JSON.stringify({ requesterMtime: currentMtime, requesterFile: __filename });
  const req = http.request(
    { hostname: "127.0.0.1", port: DASHBOARD_PORT, path: "/api/relinquish", method: "POST",
      headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(payload) },
      timeout: 1500 },
    (res) => {
      let body = "";
      res.setEncoding("utf-8");
      res.on("data", (c) => { body += c; });
      res.on("end", () => {
        let out;
        try { out = JSON.parse(body); } catch { return done(); }
        // Only a stale holder of OUR code answers relinquishing:true; peers on
        // current code answer false, non-guardians never reach here → yield.
        if (res.statusCode !== 200 || !out || !out.relinquishing) return done();
        process.stderr.write(`[workflow-guardian] Stale holder pid=${out.pid} relinquishing port ${DASHBOARD_PORT}; rebinding.\n`);
        // Holder is exiting itself; give the socket a moment to free, then rebind.
        setTimeout(() => { _reclaiming = false; tryBindDashboard(); }, 700);
      });
    }
  );
  req.on("error", () => done());   // no relinquish route / unreachable → yield
  req.on("timeout", () => { req.destroy(); done(); });
  req.write(payload);
  req.end();
}

function tryBindDashboard() {
  if (httpServer.listening) return;

  const probe = http.request(
    { hostname: "127.0.0.1", port: DASHBOARD_PORT, path: "/", method: "HEAD", timeout: 500 },
    () => {
      // Port occupied by an HTTP server. If it is our own stale orphan, ask it to
      // hand off; otherwise reclaimStaleOrphan() yields and the heartbeat waits.
      probe.destroy();
      reclaimStaleOrphan();
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

// Only boot the network/lifecycle side-effects when actually run as `node
// server.js`. Guards against a bare require() (parity tests import this module
// for buildAtomContent) probing the port, binding it, or triggering a port
// hand-off against the live guardian from a test context.
if (require.main === module) {
  tryBindDashboard();
  setImmediate(() => {
    if (!httpServer.listening && !dashboardHeartbeat) {
      dashboardHeartbeat = setInterval(tryBindDashboard, HEARTBEAT_INTERVAL_MS);
      dashboardHeartbeat.unref();
    }
  });

  // Keep MCP alive
  process.stdin.resume();

  // Orphan prevention (root fix): this process is spawned by exactly one Claude
  // Code client over stdio. When that client exits (session / VS Code closes),
  // the OS closes the pipe's write end and our stdin reaches EOF. We exit so the
  // process dies with its owner instead of lingering as an orphan that holds
  // :3848 and serves stale code. This only ever exits THIS process on ITS OWN
  // parent's exit — it never touches another instance, so an active session's
  // MCP is safe (its stdin is still connected to a live parent → no EOF).
  // Complements the /api/relinquish hand-off below, which remains the backstop
  // for abrupt kills (where EOF may not fire) and the new-code-vs-stale-orphan
  // upgrade path.
  let _parentGone = false;
  const exitOnParentGone = (why) => {
    if (_parentGone) return;
    _parentGone = true;
    try { process.stderr.write(`[workflow-guardian] stdin ${why}; parent gone, exiting (orphan prevention).\n`); } catch {}
    try { httpServer.close(); } catch {}
    process.exit(0);
  };
  process.stdin.on("end", () => exitOnParentGone("end"));
  process.stdin.on("close", () => exitOnParentGone("close"));
}

// Test/tooling surface: pure content builders (no side effects). Safe to require
// for parity tests; production boots via `node server.js` (require.main === module)
// and is unaffected. See lib/verify/verify_atom_io_equivalence.py:test_13.
module.exports = { buildAtomContent, renderKnowledgeLines, isBlockKnowledge };

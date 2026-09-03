// http-api.js — dashboard 唯讀 API 端點群（含 http-util helpers: jsonRes/pyCmd/makeJobRunner/execJson/readJsonBody）。
// 私有可變 state（healthCache/worldCommands/worldDev/_ollamaCache/testRunner/healRunner）只透過本檔 handler 存取。
const fs = require("fs");
const path = require("path");
const http = require("http");
const https = require("https");
const { exec } = require("child_process");
const { CLAUDE_DIR, WORKFLOW_DIR, MEMORY_DIR, TOOLS_DIR, loadConfig, loadRegistry, getRegistryMemDirs, PYTHON_EXE } = require("./paths");
const { listAllSessions, readState, writeState } = require("./state");
const { enrichAtomWithAccess } = require("./atom-access");

// ─── v2.1 API Handlers ──────────────────────────────────────────────────────

function jsonRes(res, code, data) {
  res.writeHead(code, { "Content-Type": "application/json" });
  res.end(JSON.stringify(data));
}

// Build a safe python command (Windows path backslashes must be forward-slashed for exec)
function pyCmd(scriptPath, args) {
  return '"' + PYTHON_EXE.replace(/\\/g, "/") + '" "' + scriptPath.replace(/\\/g, "/") + '" ' + args;
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
    // scan registry project dirs
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

// run_verify.py --json 的 schema 與 dashboard 前端契約不同：前者 {total,passed,failed,
// errors,skipped,cases:[{id,outcome,duration_s,message}]}，後者吃 {passed,failed,skipped,
// total,results:[{name,passed,skipped,duration_ms,message}]}。映射在此，前端不動。
// errors（setup/teardown 失敗）併入 failed——對使用者而言同樣是「沒過」。
function mapVerifyToDashboard(v) {
  const cases = Array.isArray(v && v.cases) ? v.cases : [];
  return {
    passed: (v && v.passed) || 0,
    failed: ((v && v.failed) || 0) + ((v && v.errors) || 0),
    skipped: (v && v.skipped) || 0,
    total: (v && v.total) || cases.length,
    results: cases.map((c) => ({
      name: c.id,
      passed: c.outcome === "passed",
      skipped: c.outcome === "skipped",
      duration_ms: Math.round((c.duration_s || 0) * 1000),
      message: c.message || null,
    })),
  };
}

const testRunner = makeJobRunner({ maxConcurrent: 1, ttlMs: 300000 });
function apiTestRunStart(req, res) {
  // V5 統一 verify 入口（hooks/tools/lib/skills 各層 verify/）；舊 tools/test-memory-v21.py
  // 已於 V5 Wave 5 汰除，此處為當時漏改的呼叫點。1400 餘案 JSON 約 300 KB → 放大 maxBuffer。
  const scriptPath = path.join(CLAUDE_DIR, "run_verify.py");
  const r = testRunner.start(() =>
    execJson(pyCmd(scriptPath, "--json"), { timeout: 180000, maxBuffer: 32 * 1024 * 1024 })
      .then(mapVerifyToDashboard)
  );
  if (!r.ok) return jsonRes(res, 409, { error: "test already running" });
  jsonRes(res, 202, { job_id: r.id, status: "running" });
}
function apiTestRunStatus(req, res, jobId) { return testRunner.statusRes(res, jobId); }

// ── World Command Bus：Claude/使用者下指令 → 前端輪詢執行 → 回報；snapshot 供讀取世界狀態 ──
//   ★正名：屬「腦內世界」L2 娛樂層的按需通道（非死路、非常駐）。僅在瀏覽器開著 world.html
//   時才有前端輪詢消費；無人開＝命令留佇列（cap 200）自然過期，不阻斷任何收尾流程、不隨
//   guardian pipeline 常駐。保留：它是 Claude↔世界的有效按需橋，勿刪。
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
//   兩條入口，職責分離：
//     /api/heal/:atom        單一 atom（腦內世界診所：手動拖入=含 L2；auto=1 自走=僅 L1）
//                            ——L2 娛樂外掛的按需觸發，需瀏覽器開著。
//     /api/heal-all          世界無關的背景 L2 sweep（headless 可觸發）：只掃 broken_refs
//                            交 LLM 判斷，不碰 reverse_refs（L1 已由 SessionEnd 的
//                            atom-health-check --fix-refs 機械補齊，別重覆跑）。
//                            預期呼叫者＝/memory health 或（未來·gated）SessionEnd 背景，
//                            非常駐 daemon（不隨 guardian 起 timer 白燒）。
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
      // ★不收 missing_reverse_refs：反向連結（L1）已由 SessionEnd 的 atom-health-check
      //   --fix-refs 機械補齊。此背景 sweep 只做 L2（死連結，需 LLM），避免與 --fix-refs
      //   重覆跑（見上方入口註解）。單一 atom 的 L1 仍走 /api/heal/:atom（診所按需）。
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
    // if root itself is the .claude dir, memory is at root/memory/ directly
    const rootNorm = path.resolve(info.root || "");
    const isClaudeDir = rootNorm.toLowerCase() === path.resolve(CLAUDE_DIR).toLowerCase();
    const memDir = isClaudeDir
      ? path.join(rootNorm, "memory")
      : path.join(rootNorm, ".claude", "memory");
    if (fs.existsSync(memDir) && fs.existsSync(path.join(memDir, "MEMORY.md"))) {
      proj.has_memory = true;
      // 核心 ~/.claude：atom 散在 memory/<範疇>/…、memory/Failures/…、_AIDocs/…，
      // 以 memory/_atom_index.json 計數；index 讀不到才退回數根層平鋪檔。
      const indexEntries = isClaudeDir ? readAtomIndexEntries() : null;
      if (indexEntries) {
        proj.atom_count = indexEntries.length;
        proj.failure_count = indexEntries.filter(e => layerFromRelPath(e && e.path) === "failures").length;
      } else {
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
      }
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

// --- Atom index path helpers（純函式，供 apiAtoms / apiProjects 與驗證腳本共用） ---
// index 的 path 是相對 CLAUDE_DIR 的 posix 路徑，例：
//   memory/decisions.md · memory/Failures/<主題>/x.md · _AIDocs/Failures/x.md · _AIDocs/_atoms/<domain>/x.md

function normalizeRelPath(rel) {
  return String(rel || "").replace(/\\/g, "/").replace(/^\.\//, "");
}

// dashboard 分層：failures（兩處 Failures 樹）/ local（本地範疇 _AIDocs/_atoms）/ global（其餘）
function layerFromRelPath(rel) {
  const r = normalizeRelPath(rel);
  if (r.startsWith("memory/Failures/") || r.startsWith("_AIDocs/Failures/")) return "failures";
  if (r.startsWith("_AIDocs/_atoms/")) return "local";
  return "global";
}

// 範疇段：去掉根層前綴（memory/ 或 _AIDocs/_atoms/）與檔名後剩下的目錄段。
//   memory/x.md → []            memory/a/b/x.md → ["a","b"]
//   _AIDocs/Failures/x.md → ["Failures"]   _AIDocs/_atoms/a/b/x.md → ["a","b"]
function categorySegmentsFromRelPath(rel) {
  const parts = normalizeRelPath(rel).split("/").filter(Boolean);
  parts.pop();  // 檔名
  if (parts[0] === "memory") return parts.slice(1);
  if (parts[0] === "_AIDocs") return parts[1] === "_atoms" ? parts.slice(2) : parts.slice(1);
  return parts;
}

// 注入範疇：本地（僅 ~/.claude 內注入）vs 核心（全專案注入）
function realmFromRelPath(rel) {
  return normalizeRelPath(rel).startsWith("_AIDocs/_atoms/") ? "local" : "core";
}

// 讀 memory/_atom_index.json 的 atoms 陣列；檔缺或 JSON 壞回 null（呼叫端決定回退）
function readAtomIndexEntries() {
  try {
    const raw = fs.readFileSync(path.join(MEMORY_DIR, "_atom_index.json"), "utf-8");
    const idx = JSON.parse(raw);
    return Array.isArray(idx && idx.atoms) ? idx.atoms : null;
  } catch { return null; }
}

// 單一 .md 檔 → dashboard atom 物件（frontmatter、知識條數、行數、last_used 距今、全文、遙測）。
// 讀檔或解析失敗回 null。
function parseAtomFile(filePath, fileName, layerLabel, defaultScope) {
  try {
    const content = fs.readFileSync(filePath, "utf-8");
    // 舊專案層 MEMORY.md 遷移殘留 stub（metadata 行 `- Status: migrated-v2.21`）不算 atom；
    // 錨在行首，正文裡提到這串字的 atom 不受影響
    if (/^-\s+Status:\s*migrated-v2\.21\s*$/m.test(content)) return null;
    const atom = {
      name: fileName.replace(/\.md$/, ""),
      layer: layerLabel,
      scope: defaultScope,
      file: fileName,
    };
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

    // `## 知識` 段內 `- [` 開頭的條目數
    let knowledgeCount = 0;
    let inKnowledge = false;
    for (const line of content.split("\n")) {
      if (/^##\s+知識/.test(line)) { inKnowledge = true; continue; }
      if (/^##\s+/.test(line) && inKnowledge) break;
      if (inKnowledge && /^- \[/.test(line)) knowledgeCount++;
    }
    atom.knowledge_count = knowledgeCount;
    atom.line_count = content.split("\n").length;

    if (atom.last_used) {
      const lu = new Date(atom.last_used);
      if (!isNaN(lu.getTime())) atom.days_since_used = Math.floor((Date.now() - lu.getTime()) / 86400000);
    }

    atom.content = content;  // detail view 用全文
    enrichAtomWithAccess(atom, filePath);  // 戰力/遙測
    return atom;
  } catch { return null; }
}

// 全部 atom 清單：global 層以 memory/_atom_index.json 為真相（含 memory/<範疇>/…、
// memory/Failures/…、_AIDocs/Failures/…、_AIDocs/_atoms/…），專案層照舊掃 registry / projects/。
function apiAtoms(req, res) {
  const atoms = [];
  const seenAtomFiles = new Set();

  // 唯一的檔案解析入口：去重後交 parseAtomFile，回傳 atom 物件（已 push）或 null
  function pushAtomFromFile(filePath, fileName, layerLabel, defaultScope) {
    const fileKey = path.resolve(filePath).toLowerCase();
    if (seenAtomFiles.has(fileKey)) return null;
    seenAtomFiles.add(fileKey);
    const atom = parseAtomFile(filePath, fileName, layerLabel, defaultScope);
    if (atom) atoms.push(atom);
    return atom;
  }

  // global 層：逐筆 index entry；檔不存在跳過
  function scanFromIndex(entries) {
    for (const entry of entries) {
      if (!entry || typeof entry.path !== "string") continue;
      const rel = normalizeRelPath(entry.path);
      const filePath = path.join(CLAUDE_DIR, ...rel.split("/"));
      if (!fs.existsSync(filePath)) continue;
      const atom = pushAtomFromFile(filePath, path.posix.basename(rel), layerFromRelPath(rel), entry.scope || "global");
      if (!atom) continue;
      atom.rel_path = rel;
      atom.category = categorySegmentsFromRelPath(rel);
      atom.realm = realmFromRelPath(rel);
    }
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

  // global 層：index 逐筆；index 缺失或壞掉才退回掃 memory/ 根層平鋪
  const indexEntries = readAtomIndexEntries();
  if (indexEntries) scanFromIndex(indexEntries);
  else scanFlatDir(MEMORY_DIR, "global", "global");

  // V4: global shared/ + roles/{r}/ scan (本專案目前無此目錄，預留給未來)
  scanV4ScopeDirs(MEMORY_DIR, "", "");

  // scan registry project dirs
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

// heal-job 狀態 wrapper：healRunner 私有於本檔，只透過本 handler 對外（守 state 不外露）。
function apiHealJobStatus(req, res, jobId) { return healRunner.statusRes(res, jobId); }

module.exports = {
  jsonRes,
  apiEpisodic, apiHealth, apiTestRunStart, apiTestRunStatus,
  apiWorldCommandPost, apiWorldCommandsGet, apiWorldResultPost, apiWorldSnapshot, apiWorldDev,
  apiHealAll, apiHealReview, apiHealJobStatus, apiHealStart,
  apiVectorStatus, apiOllamaBackendsStatus, apiKnowledgeQueue,
  apiAtoms, apiProjects, apiSkills, apiMcpServers,
  // atom index 路徑純函式（驗證腳本用）
  layerFromRelPath, categorySegmentsFromRelPath, realmFromRelPath,
};

// funnel.js — python subprocess 橋接（conflict-detector / write-gate / atom_io_cli / access）。
const fs = require("fs");
const path = require("path");
const http = require("http");
const { TOOLS_DIR, CLAUDE_DIR, PYTHON_EXE } = require("./paths");
const { crashLog } = require("./log");

/** Run conflict-detector --mode=write-check.
 *  Returns Promise<{verdict, matches, detector_model, skipped, skip_reason, scope}>.
 *  Fail-open: on script error resolves to verdict=ok+skipped=true (do not block writes
 *  when detector infra is down). Longer timeout than write-gate (LLM is slower). */
function execConflictDetector(content, scope, projectCwd, subdir) {
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
    // 分區感知：incoming 落 projects/<X> 時其他分區相似 atom warn 不 block
    if (subdir) {
      args.push("--subdir", subdir);
    }
    const cp = require("child_process").spawn(PYTHON_EXE, [scriptPath, ...args], {
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

/** TSV append to {baseDir}/_merge_history.log. SPEC §10.
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

/** render CONTRADICT report (non-atom) for _pending_review/{slug}.conflict.md. */
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

/** Run write-gate Python script for dedup check. Returns Promise<{action, reason}>.
 *  Payload goes over stdin (script's no-args pipe mode) — no shell, no escaping
 *  surface. Fail-open on any infra error, but crashLog so the degradation is
 *  visible (可觀測性鐵律). */
function execWriteGate(content, classification, layers) {
  return new Promise((resolve) => {
    const scriptPath = path.join(TOOLS_DIR, "memory-write-gate.py");
    if (!fs.existsSync(scriptPath)) {
      return resolve({ action: "add", reason: "write-gate script not found, allowing" });
    }
    let cp;
    try {
      cp = require("child_process").spawn(PYTHON_EXE, [scriptPath], {
        windowsHide: true,
        env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      });
    } catch (e) {
      crashLog("write-gate unavailable (spawn failed)", e);
      return resolve({ action: "add", reason: "write-gate unavailable, allowing" });
    }
    let out = "", err = "", timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      try { cp.kill(); } catch {}
    }, 15000);
    cp.stdout.on("data", (d) => { out += d.toString("utf-8"); });
    cp.stderr.on("data", (d) => { err += d.toString("utf-8"); });
    cp.on("close", () => {
      clearTimeout(timer);
      if (timedOut || !out) {
        crashLog("write-gate unavailable",
          timedOut ? "timeout (15s), killed" : `no output; stderr=${err.slice(0, 200)}`);
        return resolve({ action: "add", reason: "write-gate unavailable, allowing" });
      }
      try {
        resolve(JSON.parse(out.trim()));
      } catch (e) {
        crashLog("write-gate parse error", `${e.message} stderr=${err.slice(0, 200)}`);
        resolve({ action: "add", reason: "write-gate parse error, allowing" });
      }
    });
    cp.on("error", (e) => {
      clearTimeout(timer);
      crashLog("write-gate unavailable (spawn error)", e);
      resolve({ action: "add", reason: "write-gate unavailable, allowing" });
    });
    try {
      // layers：去重只比這幾層（global + 當前專案自己的層）；不傳 = 全庫比對
      cp.stdin.write(JSON.stringify({ content, classification, layers: layers || null }));
      cp.stdin.end();
    } catch {} // close handler resolves either way
  });
}

/** Upsert atom entry to _atom_index.json (SoT) via funnel.
 *  Auto-regenerates _ATOM_INDEX.md mirror via lib/atom_index_json.upsert_atom. */
async function appendToIndex(memDir, atomName, relPath, triggers) {
  const r = await funnelWriteIndex(memDir, atomName, relPath, triggers, "mcp");
  if (!r.ok) crashLog("appendToIndex funnel (json)", r.error);
}

/** Trigger vector service incremental re-index (fire and forget, but surfaced:
 *  service down / non-2xx goes to crashLog — 可觀測性鐵律, no silent swallow).
 *  Route SYNC: tools/memory-vector-service/service.py POST /index/incremental
 *  (no body — handler just kicks a background incremental build). */
function triggerVectorReindex() {
  try {
    const url = "http://127.0.0.1:3849/index/incremental";
    const req = http.request(url, { method: "POST", timeout: 3000 }, (res) => {
      if (res.statusCode < 200 || res.statusCode >= 300) {
        crashLog("vector reindex", `HTTP ${res.statusCode} from POST /index/incremental`);
      }
      res.resume();
    });
    req.on("timeout", () => { try { req.destroy(new Error("timeout (3s)")); } catch {} });
    req.on("error", (e) => crashLog("vector reindex unavailable", e));
    req.end();
  } catch (e) {
    crashLog("vector reindex unavailable", e);
  }
}

/** Regenerate the atom catalog from _atom_index.json (fire and forget).
 *  No arg → global memory/MEMORY.md (+ _local_catalog.md + per-level _INDEX.md).
 *  memoryDir → project layer (<proj>/.claude/memory): sync-memory-index --memory-dir upserts the
 *  `<!-- atom-catalog -->` block in that project's MEMORY.md (shared/<Lv1>/ rows); it never writes
 *  _local_catalog.md / _INDEX.md there. Caller: atom-tools after a shared create/replace. */
function syncMemoryIndex(memoryDir) {
  try {
    const script = path.join(TOOLS_DIR, "sync-memory-index.py");
    if (!fs.existsSync(script)) return;
    const argv = [script, "--write"];
    if (memoryDir) argv.push("--memory-dir", String(memoryDir));
    // 背景重產但不靜默：收 stderr、非 0 退出落 crashLog（可觀測性鐵律——橋接檔曾
    // 13/13 全壞 7 週無人知，就是這條 fire-and-forget 把訊號吞掉）。
    const cp = require("child_process").spawn(PYTHON_EXE, argv, {
      windowsHide: true, detached: true, stdio: ["ignore", "ignore", "pipe"],
    });
    let err = "";
    if (cp.stderr) cp.stderr.on("data", (d) => { if (err.length < 2000) err += String(d); });
    cp.on("error", (e) => crashLog("sync-memory-index spawn error", e));
    cp.on("exit", (code) => {
      if (code !== 0) crashLog("sync-memory-index failed", `exit=${code} stderr=${err.slice(0, 400)}`);
      else if (err.includes("[native-memory-bridge]")) crashLog("native-memory-bridge warning", err.slice(0, 400));
    });
    cp.unref();
  } catch (e) { crashLog("sync-memory-index unavailable", e); }
}
// ─── Atom Funnel Bridge (spawn lib/atom_io_cli) ─────────────────────

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
        PYTHON_EXE, ["-m", "lib.atom_io_cli"],
        {
          cwd: CLAUDE_DIR,
          windowsHide: true,
          env: { ...process.env, PYTHONIOENCODING: "utf-8" },
        }
      );
    } catch (e) {
      return resolve({ ok: false, error: `spawn failed: ${e.message}` });
    }
    let out = "", err = "", timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      try { cp.kill(); } catch {}
    }, 30000);
    cp.stdout.on("data", (d) => { out += d.toString("utf-8"); });
    cp.stderr.on("data", (d) => { err += d.toString("utf-8"); });
    cp.on("close", () => {
      clearTimeout(timer);
      if (timedOut) {
        return resolve({ ok: false, error: `atom_io_cli timeout (30s), killed (action=${action})` });
      }
      try {
        resolve(JSON.parse(out));
      } catch (e) {
        resolve({ ok: false, error: `cli parse fail: ${e.message} stderr=${err.slice(0, 200)}` });
      }
    });
    cp.on("error", (e) => {
      clearTimeout(timer);
      resolve({ ok: false, error: `spawn error: ${e.message}` });
    });
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

/** Single-atom upsert via lib.atom_io.write_index → _atom_index.json. */
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
module.exports = {
  execConflictDetector, appendMergeHistory, buildConflictReport, execWriteGate,
  appendToIndex, triggerVectorReindex, syncMemoryIndex, spawnAtomCli,
  funnelWriteRaw,
};

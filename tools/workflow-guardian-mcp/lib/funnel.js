// funnel.js — python subprocess 橋接（conflict-detector / write-gate / atom_io_cli / access）。
const fs = require("fs");
const path = require("path");
const http = require("http");
const { exec } = require("child_process");
const { TOOLS_DIR, CLAUDE_DIR } = require("./paths");
const { crashLog } = require("./log");

/** Run conflict-detector --mode=write-check.
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

/** Upsert atom entry to _atom_index.json (SoT) via funnel.
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

module.exports = {
  execConflictDetector, appendMergeHistory, buildConflictReport, execWriteGate,
  appendToIndex, triggerVectorReindex, syncMemoryIndex, spawnAtomCli,
  funnelWriteRaw, flatLegacyFallback,
};

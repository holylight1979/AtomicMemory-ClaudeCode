// second-opinion.js：MCP tools `second_opinion_start` / `second_opinion_result` 的 Node 面。
//
// 做什麼：start＝同步 spawn `tools/second-opinion/run.py prepare`（20 s 內回 job_id／hash／status），
// 過閘（status=started）才 detached 起 `run.py execute` 跑 codex；result＝讀 job 目錄的 status.json＋reply.md。
// 不碰 state、不寫 live 檔（job 目錄由 py 寫）；每個 spawn 都有 setTimeout＋kill＋clearTimeout。
// 立場：independent 模式帶 draft 直接拒（不 spawn）；prepare blocked／failed 都回 isError，絕不把「沒起來」報成功。
// sendToolResult 來自 mcp.js（mcp.handleToolCall lazy-require 本檔，handler 內 lazy-require 即可）。

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const { WORKFLOW_DIR, TOOLS_DIR, PYTHON_EXE } = require("./paths");
const { crashLog } = require("./log");

const JOB_ROOT = path.join(WORKFLOW_DIR, "second-opinion");
const RUN_PY = path.join(TOOLS_DIR, "second-opinion", "run.py");
const KINDS = ["diagnose", "evaluate", "stage-review"];
const MODES = ["independent", "review"];
const JOB_ID_RE = /^\d{8}-\d{6}-[0-9a-z]{8}-(diagnose|evaluate|stage-review)$/;
const PREPARE_TIMEOUT_MS = 20000;
const RESULT_MAX_BYTES = 20 * 1024;
const STALE_GRACE_S = 90; // running 超過 timeout_s + 這個秒數仍沒結果 → 視為 execute 子程序死了

/** 參數守門；回錯誤字串（空＝合格）。獨立模式帶 draft 在這裡就拒，不 spawn。 */
function validateStart(a) {
  if (!a || typeof a !== "object") return "arguments 必須是物件";
  if (!KINDS.includes(a.kind)) return `kind 只收 ${KINDS.join("|")}（got ${a.kind}）`;
  if (!String(a.part || "").trim()) return "part 必填（部位名）";
  if (!String(a.cwd || "").trim()) return "cwd 必填（專案內路徑）";
  if (!MODES.includes(a.mode)) return `mode 只收 ${MODES.join("|")}（got ${a.mode}）`;
  if (!String(a.question || "").trim()) return "question 必填";
  const hasDraft = !!String(a.draft || "").trim();
  if (a.mode === "independent" && hasDraft) return "independent 模式不收 draft：獨立作答不能看到己方答案（要評草稿請用 mode=review）";
  if (a.mode === "review" && !hasDraft) return "review 模式必須帶 draft（沒有草稿就沒有東西可逐段評）";
  if (a.sealed !== undefined && !(Array.isArray(a.sealed) && a.sealed.every((s) => typeof s === "string"))) {
    return "sealed 必須是字串陣列";
  }
  return "";
}

/** 同步 spawn `run.py prepare`（request 走 stdin）；20 s 逾時 kill。回 {out, err, code, timedOut, spawnError}。 */
function spawnPrepare(requestJson) {
  return new Promise((resolve) => {
    let cp;
    try {
      cp = spawn(PYTHON_EXE, ["-X", "utf8", RUN_PY, "prepare", "--request", "-"], {
        cwd: path.dirname(RUN_PY), windowsHide: true,
        env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      });
    } catch (e) {
      return resolve({ out: "", err: "", code: null, timedOut: false, spawnError: e.message });
    }
    let out = "", err = "", timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      try { cp.kill(); } catch {}
    }, PREPARE_TIMEOUT_MS);
    cp.stdout.on("data", (d) => { out += d.toString("utf-8"); });
    cp.stderr.on("data", (d) => { if (err.length < 4000) err += d.toString("utf-8"); });
    cp.on("close", (code) => {
      clearTimeout(timer);
      resolve({ out, err, code, timedOut, spawnError: "" });
    });
    cp.on("error", (e) => {
      clearTimeout(timer);
      resolve({ out, err, code: null, timedOut, spawnError: e.message });
    });
    try {
      cp.stdin.write(requestJson);
      cp.stdin.end();
    } catch {} // close handler resolves either way
  });
}

/** 分離子程序跑 execute（codex 跑 60～300 s，MCP 不等）；輸出落 job_dir/execute.log；失敗 crashLog。
 *  刻意沒有 setTimeout／kill（detached，MCP 回應不等它）：上限在 py 側三處（run_guard 60 s、探針 wait(timeout)+kill、
 *  正式 codex wait(timeout)+kill）加 js readResult 逾 timeout_s+90 s 回 failed；hardening verify 的 SPAWN_TIMEOUT_EXEMPT 登記同句。
 *  execute.log 是子程序 stdout/stderr 的導向檔（由 MCP 建立），不是 state、不是 job 結果檔；job 結果檔全由 py 寫。 */
function spawnExecute(jobDir) {
  let logFd = null;
  try { logFd = fs.openSync(path.join(jobDir, "execute.log"), "a"); } catch {}
  const cp = spawn(PYTHON_EXE, ["-X", "utf8", RUN_PY, "execute", "--job", jobDir], {
    cwd: path.dirname(RUN_PY), windowsHide: true, detached: true,
    stdio: ["ignore", logFd === null ? "ignore" : logFd, logFd === null ? "ignore" : logFd],
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  });
  cp.on("error", (e) => crashLog("second_opinion execute spawn error", e));
  cp.unref();
  if (logFd !== null) { try { fs.closeSync(logFd); } catch {} }
}

/** prepare 的 stdout（`key: value` 行）→ 物件；notes 聚成陣列。 */
function parsePrepare(out) {
  const r = { job_id: "", hash: "", status: "", reason: "", notes: [], job_dir: "" };
  for (const line of String(out || "").split("\n")) {
    const m = /^([a-z_]+):\s?(.*)$/.exec(line.trim());
    if (!m) continue;
    if (m[1] === "note") r.notes.push(m[2]);
    else if (m[1] in r) r[m[1]] = m[2];
  }
  return r;
}

async function toolSecondOpinionStart(id, args) {
  const { sendToolResult } = require("./mcp");
  const bad = validateStart(args);
  if (bad) return sendToolResult(id, `second_opinion_start 拒收：${bad}`, true);
  const request = {
    kind: args.kind, part: String(args.part).trim(), cwd: String(args.cwd).trim(), mode: args.mode,
    question: String(args.question).trim(),
    ...(args.mode === "review" && { draft: String(args.draft) }),
    ...(Array.isArray(args.sealed) && { sealed: args.sealed }),
    ...(args.session_id && { session_id: String(args.session_id) }),
  };
  const res = await spawnPrepare(JSON.stringify(request));
  if (res.spawnError) return sendToolResult(id, `job_id: -\nhash: -\nstatus: failed\nreason: prepare spawn 失敗：${res.spawnError}`, true);
  if (res.timedOut) return sendToolResult(id, `job_id: -\nhash: -\nstatus: failed\nreason: prepare 逾時（${PREPARE_TIMEOUT_MS / 1000}s）已 kill`, true);
  const p = parsePrepare(res.out);
  if (!p.status) {
    return sendToolResult(id, `job_id: -\nhash: -\nstatus: failed\nreason: prepare 無輸出（exit=${res.code}）stderr=${res.err.slice(0, 600)}`, true);
  }
  const lines = [`job_id: ${p.job_id}`, `hash: ${p.hash}`, `status: ${p.status}`];
  if (p.reason) lines.push(`reason: ${p.reason}`);
  for (const n of p.notes) lines.push(`note: ${n}`);
  if (p.status !== "started") return sendToolResult(id, lines.join("\n"), true);
  try {
    spawnExecute(p.job_dir);
  } catch (e) {
    crashLog("second_opinion execute spawn", e);
    return sendToolResult(id, lines.concat([`reason: execute 起不來：${e.message}`]).join("\n").replace("status: started", "status: failed"), true);
  }
  lines.push(`job_dir: ${p.job_dir}`, "下一步：codex 跑完（通常 60～300 s）後呼叫 second_opinion_result({job_id})。");
  return sendToolResult(id, lines.join("\n"));
}

function readJson(p) {
  try { return JSON.parse(fs.readFileSync(p, "utf-8")); } catch { return null; }
}

/** job_id → {text, isError}。running 超過 timeout_s＋寬限仍無結果 → 視為 failed（子程序死了不能永遠 running）。 */
function readResult(jobId) {
  if (!JOB_ID_RE.test(String(jobId || ""))) return { text: `second_opinion_result 拒收：job_id 格式不對（${jobId}）`, isError: true };
  const jobDir = path.join(JOB_ROOT, jobId);
  const st = readJson(path.join(jobDir, "status.json"));
  if (!st) return { text: `status: failed\nreason: 找不到 job（${jobDir}）`, isError: true };
  let status = st.status === "started" ? "running" : String(st.status || "failed");
  const head = [`job_id: ${jobId}`, `hash: ${st.hash || "-"}`, `model: ${st.model || "-"}`, `mode: ${st.mode || "-"}`];
  if (status === "running") {
    const ageS = (Date.now() - Date.parse(String(st.updated_at || "").replace(" ", "T"))) / 1000;
    const limit = Number(st.timeout_s || 300) + STALE_GRACE_S;
    if (Number.isFinite(ageS) && ageS > limit) {
      status = "failed";
      head.push(`reason: 已 ${Math.round(ageS)} s 無更新（上限 ${limit} s），execute 子程序疑似中斷；看 ${path.join(jobDir, "execute.log")}`);
    } else {
      head.push(`stage: ${st.stage || "-"}`);
    }
  }
  if (status === "failed" || status === "blocked") {
    if (st.reason) head.push(`reason: ${st.reason}`);
    return { text: [`status: ${status}`].concat(head).join("\n"), isError: true };
  }
  if (status !== "done") return { text: [`status: ${status}`].concat(head).join("\n"), isError: false };
  const replyPath = path.join(jobDir, "reply.md");
  let reply = "";
  try { reply = fs.readFileSync(replyPath, "utf-8"); } catch (e) {
    return { text: [`status: failed`].concat(head, [`reason: done 但讀不到 reply.md：${e.message}`]).join("\n"), isError: true };
  }
  if (st.guard_note) head.push(`guard_note: ${st.guard_note}`);
  if (Buffer.byteLength(reply, "utf-8") > RESULT_MAX_BYTES) {
    reply = reply.slice(0, RESULT_MAX_BYTES) + `\n\n…（已截斷，完整回覆：${replyPath}）\n`;
  }
  return { text: [`status: done`].concat(head, ["", reply]).join("\n"), isError: false };
}

async function toolSecondOpinionResult(id, args) {
  const { sendToolResult } = require("./mcp");
  const jobId = args && args.job_id;
  if (!String(jobId || "").trim()) return sendToolResult(id, "second_opinion_result 拒收：job_id 必填", true);
  const r = readResult(String(jobId).trim());
  return sendToolResult(id, r.text, r.isError);
}

module.exports = {
  toolSecondOpinionStart, toolSecondOpinionResult, validateStart, parsePrepare, readResult,
  JOB_ROOT, RUN_PY, KINDS, MODES, JOB_ID_RE, PREPARE_TIMEOUT_MS, RESULT_MAX_BYTES,
};

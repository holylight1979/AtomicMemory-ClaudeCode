// smoke_mcp_stdio.js — 以 stdio JSON-RPC 真起 server.js，驗 MCP tool 面：
//   tools/list 含 7 個 tool；knowledge_harvest_report chip（items=[] / 含 skip / 缺 reason 拒收）；
//   atom_write dry_run=true 帶 supersedes 不報 schema 錯；atom_retire 缺 reason 拒。
// 怎麼跑：node tools/workflow-guardian-mcp/verify/smoke_mcp_stdio.js
// 隔離埠 WG_DASHBOARD_PORT=38499（不撞 3848 的 live guardian）；dry_run 不落檔、不動索引。
const path = require("path");
const { spawn } = require("child_process");

const SERVER = path.join(__dirname, "..", "server.js");
const PORT = process.env.WG_SMOKE_PORT || "38499";
const EXPECTED_TOOLS = [
  "atom_write", "atom_promote", "atom_move", "atom_edit_meta",
  "anti_evasion_report", "knowledge_harvest_report", "atom_retire",
];

const cp = spawn(process.execPath, [SERVER], {
  cwd: path.dirname(SERVER),
  windowsHide: true,
  env: { ...process.env, WG_DASHBOARD_PORT: PORT, PYTHONIOENCODING: "utf-8" },
  stdio: ["pipe", "pipe", "pipe"],
});
let stderr = "";
cp.stderr.on("data", (d) => { stderr += d.toString(); });

const pending = new Map();
let buf = "";
cp.stdout.on("data", (d) => {
  buf += d.toString("utf-8");
  let i;
  while ((i = buf.indexOf("\n")) !== -1) {
    const line = buf.slice(0, i).trim();
    buf = buf.slice(i + 1);
    if (!line) continue;
    let msg;
    try { msg = JSON.parse(line); } catch { continue; }
    const p = pending.get(msg.id);
    if (p) { pending.delete(msg.id); p(msg); }
  }
});

let nextId = 1;
function rpc(method, params, timeoutMs = 60000) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => { pending.delete(id); reject(new Error(`timeout ${method} id=${id}`)); }, timeoutMs);
    pending.set(id, (m) => { clearTimeout(t); resolve(m); });
    cp.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
  });
}
const callTool = (name, args) => rpc("tools/call", { name, arguments: args });
const textOf = (m) => (m.result && m.result.content && m.result.content[0] && m.result.content[0].text) || "";

const failures = [];
function check(cond, label, detail) {
  if (cond) { console.log(`  ok   ${label}`); return; }
  failures.push(label);
  console.log(`  FAIL ${label}${detail ? "\n       " + String(detail).slice(0, 600) : ""}`);
}

(async () => {
  const init = await rpc("initialize", { protocolVersion: "2025-11-25", capabilities: {}, clientInfo: { name: "smoke", version: "0" } });
  check(init.result && init.result.serverInfo, "initialize");

  // 1. tools/list
  const list = await rpc("tools/list", {});
  const names = (list.result.tools || []).map((t) => t.name);
  check(names.length === 7, `tools/list has 7 tools (got ${names.length})`, names.join(","));
  for (const n of EXPECTED_TOOLS) check(names.includes(n), `tools/list includes ${n}`);
  const aw = (list.result.tools || []).find((t) => t.name === "atom_write");
  check(aw && aw.inputSchema.properties.supersedes && aw.inputSchema.properties.supersedes.type === "array",
        "atom_write schema has supersedes:array");
  const ar = (list.result.tools || []).find((t) => t.name === "atom_retire");
  check(ar && ar.inputSchema.required.includes("reason"), "atom_retire schema requires reason");

  // 2. knowledge_harvest_report
  const h0 = await callTool("knowledge_harvest_report", { items: [] });
  check(textOf(h0) === "[Harvest] 本場無新知識" && !h0.result.isError, "harvest items=[] → 本場無新知識", textOf(h0));

  const h1 = await callTool("knowledge_harvest_report", { items: [
    { source: "decision", summary: "x", action: "created", atom: "a", path: "C:/x/a.md", scope: "local" },
    { source: "mechanism", summary: "y", action: "appended", atom: "b", path: "C:/x/b.md" },
    { source: "atom_retire", summary: "z", action: "retired", atom: "c", path: "C:/x/c.md" },
    { source: "external_fact", summary: "w", action: "skip", reason: "一次性事實" },
  ] });
  check(textOf(h1) === "[Harvest] 2 寫入／1 退役／1 不寫" && !h1.result.isError, "harvest chip counts", textOf(h1));

  const h2 = await callTool("knowledge_harvest_report", { items: [
    { source: "correction", summary: "no reason", action: "skip" },
    { source: "decision", summary: "no path", action: "created", atom: "a" },
  ] });
  check(h2.result.isError === true && /reason/.test(textOf(h2)) && /path/.test(textOf(h2)),
        "harvest rejects skip w/o reason + created w/o path", textOf(h2));

  // 3. atom_write dry_run 帶 supersedes：不得被 schema/參數層拒（py build 若尚未支援 supersedes
  //    會回 bad params，那是 py 側契約，不是 js schema 錯）。
  const w = await callTool("atom_write", {
    title: "smoke-supersedes-dry-run-不落檔", scope: "global", realm: "local", domain: "MemDev",
    confidence: "[臨]", triggers: ["smoke"], knowledge: ["[臨] smoke only"], mode: "create",
    supersedes: ["some-old-atom"], dry_run: true, skip_gate: true,
  });
  const wt = textOf(w);
  check(!/Missing required|supersedes must be|Unknown tool|cannot supersede/.test(wt),
        "atom_write dry_run with supersedes passes js schema layer", wt);
  console.log("       atom_write dry_run →", wt.split("\n")[0].slice(0, 160));

  const wSelf = await callTool("atom_write", {
    title: "self-ref-atom", scope: "global", realm: "local", domain: "MemDev",
    confidence: "[臨]", triggers: ["smoke"], knowledge: ["[臨] x"], mode: "create",
    supersedes: ["self-ref-atom"], dry_run: true, skip_gate: true,
  });
  check(wSelf.result.isError === true && /cannot supersede itself/.test(textOf(wSelf)),
        "atom_write rejects self-supersede", textOf(wSelf));

  // 4. atom_retire 缺 reason → 拒（不 spawn py）
  const r0 = await callTool("atom_retire", { atom_name: "nope", scope: "global" });
  check(r0.result.isError === true && /reason is required/.test(textOf(r0)), "atom_retire requires reason", textOf(r0));

  cp.stdin.end();
  await new Promise((res) => { cp.on("exit", res); setTimeout(() => { try { cp.kill(); } catch {} res(); }, 5000); });
  if (failures.length) {
    console.log(`\nSMOKE FAILED (${failures.length}): ${failures.join(" | ")}`);
    console.log("[server stderr tail]\n" + stderr.slice(-1500));
    process.exit(1);
  }
  console.log("\nSMOKE OK");
  process.exit(0);
})().catch((e) => {
  console.log("SMOKE ERROR:", e.message);
  console.log("[server stderr tail]\n" + stderr.slice(-1500));
  try { cp.kill(); } catch {}
  process.exit(1);
});

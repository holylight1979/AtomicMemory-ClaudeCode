// smoke_mcp_stdio.js — 以 stdio JSON-RPC 真起 server.js，驗 MCP tool 面：
//   tools/list 含 9 個 tool；atom_source 缺 atom 拒（不 spawn py）；
//   memory_search 一次真查（回表格標頭或 schema_version）；knowledge_harvest_report chip（items=[] / 含 skip / 缺 reason 拒收）；
//   atom_write dry_run=true 帶 supersedes 不報 schema 錯；atom_write schema 有 dedupe{verdict,of,why}（去重宣告；路由見 verify_atom_write_dedupe.js）；atom_retire 缺 reason 拒；
//   atom_write scope=org dry_run：這台已接上公司層 → Path 落 <org_root>/.claude/memory/shared/；未接上 → 明確拒絕。
// 怎麼跑：node tools/workflow-guardian-mcp/verify/smoke_mcp_stdio.js（尾行 MCP_SMOKE_CHECK PASS|FAIL）
// 隔離埠 WG_DASHBOARD_PORT=38499（不撞 3848 的 live guardian）；dry_run 不落檔、不動索引。
// 隔離資料根：WG_CLAUDE_DIR 指 os.tmpdir() 下的暫存根（require 任何 lib 之前設；只放範疇閘要的 taxonomy.json、realm-lexicon.json），
//   server 子行程繼承；守門總開關明帶 WG_V6=1（這裡驗的是開著的 tool 面）。跑完對帳：server 的啟動紀錄 <pid>.json
//   落在暫存根的 workflow/mcp-boot，原本的資料根沒有這個檔。
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const CODE = path.resolve(__dirname, "..", "..", "..");
const REAL_ROOT = process.env.WG_CLAUDE_DIR || path.join(os.homedir(), ".claude");   // 沒隔離時 server 會寫的那個資料根
const ROOT = fs.mkdtempSync(path.join(os.tmpdir(), "wg-smoke-"));
process.env.WG_CLAUDE_DIR = ROOT;
process.env.WG_V6 = "1";
fs.mkdirSync(path.join(ROOT, "memory", "_meta"), { recursive: true });
for (const f of ["taxonomy.json", "realm-lexicon.json"]) {
  fs.copyFileSync(path.join(CODE, "memory", "_meta", f), path.join(ROOT, "memory", "_meta", f));
}

const SERVER = path.join(__dirname, "..", "server.js");
const PORT = process.env.WG_SMOKE_PORT || "38499";
const EXPECTED_TOOLS = [
  "atom_write", "atom_promote", "atom_move", "atom_edit_meta",
  "anti_evasion_report", "knowledge_harvest_report", "atom_retire", "memory_search", "atom_source",
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
  check(names.length === 9, `tools/list has 9 tools (got ${names.length})`, names.join(","));
  for (const n of EXPECTED_TOOLS) check(names.includes(n), `tools/list includes ${n}`);
  const aw = (list.result.tools || []).find((t) => t.name === "atom_write");
  check(aw && aw.inputSchema.properties.supersedes && aw.inputSchema.properties.supersedes.type === "array",
        "atom_write schema has supersedes:array");
  const dd = aw && aw.inputSchema.properties.dedupe;
  check(dd && dd.type === "object" && ["same", "supersedes", "different"].every((v) => dd.properties.verdict.enum.includes(v))
        && dd.properties.of && dd.properties.why, "atom_write schema has dedupe{verdict,of,why}");
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

  // 2b. harvest route 欄：part_doc 無 part 拒；帶 route 的 chip 有 route 計數
  const h3 = await callTool("knowledge_harvest_report", { items: [
    { source: "decision", summary: "x", action: "skip", reason: "r", route: "part_doc" },
  ] });
  check(h3.result.isError === true && /part/.test(textOf(h3)), "harvest rejects route=part_doc without part", textOf(h3));
  const h4 = await callTool("knowledge_harvest_report", { items: [
    { source: "decision", summary: "x", action: "skip", reason: "r", route: "part_doc", part: "lib" },
    { source: "mechanism", summary: "y", action: "skip", reason: "r", route: "global" },
  ] });
  check(/route: part_doc 1, global 1/.test(textOf(h4)) && !h4.result.isError, "harvest chip counts routes", textOf(h4));

  // 3b. atom_write dry_run 的閘回分型（kind= 來自 py；skip_gate 只跳 dedup/quality）
  const wk = await callTool("atom_write", {
    title: "smoke-kind-plain-不落檔", scope: "global", realm: "local", domain: "MemDev",
    confidence: "[臨]", triggers: ["smoke"], knowledge: ["[臨] smoke only"], mode: "create",
    dry_run: true, skip_gate: true,
  });
  check(/\[write-gate\] kind=plain bytes=\d+\/\d+/.test(textOf(wk)), "atom_write dry_run echoes gate kind/bytes/limit", textOf(wk));

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

  // 4. memory_search 真查一次（唯讀；cwd=~/.claude；table 預設回表格標頭，json 回 schema_version）
  const ms = await callTool("memory_search", { query: "atom_write 初次寫", cwd: path.resolve(__dirname, "..", "..", ".."), top_k: 2 });
  check(!ms.result.isError && /name \| scope \| source \| score/.test(textOf(ms)), "memory_search table has header", textOf(ms));
  const msj = await callTool("memory_search", { query: "atom_write 初次寫", cwd: path.resolve(__dirname, "..", "..", ".."), top_k: 2, format: "json" });
  check(!msj.result.isError && /"schema_version":\s*1/.test(textOf(msj)), "memory_search json has schema_version", textOf(msj));
  const ms0 = await callTool("memory_search", { query: "  " });
  check(ms0.result.isError === true && /query is required/.test(textOf(ms0)), "memory_search rejects empty query", textOf(ms0));

  // 5. atom_retire 缺 reason → 拒（不 spawn py）
  const r0 = await callTool("atom_retire", { atom_name: "nope", scope: "global" });
  check(r0.result.isError === true && /reason is required/.test(textOf(r0)), "atom_retire requires reason", textOf(r0));

  // 5b. atom_source 缺 atom → 拒（不 spawn py）；schema 有 quote
  const s0 = await callTool("atom_source", { atom: "  " });
  check(s0.result.isError === true && /atom is required/.test(textOf(s0)), "atom_source requires atom", textOf(s0));
  check(aw && aw.inputSchema.properties.quote && aw.inputSchema.properties.quote.type === "string",
        "atom_write schema has quote:string");

  // 6. scope=org 語法糖（js 只改寫成 shared + project_cwd=org 根；落點仍由 py locate 裁決）
  const norm = (x) => String(x).replace(/[\\/]+/g, "/").toLowerCase();
  const orgRoot = require("../lib/realm").orgMemoryRoot();
  const wo = await callTool("atom_write", {
    title: "smoke-org-dry-run-不落檔", scope: "org", domain: "工具",
    confidence: "[臨]", triggers: ["smoke"], knowledge: ["[臨] smoke only"], mode: "create",
    dry_run: true, skip_gate: true,
  });
  const wot = textOf(wo);
  if (orgRoot) {
    const want = norm(path.join(orgRoot, ".claude", "memory", "shared")) + "/";
    check(!wo.result.isError && /^DRY-RUN/.test(wot) && norm(wot).includes("path: " + want),
          `atom_write scope=org dry_run lands under ${want}`, wot);
  } else {
    check(wo.result.isError === true && /org_memory/.test(wot),
          "atom_write scope=org refused while this machine has not joined org_memory", wot);
  }
  console.log("       atom_write scope=org →", wot.split("\n")[0].slice(0, 160));

  // 7. 隔離對帳（server 還活著時看：啟動紀錄在 server 結束時自刪）：只落暫存根，原本的資料根沒有這次 server 的 <pid>.json
  const boot = (root) => path.join(root, "workflow", "mcp-boot", `${cp.pid}.json`);
  check(fs.existsSync(boot(ROOT)), `boot record in temp data root (${boot(ROOT)})`);
  check(!fs.existsSync(boot(REAL_ROOT)), `no boot record in real data root (${boot(REAL_ROOT)})`);

  cp.stdin.end();
  await new Promise((res) => { cp.on("exit", res); setTimeout(() => { try { cp.kill(); } catch {} res(); }, 5000); });
  try { fs.rmSync(ROOT, { recursive: true, force: true }); } catch (e) { console.log(`  warn cleanup failed: ${ROOT} (${e.message})`); }

  if (failures.length) {
    console.log(`\nSMOKE FAILED (${failures.length}): ${failures.join(" | ")}`);
    console.log("[server stderr tail]\n" + stderr.slice(-1500));
    console.log("MCP_SMOKE_CHECK FAIL");
    process.exit(1);
  }
  console.log("\nSMOKE OK");
  console.log("MCP_SMOKE_CHECK PASS");             // 哨兵尾行：收據認它（驗證範圍項目、(d) 由哪個案例驗）
  process.exit(0);
})().catch((e) => {
  console.log("SMOKE ERROR:", e.message);
  console.log("[server stderr tail]\n" + stderr.slice(-1500));
  console.log("MCP_SMOKE_CHECK FAIL");
  try { cp.kill(); } catch {}
  process.exit(1);
});

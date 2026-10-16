// smoke_mcp_stdio.js — 以 stdio JSON-RPC 真起 server.js，驗 MCP tool 面：
//   tools/list 含 13 個 tool；need_goal 參數拒收與 chip（不寫檔）；atom_source 缺 atom 拒（不 spawn py）；
//   second_opinion_start independent 帶 draft 拒、second_opinion_result 缺 job_id 拒、project_smells 缺 part 拒（都不 spawn py）；memory_search 一次真查（回表格標頭或 schema_version）；knowledge_harvest_report chip（items=[] / 含 skip / 缺 reason 拒收）；
//   atom_write dry_run=true 帶 supersedes 不報 schema 錯；atom_retire 缺 reason 拒；
//   atom_write scope=org dry_run：這台已接上公司層 → Path 落 <org_root>/.claude/memory/shared/；未接上 → 明確拒絕。
// 怎麼跑：node tools/workflow-guardian-mcp/verify/smoke_mcp_stdio.js（尾行 MCP_SMOKE_CHECK PASS|FAIL）
// 隔離埠 WG_DASHBOARD_PORT=38499（不撞 3848 的 live guardian）；dry_run 不落檔、不動索引。
const path = require("path");
const { spawn } = require("child_process");

const SERVER = path.join(__dirname, "..", "server.js");
const PORT = process.env.WG_SMOKE_PORT || "38499";
const EXPECTED_TOOLS = [
  "atom_write", "atom_promote", "atom_move", "atom_edit_meta",
  "anti_evasion_report", "knowledge_harvest_report", "atom_retire", "memory_search", "atom_source",
  "second_opinion_start", "second_opinion_result", "project_smells", "need_goal",
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
  check(names.length === 13, `tools/list has 13 tools (got ${names.length})`, names.join(","));
  for (const n of EXPECTED_TOOLS) check(names.includes(n), `tools/list includes ${n}`);
  const sos = (list.result.tools || []).find((t) => t.name === "second_opinion_start");
  check(sos && sos.inputSchema.required.includes("mode") && sos.inputSchema.properties.mode.enum.includes("independent"),
        "second_opinion_start schema requires mode with independent|review");
  const ps = (list.result.tools || []).find((t) => t.name === "project_smells");
  check(ps && ps.inputSchema.required.includes("part") && ps.inputSchema.required.includes("cwd"),
        "project_smells schema requires part+cwd");

  // 1b. 第二意見／候選池：js 層拒收（不 spawn py）
  const so0 = await callTool("second_opinion_start", {
    kind: "diagnose", part: "x", cwd: path.resolve(__dirname), mode: "independent", question: "q", draft: "我方結論",
  });
  check(so0.result.isError === true && /independent/.test(textOf(so0)) && /draft/.test(textOf(so0)),
        "second_opinion_start independent+draft rejected", textOf(so0));
  const so1 = await callTool("second_opinion_start", {
    kind: "diagnose", part: "x", cwd: path.resolve(__dirname), mode: "review", question: "q",
  });
  check(so1.result.isError === true && /review/.test(textOf(so1)) && /draft/.test(textOf(so1)),
        "second_opinion_start review w/o draft rejected", textOf(so1));
  const so2 = await callTool("second_opinion_result", { job_id: "  " });
  check(so2.result.isError === true && /job_id/.test(textOf(so2)), "second_opinion_result requires job_id", textOf(so2));
  const so3 = await callTool("second_opinion_result", { job_id: "../../etc" });
  check(so3.result.isError === true && /格式/.test(textOf(so3)), "second_opinion_result rejects bad job_id format", textOf(so3));
  const ps0 = await callTool("project_smells", { cwd: path.resolve(__dirname) });
  check(ps0.result.isError === true && /part/.test(textOf(ps0)), "project_smells requires part", textOf(ps0));
  const aw = (list.result.tools || []).find((t) => t.name === "atom_write");
  check(aw && aw.inputSchema.properties.supersedes && aw.inputSchema.properties.supersedes.type === "array",
        "atom_write schema has supersedes:array");
  const ar = (list.result.tools || []).find((t) => t.name === "atom_retire");
  check(ar && ar.inputSchema.required.includes("reason"), "atom_retire schema requires reason");

  // 1c. need_goal：js 只驗參數回 chip（不寫檔）；schema 的 action 列舉五個動作
  const ngDef = (list.result.tools || []).find((t) => t.name === "need_goal");
  check(ngDef && ngDef.inputSchema.required.includes("action")
        && ["set", "add", "update", "reconcile", "read"].every((a) => ngDef.inputSchema.properties.action.enum.includes(a)),
        "need_goal schema requires action with five actions");
  const ng0 = await callTool("need_goal", { action: "set" });
  check(ng0.result.isError === true && /goal/.test(textOf(ng0)), "need_goal set w/o goal rejected", textOf(ng0));
  const ng1 = await callTool("need_goal", { action: "set", goal: "讓使用者改完設定不用重開" });
  check(!ng1.result.isError && /\[NeedGoal\] set 已收到/.test(textOf(ng1)), "need_goal set chip", textOf(ng1));
  const ng2 = await callTool("need_goal", { action: "update", items: [{ id: "T1.1", status: "done" }] });
  check(ng2.result.isError === true && /why/.test(textOf(ng2)), "need_goal update w/o why rejected", textOf(ng2));
  const ng3 = await callTool("need_goal", { action: "reconcile", items: [{ id: "T1", status: "doing" }] });
  check(ng3.result.isError === true && /終點/.test(textOf(ng3)), "need_goal reconcile non-terminal status rejected", textOf(ng3));
  const ng4 = await callTool("need_goal", { action: "reconcile", items: [
    { id: "T1", status: "done", evidence: [{ kind: "receipt", ref: "R3", level: "measured", covers: ["T1"] }] },
  ] });
  check(!ng4.result.isError && /reconcile 已收到/.test(textOf(ng4)), "need_goal reconcile chip", textOf(ng4));
  const ng5 = await callTool("need_goal", { action: "reconcile", items: [
    { id: "T1", status: "done", evidence: [{ kind: "proof", ref: "x", level: "sure" }] },
  ] });
  check(ng5.result.isError === true && /kind/.test(textOf(ng5)) && /level/.test(textOf(ng5)),
        "need_goal reconcile bad evidence enums rejected", textOf(ng5));
  const ng6 = await callTool("need_goal", { action: "explode" });
  check(ng6.result.isError === true && /action/.test(textOf(ng6)), "need_goal unknown action rejected", textOf(ng6));
  // verify_scope：驗證範圍的宣告（該測哪些由 LLM 判斷）；js 只驗形狀
  check(ngDef && ngDef.inputSchema.properties.action.enum.includes("verify_scope") && ngDef.inputSchema.properties.reviews,
        "need_goal schema has verify_scope and reviews");
  const ng7 = await callTool("need_goal", { action: "verify_scope", items: [{ target: "hooks/verify/verify_x.py" }] });
  check(ng7.result.isError === true && /why/.test(textOf(ng7)), "need_goal verify_scope w/o why rejected", textOf(ng7));
  const ng8 = await callTool("need_goal", { action: "verify_scope", items: [{ target: "a.py", why: "w" }],
    reviews: [{ leak: "L1", verdict: "maybe" }] });
  check(ng8.result.isError === true && /verdict/.test(textOf(ng8)), "need_goal verify_scope bad review verdict rejected", textOf(ng8));
  const ng9 = await callTool("need_goal", { action: "verify_scope", items: [{ target: "a.py", why: "直接測 a" }] });
  check(!ng9.result.isError && /verify_scope 已收到/.test(textOf(ng9)), "need_goal verify_scope chip", textOf(ng9));
  // (d) 由哪個案例驗：case_for（項目）、no_case（頂層）只驗形狀
  check(ngDef && ngDef.inputSchema.properties.no_case && ngDef.inputSchema.properties.items.items.properties.case_for,
        "need_goal schema has case_for and no_case");
  check(ngDef && ngDef.inputSchema.properties.items.items.properties.depends, "need_goal schema has depends");
  const ngDep = await callTool("need_goal", { action: "verify_scope", items: [{ target: "a.py", why: "w", depends: "b.py" }] });
  check(ngDep.result.isError === true && /depends/.test(textOf(ngDep)), "need_goal verify_scope bad depends rejected", textOf(ngDep));
  const ng9b = await callTool("need_goal", { action: "verify_scope", items: [{ target: "a.py", why: "w", case_for: [] }],
    no_case: [{ path: "b.py" }] });
  check(ng9b.result.isError === true && /case_for/.test(textOf(ng9b)) && /no_case\[0\]/.test(textOf(ng9b)),
        "need_goal verify_scope bad case_for／no_case rejected", textOf(ng9b));
  const ng9c = await callTool("need_goal", { action: "verify_scope", items: [{ target: "a.py", why: "w", case_for: ["b.py"] }],
    no_case: [{ path: "c.py", reason: "只改字串" }] });
  check(!ng9c.result.isError, "need_goal verify_scope case_for／no_case accepted", textOf(ng9c));
  // same_class：達成節點可附同類別處（只驗形狀：字串）
  const itemProps = ngDef && ngDef.inputSchema.properties.items.items.properties;
  check(itemProps && itemProps.same_class && itemProps.same_class.type === "string", "need_goal schema has same_class");
  const ng10 = await callTool("need_goal", { action: "reconcile", items: [{ id: "T1", status: "done", same_class: ["x"] }] });
  check(ng10.result.isError === true && /same_class/.test(textOf(ng10)), "need_goal reconcile non-string same_class rejected", textOf(ng10));
  const ng11 = await callTool("need_goal", { action: "reconcile", items: [{ id: "T1", status: "done", same_class: "別處也用檔名猜" }] });
  check(!ng11.result.isError && /reconcile 已收到/.test(textOf(ng11)), "need_goal reconcile with same_class chip", textOf(ng11));
  // inputs：驗證範圍一項還讀的檔或資料夾（只驗形狀：非空字串陣列）
  check(itemProps && itemProps.inputs && itemProps.inputs.type === "array", "need_goal schema has inputs");
  const ng12 = await callTool("need_goal", { action: "verify_scope", items: [{ target: "a.py", why: "w", inputs: "x.md" }] });
  check(ng12.result.isError === true && /inputs/.test(textOf(ng12)), "need_goal verify_scope non-array inputs rejected", textOf(ng12));

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

  cp.stdin.end();
  await new Promise((res) => { cp.on("exit", res); setTimeout(() => { try { cp.kill(); } catch {} res(); }, 5000); });
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

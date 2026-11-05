// verify_atom_feedback_tool.js：atom_feedback 工具的 MCP 面檢查（不對真實記憶卡投票）。
// 案例：(a) tools/list 含 atom_feedback 且 required=[atom_name, verdict]；(b) 不存在的 atom_name → isError 含 not found；(c) 非法 verdict → isError。
// 跑：node tools/workflow-guardian-mcp/verify/verify_atom_feedback_tool.js（尾行 ATOM_FEEDBACK_TOOL_CHECK PASS／FAIL）
const os = require("os");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

let ok = true;
const fail = (m) => { ok = false; console.error("FAIL: " + m); };

// 起 server、依序送 requests（id 從 2 起）、收齊回應後關掉
function callOverStdio(env, requests) {
  return new Promise((resolve, reject) => {
    const srv = spawn(process.execPath, [path.join(__dirname, "..", "server.js")], { env, stdio: ["pipe", "pipe", "pipe"] });
    let out = "";
    const got = {};
    const timer = setTimeout(() => { srv.kill(); reject(new Error("逾時")); }, 30000);
    const allAnswered = () => requests.every((_, i) => got[i + 2]);
    function collectLine(line) {
      try {
        const msg = JSON.parse(line);
        if (msg.id >= 2) got[msg.id] = msg;
      } catch { /* 還沒收完整行 */ }
    }
    function onStdout(d) {
      out += d.toString("utf-8");
      out.split("\n").forEach(collectLine);
      if (!allAnswered()) return;
      clearTimeout(timer);
      srv.kill();
      resolve(got);
    }
    srv.stdout.on("data", onStdout);
    srv.on("error", reject);
    const send = (o) => srv.stdin.write(JSON.stringify(o) + "\n");
    send({ jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-11-25", capabilities: {}, clientInfo: { name: "t", version: "0" } } });
    requests.forEach((r, i) => send({ jsonrpc: "2.0", id: i + 2, ...r }));
  });
}

function contentText(c) { return c.text; }
function textOf(msg) {
  const content = (msg.result && msg.result.content) || [];
  return content.map(contentText).join("\n");
}

(async () => {
  try {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "wg-feedback-"));
    const env = { ...process.env, WG_CLAUDE_DIR: root, WG_DASHBOARD_PORT: "38499" };
    const got = await callOverStdio(env, [
      { method: "tools/list", params: {} },
      { method: "tools/call", params: { name: "atom_feedback", arguments: { atom_name: "no-such-atom-zzz-feedback-check", verdict: "helpful", scope: "global" } } },
      { method: "tools/call", params: { name: "atom_feedback", arguments: { atom_name: "no-such-atom-zzz-feedback-check", verdict: "bogus", scope: "global" } } },
    ]);

    const tool = ((got[2].result || {}).tools || []).find((t) => t.name === "atom_feedback");
    if (!tool) fail("tools/list 沒有 atom_feedback");
    else {
      const req = (tool.inputSchema && tool.inputSchema.required) || [];
      if (JSON.stringify(req) !== JSON.stringify(["atom_name", "verdict"])) fail(`required 不對：${req.join(",")}`);
      const en = ((tool.inputSchema.properties || {}).verdict || {}).enum;
      if (JSON.stringify(en) !== JSON.stringify(["helpful", "misleading"])) fail(`verdict enum 不對：${JSON.stringify(en)}`);
    }

    const b = got[3].result || {};
    if (!b.isError) fail("不存在的 atom_name 應回 isError");
    if (!/not found/i.test(textOf(got[3]))) fail(`訊息應含 not found：${textOf(got[3])}`);

    const c = got[4].result || {};
    if (!c.isError) fail("非法 verdict 應回 isError");
    if (!/verdict/i.test(textOf(got[4]))) fail(`訊息應提到 verdict：${textOf(got[4])}`);

    fs.rmSync(root, { recursive: true, force: true });
  } catch (e) {
    fail(`例外：${e && e.stack || e}`);
  }
  console.log(`ATOM_FEEDBACK_TOOL_CHECK ${ok ? "PASS" : "FAIL"}`);
  process.exit(ok ? 0 : 1);
})();

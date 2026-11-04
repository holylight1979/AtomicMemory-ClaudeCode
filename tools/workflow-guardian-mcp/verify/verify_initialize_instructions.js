// verify_initialize_instructions.js：initialize 回應的 server instructions 只給非 Claude Code 客戶端；tools/list 只有 memory_search 標免延遲。
// 案例：真起 server.js（stdio）送三次 initialize——clientInfo.name＝claude-code（不帶 instructions）、codex（帶）、沒帶 clientInfo（判不出 → 帶）；
//   instructions ≤ 1,500 字元且點到 memory_search／atom_write／索引檔；tools/list 帶 _meta["anthropic/alwaysLoad"]=true 的恰好只有 memory_search。
// 跑：node tools/workflow-guardian-mcp/verify/verify_initialize_instructions.js（尾行 INITIALIZE_INSTRUCTIONS_CHECK PASS／FAIL）
const os = require("os");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

let ok = true;
const fail = (m) => { ok = false; console.error("FAIL: " + m); };

function rpcOverStdio(env, requests) {
  return new Promise((resolve, reject) => {
    const srv = spawn(process.execPath, [path.join(__dirname, "..", "server.js")], { env, stdio: ["pipe", "pipe", "pipe"] });
    const got = {};
    let out = "";
    const timer = setTimeout(() => { srv.kill(); reject(new Error("回應逾時：" + JSON.stringify(Object.keys(got)))); }, 20000);
    srv.stdout.on("data", (d) => {
      out += d.toString("utf-8");
      const lines = out.split("\n");
      out = lines.pop();
      for (const line of lines) {
        try { const msg = JSON.parse(line); if (msg.id !== undefined) got[msg.id] = msg; } catch { /* 非 JSON 行 */ }
      }
      if (requests.every((r) => got[r.id])) { clearTimeout(timer); srv.kill(); resolve(got); }
    });
    srv.on("error", reject);
    for (const r of requests) srv.stdin.write(JSON.stringify({ jsonrpc: "2.0", ...r }) + "\n");
  });
}

(async () => {
  try {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "wg-init-"));   // 資料根放暫存（啟動紀錄不寫進 live）
    const env = { ...process.env, WG_CLAUDE_DIR: root, WG_DASHBOARD_PORT: "38497" };
    const init = (id, clientInfo) => ({ id, method: "initialize",
      params: { protocolVersion: "2025-11-25", capabilities: {}, ...(clientInfo && { clientInfo }) } });
    const got = await rpcOverStdio(env, [
      init(1, { name: "claude-code", title: "Claude Code", version: "2.1.0" }),
      init(2, { name: "codex", version: "0.1" }),
      init(3, null),
      { id: 4, method: "tools/list", params: {} },
    ]);
    const cc = got[1].result, codex = got[2].result, unknown = got[3].result;
    if (!cc || !cc.serverInfo) fail("claude-code 的 initialize 沒回 serverInfo");
    if (cc && "instructions" in cc) fail("clientInfo.name=claude-code 卻帶了 instructions");
    if (!codex || typeof codex.instructions !== "string" || !codex.instructions) fail("clientInfo.name=codex 沒帶 instructions");
    if (!unknown || unknown.instructions !== (codex && codex.instructions)) fail("沒帶 clientInfo 時應照送同一份 instructions");
    const text = (codex && codex.instructions) || "";
    if (text.length > 1500) fail(`instructions ${text.length} 字元，超過 1,500`);
    for (const k of ["memory_search", "atom_write", "MEMORY.md", "_atom_index.json", "~/.claude/memory/"]) {
      if (!text.includes(k)) fail(`instructions 沒點到 ${k}`);
    }
    const tools = (got[4].result && got[4].result.tools) || [];
    const always = tools.filter((t) => t._meta && t._meta["anthropic/alwaysLoad"] === true).map((t) => t.name);
    if (JSON.stringify(always) !== JSON.stringify(["memory_search"])) fail(`免延遲的工具應只有 memory_search，實得 ${always.join(",") || "（無）"}`);
    if (tools.length !== 9) fail(`tools/list 應 9 支，實得 ${tools.length}`);
    console.log(`instructions ${text.length} 字元；免延遲：${always.join(",")}`);
    fs.rmSync(root, { recursive: true, force: true });
  } catch (e) {
    fail(`例外：${e && e.stack || e}`);
  }
  console.log(`INITIALIZE_INSTRUCTIONS_CHECK ${ok ? "PASS" : "FAIL"}`);
  process.exit(ok ? 0 : 1);
})();

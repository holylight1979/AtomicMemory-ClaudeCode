// verify_tools_list_guard_off.js：寫碼守門關著時，工具清單不列守門專用的四個工具；開著時 13 個全列。
// 案例：listedTools(true) 13 個；listedTools(false) 9 個、四個守門工具都不在、守門之前就有的記憶工具都在；
//      真起 server.js（WG_CODING_GUARD=0）打 tools/list，回來的清單同 listedTools(false)。
// 跑：node tools/workflow-guardian-mcp/verify/verify_tools_list_guard_off.js（尾行 TOOLS_LIST_GUARD_OFF_CHECK PASS／FAIL）
const os = require("os");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

let ok = true;
const fail = (m) => { ok = false; console.error("FAIL: " + m); };
const MEMORY_TOOLS = ["atom_write", "atom_promote", "atom_move", "atom_edit_meta", "anti_evasion_report",
  "knowledge_harvest_report", "atom_retire", "memory_search", "atom_source"];

function listOverStdio(env) {
  return new Promise((resolve, reject) => {
    const srv = spawn(process.execPath, [path.join(__dirname, "..", "server.js")], { env, stdio: ["pipe", "pipe", "pipe"] });
    let out = "";
    const timer = setTimeout(() => { srv.kill(); reject(new Error("tools/list 逾時")); }, 20000);
    srv.stdout.on("data", (d) => {
      out += d.toString("utf-8");
      for (const line of out.split("\n")) {
        try {
          const msg = JSON.parse(line);
          if (msg.id === 2) { clearTimeout(timer); srv.kill(); resolve(msg.result.tools.map((t) => t.name)); return; }
        } catch { /* 還沒收完整行 */ }
      }
    });
    srv.on("error", reject);
    const send = (o) => srv.stdin.write(JSON.stringify(o) + "\n");
    send({ jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-11-25", capabilities: {}, clientInfo: { name: "t", version: "0" } } });
    send({ jsonrpc: "2.0", id: 2, method: "tools/list", params: {} });
  });
}

(async () => {
  try {
    const mcp = require("../lib/mcp");
    const on = mcp.listedTools(true).map((t) => t.name);
    const off = mcp.listedTools(false).map((t) => t.name);
    if (on.length !== mcp.TOOL_DEFINITIONS.length || on.length !== 13) fail(`守門開著應列 13 個，實際 ${on.length}`);
    if (off.length !== 9) fail(`守門關著應列 9 個，實際 ${off.length}：${off.join(",")}`);
    for (const n of mcp.GUARD_ONLY_TOOLS) if (off.includes(n)) fail(`守門關著還列了 ${n}`);
    for (const n of MEMORY_TOOLS) if (!off.includes(n)) fail(`守門關著少了記憶工具 ${n}`);

    // 真起 server：資料根放暫存（啟動紀錄不寫進 live），守門明關
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "wg-toolslist-"));
    const env = { ...process.env, WG_CLAUDE_DIR: root, WG_CODING_GUARD: "0", WG_V6: "", WG_DASHBOARD_PORT: "38498" };
    const names = await listOverStdio(env);
    if (JSON.stringify(names) !== JSON.stringify(off)) fail(`server 回的清單與 listedTools(false) 不同：${names.join(",")}`);
    fs.rmSync(root, { recursive: true, force: true });
  } catch (e) {
    fail(`例外：${e && e.stack || e}`);
  }
  console.log(`TOOLS_LIST_GUARD_OFF_CHECK ${ok ? "PASS" : "FAIL"}`);
  process.exit(ok ? 0 : 1);
})();

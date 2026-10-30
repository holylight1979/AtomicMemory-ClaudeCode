// verify_tools_list_guard_off.js：寫碼守門開或關，工具清單都是同一份 9 個記憶工具。
// 案例：真起 server.js 兩次（WG_V6=1 守門開；WG_CODING_GUARD=0 守門關）打 tools/list，兩次都回這 9 個、順序相同。
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
    // 資料根放暫存（啟動紀錄不寫進 live）
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "wg-toolslist-"));
    const base = { ...process.env, WG_CLAUDE_DIR: root, WG_DASHBOARD_PORT: "38498" };
    const on = await listOverStdio({ ...base, WG_V6: "1", WG_CODING_GUARD: "" });
    const off = await listOverStdio({ ...base, WG_V6: "", WG_CODING_GUARD: "0" });
    const want = JSON.stringify(MEMORY_TOOLS);
    if (JSON.stringify(on) !== want) fail(`守門開著的清單不是那 9 個：${on.join(",")}`);
    if (JSON.stringify(off) !== want) fail(`守門關著的清單不是那 9 個：${off.join(",")}`);
    fs.rmSync(root, { recursive: true, force: true });
  } catch (e) {
    fail(`例外：${e && e.stack || e}`);
  }
  console.log(`TOOLS_LIST_GUARD_OFF_CHECK ${ok ? "PASS" : "FAIL"}`);
  process.exit(ok ? 0 : 1);
})();

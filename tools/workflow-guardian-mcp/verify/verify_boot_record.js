// verify_boot_record.js：MCP 服務啟動紀錄（lib/boot-record.js）寫得出 hook 讀得懂的檔：pid、code_mtime、booted_at、heartbeat_at；
// 心跳只更新 heartbeat_at、不留 .tmp。跑：node tools/workflow-guardian-mcp/verify/verify_boot_record.js（結尾印 BOOT_RECORD_CHECK PASS／FAIL）
const fs = require("fs");
const os = require("os");
const path = require("path");

let ok = true;
const fail = (m) => { ok = false; console.error("FAIL: " + m); };
try {
  const { writeBootRecord } = require("../lib/boot-record");
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "boot-record-"));
  writeBootRecord(dir, 4242, 1792045981215.7, 1000, 2000);
  const rec = JSON.parse(fs.readFileSync(path.join(dir, "4242.json"), "utf8"));
  if (rec.pid !== 4242) fail("pid " + rec.pid);
  if (rec.code_mtime !== 1792045981215.7) fail("code_mtime " + rec.code_mtime);
  if (rec.booted_at !== 1000 || rec.heartbeat_at !== 2000) fail("times " + JSON.stringify(rec));
  writeBootRecord(dir, 4242, 1792045981215.7, 1000, 3000);
  const again = JSON.parse(fs.readFileSync(path.join(dir, "4242.json"), "utf8"));
  if (again.heartbeat_at !== 3000 || again.booted_at !== 1000) fail("heartbeat refresh " + JSON.stringify(again));
  if (fs.readdirSync(dir).some((f) => f.endsWith(".tmp"))) fail("tmp left behind");
  fs.rmSync(dir, { recursive: true, force: true });
} catch (e) {
  fail((e && e.stack) || String(e));
}
console.log(ok ? "BOOT_RECORD_CHECK PASS" : "BOOT_RECORD_CHECK FAIL");
process.exit(ok ? 0 : 1);

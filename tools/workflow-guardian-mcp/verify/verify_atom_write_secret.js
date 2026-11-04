// verify_atom_write_secret.js — atom_write 的 secret／not_sensitive（個人隱私敏感資訊放 personal/<user>/secret/）
//   驗：secret=true 落 personal/<user>/secret/、Scope 是本人、不進共用索引；scope 寫 global 也一樣；
//   提到敏感字眼沒宣告 → 拒寫不落檔，skip_gate 不放行；帶 not_sensitive 理由 → 照原路徑寫；
//   含真實 token → not_sensitive 也拒，secret=true 才寫得進去；append 既有 secret 卡找得到；一般內容不受影響。
// 隔離：WG_CLAUDE_DIR 指 os.tmpdir() 下的暫存資料根（require 任何 lib 之前設）；假向量服務不碰 live；目錄重產換成空函式。
// 怎麼跑：node tools/workflow-guardian-mcp/verify/verify_atom_write_secret.js（尾行 ATOM_WRITE_SECRET_CHECK PASS／FAIL）
const fs = require("fs");
const os = require("os");
const path = require("path");
const http = require("http");

const CODE = path.resolve(__dirname, "..", "..", "..");
const ROOT = fs.mkdtempSync(path.join(os.tmpdir(), "wg-secret-"));
process.env.WG_CLAUDE_DIR = ROOT;
process.chdir(ROOT);
fs.mkdirSync(path.join(ROOT, "memory", "_meta"), { recursive: true });
for (const f of ["taxonomy.json", "realm-lexicon.json"]) {   // 範疇閘／核心保護清單照本樹
  fs.copyFileSync(path.join(CODE, "memory", "_meta", f), path.join(ROOT, "memory", "_meta", f));
}
const vector = http.createServer((req, res) => { res.writeHead(200, { "Content-Type": "application/json" }); res.end("[]"); });

const funnel = require("../lib/funnel");
funnel.syncMemoryIndex = () => {};
const mcp = require("../lib/mcp");
const replies = new Map();
mcp.sendToolResult = (id, text, isError = false) => { replies.set(id, { text, isError }); };
const { toolAtomWrite } = require("../lib/atom-tools");

let nextId = 1;
async function write(args) {
  const id = nextId++;
  await toolAtomWrite(id, {
    mode: "create", confidence: "[臨]", triggers: ["secret-smoke"], knowledge: ["- [臨] 判準：先問實害"], skip_gate: true, ...args,
  });
  return replies.get(id) || { text: "(no reply)", isError: true };
}
const secretPath = (slug) => path.join(ROOT, "memory", "personal", "tester", "secret", `${slug}.md`);
const localPath = (slug) => path.join(ROOT, "_AIDocs", "_atoms", "MemDev", `${slug}.md`);
const pub = { scope: "global", realm: "local", domain: "MemDev" };
const FAKE_TOKEN = "glpat-" + "a".repeat(20);   // 拼起來才不會被掃描工具當真的

const failures = [];
function check(cond, label, detail) {
  if (cond) { console.log(`  ok   ${label}`); return; }
  failures.push(label);
  console.log(`  FAIL ${label}${detail ? "\n       " + String(detail).slice(0, 900) : ""}`);
}
const read = (p) => (fs.existsSync(p) ? fs.readFileSync(p, "utf-8") : "");
const sharedIndex = () => read(path.join(ROOT, "memory", "_atom_index.json"));

(async () => {
  await new Promise((r) => vector.listen(0, "127.0.0.1", r));
  fs.mkdirSync(path.join(ROOT, "workflow"), { recursive: true });
  fs.writeFileSync(path.join(ROOT, "workflow", "config.json"),
    JSON.stringify({ vector_search: { service_port: vector.address().port } }));
  // 共用索引要先存在：根層有索引才是實際安裝的樣子
  fs.writeFileSync(path.join(ROOT, "memory", "_atom_index.json"), JSON.stringify({ version: "1.0", atoms: [] }));

  let r = await write({ title: "key-card", scope: "personal", user: "tester", secret: true, knowledge: ["- [臨] 金鑰放在 ~/.ssh/work"] });
  check(!r.isError && fs.existsSync(secretPath("key-card")), "secret=true 落 personal/<user>/secret/", r.text);
  check(read(secretPath("key-card")).includes("- Scope: personal:tester"), "secret 卡的 Scope 是本人", read(secretPath("key-card")));
  check(!sharedIndex().includes("key-card"), "secret 卡不進共用索引", sharedIndex());
  const personalIndex = read(path.join(ROOT, "memory", "personal", "_personal_index.json"));
  check(personalIndex.includes("memory/personal/tester/secret/key-card.md"), "登記在本機索引", personalIndex);

  r = await write({ title: "key-card-2", ...pub, user: "tester", secret: true });
  check(!r.isError && fs.existsSync(secretPath("key-card-2")), "scope 寫 global＋secret=true 也落 secret/", r.text);

  r = await write({ title: "key-card", mode: "append", scope: "personal", user: "tester", secret: true, knowledge: ["- [臨] 補一條"] });
  check(!r.isError && read(secretPath("key-card")).includes("補一條"), "append 找得到既有 secret 卡", r.text);

  r = await write({ title: "leak-word", ...pub, knowledge: ["- [臨] 公司 git 存的是帳號密碼"] });
  check(r.isError && /secret=true/.test(r.text) && /not_sensitive/.test(r.text) && !fs.existsSync(localPath("leak-word")),
    "提到敏感字眼沒宣告 → 拒寫不落檔，訊息講怎麼做", r.text);

  r = await write({ title: "leak-word", ...pub, knowledge: ["- [臨] 公司 git 存的是帳號密碼"], skip_gate: true, not_sensitive: "" });
  check(r.isError && !fs.existsSync(localPath("leak-word")), "skip_gate 與空理由都不放行", r.text);

  r = await write({ title: "tech-word", ...pub, knowledge: ["- [臨] 通用做法：憑證要存獨立檔"], not_sensitive: "只是通用做法，沒有個人資訊" });
  check(!r.isError && fs.existsSync(localPath("tech-word")), "帶 not_sensitive 理由 → 照原路徑寫", r.text);

  r = await write({ title: "leak-value", ...pub, knowledge: [`- [臨] 值是 ${FAKE_TOKEN}`], not_sensitive: "我覺得沒關係" });
  check(r.isError && /真實值/.test(r.text) && !r.text.includes(FAKE_TOKEN) && !fs.existsSync(localPath("leak-value")),
    "真實 token：not_sensitive 也拒，訊息不複述值", r.text);

  r = await write({ title: "key-value", scope: "personal", user: "tester", secret: true, knowledge: [`- [臨] 值是 ${FAKE_TOKEN}`] });
  check(!r.isError && fs.existsSync(secretPath("key-value")), "真實 token：secret=true 才寫得進去", r.text);

  r = await write({ title: "plain-pref", scope: "personal", user: "tester", cross_project: true, knowledge: ["- [臨] 偏好條列式回報"] });
  check(!r.isError && fs.existsSync(path.join(ROOT, "memory", "personal", "tester", "plain-pref.md")), "一般個人卡照舊，不受影響", r.text);

  vector.close();
  try { fs.rmSync(ROOT, { recursive: true, force: true }); } catch {}
  console.log(failures.length ? "ATOM_WRITE_SECRET_CHECK FAIL" : "ATOM_WRITE_SECRET_CHECK PASS");
  process.exit(failures.length ? 1 : 0);
})().catch((e) => {
  console.log(`  FAIL 例外：${e && e.stack || e}`);
  console.log("ATOM_WRITE_SECRET_CHECK FAIL");
  process.exit(1);
});

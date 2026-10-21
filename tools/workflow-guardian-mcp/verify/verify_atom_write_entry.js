// verify_atom_write_entry.js — atom_write／atom_edit_meta 的 entry 參數（卡綁切入點）MCP（js）端：真 py funnel＋真落檔。
//   驗：create 給 entry → 檔頭 `- Entry: E04, E08`、索引 entry 欄；replace 沒給 → 原行與索引沿用；replace 給 [] → 清掉；
//   entry 格式錯（不是陣列、含逗號、空字串）→ js 先拒、不落檔；atom_edit_meta entry → 檔頭與索引一起改、[] 清空；
//   buildAtomContent（js）與 lib/atom_spec.build_atom_content（py）帶 entry 時逐字相同。
// 隔離：WG_CLAUDE_DIR 指 os.tmpdir() 下的暫存資料根（require 任何 lib 之前設）；process.chdir 到該根；寫入後的向量重索引
//   照 config 的 service_port 打到本檔起的假服務（不碰 live 3849）；目錄重產換成空函式；sendToolResult 改成收進記憶體。
// 怎麼跑：node tools/workflow-guardian-mcp/verify/verify_atom_write_entry.js（尾行 ATOM_WRITE_ENTRY_CHECK PASS|FAIL）
const fs = require("fs");
const os = require("os");
const path = require("path");
const http = require("http");
const { spawnSync } = require("child_process");

const CODE = path.resolve(__dirname, "..", "..", "..");
const ROOT = fs.mkdtempSync(path.join(os.tmpdir(), "wg-entry-"));
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
const { toolAtomWrite, toolAtomEditMeta } = require("../lib/atom-tools");
const { buildAtomContent } = require("../lib/atom-render");

let nextId = 1;
async function call(fn, args) {
  const id = nextId++;
  await fn(id, args);
  return replies.get(id) || { text: "(no reply)", isError: true };
}
const write = (args) => call(toolAtomWrite, {
  scope: "global", realm: "local", domain: "MemDev", confidence: "[臨]", triggers: ["entry-smoke"],
  knowledge: ["- [臨] 判準：先問實害"], skip_gate: true, ...args,
});
const atomPath = (slug) => path.join(ROOT, "_AIDocs", "_atoms", "MemDev", `${slug}.md`);
const indexRow = (slug) => {
  try {
    const data = JSON.parse(fs.readFileSync(path.join(ROOT, "memory", "_atom_index.json"), "utf-8"));
    return (data.atoms || []).find((a) => a.name === slug) || null;
  } catch { return null; }
};
const read = (slug) => (fs.existsSync(atomPath(slug)) ? fs.readFileSync(atomPath(slug), "utf-8") : "");

const failures = [];
function check(cond, label, detail) {
  if (cond) { console.log(`  ok   ${label}`); return; }
  failures.push(label);
  console.log(`  FAIL ${label}${detail ? "\n       " + String(detail).slice(0, 900) : ""}`);
}

(async () => {
  await new Promise((r) => vector.listen(0, "127.0.0.1", r));
  fs.mkdirSync(path.join(ROOT, "workflow"), { recursive: true });
  fs.writeFileSync(path.join(ROOT, "workflow", "config.json"),
    JSON.stringify({ vector_search: { service_port: vector.address().port } }));

  // 1. create 帶 entry
  const SLUG = "entry-card";
  const w1 = await write({ title: SLUG, mode: "create", entry: ["E04", " E08 "] });
  check(!w1.isError, "create 帶 entry 成功", w1.text);
  check(/\n- Entry: E04, E08\n/.test(read(SLUG)), "檔頭有 `- Entry: E04, E08`（前後空白去掉）", read(SLUG));
  check(JSON.stringify((indexRow(SLUG) || {}).entry) === '["E04","E08"]', "索引 entry 欄＝[E04, E08]", JSON.stringify(indexRow(SLUG)));

  // 2. replace 沒給 entry → 原行與索引沿用
  const w2 = await write({ title: SLUG, mode: "replace", knowledge: ["- [臨] 判準：換過內容"] });
  check(!w2.isError, "replace（沒給 entry）成功", w2.text);
  check(/\n- Entry: E04, E08\n/.test(read(SLUG)) && read(SLUG).includes("換過內容"), "replace 沒給 entry → 原 Entry 行帶回", read(SLUG));
  check(JSON.stringify((indexRow(SLUG) || {}).entry) === '["E04","E08"]', "replace 沒給 entry → 索引 entry 沿用", JSON.stringify(indexRow(SLUG)));

  // 3. replace 給 [] → 清掉
  const w3 = await write({ title: SLUG, mode: "replace", entry: [] });
  check(!w3.isError, "replace（entry=[]）成功", w3.text);
  check(!/^- Entry:/m.test(read(SLUG)), "entry=[] → 檔頭沒有 Entry 行", read(SLUG));
  check(indexRow(SLUG) && !("entry" in indexRow(SLUG)), "entry=[] → 索引移除 entry 鍵", JSON.stringify(indexRow(SLUG)));

  // 4. 格式錯 js 先拒、不落檔
  for (const [bad, label] of [["E04", "字串"], [["E04,E08"], "含逗號"], [[""], "空字串"], [[4], "不是字串"]]) {
    const r = await write({ title: `entry-bad-${label}`, mode: "create", entry: bad });
    check(r.isError && r.text.includes("entry must be an array of entrypoint ids"), `entry ${label} → 拒收`, r.text);
    check(!fs.existsSync(atomPath(`entry-bad-${label}`)), `entry ${label} → 沒落檔`);
  }

  // 4b. append 不動檔頭、忽略 entry：格式錯也不因它拒收，Entry 行照舊
  const wa = await write({ title: SLUG, mode: "append", knowledge: ["- [臨] 追加一條"], entry: ["E04,E08"] });
  check(!wa.isError && read(SLUG).includes("追加一條"), "append 帶格式錯的 entry → 照常追加（忽略 entry）", wa.text);
  check(!/^- Entry:/m.test(read(SLUG)), "append 不改 Entry 行", read(SLUG));

  // 5. atom_edit_meta entry
  const e1 = await call(toolAtomEditMeta, { atom_name: SLUG, scope: "global", entry: ["E20"] });
  check(!e1.isError && e1.text.includes("fields: entry"), "atom_edit_meta entry 成功", e1.text);
  check(/\n- Entry: E20\n/.test(read(SLUG)) && /\n- Trigger: entry-smoke\n/.test(read(SLUG)), "edit_meta → 檔頭 Entry: E20、Trigger 不動", read(SLUG));
  const row = indexRow(SLUG) || {};
  check(JSON.stringify(row.entry) === '["E20"]' && JSON.stringify(row.triggers) === '["entry-smoke"]',
    "edit_meta → 索引 entry=[E20]、triggers 不動", JSON.stringify(row));
  const e2 = await call(toolAtomEditMeta, { atom_name: SLUG, scope: "global", entry: [] });
  check(!e2.isError && indexRow(SLUG) && !("entry" in indexRow(SLUG)), "edit_meta entry=[] → 索引移除 entry 鍵", e2.text);
  const e3 = await call(toolAtomEditMeta, { atom_name: SLUG, scope: "global", entry: ["E1,E2"] });
  check(e3.isError && e3.text.includes("entry must be"), "edit_meta entry 含逗號 → 拒收", e3.text);

  // 6. py／js 建卡內容逐字相同（帶 entry 與不帶）
  for (const entry of [["E04", "E08"], undefined]) {
    const args = { title: "t", scope: "global", confidence: "[臨]", triggers: ["a"], knowledge: ["k"],
                   createdAt: "2026-10-21", depends: ["path:x"], related: ["r"], ...(entry && { entry }) };
    const js = buildAtomContent(args);
    const pyArgs = { title: "t", scope: "global", confidence: "[臨]", triggers: ["a"], knowledge: ["k"],
                     created_at: "2026-10-21", depends: ["path:x"], related: ["r"], ...(entry && { entry }) };
    const py = spawnSync(process.env.PYTHON || "python", ["-c",
      "import sys, json\nfrom lib.atom_spec import build_atom_content\nsys.stdout.buffer.write(build_atom_content(**json.loads(sys.argv[1])).encode('utf-8'))",
      JSON.stringify(pyArgs)], { cwd: CODE, encoding: "utf-8", env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
    check(py.status === 0 && py.stdout === js, `py／js 建卡內容逐字相同（entry=${entry ? entry.join(",") : "無"}）`,
      py.stderr || `js:\n${js}\npy:\n${py.stdout}`);
  }

  vector.close();
  try { fs.rmSync(ROOT, { recursive: true, force: true }); } catch {}
  console.log(failures.length ? `ATOM_WRITE_ENTRY_CHECK FAIL` : `ATOM_WRITE_ENTRY_CHECK PASS`);
  process.exit(failures.length ? 1 : 0);
})().catch((e) => {
  console.log(`  FAIL 例外：${e && e.stack || e}`);
  console.log("ATOM_WRITE_ENTRY_CHECK FAIL");
  process.exit(1);
});

// verify_atom_write_header_lines.js — atom_write（MCP js 端）檔頭欄位只讀同一行；append 帶的 provenance／quote 照寫。真 py funnel＋真落檔。
//   驗：舊卡的 `- Source:`／`- Quote:`／`- Depends:` 是空欄位行時，沒給這幾欄的 replace 不得把下一行（`## 知識`、別的欄位）
//   讀成值再寫回（舊讀法 `\s*(.+)` 跨行）；append 帶 provenance／quote → 檔頭 Source／Quote 換成呼叫者給的值，
//   沒給 → 不動，"" → 刪行（三態同 replace）。工具說明跟實作一致：provenance 說明寫到 append；
//   anti_evasion_report 的 k_followups 說明不宣稱寫病灶文件（Python 端只寫追蹤帳本，有部位的隨導讀卡注入）。
// 隔離：WG_CLAUDE_DIR 指 os.tmpdir() 下的暫存資料根（require 任何 lib 之前設）；process.chdir 到該根；寫入後的向量重索引
//   照 config 的 service_port 打到本檔起的假服務（不碰 live 3849）；目錄重產換成空函式；sendToolResult 改成收進記憶體。
// 怎麼跑：node tools/workflow-guardian-mcp/verify/verify_atom_write_header_lines.js（尾行 ATOM_WRITE_HEADER_LINES_CHECK PASS|FAIL）
const fs = require("fs");
const os = require("os");
const path = require("path");
const http = require("http");

const CODE = path.resolve(__dirname, "..", "..", "..");
const ROOT = fs.mkdtempSync(path.join(os.tmpdir(), "wg-header-"));
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
async function call(fn, args) {
  const id = nextId++;
  await fn(id, args);
  return replies.get(id) || { text: "(no reply)", isError: true };
}
const write = (args) => call(toolAtomWrite, {
  scope: "global", realm: "local", domain: "MemDev", confidence: "[臨]", triggers: ["header-smoke"],
  knowledge: ["- [臨] 判準：先問實害"], skip_gate: true, ...args,
});
const atomPath = (slug) => path.join(ROOT, "_AIDocs", "_atoms", "MemDev", `${slug}.md`);
const read = (slug) => (fs.existsSync(atomPath(slug)) ? fs.readFileSync(atomPath(slug), "utf-8") : "");
const blankFields = (slug, labels) => {
  const lines = read(slug).split("\n").map((l) => {
    const hit = labels.find((lb) => l.startsWith(`- ${lb}:`));
    return hit ? `- ${hit}:` : l;
  });
  fs.writeFileSync(atomPath(slug), lines.join("\n"), "utf-8");
};

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

  // 1. replace：空的 Source／Quote 行（Quote 緊接 Confidence、知識標題在檔頭後）
  const A = "header-card-a";
  const c1 = await write({ title: A, mode: "create", provenance: "session:abcdef12#11223344 2026-10-20", quote: "「原句一號」" });
  check(!c1.isError, "create 帶 Source／Quote 成功", c1.text);
  blankFields(A, ["Source", "Quote"]);
  check(/\n- Source:\n- Quote:\n/.test(read(A)), "前提：Source／Quote 是空欄位行", read(A));
  const r1 = await write({ title: A, mode: "replace", knowledge: ["- [臨] 判準：換過內容"] });
  check(!r1.isError, "replace（沒給 Source／Quote）成功", r1.text);
  const t1 = read(A);
  check(/\n## 知識\n/.test(t1) && !/^- Quote: ##/m.test(t1), "知識標題沒被吃成 Quote", t1);
  check(!/^- Source: - /m.test(t1) && !/^- Quote: - /m.test(t1), "空欄位沒把下一行的欄位讀成值", t1);
  check(t1.includes("換過內容"), "replace 內容換上", t1);

  // 2. replace：空的 Depends 行緊接著 Related（舊讀法把 Related 整行讀成依賴，寫回成 `- Depends: - Related: x`）
  const B = "header-card-b";
  const c2 = await write({ title: B, mode: "create", depends: ["path:C:/x/entry.py"], related: ["header-card-a"] });
  check(!c2.isError, "create 帶 Depends／Related 成功", c2.text);
  blankFields(B, ["Depends"]);
  check(/\n- Depends:\n- Related: header-card-a\n/.test(read(B)), "前提：Depends 空、下一行是 Related", read(B));
  const r2 = await write({ title: B, mode: "replace", knowledge: ["- [臨] 判準：B 換過"] });
  check(!r2.isError, "replace（沒給 Depends）成功", r2.text);
  const t2 = read(B);
  check(!/^- Depends:/m.test(t2), "空的 Depends 行算清（同 py），不輸出", t2);
  check(/\n- Related: header-card-a\n/.test(t2) && !t2.includes("Depends: - Related"), "Related 行原樣、沒被讀成依賴", t2);

  // 2b. 檔頭沒有 Source／Quote、知識段程式碼範例裡有長得像欄位的行：replace 不能把它讀成來源搬進檔頭
  const C = "header-card-c";
  const c3 = await write({ title: C, mode: "create" });
  check(!c3.isError, "create（沒有 Source／Quote）成功", c3.text);
  fs.writeFileSync(atomPath(C), read(C).replace("## 知識\n", "## 知識\n\n```\n- Source: 範例裡的字\n- Quote: 範例裡的字\n```\n"), "utf-8");
  const r3 = await write({ title: C, mode: "replace", knowledge: ["- [臨] 判準：C 換過"] });
  check(!r3.isError, "replace（沒給 Source／Quote）成功", r3.text);
  check(!read(C).includes("範例裡的字"), "知識段範例行沒被讀成檔頭欄位寫回", read(C));

  // 3. append 帶 provenance／quote → 檔頭換成呼叫者給的值
  const newSrc = "session:abcdef12#11223344 2026-10-20；commit:1234567 2026-10-23";
  const a1 = await write({ title: A, mode: "append", knowledge: ["- [臨] 併入的知識"], provenance: newSrc, quote: "「併入時的原句」" });
  check(!a1.isError, "append 帶 provenance／quote 成功", a1.text);
  const t3 = read(A);
  check(t3.includes(`\n- Source: ${newSrc}\n`) && (t3.match(/^- Source:/gm) || []).length === 1, "append 的 provenance 寫進 Source（只有一行）", t3);
  check(t3.includes("\n- Quote: 「併入時的原句」\n") && (t3.match(/^- Quote:/gm) || []).length === 1, "append 的 quote 寫進 Quote（只有一行）", t3);
  check(t3.includes("併入的知識") && t3.includes("換過內容"), "知識照常追加", t3);

  // 4. append 沒給 → 不動；"" → 刪行
  const a2 = await write({ title: A, mode: "append", knowledge: ["- [臨] 只加知識"] });
  check(!a2.isError && read(A).includes(`\n- Source: ${newSrc}\n`), "append 沒給 provenance → Source 不動", a2.text);
  const a3 = await write({ title: A, mode: "append", knowledge: ["- [臨] 清來源"], provenance: "" });
  check(!a3.isError && !/^- Source:/m.test(read(A)), 'append provenance="" → 刪掉 Source 行', read(A));

  // 5. 工具說明跟實作一致（AI 照說明做事、照說明宣稱）
  const tool = (name) => mcp.TOOL_DEFINITIONS.find((t) => t.name === name);
  const prov = tool("atom_write").inputSchema.properties.provenance.description;
  check(/append/.test(prov), "atom_write provenance 說明寫到 append 也會寫進 Source", prov);
  const k = tool("anti_evasion_report").inputSchema.properties.k_followups.description;
  check(!k.includes("同時寫進該部位病灶文件") && k.includes("不寫病灶文件") && k.includes("workflow/tracking/"),
    "anti_evasion_report k_followups 說明只講追蹤帳本（Python 端沒有寫病灶文件的程式）", k);

  vector.close();
  try { fs.rmSync(ROOT, { recursive: true, force: true }); } catch {}
  console.log(failures.length ? "ATOM_WRITE_HEADER_LINES_CHECK FAIL" : "ATOM_WRITE_HEADER_LINES_CHECK PASS");
  process.exit(failures.length ? 1 : 0);
})().catch((e) => {
  console.log(`  FAIL 例外：${e && e.stack || e}`);
  console.log("ATOM_WRITE_HEADER_LINES_CHECK FAIL");
  process.exit(1);
});

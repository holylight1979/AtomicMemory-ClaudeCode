// verify_atom_write_judgments.js — atom_write 的兩個 AI 宣告入口（G6 階段 5）在 MCP（js）端的接線。
//   CONFLICT_DECLARED_BY_AI：偵測器回 need_declaration → 不落檔、回「衝突待宣告（這次不寫檔）」列候選；conflict 參數原樣傳給偵測器；
//     宣告 not_conflict（偵測器回 ok）→ 照寫 shared、回覆附 conflict_declared；宣告 conflict（偵測器回 contradict）→ 落 .conflict.md、
//     不寫 shared、回覆帶理由；舊偵測器回 extend_overlap 不再自動改道 _pending_review；conflict 型別錯 js 先拒。
//   PROJECT_LITERAL_IS_HINT：從專案 cwd 寫 scope=global，內容只有字面「此專案」→ 真 py realm 閘擋、訊息帶規則名；
//     帶 scope_reason → 照寫、留帳 guard-realm_declared；scope_reason 型別錯 js 先拒。
// 隔離：WG_CLAUDE_DIR 指 os.tmpdir() 下的暫存資料根（require 任何 lib 之前設）；偵測器在 require atom-tools 前換成腳本化的假函式
//   （atom-tools 載入時解構 funnel 的匯出）；向量服務指到沒人聽的埠（寫入閘 fail-open）；sendToolResult 改成收進記憶體。
// 怎麼跑：node tools/workflow-guardian-mcp/verify/verify_atom_write_judgments.js（尾行 ATOM_WRITE_JUDGMENTS_CHECK PASS|FAIL）
const fs = require("fs");
const os = require("os");
const path = require("path");

const CODE = path.resolve(__dirname, "..", "..", "..");
const ROOT = fs.mkdtempSync(path.join(os.tmpdir(), "wg-judg-"));
const PROJ = fs.mkdtempSync(path.join(os.tmpdir(), "wg-judg-proj-"));
process.env.WG_CLAUDE_DIR = ROOT;
process.chdir(ROOT);
fs.mkdirSync(path.join(ROOT, "memory", "_meta"), { recursive: true });
for (const f of ["taxonomy.json", "realm-lexicon.json"]) {
  fs.copyFileSync(path.join(CODE, "memory", "_meta", f), path.join(ROOT, "memory", "_meta", f));
}
fs.mkdirSync(path.join(ROOT, "workflow"), { recursive: true });
fs.writeFileSync(path.join(ROOT, "workflow", "config.json"), JSON.stringify({ vector_search: { service_port: 1 } }));
fs.mkdirSync(path.join(PROJ, ".git"), { recursive: true });
fs.mkdirSync(path.join(PROJ, ".claude", "memory"), { recursive: true });

let detectorResult = { verdict: "ok", matches: [] };
const detectorCalls = [];
const funnel = require("../lib/funnel");
funnel.syncMemoryIndex = () => {};
funnel.triggerVectorReindex = () => {};
funnel.execConflictDetector = async (content, scope, projectCwd, subdir, declared, title) => {
  detectorCalls.push({ declared, title });
  return detectorResult;
};
const mcp = require("../lib/mcp");
const replies = new Map();
mcp.sendToolResult = (id, text, isError = false) => { replies.set(id, { text, isError }); };
const { toolAtomWrite } = require("../lib/atom-tools");

let nextId = 1;
async function write(args) {
  const id = nextId++;
  // skip_gate：品質／去重閘不是這支要驗的（realm 閘與衝突偵測照跑）
  await toolAtomWrite(id, { confidence: "[臨]", mode: "create", triggers: ["judg-smoke"], skip_gate: true, ...args });
  return replies.get(id) || { text: "(no reply)", isError: true };
}
const shared = (args) => write({ scope: "shared", project_cwd: PROJ, domain: "工作流", ...args });
const findFile = (dir, name) => {
  if (!fs.existsSync(dir)) return null;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) { const r = findFile(p, name); if (r) return r; } else if (e.name === name) return p;
  }
  return null;
};
const projFile = (slug) => findFile(path.join(PROJ, ".claude", "memory"), `${slug}.md`);
const KNOW = ["[臨] 衝突宣告接線測試用的知識行，夠長才過品質閘的最低長度要求，內容不重要"];

const failures = [];
function check(cond, label, detail) {
  if (cond) { console.log(`  ok   ${label}`); return; }
  failures.push(label);
  console.log(`  FAIL ${label}${detail ? "\n       " + String(detail).slice(0, 900) : ""}`);
}

(async () => {
  const cand = { atom_name: "old-card", classification: "CONTRADICT", similarity: 0.91, fact_preview: "舊卡說開" };

  // 1. 沒宣告 → 偵測器回 need_declaration → 不落檔、列候選與寫法
  detectorResult = { verdict: "need_declaration", candidates: [cand], matches: [cand], declaration_problem: "" };
  const r1 = await shared({ title: "judg-new-a", knowledge: KNOW });
  check(r1.isError && r1.text.startsWith("衝突待宣告（這次不寫檔）") && r1.text.includes("old-card") && r1.text.includes("not_conflict"),
    "need_declaration → refused with candidates and how-to", r1.text);
  check(!projFile("judg-new-a"), "need_declaration → no file written");
  check(detectorCalls.at(-1).declared === undefined && detectorCalls.at(-1).title === "judg-new-a", "detector got title, no declaration");

  // 2. 宣告不全 → 偵測器回問題 → 原樣轉述
  detectorResult = { ...detectorResult, declaration_problem: "衝突候選要逐一宣告：old-card：why 要寫一句理由" };
  const r2 = await shared({ title: "judg-new-a", knowledge: KNOW, conflict: [{ of: "old-card", verdict: "not_conflict", why: "" }] });
  check(r2.isError && r2.text.includes("宣告不收：衝突候選要逐一宣告"), "declaration problem relayed", r2.text);

  // 3. not_conflict → 偵測器回 ok → 照寫 shared、回覆附宣告
  const decl = [{ of: "old-card", verdict: "not_conflict", why: "舊卡講另一個專案的設定" }];
  detectorResult = { verdict: "ok", matches: [cand], declared: decl };
  const r3 = await shared({ title: "judg-new-b", knowledge: KNOW, conflict: decl });
  check(!r3.isError && projFile("judg-new-b") && !projFile("judg-new-b").includes("_pending_review")
        && r3.text.includes("conflict_declared: old-card=not_conflict"), "not_conflict → written to shared", r3.text);
  check(JSON.stringify(detectorCalls.at(-1).declared) === JSON.stringify(decl), "conflict passed to detector as-is");

  // 4. conflict → 偵測器回 contradict → 待審報告、不寫 shared、回覆帶理由
  detectorResult = { verdict: "contradict", primary: "old-card", matches: [cand],
                     declared: [{ of: "old-card", verdict: "conflict", why: "同一設定鍵一開一關" }] };
  const r4 = await shared({ title: "judg-new-c", knowledge: KNOW, conflict: [{ of: "old-card", verdict: "conflict", why: "同一設定鍵一開一關" }] });
  check(!r4.isError && r4.text.includes('BLOCKED — conflict declared vs "old-card"（理由：同一設定鍵一開一關）')
        && findFile(path.join(PROJ, ".claude", "memory"), "judg-new-c.conflict.md") && !projFile("judg-new-c"),
        "conflict → pending report, not written", r4.text);

  // 5. 舊偵測器的 extend_overlap 不再自動改道 _pending_review
  detectorResult = { verdict: "extend_overlap", matches: [{ ...cand, classification: "EXTEND" }] };
  const r5 = await shared({ title: "judg-new-d", knowledge: KNOW });
  check(!r5.isError && projFile("judg-new-d") && !projFile("judg-new-d").includes("_pending_review"),
        "extend_overlap no longer reroutes to _pending_review", r5.text + " → " + projFile("judg-new-d"));

  // 6. 型別錯 js 先拒
  const r6 = await shared({ title: "judg-new-e", knowledge: KNOW, conflict: "not_conflict" });
  check(r6.isError && /conflict must be an array/.test(r6.text), "conflict non-array rejected by js", r6.text);
  const r6a = await shared({ title: "judg-new-e", knowledge: KNOW, conflict: { of: "old-card", verdict: "conflict", why: "x" } });
  check(r6a.isError && /conflict must be an array/.test(r6a.text), "conflict bare object rejected (schema says array)", r6a.text);
  const r6b = await write({ scope: "global", realm: "local", domain: "MemDev", title: "judg-new-e", knowledge: KNOW, scope_reason: 1 });
  check(r6b.isError && /scope_reason must be a string/.test(r6b.text), "scope_reason non-string rejected by js", r6b.text);

  // 7. realm 閘：專案 cwd、只有字面「此專案」→ 擋並帶規則名；帶 scope_reason → 照寫、留帳
  detectorResult = { verdict: "ok", matches: [] };
  process.chdir(PROJ);
  const lit = ["[臨] 提到「此專案」這個詞的規則屬於專案規則，該寫 shared；這條本身是跨專案通則"];
  const r7 = await write({ scope: "global", domain: "工作流", title: "judg-literal", knowledge: lit });
  check(r7.isError && r7.text.includes("PROJECT_LITERAL_IS_HINT") && r7.text.includes("scope_reason"), "literal only → rejected with hint", r7.text);
  const r8 = await write({ scope: "global", domain: "工作流", title: "judg-literal", knowledge: lit,
                           scope_reason: "在講「此專案」這個詞本身怎麼判 scope，任何專案都適用" });
  process.chdir(ROOT);
  check(!r8.isError && /^Created atom: judg-literal\.md/.test(r8.text), "scope_reason → written", r8.text);
  const ledger = path.join(ROOT, "Logs", "guard-realm_declared.jsonl");
  check(fs.existsSync(ledger) && fs.readFileSync(ledger, "utf-8").includes("judg-literal"), "realm_declared ledger in temp data root", ledger);

  for (const d of [ROOT, PROJ]) { try { fs.rmSync(d, { recursive: true, force: true }); } catch {} }
  console.log(failures.length ? `ATOM_WRITE_JUDGMENTS_CHECK FAIL (${failures.length})` : "ATOM_WRITE_JUDGMENTS_CHECK PASS");
  process.exit(failures.length ? 1 : 0);
})().catch((e) => { console.error(e); console.log("ATOM_WRITE_JUDGMENTS_CHECK FAIL"); process.exit(1); });

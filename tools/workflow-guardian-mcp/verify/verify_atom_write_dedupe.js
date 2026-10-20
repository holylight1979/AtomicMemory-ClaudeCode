// verify_atom_write_dedupe.js — atom_write 去重交 AI 判的 MCP（js）端：真 py 寫入閘 + 真落檔，假向量服務給候選。
//   驗：沒宣告 → 要宣告（need_declaration）原文轉述（候選名／分數／節錄／三種寫法）且不落檔；dedupe 型別錯 js 先拒；
//   why 空／of 不在候選 → 拒並點名；supersedes → 新卡帶 `- Supersedes: <候選>`、audit 記 dedupe_declared；
//   same → 改 append 到候選卡、沒有新檔、回覆開頭講改併入哪張；different → 照常寫；沒命中給宣告 → 照寫附 note；
//   分數沒到門檻 → 照寫；向量服務沒起 → 照寫；write_gate.dedupe_declaration=false → 舊行為（similar → suggest update）。
// 隔離：WG_CLAUDE_DIR 指 os.tmpdir() 下的暫存資料根（require 任何 lib 之前設）；process.chdir 到該根（realm 閘視為核心層）；
//   寫入後的向量重索引照 config 的 service_port 打到假服務（順驗它不再寫死 live 3849）；目錄重產在 require atom-tools 前
//   換成空函式；sendToolResult 改成收進記憶體。
// 怎麼跑：node tools/workflow-guardian-mcp/verify/verify_atom_write_dedupe.js（尾行 ATOM_WRITE_DEDUPE_CHECK PASS|FAIL）
const fs = require("fs");
const os = require("os");
const path = require("path");
const http = require("http");

const CODE = path.resolve(__dirname, "..", "..", "..");
const ROOT = fs.mkdtempSync(path.join(os.tmpdir(), "wg-dedupe-"));
process.env.WG_CLAUDE_DIR = ROOT;
process.chdir(ROOT);
fs.mkdirSync(path.join(ROOT, "memory", "_meta"), { recursive: true });
for (const f of ["taxonomy.json", "realm-lexicon.json"]) {   // 範疇閘／核心保護清單照本樹
  fs.copyFileSync(path.join(CODE, "memory", "_meta", f), path.join(ROOT, "memory", "_meta", f));
}

let hits = [];   // 假向量服務這一刻要回的命中（照真服務先濾 min_score 再截 top_k）
let reindexCalls = 0;   // 寫入後的重索引要打到 config 指的這個服務（不是寫死的 live 3849）
const vector = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x");
  if (u.pathname === "/index/incremental") { reindexCalls++; res.writeHead(200); res.end("{}"); return; }
  const minScore = parseFloat(u.searchParams.get("min_score") || "0");
  const topK = parseInt(u.searchParams.get("top_k") || "5", 10);
  const rows = hits.filter((h) => h.score >= minScore).sort((a, b) => b.score - a.score).slice(0, topK);
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify(rows));
});

function writeConfig(port, writeGate) {
  fs.mkdirSync(path.join(ROOT, "workflow"), { recursive: true });
  fs.writeFileSync(path.join(ROOT, "workflow", "config.json"),
    JSON.stringify({ vector_search: { service_port: port }, write_gate: writeGate || {} }));
}

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
    scope: "global", realm: "local", domain: "MemDev", confidence: "[臨]", mode: "create",
    triggers: ["dedupe-smoke"], ...args,
  });
  return replies.get(id) || { text: "(no reply)", isError: true };
}
const atomPath = (slug) => path.join(ROOT, "_AIDocs", "_atoms", "MemDev", `${slug}.md`);
const auditRows = () => {
  try {
    return fs.readFileSync(path.join(ROOT, "memory", "_vectordb", "audit.log"), "utf-8")
      .split("\n").filter(Boolean).map((l) => JSON.parse(l));
  } catch { return []; }
};

const failures = [];
function check(cond, label, detail) {
  if (cond) { console.log(`  ok   ${label}`); return; }
  failures.push(label);
  console.log(`  FAIL ${label}${detail ? "\n       " + String(detail).slice(0, 900) : ""}`);
}

(async () => {
  await new Promise((r) => vector.listen(0, "127.0.0.1", r));
  const port = vector.address().port;
  writeConfig(port);

  // 0. 舊卡（skip_gate 不跑去重）
  const OLD = "dedupe-old-card";
  const w0 = await write({ title: OLD, skip_gate: true,
    knowledge: ["[臨] 舊卡第一行：hook 的 PreToolUse 在 payload 生成後才觸發", "[臨] 舊卡第二行：寫前提醒放 PostToolUse", "[臨] 第三行不節錄"] });
  check(!w0.isError && fs.existsSync(atomPath(OLD)), "setup: old card created", w0.text);
  await new Promise((r) => setTimeout(r, 300));   // 重索引是 fire-and-forget
  check(reindexCalls >= 1, `reindex hits the configured vector port, not live 3849 (calls=${reindexCalls})`);
  hits = [{ atom_name: OLD, score: 0.91, text: "chunk", file_path: atomPath(OLD), layer: "extra:local-atoms" }];
  const NEWK = ["[臨] hook 的 PreToolUse 拿到的是已生成的 Edit payload → 寫前提醒改放 PostToolUse，路徑 ~/.claude/hooks/x.py"];

  // 1. 沒宣告 → 拒、原文轉述、不落檔
  const r1 = await write({ title: "dedupe-new-a", knowledge: NEWK });
  check(r1.isError && /^Write-gate: 宣告不收|^Write-gate: 需要宣告/.test(r1.text) && r1.text.includes(`${OLD}（score=0.91，layer=extra:local-atoms）`)
        && r1.text.includes("｜[臨] 舊卡第一行") && !r1.text.includes("第三行不節錄")
        && ["same", "supersedes", "different"].every((v) => r1.text.includes(`"verdict":"${v}"`))
        && /searched layers: global, extra:local-atoms/.test(r1.text),
        "no declaration → need_declaration relayed verbatim", r1.text);
  check(!fs.existsSync(atomPath("dedupe-new-a")), "no declaration → no file written");

  // 2. dedupe 型別錯 → js 先拒（不 spawn py）
  const r2 = await write({ title: "dedupe-new-a", knowledge: NEWK, dedupe: "same" });
  check(r2.isError && /dedupe must be an object/.test(r2.text), "dedupe non-object rejected by js", r2.text);

  // 3. why 空／of 不在候選 → 拒並點名
  const r3 = await write({ title: "dedupe-new-a", knowledge: NEWK, dedupe: { verdict: "different", of: OLD, why: "...." } });
  check(r3.isError && r3.text.includes("宣告不收：why 要寫一句理由") && !fs.existsSync(atomPath("dedupe-new-a")),
        "why punctuation-only rejected, names why", r3.text);
  const r3b = await write({ title: "dedupe-new-a", knowledge: NEWK, dedupe: { verdict: "same", of: "not-a-candidate", why: "同一條" } });
  check(r3b.isError && r3b.text.includes("of「not-a-candidate」不在這次列出的候選卡裡") && r3b.text.includes(`1. ${OLD}`),
        "of outside candidates rejected, candidates relisted", r3b.text);

  // 4. supersedes → 新卡帶 Supersedes、audit 記 dedupe_declared
  const why4 = "舊卡的 trigger 寫法已改、本卡取代";
  const r4 = await write({ title: "dedupe-new-sup", knowledge: NEWK, dedupe: { verdict: "supersedes", of: OLD, why: why4 } });
  const sup = fs.existsSync(atomPath("dedupe-new-sup")) ? fs.readFileSync(atomPath("dedupe-new-sup"), "utf-8") : "";
  check(!r4.isError && /^Created atom: dedupe-new-sup\.md/.test(r4.text) && sup.includes(`- Supersedes: ${OLD}\n`)
        && r4.text.includes(`dedupe_declared: supersedes of=${OLD} score=0.91`)
        && /receipt: .*"supersedes":\["dedupe-old-card"\]/.test(r4.text),
        "supersedes → new card with Supersedes line + receipt", r4.text);
  const decl = auditRows().filter((a) => a.action === "dedupe_declared");
  check(decl.length === 1 && decl[0].verdict === "supersedes" && decl[0].of === OLD && decl[0].why === why4 && decl[0].score === 0.91,
        "audit has dedupe_declared row", JSON.stringify(decl));

  // 5. same → append 到候選卡、沒有新檔、回覆開頭講改併入哪張
  const before = fs.readFileSync(atomPath(OLD), "utf-8");
  const r5 = await write({ title: "dedupe-new-same", knowledge: ["[臨] 同一條的補充：PostToolUse 命中時順帶印提醒"],
    dedupe: { verdict: "same", of: OLD, why: "同一條：補一個實例" } });
  const after = fs.readFileSync(atomPath(OLD), "utf-8");
  check(!r5.isError && r5.text.startsWith(`dedupe 宣告 same：知識段改併入既有卡 ${OLD}`) && r5.text.includes("（理由：同一條：補一個實例）")
        && r5.text.includes(`Appended 1 knowledge lines to ${OLD}.md`) && /receipt: .*"op":"append"/.test(r5.text),
        "same → routed to append with route note", r5.text);
  check(after.includes("同一條的補充：PostToolUse 命中時順帶印提醒") && after.length > before.length && !fs.existsSync(atomPath("dedupe-new-same")),
        "same → knowledge appended to candidate, no new file");

  // 5b. same 走的是既有 append 路徑：合併後超預算照樣被擋（回覆開頭仍講改併入哪張）、候選卡不變
  const BIG = "dedupe-big-card";
  const pad = "這段是部位的真相與邊界說明".repeat(24);   // 一行約 870 bytes
  const wb = await write({ title: BIG, skip_gate: true, knowledge: [`[臨] 一 ${pad}`, `[臨] 二 ${pad}`, `[臨] 三 ${pad}`] });
  check(!wb.isError, "setup: near-budget card created", wb.text);
  const savedHits = hits;
  hits = [{ atom_name: BIG, score: 0.93, text: "chunk", file_path: atomPath(BIG), layer: "extra:local-atoms" }];
  const bigBefore = fs.readFileSync(atomPath(BIG), "utf-8");
  const r5b = await write({ title: "dedupe-new-big", knowledge: [`[臨] 補充 ${pad}`], dedupe: { verdict: "same", of: BIG, why: "同一條" } });
  check(r5b.isError && r5b.text.startsWith(`dedupe 宣告 same：知識段改併入既有卡 ${BIG}`) && /Write-gate rejected: knowledge 區 \d+ bytes/.test(r5b.text)
        && fs.readFileSync(atomPath(BIG), "utf-8") === bigBefore && !fs.existsSync(atomPath("dedupe-new-big")),
        "same → append path budget gate still rejects, card unchanged", r5b.text);
  hits = savedHits;

  // 6. different → 照常寫新卡
  const r6 = await write({ title: "dedupe-new-diff", knowledge: NEWK, dedupe: { verdict: "different", of: OLD, why: "舊卡講時序，本卡講路徑規則" } });
  check(!r6.isError && fs.existsSync(atomPath("dedupe-new-diff")) && !fs.readFileSync(atomPath("dedupe-new-diff"), "utf-8").includes("Supersedes")
        && r6.text.includes(`dedupe_declared: different of=${OLD}`), "different → new card, no Supersedes", r6.text);

  // 7. 分數沒到門檻 → 照寫；給了宣告 → 照寫附 note
  hits = [{ ...hits[0], score: 0.5 }];
  const r7 = await write({ title: "dedupe-low-score", knowledge: NEWK });
  check(!r7.isError && fs.existsSync(atomPath("dedupe-low-score")) && !/dedupe_declared|dedupe 宣告/.test(r7.text), "below threshold → written directly", r7.text);
  const r7b = await write({ title: "dedupe-low-score-decl", knowledge: NEWK, dedupe: { verdict: "same", of: OLD, why: "同一條" } });
  check(!r7b.isError && fs.existsSync(atomPath("dedupe-low-score-decl")) && r7b.text.includes("dedupe 宣告已忽略"),
        "no hit + declaration → written with note", r7b.text);

  // 8. 開關關掉 → 舊行為
  hits = [{ ...hits[0], score: 0.88 }];
  writeConfig(port, { dedupe_declaration: false });
  const r8 = await write({ title: "dedupe-flag-off", knowledge: NEWK, dedupe: { verdict: "different", of: OLD, why: "不同的事" } });
  check(r8.isError && r8.text.startsWith(`Write-gate: similar to ${OLD} (score=0.88), suggest update`) && !fs.existsSync(atomPath("dedupe-flag-off")),
        "dedupe_declaration=false → old suggest-update refusal", r8.text);

  // 9. 向量服務沒起 → 照寫（fail-open）
  writeConfig(1);   // port 1 沒人聽
  const r9 = await write({ title: "dedupe-vector-down", knowledge: NEWK });
  check(!r9.isError && fs.existsSync(atomPath("dedupe-vector-down")), "vector service down → fail-open write", r9.text);

  vector.close();
  process.chdir(os.tmpdir());   // Windows 刪不掉當前工作目錄：先離開暫存根再刪
  try { fs.rmSync(ROOT, { recursive: true, force: true }); } catch (e) { console.log(`  warn cleanup failed: ${ROOT} (${e.message})`); }
  if (failures.length) {
    console.log(`\nFAILED (${failures.length}): ${failures.join(" | ")}`);
    console.log("ATOM_WRITE_DEDUPE_CHECK FAIL");
    process.exit(1);
  }
  console.log("ATOM_WRITE_DEDUPE_CHECK PASS");
  process.exit(0);
})().catch((e) => {
  console.log("ERROR:", e && e.stack || e);
  console.log("ATOM_WRITE_DEDUPE_CHECK FAIL");
  process.exit(1);
});

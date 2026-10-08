// project-smells.js：MCP tool `project_smells` 的 Node 面：spawn `tools/project-smells.py --json`，
// 把專案壞味道報告變成「前 N 筆＋分類＋理由」表回給呼叫端（注入用候選池）。
// 不碰 state、不寫檔；spawn 有 setTimeout＋kill＋clearTimeout（25 s）；回應 ≤ 25KB。
// sendToolResult 來自 mcp.js（lazy-require，與 harvest.js 同模式）。

const path = require("path");
const { spawn } = require("child_process");
const { TOOLS_DIR, PYTHON_EXE } = require("./paths");

const SMELLS_PY = path.join(TOOLS_DIR, "project-smells.py");
const SMELLS_TIMEOUT_MS = 25000;
const REPLY_MAX_BYTES = 25 * 1024;
const CATEGORIES = ["hotspot", "size", "complexity", "duplication", "coupling", "stale", "custom"];

function validateArgs(a) {
  if (!a || typeof a !== "object") return "arguments 必須是物件";
  if (!String(a.part || "").trim()) return "part 必填（部位名；報告的 part 欄過濾／builtin 的掃描範圍）";
  if (!String(a.cwd || "").trim()) return "cwd 必填（專案內路徑，往上找 .claude/overview-hub.json）";
  return "";
}

/** spawn project-smells.py；25 s 逾時 kill。回 {out, err, code, timedOut, spawnError}。 */
function spawnSmells(cwd, part, topN) {
  return new Promise((resolve) => {
    const argv = ["-X", "utf8", SMELLS_PY, "--cwd", cwd, "--part", part, "--json"];
    if (Number.isInteger(topN) && topN > 0) argv.push("--top-n", String(topN));
    let cp;
    try {
      cp = spawn(PYTHON_EXE, argv, {
        cwd: path.dirname(SMELLS_PY), windowsHide: true,
        env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      });
    } catch (e) {
      return resolve({ out: "", err: "", code: null, timedOut: false, spawnError: e.message });
    }
    let out = "", err = "", timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      try { cp.kill(); } catch {}
    }, SMELLS_TIMEOUT_MS);
    cp.stdout.on("data", (d) => { out += d.toString("utf-8"); });
    cp.stderr.on("data", (d) => { if (err.length < 4000) err += d.toString("utf-8"); });
    cp.on("close", (code) => {
      clearTimeout(timer);
      resolve({ out, err, code, timedOut, spawnError: "" });
    });
    cp.on("error", (e) => {
      clearTimeout(timer);
      resolve({ out, err, code: null, timedOut, spawnError: e.message });
    });
  });
}

/** stdout = JSON 本體 + 最後一行哨兵；拆開回 {data, sentinel}。 */
function parseSmellsOutput(out) {
  const lines = String(out || "").trimEnd().split("\n");
  let sentinel = "";
  if (lines.length && /^PROJECT_SMELLS (DONE|FAIL)/.test(lines[lines.length - 1].trim())) sentinel = lines.pop().trim();
  let data = null;
  try { data = JSON.parse(lines.join("\n")); } catch {}
  return { data, sentinel };
}

function renderRows(data) {
  const lines = [];
  if (data.stale) lines.push(`stale: 報告已 ${data.age_days} 天（上限 ${data.max_age_days}），資料照回，請重產報告`);
  lines.push(`part=${data.part} source=${data.source} n=${(data.rows || []).length} dropped=${data.dropped || 0} unknown_category=${data.dropped_unknown_category || 0}`);
  if (Array.isArray(data.unknown_categories) && data.unknown_categories.length) {
    lines.push(`未映射類別（加進 overview-hub.json 的 smells_category_map）：${data.unknown_categories.join(", ")}`);
  }
  lines.push("rank | path | category | reason | source | age_days");
  for (const r of data.rows || []) {
    lines.push(`${r.rank} | ${r.path} | ${r.category} | ${r.reason} | ${r.source} | ${r.age_days}`);
  }
  let text = lines.join("\n");
  if (Buffer.byteLength(text, "utf-8") > REPLY_MAX_BYTES) text = text.slice(0, REPLY_MAX_BYTES) + "\n…（已截斷）";
  return text;
}

async function toolProjectSmells(id, args) {
  const { sendToolResult } = require("./mcp");
  const bad = validateArgs(args);
  if (bad) return sendToolResult(id, `project_smells 拒收：${bad}`, true);
  const res = await spawnSmells(String(args.cwd).trim(), String(args.part).trim(), args.top_n);
  if (res.spawnError) return sendToolResult(id, `project_smells 失敗：spawn 錯誤 ${res.spawnError}`, true);
  if (res.timedOut) return sendToolResult(id, `project_smells 失敗：子程序逾時（${SMELLS_TIMEOUT_MS / 1000}s）已 kill。smells_cmd 太慢就改成產報告檔並設 smells_report。`, true);
  const { data, sentinel } = parseSmellsOutput(res.out);
  if (!data || res.code !== 0) {
    const reason = (data && data.error) || sentinel || res.err.slice(0, 600) || `exit=${res.code}`;
    return sendToolResult(id, `project_smells 失敗：${reason}`, true);
  }
  return sendToolResult(id, renderRows(data));
}

module.exports = { toolProjectSmells, validateArgs, parseSmellsOutput, renderRows, SMELLS_PY, SMELLS_TIMEOUT_MS, CATEGORIES };

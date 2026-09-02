// anti-evasion.js — Anti-Evasion HUD 的 Node 面（扁平模組，不加抽象層）。
//
// one-writer spine：本檔的 tool handler 只回 chip、**不碰 state**；state/持久化/HUD spawn
// 由 Python PostToolUse（帶原始 session_id + turn_seq）獨佔（見 hooks/handlers/post_tool_use.py）。
// 本檔另供 HUD 唯讀 API：glob disk 上 Python 落的 aec-report/<sid>-t<turn>.json 供頁 +
// heartbeat（lazy-spawn 判窗死用）。港口持有者供頁、與哪個 session 的 MCP 跑了 tool 無關。
//
// 兩命名空間、各單一 writer（不互搶，維持 one-writer spine）：
//   report（<sid>-t<turn>.json）  = Python 寫 / Node 讀（唯讀 API 供 HUD）
//   ledger（aec-tempfiles/<sid>.jsonl）= Python 寫（handlers/aec_ledger.py）/ Node 讀 + exists() 過濾
//   decision（<sid>-p<pathhash>.json）= Node 寫（apiAecDecisionPost，HUD 殘檔面板保留/刪除鈕）/ Python 讀
//                                   （user_prompt_submit drain → 注入 → 模型 deferred 執行）
//
// sendToolResult 來自 mcp.js（循環相依：mcp.handleToolCall lazy-require 本檔，故 tool handler
// 內 lazy-require mcp 即可，載入順序無虞）。

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { WORKFLOW_DIR } = require("./paths");

// HUD 頁心跳（記憶體，港口持有者持有）；apiAecBeat 更新、apiAecBeatStatus 回 age_s。
let lastHudBeat = 0;

const REPORT_DIR = path.join(WORKFLOW_DIR, "aec-report");  // per-turn 報告檔子夾（檔名 <sid>-t<turn>.json）
const DECISION_DIR = path.join(WORKFLOW_DIR, "aec-decision");  // HUD 保留/刪除決策佇列（<sid>-t<turn>-<idx>.json）
const REPORT_CAP = 100;               // 唯讀 API 回傳上限（近 N 筆）
const SID_RE = /^[A-Za-z0-9-]+$/;     // 防路徑穿越：session_id 只允許 hex/hyphen

// ─── severity（純函式；與 Python wg_evasion.aec_severity 同規則、single source of truth）──
// (b) 真偷埋通報非空 → real-evasion；(a) 有真修補行 → notable；(a)(b) 皆「無」/空 → routine。
// (c)–(i) 為資訊性，不升級 severity（severity 只衡量「退避」訊號）。
function aecBlank(v) {
  // 放寬「無」認定含結尾標點（「無。」）；太嚴會把 routine 誤升 real-evasion → 洗 chat。
  // MIRROR: hooks/wg_evasion.py _aec_blank — keep in sync。
  const s = String(v == null ? "" : v).trim().replace(/[\s。．.,，、；;：:!！?？~～\-—…]+$/u, "");
  return s === "" || /^[無无]\s*(?:[（(][^）)]*[）)])?$/u.test(s);
}
function aecSeverity(a, b) {
  if (!aecBlank(b)) return "real-evasion";
  if (!aecBlank(a)) return "notable";
  return "routine";
}

// 摘取欄位前 n 個非空行（notable/real chip 短展開用）。
function firstLines(v, n) {
  const lines = String(v || "").split("\n").map((s) => s.trim()).filter(Boolean);
  const head = lines.slice(0, n).join(" / ");
  return lines.length > n ? head + " …" : head;
}

// ─── MCP tool handler（結構化 emit 表面；不碰 state）────────────────────────────
async function toolAntiEvasionReport(id, args) {
  const { sendToolResult } = require("./mcp");
  const a = String(args && args.a != null ? args.a : "");
  const b = String(args && args.b != null ? args.b : "");
  const sev = aecSeverity(a, b);

  let text;
  if (sev === "routine") {
    // routine → 折疊 chip 單行，不攤 prose。
    text = "anti_evasion_report ✓（routine）— 收尾檢核 (a)–(i) 已提交，內容走 HUD。";
  } else {
    // notable / real-evasion → chat 頂層一次（短展開摘要；完整內容走 HUD）。
    const lines = [`anti_evasion_report ⚠（${sev}）— 收尾檢核已提交（HUD 有完整 (a)–(i)）：`];
    if (!aecBlank(a)) lines.push("  (a) 缺失修補：" + firstLines(a, 3));
    if (!aecBlank(b)) lines.push("  (b) 逃避通報：" + firstLines(b, 3));
    text = lines.join("\n");
  }
  return sendToolResult(id, text);
}

// ─── HUD 唯讀 API ─────────────────────────────────────────────────────────────
function _json(res, code, data) {
  res.writeHead(code, { "Content-Type": "application/json" });
  res.end(JSON.stringify(data));
}

// glob WORKFLOW_DIR/aec-report/*.json → 依 at(→turn_seq) 新→舊排序。Fail-open 回 []。
function _readReports() {
  let files;
  try { files = fs.readdirSync(REPORT_DIR); }
  catch { return []; }
  const out = [];
  for (const f of files) {
    if (!f.endsWith(".json")) continue;   // 略過 .tmp（atomic write 過渡檔）
    try {
      out.push(JSON.parse(fs.readFileSync(path.join(REPORT_DIR, f), "utf-8")));
    } catch { /* skip corrupt / partial */ }
  }
  out.sort((x, y) =>
    String(y.at || "").localeCompare(String(x.at || "")) ||
    (Number(y.turn_seq) || 0) - (Number(x.turn_seq) || 0)
  );
  return out;
}

// GET /api/aec/reports[?since=<iso>] — 最新卡 + 歷史格清單（增量：at > since）。
function apiAecReports(req, res, since) {
  let reports = _readReports();
  if (since) reports = reports.filter((r) => String(r.at || "") > since);
  _json(res, 200, { reports: reports.slice(0, REPORT_CAP) });
}

// GET /api/aec/report/<sid>/<turn> — 單一回合完整報告（歷史格點開）。
function apiAecReport(req, res, sid, turn) {
  if (!SID_RE.test(String(sid || "")) || !/^\d+$/.test(String(turn || ""))) {
    return _json(res, 404, { error: "bad params" });
  }
  const p = path.join(REPORT_DIR, `${sid}-t${turn}.json`);
  try {
    _json(res, 200, JSON.parse(fs.readFileSync(p, "utf-8")));
  } catch {
    _json(res, 404, { error: "not found" });
  }
}

// GET /api/aec/beat — HUD 頁心跳（開著時每 Ns 打）。
function apiAecBeat(req, res) {
  lastHudBeat = Date.now();
  _json(res, 200, { ok: true });
}

// GET /api/aec/beat-status — 回 age_s（Python _maybe_spawn_hud 判窗死用）。
function apiAecBeatStatus(req, res) {
  const age_s = lastHudBeat ? Math.round((Date.now() - lastHudBeat) / 1000) : 999999;
  _json(res, 200, { age_s });
}

// ─── 殘檔帳本讀端（Python 寫 aec-tempfiles/<sid>.jsonl / Node 讀 + exists() 過濾）────────
// 帳本只記「進過帳」的路徑；「還在不在」由此處當下 fs.existsSync 判定——檔案系統才是權威，
// 消失的自動掉出清單、還在的持續列到被處置為止（不做 TTL）。
const LEDGER_DIR = path.join(WORKFLOW_DIR, "aec-tempfiles");

function _pathKey(p) {
  // 與 Python aec_ledger._key 同義：normalize + 小寫（Windows 不分大小寫）。
  return path.normalize(String(p || "")).replace(/[\\/]+$/, "").toLowerCase();
}

function _decisionFile(sid, p) {
  const h = crypto.createHash("sha1").update(_pathKey(p)).digest("hex").slice(0, 12);
  return path.join(DECISION_DIR, `${sid}-p${h}.json`);
}

// 讀帳本 → 去重（後寫者勝）→ exists() 過濾 → 掛上既有決策（同 sid、同路徑 hash 的決策檔）。
function readLedgerAlive(sid) {
  let text;
  try { text = fs.readFileSync(path.join(LEDGER_DIR, `${sid}.jsonl`), "utf-8"); }
  catch { return []; }
  const seen = new Map();
  for (const line of text.split("\n")) {
    const s = line.trim();
    if (!s) continue;
    try {
      const rec = JSON.parse(s);
      if (rec && rec.path) seen.set(_pathKey(rec.path), rec);
    } catch { /* skip corrupt line */ }
  }
  const out = [];
  for (const rec of seen.values()) {
    let exists = false;
    try { exists = fs.existsSync(rec.path); } catch { exists = false; }
    if (!exists) continue;
    let decision = null;
    try {
      const d = JSON.parse(fs.readFileSync(_decisionFile(sid, rec.path), "utf-8"));
      if (d && (d.action === "keep" || d.action === "delete")) {
        decision = { action: d.action, injected: !!d.injected, verified: !!d.verified };
      }
    } catch { /* no decision yet */ }
    out.push({
      path: rec.path, note: rec.note || "", source: rec.source || "", at: rec.at || "",
      decision,
    });
  }
  out.sort((x, y) => String(x.at).localeCompare(String(y.at)) || x.path.localeCompare(y.path));
  return out;
}

// GET /api/aec/tempfiles/<sid> — 該 session 帳本中「此刻仍存在」的殘檔（含既有決策）。
function apiAecTempfiles(req, res, sid) {
  if (!SID_RE.test(String(sid || ""))) return _json(res, 404, { error: "bad params" });
  _json(res, 200, { sid, items: readLedgerAlive(sid) });
}

// ─── AEC decision 寫入端（Node 唯一 writer；HUD 殘檔面板 保留/刪除鈕）──────────────
function _readBody(req, cb) {
  let body = "";
  req.on("data", (ch) => (body += ch));
  req.on("end", () => { try { cb(body ? JSON.parse(body) : {}); } catch { cb(null); } });
}

// POST /api/aec/decision — 殘檔逐項 保留/刪除 決策落磁碟。
// body: {sid, path, note?, action:"keep"|"delete"}。決策檔以路徑 hash 命名（<sid>-p<hash>.json）
// → 跨回合穩定；同路徑重點擊→覆寫同檔（reset injected:false → Python drain 重注入新決策）。
// item 欄 = "<path> — <note>" 供 Python 注入文字；path 欄供 exists() 後驗。
// atomic tmp→rename，Python glob 略過 .tmp。loopback 信任模型：無 auth，僅 127.0.0.1。
function apiAecDecisionPost(req, res) {
  _readBody(req, (body) => {
    if (!body) return _json(res, 400, { error: "bad json" });
    const sid = String(body.sid == null ? "" : body.sid);
    const p = String(body.path == null ? "" : body.path).trim();
    const note = String(body.note == null ? "" : body.note).trim();
    const action = String(body.action == null ? "" : body.action);
    if (!SID_RE.test(sid) || !p || p.length > 1000 || p.includes("\n")) {
      return _json(res, 404, { error: "bad params" });   // SID_RE 防路徑穿越
    }
    if (action !== "keep" && action !== "delete") {
      return _json(res, 400, { error: "bad action" });
    }
    const record = {
      session_id: sid,
      path: p,
      item: note ? `${p} — ${note}` : p,
      action,
      at: new Date().toISOString(),
      injected: false,
    };
    try {
      fs.mkdirSync(DECISION_DIR, { recursive: true });
      const f = _decisionFile(sid, p);
      const tmp = f + ".tmp";
      fs.writeFileSync(tmp, JSON.stringify(record, null, 2), "utf-8");
      fs.renameSync(tmp, f);   // atomic
    } catch {
      return _json(res, 500, { error: "write failed" });
    }
    _json(res, 200, { ok: true, action });
  });
}

module.exports = {
  aecBlank, aecSeverity,
  toolAntiEvasionReport,
  apiAecReports, apiAecReport, apiAecBeat, apiAecBeatStatus,
  apiAecTempfiles, readLedgerAlive,
  apiAecDecisionPost,
};

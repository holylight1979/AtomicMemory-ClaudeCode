// anti-evasion.js — Anti-Evasion HUD 的 Node 面（扁平模組，不加抽象層）。
//
// one-writer spine：本檔的 tool handler 只回 chip、**不碰 state**；state/持久化/HUD spawn
// 由 Python PostToolUse（帶原始 session_id + turn_seq）獨佔（見 hooks/handlers/post_tool_use.py）。
// 本檔另供 HUD 唯讀 API：glob disk 上 Python 落的 aec-report/<sid>-t<turn>.json 供頁 +
// heartbeat（lazy-spawn 判窗死用）。港口持有者供頁、與哪個 session 的 MCP 跑了 tool 無關。
//
// 兩個檔、都由 Python 單一寫入（Node 不寫，維持 one-writer spine）：
//   report（<sid>-t<turn>.json）       = Python PostToolUse 寫 / Node 讀（唯讀 API 供 HUD）
//   ledger（aec-tempfiles/<sid>.jsonl）= Python 寫（handlers/aec_ledger.py）/ Node 不直接讀：
//     列表與保留／刪除都轉呼叫 tools/session-artifacts.py（現場查還在不在、當場刪、結果由它寫回帳本）
//
// sendToolResult 來自 mcp.js（循環相依：mcp.handleToolCall lazy-require 本檔，故 tool handler
// 內 lazy-require mcp 即可，載入順序無虞）。

const fs = require("fs");
const path = require("path");
const { execFile } = require("child_process");
const { WORKFLOW_DIR, CODE_DIR, PYTHON_EXE } = require("./paths");

// HUD 頁心跳（記憶體，港口持有者持有）；apiAecBeat 更新、apiAecBeatStatus 回 age_s + clients。
let lastHudBeat = 0;

const REPORT_DIR = path.join(WORKFLOW_DIR, "aec-report");  // per-turn 報告檔子夾（檔名 <sid>-t<turn>.json）
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

// ─── (d)/(h) pending：把「記憶寫入」推到之後（純函式；MIRROR hooks/wg_evasion.py
// _AEC_PENDING_RE / _AEC_DONE_RE / _AEC_H_ATOM_RE / aec_pending_items — keep in sync）──
const AEC_PENDING_RE = /(?:尚未|還沒|還未|沒有|未)\s*(?:寫|記|落|建|補)|待\s*(?:寫|補|記|落|建)|(?:稍後|之後|回頭|等會|等一下|晚點|下輪|下回|下個\s*session|下一動)\s*(?:再)?\s*(?:寫|補|記|落|建)|見下一動|TODO|pending/iu;
const AEC_DONE_RE = /已\s*(?:寫|append|更新|replace|併|補|落|記|建)|不寫|不記|不落/iu;
const AEC_H_ATOM_RE = /(?:寫|補|建|落|記)[^，,；;。]{0,12}?(?:atom|記憶|知識)|atom_write/iu;

function aecVerdict(line) {
  // `- <項目> → <結論>` 取最後一個箭頭後的結論段；無箭頭取整行。
  for (const arrow of ["→", "->"]) {
    const i = line.lastIndexOf(arrow);
    if (i >= 0) line = line.slice(i + arrow.length);
  }
  return line.trim();
}
function aecPendingItems(d, h) {
  const out = [];
  for (const line of String(d == null ? "" : d).split("\n")) {
    const verdict = aecVerdict(line);
    if (!verdict || AEC_DONE_RE.test(verdict)) continue;
    if (AEC_PENDING_RE.test(verdict)) out.push(line.trim().slice(0, 120));
  }
  const hs = String(h == null ? "" : h).trim();
  if (hs.includes("下一動") && AEC_H_ATOM_RE.test(hs)) out.push("(h) " + hs.slice(0, 120));
  return out;
}

// ─── (j) 證據持久路徑／(k) 追蹤項（純函式；MIRROR hooks/wg_verify_ledger.py aec_evidence_missing /
// aec_evidence_autofill / aec_followups_missing；keep in sync）。Node 端不知道本 session 有沒有驗證收據、
// 也不知道 session id（state 與帳本路徑是 Python 的），tool handler 不印 (j)：帶入帳本路徑與缺漏回告由
// Python PostToolUse 做，擋的判定在 Python Stop。
function aecEvidenceMissing(j, receiptsNonEmpty) {
  if (!receiptsNonEmpty) return false;
  if (aecBlank(j)) return true;
  for (const raw of String(j == null ? "" : j).split("\n")) {
    const p = raw.trim().split(" \u2014 ")[0].split(" - ")[0].trim().replace(/^`|`$/g, "");
    if (!p) continue;
    let ok = false;
    try { ok = fs.existsSync(p.replace(/^~(?=[\\/]|$)/, require("os").homedir())); } catch { ok = false; }
    if (!ok) return true;
  }
  return false;
}
// 有收據、j 空／「無」、帳本檔在 → 回帳本絕對路徑；其餘回原 j（模型填了別的路徑就用模型填的）。
function aecEvidenceAutofill(j, receiptsNonEmpty, ledger) {
  let has = false;
  try { has = fs.existsSync(ledger); } catch { has = false; }
  if (receiptsNonEmpty && aecBlank(j) && has) return ledger;
  return String(j == null ? "" : j);
}
function aecFollowupsMissing(k) {
  return String(k == null ? "" : k).trim() === "";
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
  const pending = aecPendingItems(args && args.d, args && args.h);

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
  if (aecFollowupsMissing(args && args.k_followups)) {
    text += "\n⛔ (k) 追蹤項是空字串：有就一行一項，沒有寫「無」；否則 Stop 會擋。";
  }
  if (pending.length) {
    // 報告是收尾檢核不是待辦清單：記憶寫入推到之後 → 當下回告（Python Stop 另擋一次）。
    text += "\n⛔ (d)/(h) 有 " + pending.length + " 項把記憶寫入推到之後：\n" +
      pending.map((x) => "  ✗ " + x).join("\n") +
      "\n現在 atom_write 寫完，再重新呼叫 anti_evasion_report 改成「→ 已寫入 atom <名>」；否則 Stop 會擋。";
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

// GET /api/aec/beat — HUD 頁心跳（主執行緒剛把報告畫上去才打；頁被瀏覽器凍結/節流時會停）。
function apiAecBeat(req, res) {
  lastHudBeat = Date.now();
  _json(res, 200, { ok: true });
}

// GET /api/aec/stream — HUD 頁常駐連線（SSE，內容不走這條、只當存在證明）。
// 窗開著＝連線在：Edge --app 視窗被遮住久了瀏覽器會休眠/凍結頁面、心跳全停，但 TCP 連線
// 仍掛著；視窗關閉／分頁丟棄才斷。hudClients.size 是 Python 判「窗開著」的主證據，心跳為輔。
const hudClients = new Set();
let hudPing = null;
function apiAecStream(req, res) {
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
  });
  res.write(": hud\n\n");
  hudClients.add(res);
  const drop = () => { hudClients.delete(res); };
  res.on("close", drop);
  res.on("error", drop);   // 對端消失後的寫入錯誤：剔除，不得 unhandled 'error' 炸掉行程
  if (!hudPing) {
    // 15s 註解 ping：對端死掉（瀏覽器崩潰、機器休眠）時寫入失敗 → close → 剔除，連線數不虛高
    hudPing = setInterval(() => {
      for (const c of hudClients) {
        try { c.write(": ping\n\n"); } catch { hudClients.delete(c); }
      }
      if (!hudClients.size) { clearInterval(hudPing); hudPing = null; }
    }, 15000);
    hudPing.unref();
  }
}

// GET /api/aec/beat-status — Python _hud_alive 判窗用：clients（HUD 頁連線數）為主、age_s 為輔。
function apiAecBeatStatus(req, res) {
  const age_s = lastHudBeat ? Math.round((Date.now() - lastHudBeat) / 1000) : 999999;
  _json(res, 200, { age_s, clients: hudClients.size });
}

// ─── 產出物帳本（Python 寫 aec-tempfiles/<sid>.jsonl；查與刪都轉呼叫 tools/session-artifacts.py）────
// 「還在不在、能不能刪」要問 git（工作樹、分支）與保護規則，只在 Python 留一份；Node 只轉呼叫。
// 列表快取 10 秒（HUD 每 1.5 秒輪詢，不能每次都起 Python）；帳本變了或按了按鈕就作廢。
const LEDGER_DIR = path.join(WORKFLOW_DIR, "aec-tempfiles");
const ARTIFACTS_CLI = path.join(CODE_DIR, "tools", "session-artifacts.py");
const LIST_TTL_MS = 10000;
const _listCache = new Map();   // sid → {at, mtime, data, pending}

function _runArtifacts(args, timeoutMs) {
  return new Promise((resolve) => {
    execFile(PYTHON_EXE, ["-X", "utf8", ARTIFACTS_CLI, ...args, "--json"],
      { cwd: CODE_DIR, windowsHide: true, timeout: timeoutMs, encoding: "utf-8", maxBuffer: 4 * 1024 * 1024 },
      (err, stdout, stderr) => {
        const first = String(stdout || "").split("\n")[0].trim();
        try { return resolve(JSON.parse(first)); } catch { /* fall through */ }
        resolve({ ok: false, error: true,
          message: "清單工具沒有回應：" + String((err && err.message) || stderr || "空輸出").slice(0, 200) });
      });
  });
}

function _ledgerMtime(sid) {
  try { return fs.statSync(path.join(LEDGER_DIR, `${sid}.jsonl`)).mtimeMs; } catch { return 0; }
}

// GET /api/aec/tempfiles/<sid> — 這個 session 帳上還在的東西（含白話狀態、上次保留／刪除的結果）。
function apiAecTempfiles(req, res, sid) {
  if (!SID_RE.test(String(sid || ""))) return _json(res, 404, { error: "bad params" });
  const mtime = _ledgerMtime(sid);
  if (!mtime) return _json(res, 200, { sid, items: [] });
  const c = _listCache.get(sid);
  if (c && c.data && c.mtime === mtime && Date.now() - c.at < LIST_TTL_MS) return _json(res, 200, c.data);
  const entry = c && c.pending ? c : { pending: null, data: c && c.data, at: 0, mtime: 0 };
  if (!entry.pending) {
    entry.pending = _runArtifacts(["list", "--sid", sid], 30000).then((data) => {
      const ok = data && Array.isArray(data.items);
      Object.assign(entry, ok ? { data, at: Date.now(), mtime } : {}, { pending: null });
      return ok ? data : (entry.data || { sid, items: [], error: data && data.message });
    });
    _listCache.set(sid, entry);
  }
  entry.pending.then((data) => _json(res, 200, data));
}

// GET /api/aec/tempfiles-all — 全機殘留：全部帳本裡還在的東西，依 session 分組（附 session 還開著沒有）。
// 掃全部帳本要查 git，比單一 session 慢：快取 30 秒、同時只跑一支；按了任何保留／刪除就作廢。
const ALL_TTL_MS = 30000;
const _allCache = { at: 0, data: null, pending: null };
function apiAecTempfilesAll(req, res) {
  if (_allCache.data && Date.now() - _allCache.at < ALL_TTL_MS) return _json(res, 200, _allCache.data);
  if (!_allCache.pending) {
    _allCache.pending = _runArtifacts(["list", "--all"], 120000).then((data) => {
      const ok = data && Array.isArray(data.sessions);
      if (ok) Object.assign(_allCache, { data, at: Date.now() });
      _allCache.pending = null;
      return ok ? data : { sessions: [], total: 0, error: (data && data.message) || "清單工具沒有回應" };
    });
  }
  _allCache.pending.then((data) => _json(res, 200, data));
}

function _readBody(req, cb) {
  let body = "";
  req.on("data", (ch) => (body += ch));
  req.on("end", () => { try { cb(body ? JSON.parse(body) : {}); } catch { cb(null); } });
}

// POST /api/aec/decision — HUD 的保留／刪除鈕：body {sid, key, action:"keep"|"delete", force?}；
// 全機殘留的「整組清」：body {sid, all_safe:true, action:"delete"}（只刪不用再確認的，Python 現場判）。
// 當場交給 Python 執行並回 {ok, message, needs_confirm}；needs_confirm 有值＝要使用者再確認一次（HUD 帶 force 重送）。
// key 只能指名帳上那一項（Python 端比對帳本），不能拿來刪任意路徑。loopback 信任模型：無 auth，僅 127.0.0.1。
function apiAecDecisionPost(req, res) {
  _readBody(req, (body) => {
    if (!body) return _json(res, 400, { error: "bad json" });
    const sid = String(body.sid == null ? "" : body.sid);
    const key = String(body.key == null ? "" : body.key);
    const action = String(body.action == null ? "" : body.action);
    const allSafe = body.all_safe === true;
    if (!SID_RE.test(sid) || (!allSafe && (!key || key.length > 2000 || /[\r\n]/.test(key)))) {
      return _json(res, 404, { error: "bad params" });
    }
    if (action !== "keep" && action !== "delete") return _json(res, 400, { error: "bad action" });
    if (allSafe && (action !== "delete" || body.force)) return _json(res, 400, { error: "all_safe 只配 delete、不帶 force" });
    const args = allSafe ? ["act", "--sid", sid, "--all-safe", "--action", "delete"]
      : ["act", "--sid", sid, "--key", key, "--action", action, ...(body.force ? ["--force"] : [])];
    _runArtifacts(args, allSafe ? 300000 : 90000).then((r) => {
      _listCache.delete(sid);
      Object.assign(_allCache, { data: null, at: 0 });
      _json(res, 200, r);
    });
  });
}

module.exports = {
  aecBlank, aecSeverity, aecPendingItems, aecEvidenceMissing, aecEvidenceAutofill, aecFollowupsMissing,
  toolAntiEvasionReport,
  apiAecReports, apiAecReport, apiAecBeat, apiAecBeatStatus, apiAecStream,
  apiAecTempfiles, apiAecTempfilesAll,
  apiAecDecisionPost,
};

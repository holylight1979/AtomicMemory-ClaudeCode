// aec-hud-html.js — Anti-Evasion HUD 頁模板。匯出 render()->string（鏡像 dashboard-html.js）。
//
// dark HUD 單頁：即時最新收尾檢核卡（(a)–(i) 分區；舊報告僅 a–d）+ 底部近 N 回合 severity 歷史格。
// 傳輸＝輪詢（非 SSE）：setInterval 1.5s fetch /api/aec/reports（增量 ?since=）→ 渲染；
// 格子 click → fetch /api/aec/report/<sid>/<turn> 展開；每 10s fetch /api/aec/beat 送心跳。
//
// 視覺（dataviz skill 驗證）：severity 為 status palette，CVD ΔE 44.6（>>12）+ 皆 ≥3:1；
// routine=靜色灰 / notable=琥珀 / real-evasion=紅，且每格附文字標籤（secondary encoding，
// 非 color-alone）。surface 用 github-dark（與 dashboard-html.js 同族）。
//
// ★內層 <script> 為瀏覽器端 JS（非模組 state）：整塊 verbatim、**勿 hoist**（比照 _MAP C7）；
// 為免 nested-backtick，瀏覽器端一律字串串接、不用 template literal。

function render() {
  return `<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anti-Evasion HUD</title>
<style>
  :root {
    --plane: #0d1117; --surface-1: #161b22; --surface-2: #1c222b;
    --border: #30363d; --ink: #e6edf3; --ink-2: #c9d1d9; --muted: #8b949e;
    --sev-routine: #8b949e; --sev-notable: #fab219; --sev-real: #d03b3b;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background: var(--plane); color: var(--ink-2); padding: 18px; }
  h1 { color: var(--ink); font-size: 1.15em; letter-spacing: .3px; }
  .sub { color: var(--muted); font-size: .78em; margin-top: 2px; }
  .top { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 14px; }
  .poll { font-size: .74em; color: var(--muted); }
  .poll .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #3fb950; margin-right: 5px; vertical-align: middle; }
  .card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 16px; }
  .card.sev-notable { border-left: 3px solid var(--sev-notable); }
  .card.sev-real { border-left: 3px solid var(--sev-real); }
  .card-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
  .badge { font-size: .72em; font-weight: 700; padding: 3px 9px; border-radius: 20px; letter-spacing: .3px; }
  .badge.routine { background: #8b949e26; color: var(--sev-routine); border: 1px solid #8b949e55; }
  .badge.notable { background: #fab21926; color: var(--sev-notable); border: 1px solid #fab21966; }
  .badge.real { background: #d03b3b26; color: #ff9a9a; border: 1px solid #d03b3b88; }
  .meta { font-size: .76em; color: var(--muted); font-family: ui-monospace, monospace; }
  .banner { display: none; background: #d03b3b1f; border: 1px solid #d03b3b88; color: #ffb4b4; padding: 8px 12px; border-radius: 8px; font-size: .82em; margin-bottom: 14px; }
  .banner.show { display: block; }
  .sec { border-top: 1px solid var(--border); padding: 9px 0; }
  .sec:first-of-type { border-top: none; }
  .sec-h { font-size: .78em; font-weight: 600; color: var(--ink); margin-bottom: 3px; }
  .sec-h .k { color: var(--muted); font-weight: 400; }
  .sec-body { font-size: .82em; white-space: pre-wrap; color: var(--ink-2); font-family: ui-monospace, monospace; line-height: 1.45; }
  .sec-body.blank { color: #545d68; font-family: inherit; font-style: italic; }
  .grid-wrap { margin-top: 4px; }
  .grid-h { font-size: .8em; color: var(--ink); margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
  .legend { font-size: .72em; color: var(--muted); display: flex; gap: 12px; }
  .legend i { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
  .grid { display: flex; flex-wrap: wrap; gap: 5px; }
  .cell { width: 26px; height: 26px; border-radius: 5px; border: 1px solid var(--border); cursor: pointer; position: relative; display: flex; align-items: center; justify-content: center; font-size: .6em; color: #0d1117cc; font-weight: 700; transition: transform .08s; }
  .cell:hover { transform: scale(1.12); outline: 1px solid var(--ink-2); }
  .cell.routine { background: var(--sev-routine); }
  .cell.notable { background: var(--sev-notable); }
  .cell.real { background: var(--sev-real); box-shadow: 0 0 0 2px #d03b3b55; }
  .cell.active { outline: 2px solid var(--ink); }
  .empty { color: var(--muted); font-size: .82em; padding: 24px 0; text-align: center; }
  .dec-list { font-family: inherit; }
  .dec-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 4px 0; border-top: 1px dashed #ffffff0f; }
  .dec-row:first-child { border-top: none; }
  .dec-item { flex: 1; min-width: 0; word-break: break-all; }
  .dec-row.dec-done .dec-item { color: #545d68; }
  .dec-btns { flex-shrink: 0; display: flex; gap: 6px; align-items: center; }
  .aec-dec-btn { font-size: .72em; padding: 3px 10px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface-2); color: var(--ink-2); cursor: pointer; }
  .aec-dec-btn:hover { border-color: var(--ink-2); }
  .aec-dec-btn.danger { color: #ff9a9a; border-color: #d03b3b66; }
  .aec-dec-btn.danger:hover { background: #d03b3b26; border-color: #d03b3b; }
  .dec-status { font-size: .74em; color: var(--muted); }
</style>
</head>
<body>
  <div class="top">
    <div>
      <h1>Anti-Evasion HUD</h1>
      <div class="sub">收尾檢核 (a)–(i) · severity-gated · 唯讀歷史</div>
    </div>
    <div class="poll"><span class="dot"></span><span id="poll-txt">輪詢中…</span></div>
  </div>

  <div id="banner" class="banner"></div>
  <div id="card-slot">
    <div class="card"><div class="empty">尚無收尾檢核報告。動 core 檔並宣告完成、呼叫 anti_evasion_report 後出現。</div></div>
  </div>
  <div id="temp-slot"></div>

  <div class="grid-wrap">
    <div class="grid-h">
      <span>近 ${64} 回合</span>
      <span class="legend">
        <span><i style="background:var(--sev-routine)"></i>routine</span>
        <span><i style="background:var(--sev-notable)"></i>notable</span>
        <span><i style="background:var(--sev-real)"></i>real-evasion</span>
      </span>
    </div>
    <div id="grid" class="grid"></div>
  </div>

<script>
// 瀏覽器端（勿 hoist；字串串接、不用 template literal）。
var POLL_MS = 1500, BEAT_MS = 10000, GRID_N = 64;
var SEV = {
  "routine":      { cls: "routine", label: "routine" },
  "notable":      { cls: "notable", label: "notable" },
  "real-evasion": { cls: "real",    label: "real-evasion" }
};
var activeKey = null;   // 使用者點選的歷史格（null=跟隨最新）
var reports = [];       // 新→舊

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>]/g, function (ch) {
    return ch === "&" ? "&amp;" : ch === "<" ? "&lt;" : "&gt;";
  });
}
function isBlank(v) { var s = String(v == null ? "" : v).trim(); return s === "" || s === "無"; }
function sevOf(r) { return SEV[r && r.severity] || SEV.routine; }
function keyOf(r) { return (r.session_id || "?") + "|" + (r.turn_seq != null ? r.turn_seq : "?"); }

function sectionHtml(letter, name, val) {
  var blank = isBlank(val);
  var body = blank
    ? '<div class="sec-body blank">無</div>'
    : '<div class="sec-body">' + esc(val) + "</div>";
  return '<div class="sec"><div class="sec-h">(' + letter + ') ' + name +
         ' <span class="k"></span></div>' + body + "</div>";
}

function escAttr(s) { return esc(s).replace(/"/g, "&quot;"); }

// 殘檔面板：資料來自 /api/aec/tempfiles/<sid>（Python 帳本 + Node 當下 exists() 過濾），
// 不從 (i) prose 猜——(i) 只是宣告來源之一，「還在不在」以檔案系統為準。每列 保留/刪除
// 兩鈕都給（使用者決定權），刪除經 confirm() 二次確認；已決者顯示狀態但仍可改按（覆寫）。
// 注意：本 script 整塊在外層 render() 的 template literal 內，字串/comment 中的反斜線
// 都須 \\ 跳脫，否則會在 render 時被 outer JS 當跳脫序列吃掉（換行字元須寫 "\\n"）。
function tempRow(sid, it) {
  var d = it.decision;
  var status = "";
  if (d) {
    status = '<span class="dec-status">' + (d.action === "delete" ? "已排定刪除 🗑" : "已排定保留 📌") +
             (d.action === "delete" && d.injected ? "（已通知模型，仍在）" : "") + "</span>";
  }
  var attrs = ' data-sid="' + escAttr(String(sid)) + '" data-path="' + escAttr(String(it.path)) +
              '" data-note="' + escAttr(String(it.note || "")) + '"';
  var btns = status +
    '<button class="aec-dec-btn"' + attrs + ' data-action="keep">保留</button>' +
    '<button class="aec-dec-btn danger"' + attrs + ' data-action="delete">刪除</button>';
  var meta = (it.source ? esc(it.source) : "") + (it.note ? " · " + esc(it.note) : "");
  return '<div class="dec-row' + (d ? " dec-done" : "") + '">' +
         '<span class="dec-item">' + esc(it.path) +
           (meta ? '<span class="k"> — ' + meta + "</span>" : "") + "</span>" +
         '<span class="dec-btns">' + btns + "</span></div>";
}

function renderTemp(sid, items) {
  var slot = document.getElementById("temp-slot");
  if (!sid) { slot.innerHTML = ""; return; }
  var head = '<div class="card"><div class="sec"><div class="sec-h">本 session 尚存殘檔 ' +
             '<span class="k">· session ' + esc(String(sid).slice(0, 8)) + " · 帳本 ∪ scratchpad，當下 exists() 過濾 · " +
             (items.length ? items.length + " 項" : "0 項") + "</span></div>";
  if (!items.length) {
    slot.innerHTML = head + '<div class="sec-body blank">無殘檔（帳上路徑皆已不在磁碟）</div></div></div>';
    return;
  }
  var rows = "";
  for (var i = 0; i < items.length; i++) { rows += tempRow(sid, items[i]); }
  slot.innerHTML = head + '<div class="sec-body dec-list">' + rows + "</div></div></div>";
  var btns = slot.querySelectorAll(".aec-dec-btn");
  for (var b = 0; b < btns.length; b++) { btns[b].addEventListener("click", onDecClick); }
}

var lastTempKey = "";   // 上次已渲染的 sid|json，同內容不重繪（避免每 1.5s 閃）
function pollTemp(sid) {
  if (!sid) { renderTemp("", []); return; }
  fetch("/api/aec/tempfiles/" + encodeURIComponent(sid))
    .then(function (res) { return res.ok ? res.json() : { items: [] }; })
    .then(function (j) {
      var items = (j && j.items) || [];
      var key = sid + "|" + JSON.stringify(items);
      if (key === lastTempKey) { return; }
      lastTempKey = key;
      renderTemp(sid, items);
    })
    .catch(function () {});
}

function renderCard(r) {
  var slot = document.getElementById("card-slot");
  if (!r) { return; }
  var s = sevOf(r);
  var sid = String(r.session_id || "?").slice(0, 8);
  var cls = "card" + (s.cls === "notable" ? " sev-notable" : s.cls === "real" ? " sev-real" : "");
  var badgeCls = s.cls === "real" ? "real" : s.cls;
  var html = '<div class="' + cls + '">' +
    '<div class="card-head">' +
      '<span class="badge ' + badgeCls + '">' + s.label + "</span>" +
      '<span class="meta">session ' + esc(sid) + " · turn " + esc(r.turn_seq) +
        " · " + esc(r.at || "") + "</span>" +
    "</div>" +
    sectionHtml("a", "缺失發現與修補清單", r.a) +
    sectionHtml("b", "AI 逃避通報", r.b) +
    sectionHtml("c", "Token 累積警示", r.c) +
    // 舊報告（2026-09 前）只有 a–d 且 d=衍生暫存：無 e 欄視為舊格式，d 以舊標籤渲染。
    (r.e == null
      ? sectionHtml("d", "衍生暫存清單（舊格式；實際尚存者見下方殘檔面板）", r.d)
      : sectionHtml("d", "記憶收錄帳", r.d) +
        sectionHtml("e", "未告知決策＋未驗證假設", r.e) +
        sectionHtml("f", "靜默狀態改變", r.f) +
        sectionHtml("g", "版控收尾", r.g) +
        sectionHtml("h", "收尾判定", r.h) +
        sectionHtml("i", "衍生暫存清單（宣告；實際尚存者見下方殘檔面板）", r.i)) +
  "</div>";
  slot.innerHTML = html;
}

function renderGrid() {
  var grid = document.getElementById("grid");
  var cells = reports.slice(0, GRID_N).slice().reverse();   // 舊→新，最新在右
  if (!cells.length) { grid.innerHTML = ""; return; }
  var out = "";
  for (var i = 0; i < cells.length; i++) {
    var r = cells[i], s = sevOf(r), k = keyOf(r);
    var active = (k === activeKey) ? " active" : "";
    var tip = "t" + r.turn_seq + " · " + s.label + " · " + (r.at || "");
    out += '<div class="cell ' + s.cls + active + '" title="' + esc(tip) +
           '" data-key="' + esc(k) + '">' + (s.cls === "real" ? "!" : "") + "</div>";
  }
  grid.innerHTML = out;
  var nodes = grid.querySelectorAll(".cell");
  for (var j = 0; j < nodes.length; j++) {
    nodes[j].addEventListener("click", onCellClick);
  }
}

function onCellClick(e) {
  var k = e.currentTarget.getAttribute("data-key");
  var parts = k.split("|");
  activeKey = k;
  fetch("/api/aec/report/" + encodeURIComponent(parts[0]) + "/" + encodeURIComponent(parts[1]))
    .then(function (res) { return res.ok ? res.json() : null; })
    .then(function (r) { if (r) { renderCard(r); renderGrid(); } })
    .catch(function () {});
}

function findReport(sid, turn) {
  for (var i = 0; i < reports.length; i++) {
    if (String(reports[i].session_id) === String(sid) &&
        String(reports[i].turn_seq) === String(turn)) { return reports[i]; }
  }
  return null;
}

function onDecClick(e) {
  var el = e.currentTarget;
  if (el.getAttribute("data-action") === "delete" &&
      !window.confirm("確定排定刪除？\\n" + el.getAttribute("data-path"))) { return; }
  postDecision(
    el.getAttribute("data-sid"), el.getAttribute("data-path"),
    el.getAttribute("data-note"), el.getAttribute("data-action")
  );
}

// POST 決策 → 落磁碟佇列（Node 寫，檔名=路徑 hash，跨回合穩定）；成功後立刻重抓面板顯示狀態。
function postDecision(sid, p, note, action) {
  fetch("/api/aec/decision", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sid: sid, path: p, note: note, action: action })
  })
    .then(function (res) { return res.ok ? res.json() : null; })
    .then(function (j) { if (j && j.ok) { lastTempKey = ""; pollTemp(sid); } })
    .catch(function () {});
}

function updateBanner() {
  var banner = document.getElementById("banner");
  var latest = reports[0];
  if (latest && sevOf(latest).cls === "real") {
    banner.textContent = "⚠ real-evasion：最新回合偵測到 (b) AI 逃避通報。請檢視卡片。";
    banner.className = "banner show";
  } else {
    banner.className = "banner";
  }
}

function poll() {
  fetch("/api/aec/reports")
    .then(function (res) { return res.ok ? res.json() : { reports: [] }; })
    .then(function (data) {
      reports = (data && data.reports) || [];
      document.getElementById("poll-txt").textContent =
        reports.length ? (reports.length + " 筆 · 最新 t" + reports[0].turn_seq) : "尚無報告";
      if (activeKey === null && reports.length) { renderCard(reports[0]); }
      renderGrid();
      updateBanner();
      // 殘檔面板跟著目前顯示的卡片所屬 session（點了歷史格就跟那格）。
      var curSid = activeKey !== null ? String(activeKey).split("|")[0]
                                      : (reports.length ? reports[0].session_id : "");
      pollTemp(curSid);
    })
    .catch(function () {
      document.getElementById("poll-txt").textContent = "連線中斷";
    });
}
function beat() { fetch("/api/aec/beat").catch(function () {}); }

poll(); beat();
setInterval(poll, POLL_MS);
setInterval(beat, BEAT_MS);
</script>
</body>
</html>`;
}

module.exports = { render };

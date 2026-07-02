// dashboard-html.js — dashboard HTML 模板。匯出 render(versions)->string。
// 內層 3188-3889 的 const 是瀏覽器端 JS（非模組 state），整塊 verbatim，勿 hoist。

function render(versions) {
  return `<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>工作流守衛 v${versions.guardian}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, "Segoe UI", sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }
  h1 { color: #58a6ff; margin-bottom: 4px; font-size: 1.4em; }
  .subtitle { color: #8b949e; font-size: 0.85em; margin-bottom: 12px; }
  .stats { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
  .stat { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 10px 14px; min-width: 100px; }
  .stat-value { font-size: 1.4em; font-weight: bold; color: #58a6ff; }
  .stat-label { font-size: 0.75em; color: #8b949e; }
  .tab-nav { display: flex; gap: 0; border-bottom: 1px solid #30363d; margin-bottom: 16px; }
  .tab-btn { padding: 8px 16px; border: none; background: none; color: #8b949e; cursor: pointer; border-bottom: 2px solid transparent; font-size: 0.9em; font-family: inherit; }
  .tab-btn:hover { color: #c9d1d9; }
  .tab-btn.active { color: #58a6ff; border-bottom-color: #58a6ff; }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }
  .sessions { display: flex; flex-direction: column; gap: 12px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .card-name { font-weight: 600; color: #e6edf3; font-size: 1.05em; }
  .card-id { font-family: monospace; color: #79c0ff; font-size: 0.85em; }
  .badge { padding: 2px 8px; border-radius: 12px; font-size: 0.75em; font-weight: 600; }
  .badge-init { background: #1f6feb33; color: #58a6ff; }
  .badge-working { background: #f0883e33; color: #f0883e; }
  .badge-syncing { background: #d2a82633; color: #d2a826; }
  .badge-done { background: #23863633; color: #3fb950; }
  .badge-merged { background: #a371f733; color: #a371f7; }
  .card-meta { font-size: 0.8em; color: #8b949e; margin-bottom: 8px; }
  .card-stats { display: flex; gap: 16px; font-size: 0.85em; }
  .card-stats span { color: #8b949e; }
  .card-stats strong { color: #c9d1d9; }
  .details { margin-top: 10px; padding-top: 10px; border-top: 1px solid #30363d; font-size: 0.82em; }
  .details summary { cursor: pointer; color: #58a6ff; margin-bottom: 6px; }
  .file-list, .kq-list { list-style: none; padding-left: 8px; }
  .file-list li, .kq-list li { padding: 2px 0; color: #8b949e; font-family: monospace; font-size: 0.9em; }
  .kq-badge { font-weight: bold; }
  .kq-badge-fixed { color: #3fb950; }
  .kq-badge-observe { color: #d2a826; }
  .kq-badge-temp { color: #f0883e; }
  .actions { margin-top: 10px; display: flex; gap: 8px; }
  .btn { padding: 4px 12px; border-radius: 4px; border: 1px solid #30363d; background: #21262d; color: #c9d1d9; cursor: pointer; font-size: 0.8em; font-family: inherit; }
  .btn:hover { background: #30363d; }
  .btn-primary { border-color: #388bfd66; color: #58a6ff; }
  .btn-primary:hover { background: #388bfd22; }
  .btn-success { border-color: #3fb95066; color: #3fb950; }
  .btn-success:hover { background: #3fb95022; }
  .btn-danger { border-color: #f8514966; color: #f85149; }
  .btn-danger:hover { background: #f8514922; }
  .empty { text-align: center; color: #8b949e; padding: 40px; }
  .auto-refresh { font-size: 0.8em; color: #8b949e; }
  .auto-refresh label { cursor: pointer; }
  /* Timeline */
  .timeline { position: relative; padding-left: 28px; border-left: 2px solid #30363d; margin-left: 8px; }
  .timeline-item { position: relative; margin-bottom: 16px; }
  .timeline-dot { position: absolute; left: -35px; top: 10px; width: 12px; height: 12px; border-radius: 50%; border: 2px solid #0d1117; }
  .ttl-green { background: #3fb950; }
  .ttl-yellow { background: #d2a826; }
  .ttl-red { background: #f85149; }
  .ttl-critical { background: #f85149; animation: pulse 1s infinite; }
  .ttl-expired { background: #484f58; }
  @keyframes pulse { 50% { opacity: 0.4; } }
  .timeline-card { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; }
  .timeline-date { font-size: 0.75em; color: #8b949e; }
  .timeline-title { font-weight: 600; color: #e6edf3; margin: 4px 0; }
  .timeline-ttl { font-size: 0.8em; padding: 1px 6px; border-radius: 8px; font-weight: 600; }
  .timeline-knowledge { margin-top: 8px; font-size: 0.82em; color: #8b949e; }
  .timeline-knowledge li { padding: 2px 0; list-style: none; }
  .timeline-full { margin-top: 8px; padding-top: 8px; border-top: 1px solid #30363d; white-space: pre-wrap; font-family: monospace; font-size: 0.78em; color: #8b949e; max-height: 300px; overflow-y: auto; }
  /* Health */
  .health-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; margin-bottom: 16px; }
  .health-stat { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; text-align: center; }
  .health-stat .val { font-size: 1.5em; font-weight: bold; }
  .health-stat .lbl { font-size: 0.75em; color: #8b949e; }
  .issue-table { width: 100%; border-collapse: collapse; font-size: 0.82em; margin-bottom: 16px; }
  .issue-table th { text-align: left; color: #8b949e; padding: 6px 8px; border-bottom: 1px solid #30363d; }
  .issue-table td { padding: 6px 8px; border-bottom: 1px solid #21262d; }
  .level-error { color: #f85149; }
  .level-warning { color: #d2a826; }
  .level-info { color: #58a6ff; }
  .suggest-list { list-style: none; margin-bottom: 16px; }
  .suggest-list li { padding: 6px 0; border-bottom: 1px solid #21262d; font-size: 0.85em; }
  .suggest-arrow { color: #58a6ff; font-weight: bold; }
  .cache-info { font-size: 0.75em; color: #484f58; margin-top: 8px; }
  /* Tests */
  .test-card { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 6px; margin-bottom: 6px; background: #161b22; border: 1px solid #30363d; }
  .test-pass { border-left: 3px solid #3fb950; }
  .test-fail { border-left: 3px solid #f85149; }
  .test-skip { border-left: 3px solid #8b949e; }
  .test-icon { font-size: 1.1em; width: 22px; text-align: center; }
  .test-name { font-weight: 600; color: #e6edf3; flex: 1; }
  .test-duration { font-size: 0.8em; color: #8b949e; }
  .test-msg { font-size: 0.78em; color: #8b949e; font-family: monospace; }
  .test-summary { display: flex; gap: 16px; padding: 12px; background: #161b22; border: 1px solid #30363d; border-radius: 6px; margin-bottom: 12px; font-size: 0.9em; }
  .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #30363d; border-top-color: #58a6ff; border-radius: 50%; animation: spin 0.8s linear infinite; vertical-align: middle; margin-right: 8px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .run-btn { padding: 10px 24px; font-size: 1em; border-radius: 6px; border: 1px solid #3fb95066; background: #23863622; color: #3fb950; cursor: pointer; font-weight: 600; font-family: inherit; }
  .run-btn:hover { background: #23863644; }
  .run-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  /* Vector */
  .vec-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .vec-section { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 14px; }
  .vec-section h3 { font-size: 0.9em; color: #58a6ff; margin-bottom: 8px; }
  .vec-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 0.85em; }
  .vec-row .k { color: #8b949e; }
  .vec-row .v { color: #e6edf3; font-family: monospace; }
  .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .status-online { background: #3fb950; }
  .status-offline { background: #f85149; }
  .status-warn { background: #d2a826; }
  .status-disabled { background: #484f58; }
  .backend-card { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 14px; }
  .backend-card .bc-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  .backend-card .bc-name { font-weight: 600; font-size: 0.95em; }
  .backend-card .bc-tag { font-size: 0.75em; padding: 1px 6px; border-radius: 3px; background: #30363d; color: #8b949e; }
  .backend-card .bc-tag.pri { background: #58a6ff22; color: #58a6ff; }
  .section-title { font-size: 1em; font-weight: 600; color: #e6edf3; margin-bottom: 10px; }
  /* Atoms */
  .atom-table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
  .atom-table th { text-align: left; color: #8b949e; padding: 8px; border-bottom: 2px solid #30363d; cursor: pointer; user-select: none; }
  .atom-table th:hover { color: #58a6ff; }
  .atom-table td { padding: 8px; border-bottom: 1px solid #21262d; }
  .atom-table tr:hover { background: #161b2288; }
  .atom-name { color: #58a6ff; font-weight: 600; cursor: pointer; }
  .atom-name:hover { text-decoration: underline; }
  .atom-layer { font-size: 0.8em; padding: 1px 6px; border-radius: 8px; background: #30363d; color: #8b949e; }
  .atom-conf { font-weight: bold; }
  .conf-fixed { color: #3fb950; }
  .conf-observe { color: #d2a826; }
  .conf-temp { color: #f0883e; }
  .atom-detail { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 16px; margin: 12px 0; white-space: pre-wrap; font-family: monospace; font-size: 0.82em; max-height: 500px; overflow-y: auto; }
  .atom-filter { padding: 6px 12px; background: #161b22; border: 1px solid #30363d; border-radius: 4px; color: #c9d1d9; font-size: 0.9em; margin-bottom: 12px; width: 300px; font-family: inherit; }
  .atom-filter::placeholder { color: #484f58; }
  .atom-stats { display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
  .proj-table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
  .proj-table th { text-align: left; color: #8b949e; padding: 8px; border-bottom: 2px solid #30363d; }
  .proj-table td { padding: 8px; border-bottom: 1px solid #21262d; vertical-align: top; }
  .proj-table tr:hover { background: #161b2288; }
  .proj-root { font-family: monospace; font-size: 0.85em; color: #79c0ff; word-break: break-all; }
  .proj-badge-mem { background: #23863622; color: #3fb950; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; }
  .proj-badge-nomem { background: #30363d; color: #8b949e; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; }
  .proj-alias { font-size: 0.8em; color: #8b949e; }
  .proj-filter-btn { background: none; border: 1px solid #30363d; color: #58a6ff; padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 0.8em; font-family: inherit; }
  .proj-filter-btn:hover { background: #58a6ff22; }
  .hot-cache-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; display: flex; align-items: center; gap: 12px; font-size: 0.85em; }
  .hot-cache-card.has-cache { border-color: #3fb95066; }
  .hot-cache-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .hot-cache-dot.green { background: #3fb950; }
  .hot-cache-dot.gray { background: #484f58; }
  .vector-indicator { display: inline-flex; align-items: center; gap: 4px; cursor: pointer; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; }
  .vector-indicator:hover { background: #30363d; }
  .vector-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
  .vector-dot.ready { background: #3fb950; }
  .vector-dot.not-ready { background: #f85149; }
</style>
</head>
<body>
<div style="display:flex;justify-content:space-between;align-items:baseline;">
  <div><h1>工作流守衛 v${versions.guardian}</h1><p class="subtitle">記憶與對話監控</p></div>
  <div class="auto-refresh"><label><input type="checkbox" id="autoRefresh" checked> 自動重整 (5秒)</label></div>
</div>

<div class="stats" id="statsBar"></div>
<div id="hotCacheCard" class="hot-cache-card" style="display:none"></div>

<nav class="tab-nav">
  <button class="tab-btn active" data-tab="sessions">對話</button>
  <button class="tab-btn" data-tab="episodic">情境記憶</button>
  <button class="tab-btn" data-tab="health">健康檢查</button>
  <button class="tab-btn" data-tab="atoms">原子記憶 v${versions.atom_memory}</button>
  <button class="tab-btn" data-tab="projects">已知專案</button>
  <button class="tab-btn" data-tab="tests">測試</button>
  <button class="tab-btn" data-tab="vector">向量服務</button>
  <button class="tab-btn" data-tab="env">環境</button>
</nav>

<div id="panelSessions" class="tab-panel active">
  <div class="sessions" id="sessionList"></div>
</div>

<div id="panelEpisodic" class="tab-panel">
  <div id="episodicContent"></div>
</div>

<div id="panelHealth" class="tab-panel">
  <div id="healthContent"><div class="empty">載入健康資料中...</div></div>
</div>

<div id="panelAtoms" class="tab-panel">
  <div id="atomsContent"><div class="empty">載入原子記憶中...</div></div>
</div>

<div id="panelProjects" class="tab-panel">
  <div id="projectsContent"><div class="empty">載入已知專案中...</div></div>
</div>

<div id="panelTests" class="tab-panel">
  <div id="testsContent">
    <div style="text-align:center;padding:20px;">
      <button class="run-btn" id="runTestsBtn" onclick="startTestRun()">執行端對端測試</button>
    </div>
    <div id="testResults"></div>
  </div>
</div>

<div id="panelVector" class="tab-panel">
  <div id="vectorContent"><div class="empty">載入向量服務狀態中...</div></div>
</div>

<div id="panelEnv" class="tab-panel">
  <div id="envContent"><div class="empty">載入環境資訊中...</div></div>
</div>

<script>
let refreshTimer;
let currentTab = "sessions";
let testJobId = null;
let testPollTimer = null;

function switchTab(name) {
  const btn = document.querySelector('[data-tab="' + name + '"]');
  if (btn) btn.click();
}

// ─── Tab Switching ───

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const prevTab = currentTab;
    currentTab = btn.dataset.tab;
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    document.getElementById("panel" + currentTab.charAt(0).toUpperCase() + currentTab.slice(1)).classList.add("active");
    if (prevTab === "vector" && currentTab !== "vector") stopBackendsPolling();
    refreshCurrentTab();
  });
});

async function refreshCurrentTab() {
  const prevScroll = window.scrollY;
  switch (currentTab) {
    case "sessions": await renderSessions(); break;
    case "episodic": await renderEpisodic(); break;
    case "health": await renderHealth(false); break;
    case "atoms": await renderAtoms(); break;
    case "projects": await renderProjects(); break;
    case "tests": break;
    case "vector": await renderVector(); break;
    case "env": await renderEnv(); break;
  }
  window.scrollTo(0, prevScroll);
}

// ─── Sessions Panel (existing logic) ───

async function fetchSessions() {
  try { const r = await fetch("/api/sessions"); return await r.json(); }
  catch { return []; }
}

async function sendSignal(sid, signal) {
  await fetch("/api/sessions/" + sid + "/signal", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ signal })
  });
  renderSessions();
}

async function deleteSession(sid) {
  if (!confirm("確定要刪除對話 " + sid.slice(0,8) + "?")) return;
  await fetch("/api/sessions/" + sid, { method: "DELETE" });
  renderSessions();
}

function badgeClass(phase) { return "badge badge-" + (phase || "init"); }

function clsBadge(c) {
  if (c === "[固]") return '<span class="kq-badge kq-badge-fixed">[固]</span>';
  if (c === "[觀]") return '<span class="kq-badge kq-badge-observe">[觀]</span>';
  return '<span class="kq-badge kq-badge-temp">[臨]</span>';
}

function esc(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

async function renderSessions() {
  const [sessions, vecReady] = await Promise.all([fetchSessions(), fetchVectorReady()]);
  const active = sessions.filter(s => !s.ended);
  const pending = sessions.filter(s => s.sync_pending && !s.ended);
  const vecHtml = '<div class="stat"><div class="vector-indicator" onclick="switchTab(\\'vector\\')"><span class="vector-dot ' + (vecReady?"ready":"not-ready") + '"></span> Vector</div></div>';
  updateStats(sessions.length, active.length, pending.length, vecHtml);
  renderHotCache();

  if (sessions.length === 0) {
    document.getElementById("sessionList").innerHTML = '<div class="empty">無進行中的對話。</div>';
    return;
  }

  const cards = await Promise.all(sessions.map(async (s) => {
    let detail;
    try { const r = await fetch("/api/sessions/" + s.session_id); detail = await r.json(); }
    catch { detail = {}; }
    const files = detail.modified_files || [];
    const kq = detail.knowledge_queue || [];
    const uniqueFiles = [...new Set(files.map(f => f.path))];
    let fileHtml = "";
    if (uniqueFiles.length > 0) {
      fileHtml = '<details><summary>修改檔案 (' + uniqueFiles.length + ')</summary><ul class="file-list">' +
        uniqueFiles.map(f => "<li>" + esc(f.split(/[\\\\/]/).pop()) + ' <span style="color:#484f58">' + esc(f) + "</span></li>").join("") + "</ul></details>";
    }
    let kqHtml = "";
    if (kq.length > 0) {
      kqHtml = '<details><summary>知識佇列 (' + kq.length + ')</summary><ul class="kq-list">' +
        kq.map(q => "<li>" + clsBadge(q.classification) + " " + esc((q.content||"").slice(0,80)) + "</li>").join("") + "</ul></details>";
    }
    return '<div class="card">' +
      '<div class="card-header"><span class="card-name">' + esc(s.name||"?") + '</span><span class="' + badgeClass(s.phase) + '">' + s.phase + (s.muted?" (已靜音)":"") + '</span></div>' +
      '<div class="card-meta"><span class="card-id">' + s.session_id.slice(0,8) + '</span> &middot; ' + esc(s.project||"?") + ' &middot; ' + s.age_minutes + ' 分鐘' + (s.ended?" &middot; 已結束":"") + (s.merged_into?' &middot; <span style="color:#a371f7">已合併至 '+s.merged_into.slice(0,8)+'</span>':"") + '</div>' +
      '<div class="card-stats"><span>檔案：<strong>' + s.modified_files_count + '</strong></span><span>知識：<strong>' + s.knowledge_queue_count + '</strong></span><span>同步：<strong>' + (s.sync_pending?"待處理":"完成") + '</strong></span></div>' +
      (fileHtml||kqHtml ? '<div class="details">' + fileHtml + kqHtml + '</div>' : '') +
      '<div class="actions">' +
        '<button class="btn" onclick="sendSignal(\\'' + s.session_id + '\\',\\'sync_completed\\')">標記已同步</button>' +
        '<button class="btn" onclick="sendSignal(\\'' + s.session_id + '\\',\\'reset\\')">重置</button>' +
        (s.muted ? '' : '<button class="btn" onclick="sendSignal(\\'' + s.session_id + '\\',\\'mute\\')">靜音</button>') +
        '<button class="btn btn-danger" onclick="deleteSession(\\'' + s.session_id + '\\')">刪除</button>' +
      '</div></div>';
  }));
  document.getElementById("sessionList").innerHTML = cards.join("");
}

// ─── Stats Bar ───

function updateStats(total, active, pending, extra) {
  let html = '<div class="stat"><div class="stat-value">' + total + '</div><div class="stat-label">對話數</div></div>' +
    '<div class="stat"><div class="stat-value">' + active + '</div><div class="stat-label">進行中</div></div>' +
    '<div class="stat"><div class="stat-value">' + pending + '</div><div class="stat-label">待同步</div></div>';
  if (extra) html += extra;
  document.getElementById("statsBar").innerHTML = html;
}

// ─── Hot Cache Card ───

async function renderHotCache() {
  const el = document.getElementById("hotCacheCard");
  try {
    const data = await (await fetch("/api/hot-cache")).json();
    if (data.empty) { el.style.display = "none"; return; }
    const hasUninjected = !data.injected && (data.knowledge||[]).length > 0;
    el.className = "hot-cache-card" + (hasUninjected ? " has-cache" : "");
    el.style.display = "flex";
    const ageMin = Math.round((data.age_seconds||0) / 60);
    const ageStr = ageMin < 1 ? "<1 分鐘" : ageMin + " 分鐘前";
    el.innerHTML =
      '<span class="hot-cache-dot ' + (hasUninjected ? "green" : "gray") + '"></span>' +
      '<span><strong>Hot Cache</strong></span>' +
      '<span>來源: ' + (data.source||"?") + '</span>' +
      '<span>知識: ' + (data.knowledge||[]).length + ' 條</span>' +
      '<span>注入: ' + (data.injected ? "已注入" : "待注入") + '</span>' +
      '<span style="color:#8b949e">' + ageStr + '</span>';
  } catch { el.style.display = "none"; }
}

// ─── Vector Ready Indicator ───

async function fetchVectorReady() {
  try {
    const data = await (await fetch("/api/vector-ready")).json();
    return data.ready;
  } catch { return false; }
}

// ─── Episodic Timeline ───

async function renderEpisodic() {
  const el = document.getElementById("episodicContent");
  try {
    const atoms = await (await fetch("/api/episodic")).json();
    if (!atoms.length) {
      el.innerHTML = '<div class="empty">無情境記憶紀錄。<br><span style="font-size:0.85em">情境記憶在對話結束時自動生成。</span></div>';
      return;
    }
    let html = '<div class="timeline">';
    for (const a of atoms) {
      const d = a.days_until_expiry;
      let dotCls = "ttl-green";
      let ttlLabel = d + "天剩餘";
      let ttlStyle = "background:#3fb95022;color:#3fb950";
      if (d !== null && d <= 0) { dotCls = "ttl-expired"; ttlLabel = "已過期"; ttlStyle = "background:#484f5822;color:#484f58"; }
      else if (d !== null && d <= 3) { dotCls = "ttl-critical"; ttlLabel = d + "天剩餘"; ttlStyle = "background:#f8514922;color:#f85149"; }
      else if (d !== null && d <= 7) { dotCls = "ttl-red"; ttlStyle = "background:#f8514922;color:#f85149"; }
      else if (d !== null && d <= 14) { dotCls = "ttl-yellow"; ttlStyle = "background:#d2a82622;color:#d2a826"; }

      const knLines = (a.knowledge_lines || []).slice(0, 5).map(l => "<li>" + esc(l) + "</li>").join("");
      const moreCount = (a.knowledge_lines||[]).length - 5;
      const hasMore = moreCount > 0;

      html += '<div class="timeline-item"><div class="timeline-dot ' + dotCls + '"></div><div class="timeline-card">' +
        '<div style="display:flex;justify-content:space-between;align-items:center">' +
          '<span class="timeline-date">' + esc(a.created || "?") + '</span>' +
          '<span class="timeline-ttl" style="' + ttlStyle + '">' + ttlLabel + '</span>' +
        '</div>' +
        '<div class="timeline-title">' + esc(a.title) + '</div>' +
        '<div style="font-size:0.78em;color:#8b949e">' + esc(a.triggers.join(", ")) + '</div>' +
        (knLines ? '<ul class="timeline-knowledge">' + knLines + (hasMore ? '<li style="color:#58a6ff">... +' + moreCount + ' 更多</li>' : '') + '</ul>' : '') +
        '<details><summary style="font-size:0.8em;color:#58a6ff;cursor:pointer;margin-top:6px">完整內容</summary>' +
          '<div class="timeline-full">' + esc(a.full_content) + '</div></details>' +
      '</div></div>';
    }
    html += '</div>';
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty">載入情境記憶失敗：' + esc(e.message) + '</div>';
  }
}

// ─── Memory Health ───

let lastHealthData = null;

let _healthInfoVisible = false;
function toggleHealthInfo() {
  _healthInfoVisible = !_healthInfoVisible;
  document.querySelectorAll('.health-info-row').forEach(r => {
    r.style.display = _healthInfoVisible ? '' : 'none';
  });
}

async function renderHealth(force) {
  const el = document.getElementById("healthContent");
  try {
    const url = "/api/health" + (force ? "?force=1" : "");
    el.innerHTML = '<div class="empty"><span class="spinner"></span> 載入健康報告中...</div>';
    const data = await (await fetch(url)).json();
    if (data.error) { el.innerHTML = '<div class="empty">健康檢查失敗：' + esc(data.error) + '</div>'; return; }
    lastHealthData = data;

    const cc = data.confidence_counts || {};
    let html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">' +
      '<span class="section-title">記憶健康報告</span>' +
      '<button class="btn btn-primary" onclick="renderHealth(true)">立即重整</button></div>';

    // Confidence counts
    html += '<div class="health-grid">';
    html += '<div class="health-stat"><div class="val" style="color:#3fb950">' + (cc["[固]"]||0) + '</div><div class="lbl">[固] 確定</div></div>';
    html += '<div class="health-stat"><div class="val" style="color:#d2a826">' + (cc["[觀]"]||0) + '</div><div class="lbl">[觀] 觀察</div></div>';
    html += '<div class="health-stat"><div class="val" style="color:#f0883e">' + (cc["[臨]"]||0) + '</div><div class="lbl">[臨] 臨時</div></div>';
    html += '<div class="health-stat"><div class="val">' + (data.total_atoms||0) + '</div><div class="lbl">原子總數</div></div>';
    html += '<div class="health-stat"><div class="val">' + (data.distant_count||0) + '</div><div class="lbl">疏遠區</div></div>';
    html += '</div>';

    // Issues — grouped by severity
    const issues = data.issues || [];
    const errCount = issues.filter(i => i.level === "error").length;
    const warnCount = issues.filter(i => i.level === "warning").length;
    const infoCount = issues.filter(i => i.level === "info").length;
    if (issues.length) {
      html += '<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">' +
        '<span class="section-title">問題</span>' +
        (errCount ? '<span style="color:#f85149;font-weight:bold">' + errCount + ' error</span>' : '') +
        (warnCount ? '<span style="color:#d2a826;font-weight:bold">' + warnCount + ' warning</span>' : '') +
        (infoCount ? '<span style="color:#8b949e">' + infoCount + ' info</span>' : '') +
        '<button class="btn" style="font-size:0.75em;padding:2px 8px" onclick="toggleHealthInfo()">顯示/隱藏 info</button>' +
        '</div>';
      html += '<table class="issue-table"><tr><th>等級</th><th>分類</th><th>檔案</th><th>訊息</th></tr>';
      for (const i of issues) {
        const hideClass = i.level === "info" ? ' class="health-info-row" style="display:' + (_healthInfoVisible ? '' : 'none') + '"' : '';
        html += '<tr' + hideClass + '><td class="level-' + i.level + '">' + i.level + '</td><td>' + esc(i.category) + '</td><td style="font-family:monospace;font-size:0.85em">' + esc(i.file) + '</td><td>' + esc(i.message) + '</td></tr>';
      }
      html += '</table>';
    } else {
      html += '<div style="color:#3fb950;margin-bottom:12px">✓ 無任何問題</div>';
    }

    // Promotions
    const promos = data.promotions || [];
    if (promos.length) {
      html += '<div class="section-title">晉升候選</div><ul class="suggest-list">';
      for (const p of promos) {
        html += '<li><span style="font-family:monospace">' + esc(p.file) + '</span> ' + p.current + ' <span class="suggest-arrow">&rarr;</span> ' + p.suggested + '<br><span style="color:#8b949e;font-size:0.82em">' + esc(p.reason) + '</span></li>';
      }
      html += '</ul>';
    }

    // Demotions
    const demos = data.demotions || [];
    if (demos.length) {
      html += '<div class="section-title">降級 / 過期警告</div><ul class="suggest-list">';
      for (const d of demos) {
        html += '<li><span style="font-family:monospace">' + esc(d.file) + '</span> ' + d.current + ' <span class="suggest-arrow">&rarr;</span> ' + d.suggested + '<br><span style="color:#8b949e;font-size:0.82em">' + esc(d.reason) + '</span></li>';
      }
      html += '</ul>';
    }

    // Reference integrity
    const brokenRefs = data.broken_refs || [];
    const missingRev = data.missing_reverse_refs || [];
    const staleAtoms = data.stale_atoms || [];
    html += '<div class="section-title">參照完整性</div>';
    if (!brokenRefs.length && !missingRev.length && !staleAtoms.length) {
      html += '<div style="color:#3fb950;margin-bottom:12px">✓ 所有參照完整、無過期 atom</div>';
    } else {
      if (brokenRefs.length) {
        html += '<div style="margin-bottom:8px"><strong style="color:#f85149">斷裂參照 (' + brokenRefs.length + ')</strong></div>';
        html += '<table class="issue-table"><tr><th>來源 Atom</th><th>指向（不存在）</th></tr>';
        for (const r of brokenRefs) { html += '<tr><td>' + esc(r.atom || "") + '</td><td style="color:#f85149">' + esc(r.missing_ref || "") + '</td></tr>'; }
        html += '</table>';
      }
      if (missingRev.length) {
        html += '<div style="margin-bottom:8px"><strong style="color:#d2a826">缺反向參照 (' + missingRev.length + ')</strong></div>';
        html += '<table class="issue-table"><tr><th>說明</th></tr>';
        for (const r of missingRev) { html += '<tr><td style="color:#d2a826">' + esc(r.direction || (r.atom_a + " → " + r.atom_b)) + '</td></tr>'; }
        html += '</table>';
      }
      if (staleAtoms.length) {
        html += '<div style="margin-bottom:8px"><strong style="color:#f0883e">過期 Atom (' + staleAtoms.length + ')</strong></div><ul>';
        for (const s of staleAtoms) { html += '<li>' + esc(s.name || s) + ' — Last-used: ' + esc(s.last_used || "?") + '</li>'; }
        html += '</ul>';
      }
    }

    // Audit stats
    const as = data.audit_stats || {};
    if (as.total_entries) {
      html += '<div class="section-title">審計摘要</div><div class="health-grid">';
      const ba = as.by_action || {};
      for (const [k, v] of Object.entries(ba)) {
        html += '<div class="health-stat"><div class="val">' + v + '</div><div class="lbl">' + k + '</div></div>';
      }
      html += '<div class="health-stat"><div class="val">' + as.total_entries + '</div><div class="lbl">總筆數</div></div>';
      html += '</div>';
    }

    html += '<div class="cache-info">掃描時間：' + esc(data.scan_date || "?") + ' | 層級：' + (data.layers||[]).join(", ") + '</div>';
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty">載入健康資料失敗：' + esc(e.message) + '</div>';
  }
}

// ─── E2E Test Runner ───

async function startTestRun() {
  const btn = document.getElementById("runTestsBtn");
  const el = document.getElementById("testResults");
  btn.disabled = true;
  el.innerHTML = '<div style="text-align:center;padding:16px"><span class="spinner"></span> 測試執行中... <span id="testElapsed">0s</span></div>';
  const startTime = Date.now();
  const elapsedTimer = setInterval(() => {
    const s = ((Date.now() - startTime) / 1000).toFixed(0);
    const te = document.getElementById("testElapsed");
    if (te) te.textContent = s + "s";
  }, 500);

  try {
    const r = await fetch("/api/test-run", { method: "POST" });
    const d = await r.json();
    if (d.error) { el.innerHTML = '<div class="empty">' + esc(d.error) + '</div>'; btn.disabled = false; clearInterval(elapsedTimer); return; }
    testJobId = d.job_id;
    testPollTimer = setInterval(async () => {
      try {
        const sr = await fetch("/api/test-run/" + testJobId);
        const sd = await sr.json();
        if (sd.status !== "running") {
          clearInterval(testPollTimer);
          clearInterval(elapsedTimer);
          testPollTimer = null;
          btn.disabled = false;
          renderTestResults(sd);
        }
      } catch {}
    }, 2000);
  } catch (e) {
    el.innerHTML = '<div class="empty">測試執行失敗：' + esc(e.message) + '</div>';
    btn.disabled = false;
    clearInterval(elapsedTimer);
  }
}

function renderTestResults(job) {
  const el = document.getElementById("testResults");
  if (job.status === "error") {
    const err = job.result || {};
    el.innerHTML = '<div class="empty" style="color:#f85149">測試失敗：' + esc(err.error || "unknown") + (err.stderr ? '<br><pre style="text-align:left;font-size:0.8em;margin-top:8px">' + esc(err.stderr) + '</pre>' : '') + '</div>';
    return;
  }
  const r = job.result || {};
  const results = r.results || [];
  let html = '<div class="test-summary">' +
    '<span style="color:#3fb950;font-weight:600">通過：' + (r.passed||0) + '</span>' +
    '<span style="color:#f85149;font-weight:600">失敗：' + (r.failed||0) + '</span>' +
    '<span style="color:#8b949e">略過：' + (r.skipped||0) + '</span>' +
    '<span style="color:#8b949e">總計：' + (r.total||0) + '</span>' +
    '<span style="color:#8b949e">耗時：' + ((job.elapsed_ms||0)/1000).toFixed(1) + 's</span>' +
  '</div>';
  for (const t of results) {
    const cls = t.skipped ? "test-skip" : (t.passed ? "test-pass" : "test-fail");
    const icon = t.skipped ? "&#9711;" : (t.passed ? "&#10003;" : "&#10007;");
    const iconColor = t.skipped ? "#8b949e" : (t.passed ? "#3fb950" : "#f85149");
    html += '<div class="test-card ' + cls + '">' +
      '<span class="test-icon" style="color:' + iconColor + '">' + icon + '</span>' +
      '<span class="test-name">' + esc(t.name) + '</span>' +
      '<span class="test-duration">' + (t.duration_ms||0).toFixed(0) + 'ms</span>' +
    '</div>';
    if (t.message) {
      html += '<div style="padding:0 14px 6px 48px"><span class="test-msg">' + esc(t.message) + '</span></div>';
    }
  }
  el.innerHTML = html;
}

// ─── Vector Status ───

let _backendsHtml = "";  // cached backend HTML (refreshed independently)
let _backendsTimer = null;

async function fetchBackendsStatus() {
  try {
    const r = await fetch("/api/ollama-backends-status");
    const d = await r.json();
    const bs = (d.backends || []).sort((a,b) => a.priority - b.priority);
    if (!bs.length) { _backendsHtml = ""; return; }

    const statusMap = {
      online: { dot: "status-online", label: "線上", color: "#3fb950" },
      offline: { dot: "status-offline", label: "離線", color: "#f85149" },
      timeout: { dot: "status-offline", label: "逾時", color: "#f85149" },
      auth_expired: { dot: "status-warn", label: "Token 過期", color: "#d2a826" },
      disabled: { dot: "status-disabled", label: "停用", color: "#484f58" },
    };
    const checkedAt = d.checked_at ? new Date(d.checked_at).toLocaleTimeString() : "?";
    const cached = d.cached ? ' <span style="color:#484f58;font-size:0.75em">(快取)</span>' : "";

    let html = '<div style="margin-top:16px"><h3 style="font-size:0.95em;color:#e6edf3;margin-bottom:8px">Ollama 後端' + cached + ' <span style="color:#484f58;font-size:0.75em;font-weight:normal">最後檢查 ' + checkedAt + '</span></h3>';

    // Long DIE warning
    if (d.long_die) {
      html += '<div style="background:#d2a82622;border:1px solid #d2a82644;border-radius:6px;padding:8px 12px;margin-bottom:10px;font-size:0.85em;color:#d2a826">';
      html += '⚠ ' + esc(d.long_die.backend) + ' 長期停用至 ' + esc(d.long_die.until||"?") + '：' + esc(d.long_die.message||"");
      html += '</div>';
    }

    html += '<div class="vec-grid">';
    for (const b of bs) {
      const s = statusMap[b.status] || { dot: "status-warn", label: b.status, color: "#d2a826" };
      const isRemote = !b.base_url.includes("127.0.0.1") && !b.base_url.includes("localhost");
      html += '<div class="backend-card">';
      html += '<div class="bc-header"><span class="status-dot ' + s.dot + '"></span>';
      html += '<span class="bc-name">' + esc(b.name) + '</span>';
      html += '<span class="bc-tag pri">P' + b.priority + '</span>';
      html += '<span class="bc-tag">' + (isRemote ? "遠端" : "本機") + '</span>';
      html += '</div>';
      html += '<div class="vec-row"><span class="k">狀態</span><span class="v" style="color:' + s.color + '">' + s.label;
      if (b.latency_ms != null && b.status === "online") html += ' (' + b.latency_ms + 'ms)';
      html += '</span></div>';
      html += '<div class="vec-row"><span class="k">URL</span><span class="v" style="font-size:0.8em;word-break:break-all">' + esc(b.base_url) + '</span></div>';
      html += '<div class="vec-row"><span class="k">LLM</span><span class="v">' + esc(b.llm_model) + '</span></div>';
      html += '<div class="vec-row"><span class="k">Embedding</span><span class="v">' + esc(b.embedding_model) + '</span></div>';
      if (b.long_die) {
        html += '<div class="vec-row"><span class="k">DIE 狀態</span><span class="v" style="color:#d2a826">長期停用至 ' + esc(b.long_die.until||"?") + '</span></div>';
      }
      html += '</div>';
    }
    html += '</div></div>';
    _backendsHtml = html;
  } catch (e) {
    _backendsHtml = '<div style="margin-top:16px;color:#8b949e;font-size:0.85em">Ollama 後端狀態載入失敗：' + esc(e.message) + '</div>';
  }
}

function startBackendsPolling() {
  if (_backendsTimer) return;
  fetchBackendsStatus();
  _backendsTimer = setInterval(fetchBackendsStatus, 30000);
}
function stopBackendsPolling() {
  if (_backendsTimer) { clearInterval(_backendsTimer); _backendsTimer = null; }
}

async function renderVector() {
  const el = document.getElementById("vectorContent");
  startBackendsPolling();
  try {
    const r = await fetch("/api/vector-status");
    const d = await r.json();
    if (d.error) {
      el.innerHTML = '<div class="card" style="text-align:center;padding:24px"><span class="status-dot status-offline"></span><strong style="color:#f85149">離線</strong><br><span style="color:#8b949e;font-size:0.85em">' + esc(d.error) + '</span></div>' + _backendsHtml;
      return;
    }
    const svc = d.service || {};
    const idx = d.index || {};
    const cfg = d.config || {};
    const job = d.index_job || {};
    const upH = Math.floor((svc.uptime_seconds||0)/3600);
    const upM = Math.floor(((svc.uptime_seconds||0)%3600)/60);

    let html = '<div style="margin-bottom:12px"><span class="status-dot status-online"></span><strong style="color:#3fb950">線上</strong> <span style="color:#8b949e;font-size:0.85em">(' + esc(svc.embedder||"?") + ' on port ' + (svc.port||3849) + ')</span></div>';
    html += '<div class="vec-grid">';

    // Service info
    html += '<div class="vec-section"><h3>服務</h3>';
    html += '<div class="vec-row"><span class="k">運行時間</span><span class="v">' + upH + 'h ' + upM + 'm</span></div>';
    html += '<div class="vec-row"><span class="k">請求次數</span><span class="v">' + (svc.requests_served||0) + '</span></div>';
    html += '<div class="vec-row"><span class="k">嵌入模型</span><span class="v">' + esc(svc.embedder||"?") + '</span></div>';
    html += '</div>';

    // Index info
    html += '<div class="vec-section"><h3>索引</h3>';
    html += '<div class="vec-row"><span class="k">總區塊數</span><span class="v">' + (idx.total_chunks||0) + '</span></div>';
    html += '<div class="vec-row"><span class="k">獨立原子</span><span class="v">' + (idx.unique_atoms||0) + '</span></div>';
    html += '<div class="vec-row"><span class="k">層級數</span><span class="v">' + (idx.layers||[]).length + '</span></div>';
    html += '</div>';

    // Config
    html += '<div class="vec-section"><h3>設定</h3>';
    html += '<div class="vec-row"><span class="k">後端</span><span class="v">' + esc(cfg.embedding_backend||"?") + '</span></div>';
    html += '<div class="vec-row"><span class="k">模型</span><span class="v">' + esc(cfg.embedding_model||"?") + '</span></div>';
    html += '<div class="vec-row"><span class="k">搜尋上限</span><span class="v">' + (cfg.search_top_k||5) + '</span></div>';
    html += '<div class="vec-row"><span class="k">最低分數</span><span class="v">' + (cfg.search_min_score||0.5) + '</span></div>';
    html += '</div>';

    // Index job
    html += '<div class="vec-section"><h3>最近索引任務</h3>';
    if (job.running) {
      html += '<div style="color:#d2a826"><span class="spinner"></span> 索引建立中...</div>';
    } else if (job.result) {
      const jr = job.result;
      html += '<div class="vec-row"><span class="k">發現原子</span><span class="v">' + (jr.atoms_found||0) + '</span></div>';
      html += '<div class="vec-row"><span class="k">已索引原子</span><span class="v">' + (jr.atoms_indexed||0) + '</span></div>';
      html += '<div class="vec-row"><span class="k">區塊數</span><span class="v">' + (jr.total_chunks||0) + '</span></div>';
      html += '<div class="vec-row"><span class="k">耗時</span><span class="v">' + ((jr.elapsed_seconds||0)).toFixed(1) + 's</span></div>';
      html += '<div class="vec-row"><span class="k">類型</span><span class="v">' + (jr.incremental?"增量":"全量") + '</span></div>';
      if (job.finished_at) {
        const fin = new Date(job.finished_at * 1000);
        html += '<div class="vec-row"><span class="k">完成時間</span><span class="v">' + fin.toLocaleString() + '</span></div>';
      }
    } else {
      html += '<div style="color:#8b949e">無近期索引紀錄</div>';
    }
    html += '</div>';

    html += '</div>';
    html += _backendsHtml;
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty">載入向量服務狀態失敗：' + esc(e.message) + '</div>';
  }
}

// ─── Projects Panel ───

async function renderProjects() {
  const el = document.getElementById("projectsContent");
  try {
    const projects = await (await fetch("/api/projects")).json();
    if (!projects.length) {
      el.innerHTML = '<div class="empty">project-registry.json 中無已知專案。</div>';
      return;
    }
    let html = '<p style="color:#8b949e;font-size:0.85em;margin-bottom:12px">來源：project-registry.json（共 ' + projects.length + ' 個專案，動態更新）</p>';
    html += '<table class="proj-table"><thead><tr>';
    html += '<th>Slug / 別名</th><th>根路徑</th><th>記憶層</th><th>Atoms</th><th>Failures</th><th>Episodic</th><th>最後活動</th><th>操作</th>';
    html += '</tr></thead><tbody>';
    for (const p of projects) {
      const memBadge = p.has_memory
        ? '<span class="proj-badge-mem">✓ .claude/memory</span>'
        : '<span class="proj-badge-nomem">未初始化</span>';
      const aliases = (p.aliases || []).length
        ? '<div class="proj-alias">' + p.aliases.map(a => esc(a)).join(', ') + '</div>'
        : '';
      const filterBtn = p.has_memory
        ? '<button class="proj-filter-btn" onclick="filterAtomsByProject(&#39;project:' + p.slug + '&#39;)">查看 Atoms</button>'
        : '';
      html += '<tr>';
      html += '<td><strong>' + esc(p.slug) + '</strong>' + aliases + '</td>';
      html += '<td><span class="proj-root">' + esc(p.root) + '</span></td>';
      html += '<td>' + memBadge + '</td>';
      html += '<td>' + (p.atom_count || 0) + '</td>';
      html += '<td>' + (p.failure_count || 0) + '</td>';
      html += '<td>' + (p.episodic_count || 0) + '</td>';
      html += '<td>' + esc(p.last_seen || '-') + '</td>';
      html += '<td>' + filterBtn + '</td>';
      html += '</tr>';
    }
    html += '</tbody></table>';
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div class="empty">載入專案清單失敗：' + esc(e.message) + '</div>';
  }
}

function filterAtomsByProject(layerPrefix) {
  // Switch to atoms tab and filter by project layer
  currentTab = "atoms";
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelector('[data-tab="atoms"]').classList.add("active");
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  document.getElementById("panelAtoms").classList.add("active");
  renderAtoms().then(() => {
    const filterInput = document.getElementById("atomFilter");
    if (filterInput) {
      filterInput.value = layerPrefix;
      filterInput.dispatchEvent(new Event("input"));
    }
  });
}

// ─── Atoms Browser ───

let atomsData = [];
const expandedAtoms = new Set();  // track expanded detail rows across refreshes

async function renderAtoms() {
  const el = document.getElementById("atomsContent");
  const prevFilter = document.getElementById("atomFilter");
  const savedFilter = prevFilter ? prevFilter.value : "";
  try {
    atomsData = await (await fetch("/api/atoms")).json();
    if (!atomsData.length) {
      el.innerHTML = '<div class="empty">無原子記憶。</div>';
      return;
    }
    renderAtomsTable(atomsData);
    if (savedFilter) {
      const fi = document.getElementById("atomFilter");
      if (fi) { fi.value = savedFilter; filterAtoms(savedFilter); }
    } else if (atomSortKey) {
      reapplySort();
    }
  } catch (e) {
    el.innerHTML = '<div class="empty">載入原子記憶失敗：' + esc(e.message) + '</div>';
  }
}

function renderAtomsTable(atoms) {
  const el = document.getElementById("atomsContent");
  const confCounts = {};
  for (const a of atoms) { confCounts[a.confidence] = (confCounts[a.confidence]||0) + 1; }

  let html = '<div class="atom-stats">';
  html += '<div class="stat"><div class="stat-value">' + atoms.length + '</div><div class="stat-label">原子總數</div></div>';
  if (confCounts["[固]"]) html += '<div class="stat"><div class="stat-value" style="color:#3fb950">' + confCounts["[固]"] + '</div><div class="stat-label">[固] 確定</div></div>';
  if (confCounts["[觀]"]) html += '<div class="stat"><div class="stat-value" style="color:#d2a826">' + confCounts["[觀]"] + '</div><div class="stat-label">[觀] 觀察</div></div>';
  if (confCounts["[臨]"]) html += '<div class="stat"><div class="stat-value" style="color:#f0883e">' + confCounts["[臨]"] + '</div><div class="stat-label">[臨] 臨時</div></div>';
  html += '</div>';

  // 收集所有 scope 給下拉選單
  const scopeSet = new Set();
  for (const a of atoms) { if (a.scope) scopeSet.add(a.scope); }
  const scopes = [...scopeSet].sort();

  html += '<div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap">';
  html += '<input id="atomFilter" class="atom-filter" type="text" placeholder="搜尋原子名稱、觸發詞..." oninput="applyAtomFilters()" style="margin-bottom:0">';
  html += '<select id="atomScopeFilter" class="atom-filter" style="width:auto;margin-bottom:0" onchange="applyAtomFilters()">';
  html += '<option value="">所有 scope</option>';
  for (const s of scopes) {
    html += '<option value="' + esc(s) + '">' + esc(s) + '</option>';
  }
  html += '</select>';
  html += '</div>';

  html += '<table class="atom-table" id="atomTable">';
  html += '<thead><tr>' +
    '<th onclick="sortAtoms(\\'name\\')">名稱 &#8597;</th>' +
    '<th onclick="sortAtoms(\\'scope\\')">Scope &#8597;</th>' +
    '<th onclick="sortAtoms(\\'layer\\')">層級 &#8597;</th>' +
    '<th onclick="sortAtoms(\\'confidence\\')">信心 &#8597;</th>' +
    '<th onclick="sortAtoms(\\'confirmations\\')">確認數 &#8597;</th>' +
    '<th onclick="sortAtoms(\\'readhits\\')">讀取數 &#8597;</th>' +
    '<th onclick="sortAtoms(\\'last_used\\')">最後使用 &#8597;</th>' +
    '<th onclick="sortAtoms(\\'knowledge_count\\')">知識數 &#8597;</th>' +
    '<th>行數</th>' +
  '</tr></thead>';
  html += '<tbody id="atomTableBody">';
  html += buildAtomRows(atoms);
  html += '</tbody></table>';
  el.innerHTML = html;
}

function buildAtomRows(atoms) {
  let html = '';
  for (const a of atoms) {
    const confClass = a.confidence === "[固]" ? "conf-fixed" : a.confidence === "[觀]" ? "conf-observe" : "conf-temp";
    const daysAgo = a.days_since_used != null ? a.days_since_used + ' 天前' : '-';
    const audienceTitle = (a.audience||[]).join(", ");
    const authorBadge = a.author ? ' <span style="color:#8b949e;font-size:0.78em">@' + esc(a.author) + '</span>' : '';
    html += '<tr data-name="' + esc(a.name) + '">' +
      '<td><span class="atom-name" onclick="toggleAtomDetail(\\'' + esc(a.name) + '\\')">' + esc(a.name) + '</span>' + authorBadge + '</td>' +
      '<td><span class="atom-layer" title="audience: ' + esc(audienceTitle||"-") + '">' + esc(a.scope||"-") + '</span></td>' +
      '<td><span class="atom-layer">' + esc(a.layer) + '</span></td>' +
      '<td><span class="atom-conf ' + confClass + '">' + esc(a.confidence||"-") + '</span></td>' +
      '<td>' + (a.confirmations||0) + '</td>' +
      '<td>' + (a.readhits||0) + '</td>' +
      '<td title="' + esc(a.last_used||"") + '">' + daysAgo + '</td>' +
      '<td>' + (a.knowledge_count||'-') + '</td>' +
      '<td>' + (a.line_count||'-') + '</td>' +
    '</tr>';
    const detailVis = expandedAtoms.has(a.name) ? '' : 'none';
    html += '<tr id="detail-' + esc(a.name) + '" style="display:' + detailVis + '"><td colspan="9"><div class="atom-detail">' + esc(a.content||"") + '</div></td></tr>';
  }
  return html;
}

function toggleAtomDetail(name) {
  const row = document.getElementById("detail-" + name);
  if (!row) return;
  if (row.style.display === "none") {
    row.style.display = "";
    expandedAtoms.add(name);
  } else {
    row.style.display = "none";
    expandedAtoms.delete(name);
  }
}

let atomSortKey = "last_used";
let atomSortAsc = false;

function applySortToBody(data) {
  const sorted = [...data].sort((a, b) => {
    let va = a[atomSortKey] ?? "", vb = b[atomSortKey] ?? "";
    if (typeof va === "number" && typeof vb === "number") return atomSortAsc ? va - vb : vb - va;
    va = String(va); vb = String(vb);
    return atomSortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
  });
  document.getElementById("atomTableBody").innerHTML = buildAtomRows(sorted);
}

function reapplySort() { applySortToBody(atomsData); }

function sortAtoms(key) {
  if (atomSortKey === key) atomSortAsc = !atomSortAsc;
  else { atomSortKey = key; atomSortAsc = key === "name"; }
  applySortToBody(atomsData);
}

function filterAtoms(query) {
  // 為了向後相容（既有呼叫點用 filterAtoms(saved)），轉呼叫 applyAtomFilters
  const fi = document.getElementById("atomFilter");
  if (fi && typeof query === "string") fi.value = query;
  applyAtomFilters();
}

function applyAtomFilters() {
  const fi = document.getElementById("atomFilter");
  const sf = document.getElementById("atomScopeFilter");
  const q = (fi ? fi.value : "").toLowerCase();
  const scope = sf ? sf.value : "";
  const filtered = atomsData.filter(a => {
    if (scope && (a.scope||"") !== scope) return false;
    if (!q) return true;
    if (a.name.toLowerCase().includes(q)) return true;
    if ((a.triggers||[]).some(t => t.toLowerCase().includes(q))) return true;
    if ((a.related||[]).some(r => r.toLowerCase().includes(q))) return true;
    if ((a.layer||"").toLowerCase().includes(q)) return true;
    if ((a.scope||"").toLowerCase().includes(q)) return true;
    if ((a.author||"").toLowerCase().includes(q)) return true;
    return false;
  });
  applySortToBody(filtered);
}

// ─── Env Tab (Skills + MCP Servers) ───

async function renderEnv() {
  const el = document.getElementById("envContent");
  try {
    const [skills, mcps] = await Promise.all([
      fetch("/api/skills").then(r => r.json()),
      fetch("/api/mcp-servers").then(r => r.json()),
    ]);
    el.innerHTML = renderSkillsSection(skills) + renderMcpSection(mcps);
  } catch (e) {
    el.innerHTML = '<div class="empty">載入環境資訊失敗：' + esc(e.message) + '</div>';
  }
}

function renderSkillsSection(skills) {
  let html = '<div class="section-title">Slash Commands / Skills（' + skills.length + '）</div>';
  if (!skills.length) return html + '<div class="empty">無 commands。</div>';

  // 依分類分組
  const byCat = {};
  for (const s of skills) {
    const cat = s.category || "其他";
    if (!byCat[cat]) byCat[cat] = [];
    byCat[cat].push(s);
  }
  const cats = Object.keys(byCat).sort();

  for (const cat of cats) {
    html += '<details open style="margin-bottom:12px"><summary style="color:#58a6ff;cursor:pointer;padding:6px 0">' + esc(cat) + ' （' + byCat[cat].length + '）</summary>';
    html += '<table class="atom-table">';
    html += '<thead><tr><th>指令</th><th>說明</th><th>來源</th></tr></thead><tbody>';
    for (const s of byCat[cat]) {
      const sourceLabel = s.source === "global" ?
        '<span class="atom-layer">global</span>' :
        '<span class="atom-layer" style="background:#1f6feb33;color:#58a6ff">' + esc(s.source) + '</span>';
      html += '<tr>' +
        '<td><span class="atom-name" onclick="toggleSkillDetail(\\'' + esc(s.name) + '\\')">' + esc(s.command) + '</span></td>' +
        '<td style="color:#c9d1d9">' + esc(s.description||"-") + '</td>' +
        '<td>' + sourceLabel + '</td>' +
      '</tr>';
      html += '<tr id="skill-detail-' + esc(s.name) + '" style="display:none"><td colspan="3"><div class="atom-detail">' + esc(s.content||"") + '</div></td></tr>';
    }
    html += '</tbody></table></details>';
  }
  return html;
}

function toggleSkillDetail(name) {
  const row = document.getElementById("skill-detail-" + name);
  if (!row) return;
  row.style.display = row.style.display === "none" ? "" : "none";
}

function renderMcpSection(mcps) {
  let html = '<div class="section-title" style="margin-top:24px">MCP Servers（' + mcps.length + '）</div>';
  if (!mcps.length) return html + '<div class="empty">無 MCP servers。</div>';

  // 依來源分組
  const bySource = {};
  for (const m of mcps) {
    if (!bySource[m.source]) bySource[m.source] = [];
    bySource[m.source].push(m);
  }
  const sources = Object.keys(bySource).sort();

  for (const src of sources) {
    html += '<details open style="margin-bottom:12px"><summary style="color:#58a6ff;cursor:pointer;padding:6px 0">' + esc(src) + ' （' + bySource[src].length + '）</summary>';
    html += '<table class="atom-table">';
    html += '<thead><tr><th>名稱</th><th>類型</th><th>狀態</th><th>command / url</th><th>env keys</th></tr></thead><tbody>';
    for (const m of bySource[src]) {
      const statusBadge = m.enabled ?
        '<span class="status-dot status-online"></span>啟用' :
        '<span class="status-dot status-disabled"></span>停用';
      const cmdDisplay = m.url ? esc(m.url) :
        (esc(m.command || "-") + (m.args.length ? ' ' + esc(m.args.slice(-1)[0]) : ''));
      html += '<tr>' +
        '<td><strong style="color:#e6edf3">' + esc(m.name) + '</strong></td>' +
        '<td><span class="atom-layer">' + esc(m.type) + '</span></td>' +
        '<td>' + statusBadge + '</td>' +
        '<td style="font-family:monospace;font-size:0.78em;color:#8b949e;word-break:break-all">' + cmdDisplay + '</td>' +
        '<td style="font-size:0.78em;color:#8b949e">' + (m.env_keys.length ? esc(m.env_keys.join(", ")) : '-') + '</td>' +
      '</tr>';
    }
    html += '</tbody></table>';
    html += '<div style="font-size:0.75em;color:#484f58;margin-top:4px">config: ' + esc(bySource[src][0].config_file) + '</div>';
    html += '</details>';
  }
  return html;
}

// ─── Auto Refresh ───

function startAutoRefresh() {
  clearInterval(refreshTimer);
  if (document.getElementById("autoRefresh").checked) {
    refreshTimer = setInterval(refreshCurrentTab, 5000);
  }
}

document.getElementById("autoRefresh").addEventListener("change", startAutoRefresh);
renderSessions();
startAutoRefresh();
</script>
</body>
</html>`;
}

module.exports = { render };

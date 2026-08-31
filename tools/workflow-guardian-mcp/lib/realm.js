// realm.js — 範疇/路由分類（py 鏡像：lib/atom_locations.py，keep in sync；parity test_14/17/22）。
// cleanRealmSegment 供跨語言 parity eval-block 讀取本檔原始碼（test_22）；
// classifyRealm 由 test_17 直接 require 本模組對拍（詞庫 JSON 化後 eval-block 不再自足）。
const fs = require("fs");
const path = require("path");
const { CLAUDE_DIR, MEMORY_DIR } = require("./paths");

// 失敗家族（feedback-* / cognitive-patterns / memory-pipeline-*）是核心層的一個 Lv1 範疇資料夾：
// memory/Failures/<主題>/。舊址 _AIDocs/Failures/ 只供讀端相容（兩處都認），寫端一律落新址。
// MIRROR: lib/atom_locations.py FAILURES_* / LEGACY_FAILURES_* — keep in sync（parity test_14）。
const FAILURES_DIR = path.join(MEMORY_DIR, "Failures");
const FAILURES_REL = "memory/Failures";
const LEGACY_FAILURES_DIR = path.join(CLAUDE_DIR, "_AIDocs", "Failures");
const LEGACY_FAILURES_REL = "_AIDocs/Failures";
const FAILURES_RELS = [FAILURES_REL, LEGACY_FAILURES_REL];
const FEEDBACK_TITLE_PREFIX = "feedback-";
// V5+ local realm（範疇限定）：本地知識物理落 _AIDocs/_atoms/<domain>/，索引仍在 memory/_atom_index.json。
// realm 由 index path 前綴推導（不存欄位）；注入閘門只在 cwd∈~/.claude 才納入。
// MIRROR: lib/atom_locations.py:LOCAL_ATOMS_* / local_write_target — keep in sync.
const LOCAL_ATOMS_DIR = path.join(CLAUDE_DIR, "_AIDocs", "_atoms");
const LOCAL_ATOMS_REL = "_AIDocs/_atoms";
const LOCAL_REALM_DOMAINS = new Set(["World", "Tools", "MemDev"]);
const LOCAL_REALM_DEFAULT_DOMAIN = "Else";
// 階層 domain 路徑最大深度（MIRROR: lib/atom_locations.py:LOCAL_REALM_MAX_DEPTH）。
const LOCAL_REALM_MAX_DEPTH = 7;
// V5+ realm 分類器。演算法鏡像 lib/atom_locations.py:classify_realm（parity test_17 守漂移）；
// 詞庫/核心保護清單/權重不再手抄——單一來源 memory/_meta/realm-lexicon.json，py/js 兩端讀同檔。
// 收詞守則見 py 端註解：核心保護硬擋 → 實例詞庫 → 安全預設 core；只掃 name + triggers。
const REALM_LEXICON_PATH = path.join(MEMORY_DIR, "_meta", "realm-lexicon.json");
// fallback 內建最小保護清單（JSON 缺失/損毀時仍硬擋最關鍵核心名；詞庫停用 → 全判 core）
function loadRealmLexicon() {
  try {
    const d = JSON.parse(fs.readFileSync(REALM_LEXICON_PATH, "utf-8"));
    const prefixes = (d.core_protected_prefixes || []).map(String);
    const exact = new Set((d.core_protected_exact || []).map(String));
    const lexicon = d.lexicon || {};
    const nameW = Number(d.name_weight), trigW = Number(d.trigger_weight);
    if (!prefixes.length || !exact.size || !Object.keys(lexicon).length ||
        !Number.isFinite(nameW) || !Number.isFinite(trigW)) {
      throw new Error("empty/missing section");
    }
    return { prefixes, exact, lexicon, nameW, trigW };
  } catch (e) {
    // fail-open + 浮訊號（可觀測性鐵律）：stderr 不污染 MCP stdout 協議
    process.stderr.write(
      `[realm.js] realm-lexicon.json unavailable (${e.message}); ` +
      "fallback to built-in minimal core-protected list; lexicon disabled (all->core)\n");
    return {
      prefixes: ["decisions", "workflow-", "toolchain", "feedback-", "memory-pipeline-", "atom-"],
      exact: new Set(["preferences", "cognitive-patterns"]),
      lexicon: {}, nameW: 10, trigW: 1,
    };
  }
}
const _REALM_LEX = loadRealmLexicon();  // 模組載入時讀一次（快取；改 JSON 需重啟 MCP）
const LOCAL_REALM_CORE_PROTECTED_PREFIXES = _REALM_LEX.prefixes;
const LOCAL_REALM_CORE_PROTECTED_EXACT = _REALM_LEX.exact;
const LOCAL_REALM_LEXICON = _REALM_LEX.lexicon;
const LOCAL_REALM_NAME_WEIGHT = _REALM_LEX.nameW;
const LOCAL_REALM_TRIGGER_WEIGHT = _REALM_LEX.trigW;

/** Realm 分類器（安全預設 core，僅高信心判 local）。回 {realm, domain, matched, protected}。
 *  只掃 name + triggers。MIRROR: lib/atom_locations.py:classify_realm — keep in sync. */
function classifyRealm(name, triggers) {
  const nm = (name || "").trim().toLowerCase();
  // 1) 核心保護硬擋（先於詞庫）
  if (LOCAL_REALM_CORE_PROTECTED_EXACT.has(nm) ||
      LOCAL_REALM_CORE_PROTECTED_PREFIXES.some(p => nm.startsWith(p))) {
    return { realm: "core", domain: null, matched: [], protected: true };
  }
  // 2) 實例詞庫掃描（name 權重 > trigger 權重，domain 消歧）
  const trigBlob = (triggers || []).map(t => (t || "").toLowerCase()).join(" ");
  const scores = {};
  const matched = [];
  for (const [term, dom] of Object.entries(LOCAL_REALM_LEXICON)) {
    let hit = 0;
    if (nm.includes(term)) hit += LOCAL_REALM_NAME_WEIGHT;
    if (trigBlob.includes(term)) hit += LOCAL_REALM_TRIGGER_WEIGHT;
    if (hit) { scores[dom] = (scores[dom] || 0) + hit; matched.push(term); }
  }
  if (Object.keys(scores).length === 0) {
    return { realm: "core", domain: null, matched: [], protected: false };
  }
  // 平手 → 在「實際命中的 domain」裡依固定序取首位（對拍 py max(sorted(scores), key)）。
  // 不得只在 LOCAL_REALM_DOMAINS 三元集合裡挑：詞庫一旦映到第 4 個 domain 或多段路徑
  // （OS/Windows），會回到分數 0 的預設首位、與 py 分歧。
  const domsSorted = Object.keys(scores).sort();
  let bestDom = domsSorted[0];
  for (const d of domsSorted) {
    if ((scores[d] || 0) > (scores[bestDom] || 0)) bestDom = d;
  }
  // Domain 段字元集 guard（base lexicon 恆過；防污染詞庫的亂碼 domain 流出 —
  // 韓文實案）。MIRROR: lib/atom_locations.py:classify_realm → _clean_segment。
  // 注意：須自足於 test_17 eval block（不得引用 cleanRealmSegment，定義在 block 外）。
  const segBad = (sg) => {
    const t = sg.replace(/\s+/g, " ").trim();
    return !t || t[0] === "_" || t[0] === "." || /[<>:"|?*]/.test(t) ||
           !/^[\x20-\x7E㐀-䶿一-鿿]+$/.test(t);
  };
  if (bestDom.split("/").filter(sg => sg.trim()).some(segBad)) {
    bestDom = LOCAL_REALM_DEFAULT_DOMAIN;
  }
  return {
    realm: "local", domain: bestDom,
    matched: [...new Set(matched)].sort(), protected: false,
  };
}
// ─── Atom Write/Promote Helpers ────────────────────────────────────────────

/** Convert title to a safe filename slug (lowercase, hyphens, no special chars) */
function slugify(title) {
  return title
    .toLowerCase()
    .replace(/[\s_]+/g, "-")
    .replace(/[^a-z0-9\u4e00-\u9fff\u3400-\u4dbf-]/g, "")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    || "untitled";
}

/** Detect an existing atom file in memDir whose name normalizes to the SAME slug
 *  but differs literally — e.g. a legacy underscore atom "client_il.md" when the
 *  incoming slug is "client-il" (slugify maps _→-). Without this guard, mode=create
 *  silently FORKS a near-duplicate atom that no append/replace path can ever reach.
 *  Returns the colliding filename (e.g. "client_il.md") or null. */
// BFS 掃 memDir 全樹（範疇資料夾必備後，同 slug 的分隔符變體可能住任一 memory/<Lv1>/…）；
// 跳 `_`/`.` 前綴目錄（_meta/_drafts/_pending_review…）。回相對 memDir 的檔名（posix 分隔）。
function findSeparatorVariant(memDir, slug) {
  const queue = [memDir];
  while (queue.length) {
    const cur = queue.shift();
    let entries;
    try { entries = fs.readdirSync(cur, { withFileTypes: true }); } catch { continue; }
    for (const e of entries) {
      if (e.isDirectory()) {
        if (e.name.startsWith("_") || e.name.startsWith(".")) continue;
        queue.push(path.join(cur, e.name));
        continue;
      }
      if (!e.isFile() || !e.name.endsWith(".md")) continue;
      const base = e.name.slice(0, -3);
      if (base === slug) continue;             // exact name handled by existsSync / locate
      if (slugify(base) === slug) {            // separator-variant collision
        return path.relative(memDir, path.join(cur, e.name)).replace(/\\/g, "/");
      }
    }
  }
  return null;
}
// V4: project root marker walk (mirrors hooks/wg_paths.find_project_root)
function findProjectRoot(cwd) {
  if (!cwd) return null;
  let p = path.resolve(cwd);
  for (let i = 0; i < 4; i++) {
    if (fs.existsSync(path.join(p, ".claude", "memory", "MEMORY.md"))) return p;
    if (fs.existsSync(path.join(p, "_AIDocs"))) return p;
    if (fs.existsSync(path.join(p, ".git")) || fs.existsSync(path.join(p, ".svn"))) return p;
    const parent = path.dirname(p);
    if (parent === p) break;
    p = parent;
  }
  return null;
}

// Mirrors wg_roles.get_current_user (env override + os user).
function getCurrentUser() {
  if (process.env.CLAUDE_USER) return process.env.CLAUDE_USER;
  try { return require("os").userInfo().username; } catch { return "unknown"; }
}

// SPEC 7.4 first-version sensitive audience set.
const SENSITIVE_AUDIENCE = new Set(["architecture", "decision"]);
function isSensitiveAudience(audience) {
  if (!Array.isArray(audience)) return false;
  return audience.some(a => SENSITIVE_AUDIENCE.has(String(a).trim().toLowerCase()));
}

/** Resolve the memory directory for a given scope.
 *  V4: shared / role / personal land in project subdirs;
 *  legacy "project" maps to "shared"; "global" unchanged.
 *  Returns { dir, error } — caller checks error.
 */
function resolveMemDir(scope, projectCwd, opts = {}) {
  scope = scope || "shared";

  // ─── S3.2 P3+P4: cwd-scope mismatch 防護 ────────────────────────────────
  // 防止「在專案 root 下用 scope=global 寫個人/專案知識到全域」與
  // 「在 ~/.claude 下用 scope=shared/role/personal 落到不存在的 V4 子層」。
  // force_global escape hatch 給 migration / 測試使用。
  const normCwd = (s) => {
    if (!s) return "";
    try { return path.resolve(s).toLowerCase(); }
    catch { return String(s).toLowerCase(); }
  };
  const claudeDirNorm = normCwd(CLAUDE_DIR);
  const cwdNorm = normCwd(projectCwd);
  const isUnderClaudeDir = cwdNorm && (
    cwdNorm === claudeDirNorm ||
    cwdNorm.startsWith(claudeDirNorm + path.sep.toLowerCase()) ||
    cwdNorm.startsWith(claudeDirNorm + "/")
  );

  if (scope === "global" && !opts.force_global) {
    // P3: 若 cwd 落在某個專案 root（非 ~/.claude）→ 拒絕（避免污染 global）
    if (cwdNorm && !isUnderClaudeDir) {
      const projRoot = findProjectRoot(projectCwd);
      if (projRoot && normCwd(projRoot) !== claudeDirNorm) {
        return { error:
          `scope=global rejected: cwd=${projectCwd} is inside project root=${projRoot}; ` +
          `use scope=shared/role/personal for project knowledge, or pass force_global=true`,
        };
      }
    }
  }

  if ((scope === "shared" || scope === "role" || scope === "personal") && isUnderClaudeDir) {
    // P4: ~/.claude 本身沒有 V4 sub-scope 結構（已被 P1 防護擋住）
    return { error:
      `scope=${scope} rejected: cwd=${projectCwd} is under ~/.claude itself; ` +
      `use scope=global for cross-project knowledge`,
    };
  }
  // ─── /S3.2 P3+P4 ────────────────────────────────────────────────────────

  if (scope === "global") {
    fs.mkdirSync(MEMORY_DIR, { recursive: true });
    return { dir: MEMORY_DIR, base: MEMORY_DIR };
  }

  // Legacy: scope=project returns root memory dir (no V4 subdir).
  // atom_write should pre-map project→shared via callers; here we keep legacy
  // root-dir behavior for atom_promote / readers that still pass "project".
  if (scope === "project" && projectCwd) {
    const projMem = path.join(projectCwd, ".claude", "memory");
    if (fs.existsSync(projMem)) return { dir: projMem, base: projMem };
    const norm = projectCwd.replace(/\\/g, "/").replace(/\/+$/, "");
    const slug = norm.replace(/[^a-zA-Z0-9]/g, "-").replace(/-+/g, "-");
    const projDir = path.join(CLAUDE_DIR, "projects", slug, "memory");
    if (fs.existsSync(projDir)) return { dir: projDir, base: projDir };
    return { dir: projMem, base: projMem };
  }

  if (scope === "role" && !opts.role) {
    return { error: "scope=role requires 'role' parameter (e.g., 'art', 'programmer')" };
  }
  if (scope !== "shared" && scope !== "role" && scope !== "personal") {
    return { error: `Unknown scope: ${scope}` };
  }

  const root = findProjectRoot(projectCwd || "");
  if (!root) {
    return { error: `No project root found for scope=${scope} (need .git/.svn/_AIDocs/.claude/memory/MEMORY.md marker under ${projectCwd || "(no cwd)"})` };
  }
  // ~/.claude itself is global memory; reject V4 sub-scopes there
  try {
    if (path.resolve(root) === path.resolve(CLAUDE_DIR)) {
      return { error: `cwd is ~/.claude itself; use scope=global for cross-project knowledge` };
    }
  } catch {}

  const base = path.join(root, ".claude", "memory");
  let dir;
  if (scope === "shared") dir = path.join(base, "shared");
  else if (scope === "role") dir = path.join(base, "roles", opts.role);
  else dir = path.join(base, "personal", opts.user);

  fs.mkdirSync(dir, { recursive: true });
  return { dir, base };
}
/** index path 屬失敗家族（新址 memory/Failures/ 或舊址 _AIDocs/Failures/）。
 *  MIRROR: lib/atom_locations.py:is_in_failures_path。 */
function isInFailuresPath(relPath) {
  const p = relPath || "";
  return FAILURES_RELS.some((r) => p.startsWith(r + "/"));
}

/** 已註冊 Failures atom（非 feedback- 前綴，如 cognitive-patterns / memory-pipeline-*）。
 *  新舊兩址的 index path 都認。MIRROR: lib/atom_locations.py:failures_atom_stems ∈ is_failures_routed_title。
 *  缺此判定時這些 atom 的 append/replace 會在 memory/ 根找不到檔。 */
function isRegisteredFailuresStem(slug) {
  try {
    const data = JSON.parse(
      fs.readFileSync(path.join(MEMORY_DIR, "_atom_index.json"), "utf-8"));
    return (data.atoms || []).some(
      (a) => isInFailuresPath(a.path) && path.basename(a.path || "", ".md") === slug);
  } catch {
    return false;
  }
}

/** 失敗家族路由疊加：把 resolveMemDir 結果改寫為 memory/Failures/ 目的地（主題子層由 py 端路由決定）。
 *  索引仍在 memory/_atom_index.json（單一索引來源）。
 *  MIRROR: lib/atom_locations.py:failures_write_target — keep in sync.
 *  Returns: { memDir, baseDir, indexDir, indexRoot, routedToFailures }.
 */
function applyFeedbackRouting(resolved, slug, scope) {
  // 預設沿用既有語意：indexDir = baseDir, indexRoot = baseDir 的父目錄
  let memDir = resolved.dir;
  let baseDir = resolved.base;
  let indexDir = baseDir;
  let indexRoot = path.dirname(baseDir);
  let routedToFailures = false;
  if (scope === "global" &&
      (slug.startsWith(FEEDBACK_TITLE_PREFIX) || isRegisteredFailuresStem(slug))) {
    fs.mkdirSync(FAILURES_DIR, { recursive: true });
    memDir = FAILURES_DIR;
    baseDir = FAILURES_DIR;
    indexDir = MEMORY_DIR;
    indexRoot = CLAUDE_DIR;
    routedToFailures = true;
  }
  return { memDir, baseDir, indexDir, indexRoot, routedToFailures };
}

/** 單段正規化（path-traversal 最後防線）。MIRROR: lib/atom_locations.py:_clean_segment。
 *  非法（空 / 含分隔 / `_`·`.` 前綴 / 不安全字元 / 非 CJK·ASCII 字元）→ ""
 *  （caller 截斷/退 fail-safe）。字元集 guard：LLM 生成 domain 視為不可信輸入，
 *  跨文字系統字元（Hangul「자동화」實案）穿透 snap 防線 → 整段拒。
 *  MIRROR: lib/atom_locations.py:_SEG_ALLOWED_RE（parity test_22）。 */
function cleanRealmSegment(seg) {
  const s = (seg || "").replace(/\s+/g, " ").trim();
  if (!s || s.includes("/") || s.includes("\\")) return "";
  if (s[0] === "_" || s[0] === ".") return "";
  if (/[<>:"|?*]/.test(s)) return "";
  // 字元集 guard regex 內聯（test_22 eval block 自足性：不得引用函式外 const）
  if (!/^[\x20-\x7E㐀-䶿一-鿿]+$/.test(s)) return "";
  return s;
}

/** scope=shared + subdir 的 create 落點：`<memory root>/<subdir>/`（相對 base，多段斜線）。
 *  一 repo 多專案分區佈局（memory/projects/<專案名>/）一次寫到位。
 *  逐段 cleanRealmSegment 沙盒化，再拒受保護段（personal/roles/episodic 等定位 skip 目錄）。
 *  MIRROR: lib/atom_locations.py:project_subdir_target — keep in sync。
 *  Returns: { dir } 或 { error }。合法時 mkdir-p。 */
const SUBDIR_PROTECTED = new Set([
  // SYNC: lib/atom_locations.py _LOCATE_SKIP_DIRS（`_` 前綴段 cleanRealmSegment 已拒，
  // 此集合防的是無底線的保護目錄名）
  "episodic", "templates", "personal", "roles", "wisdom",
]);
function resolveSubdirTarget(base, subdir) {
  const rawSegs = String(subdir || "").replace(/\\/g, "/").split("/")
    .filter((s) => s.trim());
  if (rawSegs.length === 0) return { error: "invalid subdir: subdir is empty" };
  const segs = [];
  for (const raw of rawSegs) {
    const seg = cleanRealmSegment(raw);
    if (!seg) return { error: `invalid subdir: segment invalid: '${raw}'` };
    if (SUBDIR_PROTECTED.has(seg)) {
      return { error: `invalid subdir: segment protected: '${seg}'` };
    }
    segs.push(seg);
  }
  const dir = path.join(base, ...segs);
  fs.mkdirSync(dir, { recursive: true });
  return { dir };
}

/** V5+ local-realm 路由：本地範疇 atom 物理落 _AIDocs/_atoms/<domain_path>/。
 *  realm 由 index path 前綴推導（不存欄位）。索引仍在 memory/_atom_index.json。
 *  domain 支援多段階層路徑（"OS/Windows/WSL"，mkdir-p 全鏈）；空/全非法 → DEFAULT。
 *  每段過 cleanRealmSegment 防寫到樹外。MIRROR: lib/atom_locations.py:local_write_target。
 *  Returns: { memDir, baseDir, indexDir, indexRoot }.
 */
function applyLocalRouting(domain) {
  const dom = (domain || "").trim() || LOCAL_REALM_DEFAULT_DOMAIN;
  let segs = dom.split("/").map(cleanRealmSegment).filter(Boolean).slice(0, LOCAL_REALM_MAX_DEPTH);
  if (segs.length === 0) segs = [LOCAL_REALM_DEFAULT_DOMAIN];  // fail-safe，永不寫到樹外
  const memDir = path.join(LOCAL_ATOMS_DIR, ...segs);
  fs.mkdirSync(memDir, { recursive: true });
  return { memDir, baseDir: memDir, indexDir: MEMORY_DIR, indexRoot: CLAUDE_DIR };
}

// 核心層範疇分類法：單一來源 memory/_meta/taxonomy.json（py: lib/atom_taxonomy.py 讀同檔）。
// js 端只拿來做錯誤訊息與快速預檢；路由邏輯以 py 端為準。
const TAXONOMY_PATH = path.join(MEMORY_DIR, "_meta", "taxonomy.json");
// 缺檔/壞檔 → null + stderr 訊號（不藏第二份手抄清單；寫入閘由 py 端拒寫）。
function loadTaxonomy() {
  try {
    const d = JSON.parse(fs.readFileSync(TAXONOMY_PATH, "utf-8"));
    const core = d.core;
    if (!core || typeof core !== "object" || !Object.keys(core).length) {
      throw new Error("core section empty");
    }
    if (d.reserved !== undefined && !Array.isArray(d.reserved)) {
      throw new Error("reserved must be list");
    }
    return d;
  } catch (e) {
    process.stderr.write(
      `[realm.js] taxonomy.json unavailable (${e.message}); ` +
      "CORE_CATEGORIES empty; category gate handled by py side\n");
    return null;
  }
}
const _TAXONOMY = loadTaxonomy();  // 模組載入時讀一次（改 JSON 需重啟 MCP）
const CORE_CATEGORIES = _TAXONOMY ? Object.keys(_TAXONOMY.core) : [];
// 範疇資料夾禁用名（小寫比對）：撞 atom 掃描 skip 名單、subdir 保護段、舊址小寫 failures。
// MIRROR: lib/atom_locations.py CATEGORY_RESERVED_SEGMENTS（parity test_14c）。
const CATEGORY_RESERVED_SEGMENTS = new Set([
  ...((_TAXONOMY && _TAXONOMY.reserved) || []).map(String),
  ...SUBDIR_PROTECTED,
  "shared", "roles", "projects", "unity", "memory", "failures",
].map((s) => s.toLowerCase()));

// ─── Write-gate 去重層清單 ─────────────────────────────────────────────────

/** 專案記憶根（<root>/.claude/memory）→ 向量庫 layer 標籤用的專案 slug。
 *  MIRROR: hooks/wg_core.py:cwd_to_project_slug（: \ / . → -，全小寫；c:\Projects → c--projects）。 */
function projectSlugOf(memBase) {
  const root = path.dirname(path.dirname(memBase));
  return root.replace(/[:\\/.]/g, "-").toLowerCase();
}

/** 去重只比「寫入者能 append 到」的層：
 *  global → global + ~/.claude 本地 atom
 *  shared → 再加 shared:<slug>；role → 再加 role:<slug>:<role>；personal → 再加 personal:<slug>:<user>
 *  別的專案、別人的 personal 層一律不比（比到了也不能 append 過去，只會卡死寫入）。 */
function dedupLayersFor(scope, memBase, { role, user } = {}) {
  const layers = ["global", "extra:local-atoms"];
  if (scope === "global" || !memBase) return layers;
  const slug = projectSlugOf(memBase);
  layers.push(`shared:${slug}`);
  if (scope === "role" && role) layers.push(`role:${slug}:${role}`);
  if (scope === "personal" && user) layers.push(`personal:${slug}:${user}`);
  return layers;
}

module.exports = {
  classifyRealm, slugify, findSeparatorVariant, findProjectRoot, getCurrentUser,
  isSensitiveAudience, resolveMemDir, isInFailuresPath, isRegisteredFailuresStem,
  applyFeedbackRouting, cleanRealmSegment, applyLocalRouting, resolveSubdirTarget, loadTaxonomy,
  projectSlugOf, dedupLayersFor,
  FAILURES_DIR, FAILURES_REL, LEGACY_FAILURES_DIR, LEGACY_FAILURES_REL, FAILURES_RELS,
  FEEDBACK_TITLE_PREFIX, LOCAL_ATOMS_DIR, LOCAL_REALM_DOMAINS, LOCAL_REALM_DEFAULT_DOMAIN,
  TAXONOMY_PATH, CORE_CATEGORIES, CATEGORY_RESERVED_SEGMENTS,
};

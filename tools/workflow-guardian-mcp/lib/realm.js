// realm.js — 範疇/路由分類（py 鏡像：lib/atom_locations.py，keep in sync；parity test_14/17/22）。
// classifyRealm / cleanRealmSegment 供跨語言 parity eval-block 讀取本檔原始碼。
const fs = require("fs");
const path = require("path");
const { CLAUDE_DIR, MEMORY_DIR } = require("./paths");

// V5+ feedback-* 路由常數（MIRROR: lib/atom_locations.py — keep in sync）
const FAILURES_DIR = path.join(CLAUDE_DIR, "_AIDocs", "Failures");
const FAILURES_REL = "_AIDocs/Failures";
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
// V5+ realm 分類器（MIRROR: lib/atom_locations.py:classify_realm / CORE_PROTECTED_* /
// LOCAL_REALM_LEXICON — keep in sync；parity test_17 守漂移）。設計守則見 py 端註解：
// 核心保護硬擋 → 實例詞庫 → 安全預設 core；只掃 name + triggers，絕不用記憶系統通用詞。
const LOCAL_REALM_CORE_PROTECTED_PREFIXES = [
  "decisions", "workflow-", "toolchain", "feedback-", "memory-pipeline-", "atom-",
];
const LOCAL_REALM_CORE_PROTECTED_EXACT = new Set([
  "preferences", "cognitive-patterns", "goal-driven-verify-loopkarpathy-吸收",
  "自己flag的維護動作直接做完不要反問",  // 跨專案行為規則,曾遭 LLM sweep 誤搬 local→硬擋
  "記憶汙染與上下文腐化-注入萃取自檢",  // 跨專案 governance atom,談記憶術語易誤判 local→硬擋
  // 跨專案 meta-cognitive atom（驗證紀律 / escalation 誤判辨識）：曾遭 sweep 誤降 local→硬擋
  "品質完整性判定須讀完整內容-勿從截斷採樣斷言",
  "escalation-hook-在-edit-count-proxy-上-false-fire-的辨識無真實失敗迴圈時不盲從不編造",
]);
const LOCAL_REALM_LEXICON = {
  "腦內世界": "World", "world.html": "World", "reconcile-render": "World",
  "環境演化": "World", "env-layer": "World",
  "gdoc": "Tools", "harvester": "Tools", "electron-uia": "Tools",
  "electron 自動化": "Tools", "codex": "Tools", "logs_2.sqlite": "Tools", "反編譯": "Tools",
  "guardian-dashboard": "MemDev", "孤兒佔埠": "MemDev", "eaddrinuse": "MemDev",
};
const LOCAL_REALM_NAME_WEIGHT = 10;
const LOCAL_REALM_TRIGGER_WEIGHT = 1;

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
  // 平手 → 依 sorted(LOCAL_REALM_DOMAINS) 固定序首位（對拍 py max(sorted, key)）
  const domsSorted = [...LOCAL_REALM_DOMAINS].sort();
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
function findSeparatorVariant(memDir, slug) {
  let entries;
  try { entries = fs.readdirSync(memDir); } catch { return null; }
  for (const name of entries) {
    if (!name.endsWith(".md")) continue;
    const base = name.slice(0, -3);
    if (base === slug) continue;             // exact name handled by existsSync
    if (slugify(base) === slug) return name; // separator-variant collision
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
/** 已註冊 Failures atom（非 feedback- 前綴，如 cognitive-patterns / memory-pipeline-*）。
 *  MIRROR: lib/atom_locations.py:failures_atom_stems ∈ is_failures_routed_title。
 *  缺此判定時這些 atom 的 append/replace 會在 memory/ 找不到檔。 */
function isRegisteredFailuresStem(slug) {
  try {
    const data = JSON.parse(
      fs.readFileSync(path.join(MEMORY_DIR, "_atom_index.json"), "utf-8"));
    return (data.atoms || []).some(
      (a) => (a.path || "").startsWith(FAILURES_REL + "/") &&
        path.basename(a.path, ".md") === slug);
  } catch {
    return false;
  }
}

/** V5+ feedback-* 路由疊加。將 resolveMemDir 結果改寫為 _AIDocs/Failures/ 目的地。
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

module.exports = {
  classifyRealm, slugify, findSeparatorVariant, findProjectRoot, getCurrentUser,
  isSensitiveAudience, resolveMemDir, isRegisteredFailuresStem, applyFeedbackRouting,
  cleanRealmSegment, applyLocalRouting,
  FAILURES_DIR, FAILURES_REL, FEEDBACK_TITLE_PREFIX, LOCAL_ATOMS_DIR,
  LOCAL_REALM_DOMAINS, LOCAL_REALM_DEFAULT_DOMAIN,
};

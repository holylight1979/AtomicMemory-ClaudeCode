// paths.js — 路徑錨與載入器（CLAUDE/WORKFLOW/MEMORY/TOOLS/CONFIG/REGISTRY/VERSION）＋ config/registry/version 讀取。
// 全樹最底層葉模組（零內部相依）。
const fs = require("fs");
const path = require("path");

const CLAUDE_DIR = path.join(require("os").homedir(), ".claude");
const WORKFLOW_DIR = path.join(CLAUDE_DIR, "workflow");
const MEMORY_DIR = path.join(CLAUDE_DIR, "memory");
const TOOLS_DIR = path.join(CLAUDE_DIR, "tools");
const CONFIG_PATH = path.join(WORKFLOW_DIR, "config.json");
const REGISTRY_PATH = path.join(MEMORY_DIR, "project-registry.json");
const VERSION_PATH = path.join(CLAUDE_DIR, "version.json");
function loadVersions() {
  try { return JSON.parse(fs.readFileSync(VERSION_PATH, "utf-8")); }
  catch { return { guardian: "0.0.0", atom_memory: "?" }; }
}
const VERSIONS = loadVersions();

function loadRegistry() {
  try {
    return JSON.parse(fs.readFileSync(REGISTRY_PATH, "utf-8"));
  } catch {
    return { projects: {} };
  }
}

/** Returns [{slug, memDir}] for all registered projects that have .claude/memory/ */
function getRegistryMemDirs() {
  const reg = loadRegistry();
  const results = [];
  for (const [slug, info] of Object.entries(reg.projects || {})) {
    if (!info.root) continue;
    const newMem = path.join(info.root, ".claude", "memory");
    if (fs.existsSync(newMem)) {
      results.push({ slug, memDir: newMem });
    }
  }
  return results;
}

function loadConfig() {
  try {
    return JSON.parse(fs.readFileSync(CONFIG_PATH, "utf-8"));
  } catch {
    return {};
  }
}

// ── Python 直譯器解析 ──────────────────────────────────────────────────────
// Windows 裸 spawn "python" 會被 PATH 順位上的 Microsoft Store 佔位程式攔走
// （零輸出、exit 9009）→ 下游 JSON 解析炸 "Unexpected end of JSON input" 且
// stderr 無線索。解析順序：WG_PYTHON env → 常見安裝路徑探測 → fail-open 回
// "python"（非 Windows / 未知佈局仍走 PATH）。模組載入時解析一次。
function resolvePythonExe() {
  const envPy = process.env.WG_PYTHON;
  if (envPy) {
    try { if (fs.existsSync(envPy)) return envPy; } catch {}
  }
  if (process.platform !== "win32") return "python";
  const candidates = [];
  const local = process.env.LOCALAPPDATA;
  const versions = ["314", "313", "312", "311", "310"];
  if (local) {
    for (const v of versions) {
      candidates.push(path.join(local, "Programs", "Python", "Python" + v, "python.exe"));
    }
    candidates.push(path.join(local, "Python", "bin", "python.exe"));
  }
  for (const v of versions) {
    candidates.push("C:\\Python" + v + "\\python.exe");
    candidates.push("C:\\Program Files\\Python" + v + "\\python.exe");
  }
  for (const c of candidates) {
    try { if (fs.existsSync(c)) return c; } catch {}
  }
  return "python";
}
const PYTHON_EXE = resolvePythonExe();
// fail-open 必浮訊號：退回裸 "python" 時在 stderr 留一行（MCP stdio 的 stderr 不進協定），
// 否則撞到 Store 佔位程式只會看到下游 "Unexpected end of JSON input"，無從追。
const PYTHON_EXE_FALLBACK = PYTHON_EXE === "python" && process.platform === "win32";
if (PYTHON_EXE_FALLBACK) {
  process.stderr.write("[workflow-guardian] WARN: 找不到 Python 絕對路徑，退回裸 \"python\"（可能被 Microsoft Store 佔位程式攔走）；請設 WG_PYTHON 指向 python.exe\n");
}

module.exports = {
  CLAUDE_DIR, WORKFLOW_DIR, MEMORY_DIR, TOOLS_DIR, CONFIG_PATH, REGISTRY_PATH, VERSION_PATH,
  loadVersions, VERSIONS, loadRegistry, getRegistryMemDirs, loadConfig,
  resolvePythonExe, PYTHON_EXE, PYTHON_EXE_FALLBACK,
};

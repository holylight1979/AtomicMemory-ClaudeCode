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

module.exports = {
  CLAUDE_DIR, WORKFLOW_DIR, MEMORY_DIR, TOOLS_DIR, CONFIG_PATH, REGISTRY_PATH, VERSION_PATH,
  loadVersions, VERSIONS, loadRegistry, getRegistryMemDirs, loadConfig,
};

// realm.js — MCP js 端僅存的「非路由」輔助：使用者名、write-gate 去重層清單。
//
// atom 該落在哪（scope/realm/feedback/subdir/待審/範疇閘/cwd 防護/既有檔定位/分隔符變體）
// 一律由 py lib/atom_io.locate_atom 裁決（atom-tools.js 經 spawnAtomCli("locate") 取用）。
// 本檔不得再長出第二套路由或分類邏輯（verify_atom_io_equivalence test_14/17 守此不變式）。
const path = require("path");

// Mirrors wg_roles.get_current_user (env override + os user).
function getCurrentUser() {
  if (process.env.CLAUDE_USER) return process.env.CLAUDE_USER;
  try { return require("os").userInfo().username; } catch { return "unknown"; }
}

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

module.exports = { getCurrentUser, projectSlugOf, dedupLayersFor };

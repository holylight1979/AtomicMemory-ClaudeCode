"""verify_tools_data_root_lib.py：lib 四支（project_root、atom_locations、atom_taxonomy、realm_gate）、wg_core 的 Logs、
MCP paths.js 的資料常數都看資料根（lib.project_root.claude_data_dir），程式碼仍看檔案位置。

做什麼（每案開冷啟動子行程：常數在 import 時算好、預設參數在定義時綁死；一律 -P 且 cwd 在 tmp，cwd 不進 sys.path）：
- 常數：WG_CLAUDE_DIR＝tmp 資料根 → lib 常數與預設參數都在 tmp 資料根；`lib.xxx` 與頂層 `xxx` 兩種載法都測；
  沒設 → 都在 tmp家/.claude。
- 真的讀寫 tmp：詞庫、taxonomy、config、registry 從 tmp 資料根讀；guard log 寫進 tmp資料根/Logs；
  資料根本身不能當宣告根；資料根與程式碼根的頂層資料夾名都不當專名。
- lib 尾巴：provenance、atom_spec 的 Depends 根、ollama_extract_core 的 debug log、overview_scaffold 的退路都在 tmp 資料根；
  核心根＝資料根或程式碼根之內、或資料根 repo 的 git worktree（範疇閘與 atom 落點同一個判斷）。
- 要 hooks/ 在 sys.path 的三支：wg_evasion 禁語表、UPS 決策項相對路徑看資料根；version_guard 掃資料根或程式碼根內的檔。
- MCP：同一組 env（tmp／空白／不設）下 node 的 paths.js 與 Python 的 claude_data_dir() 算出同一個資料根，
  version.json 看程式碼根，config／registry／org-memory.local.json 從 tmp 資料根讀。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_tools_data_root_lib.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parents[2]
MCP_LIB = TREE / "tools" / "workflow-guardian-mcp" / "lib"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

LIB_CONSTS = {
    "al": ["CLAUDE_DIR", "GLOBAL_MEMORY_DIR", "FAILURES_DIR", "LEGACY_FAILURES_DIR", "LOCAL_ATOMS_DIR",
           "LEARNED_LEXICON_PATH", "TAXONOMY_LEARNED_PATH", "REALM_LEXICON_PATH"],
    "at": ["CLAUDE_DIR", "TAXONOMY_PATH", "CONFIG_PATH"],
    "rg": ["CLAUDE_DIR", "REGISTRY_PATH"],
    "pr": ["CLAUDE_DIR"],
}

CONST_PROBE = r"""
import json, sys
tree, mode, consts = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
if mode == "pkg":
    sys.path.insert(0, tree)
    from lib import atom_locations as al, atom_taxonomy as at, realm_gate as rg, project_root as pr
else:
    sys.path.insert(0, tree + "/lib")
    import atom_locations as al, atom_taxonomy as at, realm_gate as rg, project_root as pr
mods = {"al": al, "at": at, "rg": rg, "pr": pr}
out = {f"{m}.{n}": str(getattr(mods[m], n)) for m, names in consts.items() for n in names}
for f in ("load_taxonomy", "core_categories", "gate_enabled"):
    out[f"at.{f}.default"] = str(getattr(at, f).__defaults__[0])
out["files"] = {k: getattr(v, "__file__", "") for k, v in mods.items()}
print("PROBE_JSON " + json.dumps(out))
"""

READ_PROBE = r"""
import json, sys
from pathlib import Path
tree, data, proj = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, tree)
sys.path.insert(0, tree + "/hooks")
from lib import atom_locations as al, atom_taxonomy as at, realm_gate as rg, project_root as pr, atom_io
import wg_core
out = {"lexicon_source": al.core_protected_source()}
try:
    out["categories"] = at.core_categories()
except at.TaxonomyUnavailable:
    out["categories"] = None
out["gate"] = at.gate_enabled()
out["names"] = [n for n, _, _ in rg.known_project_names()]
out["terms"] = sorted(rg.project_terms(proj))
out["core_data"] = rg.is_core_root(data)
res = pr.resolve_project_root(data / "sub")
out["decl_path"] = str(res.path) if res.path else ""
out["decl_warnings"] = res.warnings
out["logs_dir"] = str(wg_core.logs_dir())
wg_core.append_guard_log("a2cprobe", {"x": 1})
out["wg_failures"] = str(wg_core.FAILURES_DIR)
out["audit_log"] = str(atom_io.AUDIT_LOG)
print("PROBE_JSON " + json.dumps(out, ensure_ascii=False))
"""


def _n(p) -> str:
    return os.path.normcase(os.path.realpath(str(p)))


def _under(p, root) -> bool:
    a, r = _n(p), _n(root)
    return a == r or a.startswith(r + os.sep)


def _env(home: Path, wg=None) -> dict:
    drop = ("WG_CLAUDE_DIR", "PYTHONPATH", "PYTEST_CURRENT_TEST", "WG_TEST_LOGS_DIR")
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env.update({"HOME": str(home), "USERPROFILE": str(home), "PYTHONIOENCODING": "utf-8"})
    if wg is not None:
        env["WG_CLAUDE_DIR"] = str(wg)
    return env


def _run(argv, env, cwd) -> dict:
    r = subprocess.run(argv, env=env, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120, creationflags=NO_WINDOW)
    line = next((l for l in r.stdout.splitlines() if l.startswith("PROBE_JSON ")), None)
    assert r.returncode == 0 and line, f"rc={r.returncode}\n{r.stdout[-1500:]}\n{r.stderr[-3000:]}"
    return json.loads(line[len("PROBE_JSON "):])


def _py(snippet: str, args, env, cwd) -> dict:
    return _run([sys.executable, "-X", "utf8", "-P", "-c", snippet, *map(str, args)], env, cwd)


@pytest.fixture
def dirs(tmp_path):
    home, data, cwd = tmp_path / "home", tmp_path / "data", tmp_path / "cwd"
    for d in (home, data, cwd):
        d.mkdir()
    return home, data, cwd


@pytest.mark.parametrize("mode", ["pkg", "top"])
def test_lib_constants_and_defaults_follow_data_root(mode, dirs):
    home, data, cwd = dirs
    got = _py(CONST_PROBE, [TREE, mode, json.dumps(LIB_CONSTS)], _env(home, data), cwd)
    assert all(_under(f, TREE / "lib") for f in got.pop("files").values())             # 程式碼從本樹載
    for k, v in got.items():
        assert _under(v, data) and not _under(v, TREE), (mode, k, v)                    # 反例：舊碼落在家目錄
    for k in ("al.CLAUDE_DIR", "at.CLAUDE_DIR", "rg.CLAUDE_DIR", "pr.CLAUDE_DIR"):
        assert _n(got[k]) == _n(data), (k, got[k])
    got = _py(CONST_PROBE, [TREE, mode, json.dumps(LIB_CONSTS)], _env(home), cwd)      # 沒設 → tmp家/.claude
    got.pop("files")
    for k, v in got.items():
        assert _under(v, home / ".claude"), (mode, k, v)


def test_lib_and_wg_core_really_read_and_write_data_root(dirs, tmp_path):
    home, data, cwd = dirs
    meta = data / "memory" / "_meta"
    meta.mkdir(parents=True)
    shutil.copyfile(TREE / "memory" / "_meta" / "realm-lexicon.json", meta / "realm-lexicon.json")
    (meta / "taxonomy.json").write_text(json.dumps({"core": {"ZetaCat": {}}}), encoding="utf-8")
    (data / "workflow").mkdir()
    (data / "workflow" / "config.json").write_text(json.dumps({"taxonomy": {"gate_enabled": True}}), encoding="utf-8")
    (data / "memory" / "project-registry.json").write_text(
        json.dumps({"projects": {"zeta": {"root": str(tmp_path / "ZetaProject")}}}), encoding="utf-8")
    (data / ".claude" / "memory").mkdir(parents=True)                                     # 資料根長得像可認領的根層
    (data / ".claude" / "memory" / "MEMORY.md").write_text("# m\n", encoding="utf-8")
    (data / "sub" / ".claude").mkdir(parents=True)
    (data / "sub" / ".claude" / "project-tree.json").write_text(json.dumps({"root": ".."}), encoding="utf-8")
    proj = tmp_path / "proj"
    for d in ("hooks", "lib", "Zeta"):                                                   # hooks／lib 只在程式碼根有
        (proj / d).mkdir(parents=True)

    got = _py(READ_PROBE, [TREE, data, proj], _env(home, data), cwd)
    assert got["lexicon_source"] == "json"                                               # 詞庫從資料根讀（家目錄沒有）
    assert got["categories"] == ["ZetaCat"] and got["gate"] is True
    assert "ZetaProject" in got["names"]
    assert "Zeta" in got["terms"] and "hooks" not in got["terms"] and "lib" not in got["terms"], got["terms"]
    assert got["core_data"] is True
    assert _n(got["decl_path"] or tmp_path) != _n(data) and any("不採用" in w for w in got["decl_warnings"]), got
    assert _n(got["logs_dir"]) == _n(data / "Logs")
    assert (data / "Logs" / "guard-a2cprobe.jsonl").is_file()
    assert not (home / ".claude").exists()                                               # 反例：家目錄不被碰
    assert _n(got["wg_failures"]) == _n(data / "memory" / "Failures")
    assert _under(got["audit_log"], data)


TAIL_PROBE = r"""
import json, sys
from pathlib import Path
tree, data, wt, proj = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
sys.path.insert(0, str(tree))
from lib import atom_spec, provenance, ollama_extract_core as oec, realm_gate as rg, atom_io
out = {"projects_dir": str(provenance.PROJECTS_DIR),
       "depends_default": str(atom_spec.resolve_depends_path("tools/x.py")),
       "depends_base": str(atom_spec.depends_base_for(data / "memory"))}
oec._atom_debug_log("ERROR", "dr2probe")
out["debug_logs"] = [p.name for p in (data / "Logs").glob("atom-debug-*.log")]
roots = {"tree": tree, "tree_hooks": tree / "hooks", "data": data, "wt": wt, "proj": proj}
out["core"] = {k: rg.is_core_root(p) for k, p in roots.items()}
fields = {"title": "此專案踩坑", "knowledge": ["此專案的 hook 會擋"]}
out["gate_wt"] = rg.check_global_write(str(wt), **fields)
out["gate_tree"] = rg.check_global_write(str(tree / "hooks"), **fields)
out["gate_proj"] = rg.check_global_write(str(proj), **fields)

def target(scope, cwd, **kw):
    return atom_io._resolve_target(scope, str(cwd), None, "u", None, False, create_dirs=False, **kw)

out["global_wt"] = target("global", wt, enforce_cwd_scope=True).get("error")
out["global_proj"] = target("global", proj, enforce_cwd_scope=True).get("error")
out["shared_wt"] = target("shared", wt).get("error")
out["personal_wt"] = bool(target("personal", wt).get("personal_global"))
sys.modules["wg_core"] = None                     # wg_core 載不到 → overview_scaffold 走 lib 的退路
from lib import overview_scaffold as osc
out["osc_live"] = str(osc._live_claude_dir())
out["osc_layer"] = [str(x) for x in osc.detect_layer(data / "sub")]
print("PROBE_JSON " + json.dumps(out, ensure_ascii=False))
"""


def test_lib_tail_follows_data_root_and_worktree_is_core(dirs, tmp_path):
    """lib 尾巴（provenance、atom_spec、ollama_extract_core、overview_scaffold 退路）的資料都在 tmp 資料根；
    核心根＝資料根或程式碼根之內、或資料根 repo 的 git worktree：cwd 在 worktree 時含「此專案」的 global 卡放行、
    落點的 global／personal 走根層、shared 拒寫；一般專案照舊被擋。"""
    home, data, cwd = dirs
    wt, proj = tmp_path / "wt", tmp_path / "proj"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {data / '.git' / 'worktrees' / 'wt'}\n", encoding="utf-8")
    (proj / ".git").mkdir(parents=True)
    got = _py(TAIL_PROBE, [TREE, data, wt, proj], _env(home, data), cwd)
    assert _n(got["projects_dir"]) == _n(data / "projects")
    assert _n(got["depends_default"]) == _n(data / "tools" / "x.py") and _n(got["depends_base"]) == _n(data)
    assert len(got["debug_logs"]) == 1
    assert got["core"] == {"tree": True, "tree_hooks": True, "data": True, "wt": True, "proj": False}, got["core"]
    assert got["gate_wt"] is None and got["gate_tree"] is None, got                          # 反例：舊碼把 worktree 當專案拒寫
    assert got["gate_proj"] and "此專案" in got["gate_proj"]
    assert got["global_wt"] is None and got["global_proj"] and "inside project root" in got["global_proj"], got
    assert got["shared_wt"] and "rejected" in got["shared_wt"] and got["personal_wt"] is True, got
    assert _n(got["osc_live"]) == _n(data) and got["osc_layer"][0] == "root" and _n(got["osc_layer"][1]) == _n(data)
    assert not (home / ".claude").exists()                                                  # 反例：家目錄不被碰


STANDALONE_SPEC_PROBE = r"""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("any_name_atom_spec", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
sys.modules["any_name_atom_spec"] = mod
spec.loader.exec_module(mod)
print("PROBE_JSON " + json.dumps({"depends_default": str(mod.resolve_depends_path("x"))}))
"""


def test_atom_spec_loads_standalone_by_file(dirs):
    """atom_spec 原本零相依、可單獨按檔案載入；加了資料根相依後，lib/ 不在 sys.path（-P、cwd 在 tmp）時照樣載得起來。"""
    home, data, cwd = dirs
    got = _py(STANDALONE_SPEC_PROBE, [TREE / "lib" / "atom_spec.py"], _env(home, data), cwd)
    assert _n(got["depends_default"]) == _n(data / "x")


HOOK_PROBE = r"""
import json, sys
from pathlib import Path
tree, data = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(tree / "hooks"))
import wg_evasion, version_guard
from handlers import user_prompt_submit as ups
out = {"phrases": str(wg_evasion._PHRASES_JSON), "decision": str(ups._decision_item_path("workflow/x.json")),
       "scan_code": version_guard.is_scannable_path(str(tree / "hooks" / "a.py")),
       "scan_data": version_guard.is_scannable_path(str(data / "memory" / "a.md")),
       "scan_other": version_guard.is_scannable_path(str(data.parent / "other" / "a.py"))}
print("PROBE_JSON " + json.dumps(out, ensure_ascii=False))
"""


def test_hook_modules_follow_data_root(dirs, tmp_path):
    """要 hooks/ 在 sys.path 才載得到的三支：wg_evasion 的禁語表、UPS 決策項相對路徑都看資料根；
    version_guard 只掃本系統自己的檔＝資料根或程式碼根之內，其他路徑不掃。"""
    home, data, cwd = dirs
    got = _py(HOOK_PROBE, [TREE, data], _env(home, data), cwd)
    assert _n(got["phrases"]) == _n(data / "memory" / "_meta" / "forbidden-phrases.json")
    assert _n(got["decision"]) == _n(data / "workflow" / "x.json")
    assert got["scan_code"] is True and got["scan_data"] is True and got["scan_other"] is False, got
    assert not (home / ".claude").exists()


NODE_PROBE = r"""
const lib = process.argv[1];
const p = require(lib + "/paths.js");
console.log("PROBE_JSON " + JSON.stringify({
  CLAUDE_DIR: p.CLAUDE_DIR, CODE_DIR: p.CODE_DIR, WORKFLOW_DIR: p.WORKFLOW_DIR, MEMORY_DIR: p.MEMORY_DIR,
  CONFIG_PATH: p.CONFIG_PATH, REGISTRY_PATH: p.REGISTRY_PATH, VERSION_PATH: p.VERSION_PATH,
  config: p.loadConfig(), registry: p.loadRegistry(), org: p.loadOrgLocal() }));
"""
PY_ROOT_PROBE = ("import json, sys; sys.path.insert(0, sys.argv[1]); from lib.project_root import claude_data_dir; "
                 "print('PROBE_JSON ' + json.dumps({'CLAUDE_DIR': str(claude_data_dir())}))")


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_mcp_paths_js_agrees_with_python_data_root(dirs):
    home, data, cwd = dirs
    (data / "workflow").mkdir()
    (data / "memory").mkdir()
    (data / "workflow" / "config.json").write_text(json.dumps({"probe": "data-config"}), encoding="utf-8")
    (data / "workflow" / "org-memory.local.json").write_text(json.dumps({"probe": "data-org"}), encoding="utf-8")
    (data / "memory" / "project-registry.json").write_text(json.dumps({"projects": {"zeta": {}}}), encoding="utf-8")
    for wg, expect in ((data, data), ("   ", home / ".claude"), (None, home / ".claude")):
        env = _env(home, wg)
        js = _run(["node", "-e", NODE_PROBE, str(MCP_LIB)], env, cwd)
        py = _py(PY_ROOT_PROBE, [TREE], env, cwd)
        assert _n(js["CLAUDE_DIR"]) == _n(py["CLAUDE_DIR"]) == _n(expect), (wg, js["CLAUDE_DIR"], py["CLAUDE_DIR"])
        assert _n(js["CODE_DIR"]) == _n(TREE) and _n(js["VERSION_PATH"]) == _n(TREE / "version.json")   # 版本標記看程式碼根
        for k in ("WORKFLOW_DIR", "MEMORY_DIR", "CONFIG_PATH", "REGISTRY_PATH"):
            assert _under(js[k], expect) and not _under(js[k], TREE), (wg, k, js[k])
    js = _run(["node", "-e", NODE_PROBE, str(MCP_LIB)], _env(home, data), cwd)
    assert js["config"] == {"probe": "data-config"} and js["org"] == {"probe": "data-org"}          # 真的從資料根讀
    assert js["registry"] == {"projects": {"zeta": {}}}

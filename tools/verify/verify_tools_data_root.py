"""verify_tools_data_root.py：tools/ 的資料看資料根（lib.project_root.claude_data_dir）、程式碼看檔案位置。

做什麼：
- 資料根單一來源：claude_data_dir() 在 WG_CLAUDE_DIR 有設／空白／沒設時的值；wg_core.CLAUDE_DIR 在子行程裡與它相同。
- 改到的每支工具：子行程載入（不跑 main），WG_CLAUDE_DIR＝tmp 資料根 → 資料常數都在 tmp 資料根、程式碼常數都在本樹；
  沒設 WG_CLAUDE_DIR、HOME 指到 tmp 家 → 資料常數都在 tmp家/.claude。子行程一律 -P 且 cwd 在 tmp（工具沒自己插程式碼根就紅）；
  常數名可用點號與 [鍵] 取屬性、預設參數（例 OllamaClient.LONG_DIE_MARKER、ensure_service.__kwdefaults__[flag_path]）。
- 成對：向量 config／starter／rag-engine 的 _vectordb 同一處；codex-companion state.py 寫的檔 hooks/codex_companion 讀得到。
- 假 worktree：把 followup-check.py 與 lib/project_root.py 複製到 tmp 的「程式碼樹」，資料根是另一個 tmp，
  跑 --add／--list → 讀寫全落資料根，程式碼樹底下不出現 workflow／Logs／memory（反例：舊碼會寫進程式碼樹）。
- 一般安裝（程式碼根＝資料根）時每個常數與舊算法逐字相同。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_tools_data_root.py
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
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# 工具 → (資料常數, 程式碼常數)
TOOLS = {
    "followup-check.py": (["FOLLOWUPS", "INJECTION_TURNS_LOG"], ["CODE_DIR"]),
    "atom-provenance-backfill.py": (["PROJECTS_DIR", "AUDIT_LOG", "LOG_PATH", "LOCK_PATH", "MARKER_PATH"], ["CODE_DIR"]),
    "health-weekly.py": (["WORKFLOW", "MEMORY", "RECALL_MISS_LOG"], ["TOOLS", "CODE_DIR"]),
    "memory-effect-report.py": (["ATOM_INDEX", "RESCUE_LOG", "RECALL_MISS_LOG", "INJECTION_TURNS_LOG"], ["CODE_DIR"]),
    "atom-date-lint.py": (["INDEX"], ["CODE_DIR"]),
    "atom-heal.py": (["MEMORY"], ["ROOT", "TOOLS"]),
    "fix-hook-python.py": (["SETTINGS"], ["CODE_DIR"]),
    "scorecard-report.py": (["WORKFLOW_DIR"], ["CODE_DIR"]),
    "statusline.py": (["WORKFLOW_DIR"], ["CODE_DIR"]),
    "refix-churn.py": (["CONFIG_PATH"], ["CODE_DIR"]),
    "overview-map-scaffold.py": (["CONFIG_PATH"], ["CODE_DIR"]),
    "native-memory-bridge.py": (["ATOM_INDEX"], ["CODE_DIR"]),
    "sync-memory-index.py": (["MEMORY_DIR", "_CONFIG_PATH"], []),
    "sync-atom-index.py": (["MEMORY_DIR"], []),
    "memory-eval/genqueries.py": (["DEFAULT_MEMORY_DIR"], ["CODE_DIR"]),
    "memory-eval/run.py": (["DEFAULT_MEMORY_DIR", "CONFIG_PATH"], ["CODE_DIR"]),
    "memory-eval/online_replay.py": (["CONFIG_PATH"], ["CODE_DIR"]),
    "second-opinion/run.py": (["CONFIG_PATH", "JOB_ROOT"], ["COMPANION_DIR", "REPLAY_GUARD", "CODE_DIR"]),
    "second-opinion/pack.py": (["CLAUDE_DIR"], ["CODE_DIR"]),
    "memory-vector-service/config.py": (["CLAUDE_DIR", "CONFIG_PATH", "VECTORDB_DIR"], []),
    "memory-vector-service/starter.py": (
        ["CLAUDE_DIR", "WORKFLOW_DIR", "LOGS_DIR", "SERVICE_LOG", "PROBE_LOG", "FLAG_PATH", "PID_FILE", "SPAWN_LOCK",
         "ensure_service.__kwdefaults__[flag_path]", "ensure_service.__kwdefaults__[pid_file]",
         "ensure_service.__kwdefaults__[log_path]", "ensure_service.__kwdefaults__[lock_path]",
         "_slog.__defaults__[0]", "_kill_stale_pid.__defaults__[0]", "_rotate_log.__defaults__[0]",
         "_spawn_lock_fresh.__defaults__[0]", "_spawn_service.__defaults__[1]", "_write_flag.__defaults__[0]",
         "_log_probe.__defaults__[0]"],
        ["SERVICE_SCRIPT", "ensure_service.__kwdefaults__[service_script]", "_spawn_service.__defaults__[0]"]),
    "rag-engine.py": (["VECTORDB_DIR"], ["SERVICE_DIR"]),
    "codex-companion/state.py": (["WORKFLOW_DIR"], []),
    "../hooks/codex_companion.py": (["CLAUDE_DIR", "WORKFLOW_DIR", "CONFIG_PATH"], ["COMPANION_DIR", "AUDIT_SCRIPT"]),
}

PROBE = r"""
import importlib.util, json, sys
path, names = sys.argv[1], json.loads(sys.argv[2])
spec = importlib.util.spec_from_file_location("probe_tool_mod", path)
mod = importlib.util.module_from_spec(spec)
sys.modules["probe_tool_mod"] = mod
spec.loader.exec_module(mod)

def get(name):
    obj = mod
    for part in name.split("."):
        part, _, key = part.partition("[")
        obj = getattr(obj, part)
        if key:
            key = key.rstrip("]")
            obj = obj[int(key)] if key.isdigit() else obj[key]
    return obj

print("PROBE_JSON " + json.dumps({n: str(get(n)) for n in names}))
"""


def _n(p) -> str:
    return os.path.normcase(os.path.realpath(str(p)))


def _under(p, root) -> bool:
    a, r = _n(p), _n(root)
    return a == r or a.startswith(r + os.sep)


def _env(home: Path, wg=None) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("WG_CLAUDE_DIR", "PYTHONPATH")}
    env.update({"HOME": str(home), "USERPROFILE": str(home), "PYTHONIOENCODING": "utf-8"})
    if wg is not None:
        env["WG_CLAUDE_DIR"] = str(wg)
    return env


def _probe(tool: str, names, env, cwd: Path) -> dict:
    """-P 且 cwd 在 tmp：cwd 不進 sys.path，工具沒自己插程式碼根就 import 不到 lib.*。"""
    r = subprocess.run([sys.executable, "-X", "utf8", "-P", "-c", PROBE, str(TREE / "tools" / tool), json.dumps(names)],
                       env=env, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=120, creationflags=NO_WINDOW)
    line = next((l for l in r.stdout.splitlines() if l.startswith("PROBE_JSON ")), None)
    assert r.returncode == 0 and line, f"{tool} rc={r.returncode}\n{r.stderr[-3000:]}"
    return json.loads(line[len("PROBE_JSON "):])


@pytest.fixture
def dirs(tmp_path):
    home, data = tmp_path / "home", tmp_path / "data"
    home.mkdir()
    data.mkdir()
    return home, data


@pytest.fixture
def cwd(tmp_path):
    d = tmp_path / "cwd"
    d.mkdir()
    return d


def test_claude_data_dir_single_source_and_wg_core_agree(dirs):
    home, data = dirs
    snippet = ("import json, sys; sys.path.insert(0, sys.argv[1] + '/lib'); sys.path.insert(0, sys.argv[1] + '/hooks');"
               "from project_root import claude_data_dir; import wg_core;"
               "print(json.dumps([str(claude_data_dir()), str(wg_core.CLAUDE_DIR)]))")
    for wg, expect in ((data, data), ("   ", home / ".claude"), (None, home / ".claude")):
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", snippet, str(TREE)], env=_env(home, wg),
                           capture_output=True, text=True, encoding="utf-8", timeout=60, creationflags=NO_WINDOW)
        assert r.returncode == 0, r.stderr[-2000:]
        a, b = json.loads(r.stdout.strip().splitlines()[-1])
        assert _n(a) == _n(expect) and _n(b) == _n(expect), (wg, a, b)


@pytest.mark.parametrize("tool", sorted(TOOLS))
def test_tool_data_follows_data_root_code_follows_file(tool, dirs, cwd):
    home, data = dirs
    data_names, code_names = TOOLS[tool]
    got = _probe(tool, data_names + code_names, _env(home, data), cwd)                 # WG_CLAUDE_DIR＝tmp 資料根
    for n in data_names:
        assert _under(got[n], data) and not _under(got[n], TREE), (n, got[n])            # 反例：資料不得落在本樹
    for n in code_names:
        assert _under(got[n], TREE) and not _under(got[n], data), (n, got[n])
    got = _probe(tool, data_names, _env(home), cwd)                                     # 沒設 → 家目錄/.claude
    for n in data_names:
        assert _under(got[n], home / ".claude"), (n, got[n])


PAIR_PROBE = r"""
import importlib.util, json, sys
from pathlib import Path
tree = Path(sys.argv[1])

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

svc = tree / "tools" / "memory-vector-service"
sys.path.insert(0, str(svc))
import config
starter = load("probe_starter", svc / "starter.py")
rag = load("probe_rag", tree / "tools" / "rag-engine.py")
starter._write_flag()
cc = load("probe_cc", tree / "hooks" / "codex_companion.py")
import state
state.write_state("a2c-probe", state.new_state("a2c-probe", ""))
print("PROBE_JSON " + json.dumps({
    "config_file": config.__file__, "port": config.load_config()["service_port"],
    "vectordb": [str(config.VECTORDB_DIR), str(rag.VECTORDB_DIR), str(starter.PID_FILE.parent)],
    "flag": str(starter.FLAG_PATH),
    "state_file": state.__file__, "workflow": [str(state.WORKFLOW_DIR), str(cc.WORKFLOW_DIR)],
    "assess_glob": [p.name for p in cc.WORKFLOW_DIR.glob("companion-state-a2c-probe.json")]}))
"""


def test_paired_vector_and_companion_share_data_root(dirs, cwd):
    """成對兩組：向量 config／starter／rag-engine 的 _vectordb 同一處；codex-companion 的 state.py 寫的檔，
    hooks/codex_companion 從同一個 workflow 讀得到；全落 tmp 資料根、家目錄不被碰。"""
    home, data = dirs
    (data / "workflow").mkdir()
    (data / "workflow" / "config.json").write_text(json.dumps({"vector_search": {"service_port": 39999}}),
                                                  encoding="utf-8")
    r = subprocess.run([sys.executable, "-X", "utf8", "-P", "-c", PAIR_PROBE, str(TREE)], env=_env(home, data),
                       cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=120, creationflags=NO_WINDOW)
    line = next((l for l in r.stdout.splitlines() if l.startswith("PROBE_JSON ")), None)
    assert r.returncode == 0 and line, f"rc={r.returncode}\n{r.stderr[-3000:]}"
    got = json.loads(line[len("PROBE_JSON "):])
    assert _under(got["config_file"], TREE) and _under(got["state_file"], TREE)
    assert got["port"] == 39999                                                         # config 從資料根讀
    assert len({_n(p) for p in got["vectordb"]}) == 1 and _n(got["vectordb"][0]) == _n(data / "memory" / "_vectordb")
    assert (data / "workflow" / "vector_ready.flag").is_file() and _n(got["flag"]).startswith(_n(data))
    assert len({_n(p) for p in got["workflow"]}) == 1 and _n(got["workflow"][0]) == _n(data / "workflow")
    assert got["assess_glob"] == ["companion-state-a2c-probe.json"]                     # 寫的和讀的同一處
    assert not (home / ".claude").exists()                                              # 反例：家目錄不被碰


def test_fake_worktree_followup_check_reads_and_writes_data_root_only(tmp_path):
    code, data, home = tmp_path / "code", tmp_path / "data", tmp_path / "home"
    (code / "tools").mkdir(parents=True)
    (code / "lib").mkdir()
    home.mkdir()
    shutil.copyfile(TREE / "tools" / "followup-check.py", code / "tools" / "followup-check.py")
    shutil.copyfile(TREE / "lib" / "project_root.py", code / "lib" / "project_root.py")
    (code / "lib" / "__init__.py").write_text("", encoding="utf-8")
    item = {"id": "a3-probe", "title": "探針", "due": "2099-01-01", "since": "2026-10-01", "check": "none"}

    def run(*args):
        return subprocess.run([sys.executable, "-X", "utf8", str(code / "tools" / "followup-check.py"), *args],
                              env=_env(home, data), capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=60, creationflags=NO_WINDOW)
    r = run("--add", json.dumps(item, ensure_ascii=False))
    assert r.returncode == 0, r.stderr[-2000:]
    assert (data / "workflow" / "followups.json").is_file()                            # 寫進資料根
    r = run("--list")
    assert r.returncode == 0 and "a3-probe" in r.stdout, r.stdout + r.stderr          # 從資料根讀回
    assert not any((code / d).exists() for d in ("workflow", "Logs", "memory"))       # 反例：程式碼樹不被碰


def test_normal_install_paths_identical_to_old_algorithm(dirs, cwd):
    """程式碼根＝資料根（一般安裝）：用本樹當 WG_CLAUDE_DIR，資料常數＝舊算法（檔案位置根）組出的同一路徑。"""
    home, _ = dirs
    got = _probe("followup-check.py", ["FOLLOWUPS", "CODE_DIR"], _env(home, TREE), cwd)
    assert _n(got["FOLLOWUPS"]) == _n(TREE / "workflow" / "followups.json") and _n(got["CODE_DIR"]) == _n(TREE)
    got = _probe("sync-memory-index.py", ["MEMORY_DIR", "_CONFIG_PATH"], _env(home, TREE), cwd)
    assert _n(got["MEMORY_DIR"]) == _n(TREE / "memory") and _n(got["_CONFIG_PATH"]) == _n(TREE / "workflow" / "config.json")


def test_normal_install_without_override_raw_strings_identical(dirs):
    """真正的一般安裝：沒設 WG_CLAUDE_DIR、程式碼就裝在 tmp家/.claude → 資料常數與程式碼根的原始字串（不正規化）
    和舊算法（Path(__file__) 推出的根）組出的完全相同。"""
    home, _ = dirs
    root = home / ".claude"
    (root / "tools").mkdir(parents=True)
    (root / "lib").mkdir()
    shutil.copyfile(TREE / "tools" / "followup-check.py", root / "tools" / "followup-check.py")
    shutil.copyfile(TREE / "lib" / "project_root.py", root / "lib" / "project_root.py")
    (root / "lib" / "__init__.py").write_text("", encoding="utf-8")
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", PROBE, str(root / "tools" / "followup-check.py"),
                        json.dumps(["FOLLOWUPS", "INJECTION_TURNS_LOG", "CODE_DIR", "CLAUDE_DIR"])],
                       env=_env(home), capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=60, creationflags=NO_WINDOW)
    line = next((l for l in r.stdout.splitlines() if l.startswith("PROBE_JSON ")), None)
    assert r.returncode == 0 and line, r.stderr[-2000:]
    got = json.loads(line[len("PROBE_JSON "):])
    old_root = (root / "tools" / "followup-check.py").resolve().parent.parent              # 舊算法的根
    assert got["CODE_DIR"] == str(old_root) and got["CLAUDE_DIR"] == str(old_root)
    assert got["FOLLOWUPS"] == str(old_root / "workflow" / "followups.json")
    assert got["INJECTION_TURNS_LOG"] == str(old_root / "Logs" / "injection-turns.jsonl")


LIB_ORIGIN_PROBE = r"""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("probe_tool_mod", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
sys.modules["probe_tool_mod"] = mod
spec.loader.exec_module(mod)
print("PROBE_JSON " + json.dumps({k: getattr(m, "__file__", "") or "" for k, m in sys.modules.items()
                                  if k == "lib" or k.startswith("lib.")}))
"""


@pytest.mark.parametrize("tool", ["atom-set-realm.py", "realm_llm_classify.py"])
def test_home_decoy_lib_never_loaded_by_tools(tool, dirs):
    """家目錄放誘餌 lib（import 就丟例外），沒設 WG_CLAUDE_DIR 冷啟動載入工具：lib.* 全來自工具自己的樹（反例：舊碼插家目錄會載到誘餌）。"""
    home, _ = dirs
    decoy = home / ".claude" / "lib"
    decoy.mkdir(parents=True)
    (decoy / "__init__.py").write_text("raise ImportError('decoy lib loaded from home')\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "-X", "utf8", "-P", "-c", LIB_ORIGIN_PROBE, str(TREE / "tools" / tool)],
                       env=_env(home), capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=120, creationflags=NO_WINDOW)
    line = next((l for l in r.stdout.splitlines() if l.startswith("PROBE_JSON ")), None)
    assert r.returncode == 0 and line, f"{tool} rc={r.returncode}\n{r.stderr[-3000:]}"
    files = json.loads(line[len("PROBE_JSON "):])
    assert files and all(_under(f, TREE) for f in files.values() if f), files


HOOKS_ORIGIN_PROBE = r"""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("probe_tool_mod", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
sys.modules["probe_tool_mod"] = mod
spec.loader.exec_module(mod)
if sys.argv[2]:
    getattr(mod, sys.argv[2])()
print("PROBE_JSON " + json.dumps({k: getattr(m, "__file__", "") or "" for k, m in sys.modules.items()
                                  if k.startswith("wg_")}))
"""


@pytest.mark.parametrize("tool,call", [("heal-review.py", ""), ("sync-atom-index.py", "_project_memory_dirs")])
def test_home_decoy_hooks_never_loaded_by_tools(tool, call, dirs):
    """家目錄放誘餌 hooks/wg_roles.py、wg_core.py（import 就寫標記再丟例外），沒設 WG_CLAUDE_DIR 冷啟動：
    wg_* 全來自工具自己的樹、誘餌沒被載（反例：舊碼用資料根別名 CLAUDE／CLAUDE_ROOT 拼 hooks 會載到誘餌；
    heal-review 的 try/except 會把誘餌的例外吞掉，只有標記看得出來）。"""
    home, _ = dirs
    decoy = home / ".claude" / "hooks"
    decoy.mkdir(parents=True)
    marker = home / "decoy-hooks-ran.txt"
    for name in ("wg_roles.py", "wg_core.py"):
        (decoy / name).write_text(f"open(r'{marker}', 'a').write('{name}\\n')\nraise ImportError('decoy hooks loaded')\n",
                                  encoding="utf-8")
    r = subprocess.run([sys.executable, "-X", "utf8", "-P", "-c", HOOKS_ORIGIN_PROBE, str(TREE / "tools" / tool), call],
                       env=_env(home), capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=120, creationflags=NO_WINDOW)
    line = next((l for l in r.stdout.splitlines() if l.startswith("PROBE_JSON ")), None)
    assert r.returncode == 0 and line, f"{tool} rc={r.returncode}\n{r.stderr[-3000:]}"
    assert not marker.exists(), marker.read_text(encoding="utf-8")
    files = json.loads(line[len("PROBE_JSON "):])
    assert files and all(_under(f, TREE) for f in files.values() if f), files

"""verify_sys_path_file_relative.py：hook／lib 找「程式碼」一律用自己的檔案位置推樹根；家目錄與 WG_CLAUDE_DIR 只定位使用者資料。

做什麼：
- 載入探針：子行程把 HOME／USERPROFILE 指到 tmp、不設 WG_CLAUDE_DIR、`python -P`（cwd 不進 sys.path），載入 wg_core、wg_atoms、
  wg_depends、wg_overview、wg_provenance、wg_episodic、codex_companion、handlers.ups_context／session_start／ups_gates 與三支 worker
  （extract-worker、user-extract-worker、vcs-sync-worker），斷言 ① 沒有 sys.path 項目落在 tmp 家目錄 ② 新插的 sys.path 項目都在本樹
  ③ `import lib.atom_access` 解析到本樹的檔 ④ codex_companion 的 COMPANION_DIR／AUDIT_SCRIPT 在本樹、資料根 CLAUDE_DIR 在 tmp 家。
- 反例：家目錄放一份假的 `.claude/lib/atom_access.py`，本樹的檔仍要勝出。
- codex_companion 起 audit 子行程時 argv 指本樹的 audit.py（Popen 換成假的，不真的 spawn）。
- hook 進程探針：假 HOME、不設 WG_CLAUDE_DIR，以 hooks/workflow-guardian.py 跑 SessionStart／UserPromptSubmit／PreToolUse／Stop 各一次，
  不拋例外、載入的 hook 模組都在本樹、沒有模組來自 tmp 家或 live ~/.claude（本樹不是 live 時）。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_sys_path_file_relative.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parents[2]
LIVE = Path.home() / ".claude"                 # 測試行程的真家目錄（子行程才換成 tmp）
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

PROBE = r"""
import importlib.util, json, sys
tree = sys.argv[1]
before = list(sys.path)
sys.path.insert(0, tree + "/hooks")
import wg_core, wg_atoms, wg_depends, wg_overview, wg_provenance, wg_episodic, codex_companion
import handlers.ups_context, handlers.session_start, handlers.ups_gates
for name in ("extract-worker", "user-extract-worker", "vcs-sync-worker"):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), tree + "/hooks/" + name + ".py")
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
import lib.atom_access
print("PROBE_JSON " + json.dumps({"before": before, "after": sys.path, "atom_access": lib.atom_access.__file__,
                                  "claude_dir": str(wg_core.CLAUDE_DIR), "companion_dir": str(codex_companion.COMPANION_DIR),
                                  "audit_script": str(codex_companion.AUDIT_SCRIPT),
                                  "cc_claude_dir": str(codex_companion.CLAUDE_DIR)}))
"""

HOOK_RUNNER = r"""
import atexit, json, runpy, sys
out, guardian = sys.argv[1], sys.argv[2]

def dump():
    files = [getattr(m, "__file__", None) for m in list(sys.modules.values())]
    with open(out, "w", encoding="utf-8") as fh:
        json.dump([f for f in files if f], fh)
atexit.register(dump)
sys.argv = [guardian]
runpy.run_path(guardian, run_name="__main__")
"""


def _norm(p: str) -> str:
    return os.path.normcase(os.path.realpath(p))


def _under(p: str, root: Path) -> bool:
    a, r = _norm(p), _norm(str(root))
    return a == r or a.startswith(r + os.sep)


def _env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("WG_CLAUDE_DIR", "PYTHONPATH")}
    env.update({"HOME": str(home), "USERPROFILE": str(home), "PYTHONIOENCODING": "utf-8"})
    return env


def _probe(home: Path) -> dict:
    r = subprocess.run([sys.executable, "-X", "utf8", "-P", "-c", PROBE, str(TREE)], cwd=str(TREE), env=_env(home),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                       creationflags=NO_WINDOW)
    line = next((l for l in r.stdout.splitlines() if l.startswith("PROBE_JSON ")), None)
    assert r.returncode == 0 and line, f"rc={r.returncode}\nstdout={r.stdout[-2000:]}\nstderr={r.stderr[-4000:]}"
    return json.loads(line[len("PROBE_JSON "):])


@pytest.fixture
def empty_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return home


def test_no_sys_path_entry_under_fake_home_and_inserted_all_in_tree(empty_home):
    out = _probe(empty_home)
    in_home = [p for p in out["after"] if p and _under(p, empty_home)]
    assert in_home == [], in_home                                                       # ① 沒有一項落在 tmp 家
    added = [p for p in out["after"] if p and p not in out["before"]]
    assert added and all(_under(p, TREE) for p in added), added                         # ② 新插的都在本樹
    assert _norm(out["atom_access"]) == _norm(str(TREE / "lib" / "atom_access.py"))     # ③ lib 解析到本樹
    assert Path(out["claude_dir"]) == empty_home / ".claude"                            # 資料根仍跟家目錄走
    assert _norm(out["companion_dir"]) == _norm(str(TREE / "tools" / "codex-companion"))  # ④ 程式碼在本樹
    assert _norm(out["audit_script"]) == _norm(str(TREE / "tools" / "codex-companion" / "audit.py"))
    assert Path(out["cc_claude_dir"]) == empty_home / ".claude"                         # codex_companion 的資料根不動


def test_decoy_lib_in_home_never_wins(empty_home):
    decoy = empty_home / ".claude" / "lib"
    decoy.mkdir(parents=True)
    (decoy / "__init__.py").write_text("", encoding="utf-8")
    (decoy / "atom_access.py").write_text("raise ImportError('decoy lib loaded')\n", encoding="utf-8")
    out = _probe(empty_home)
    assert _norm(out["atom_access"]) == _norm(str(TREE / "lib" / "atom_access.py"))
    assert not any(p and _under(p, empty_home) for p in out["after"])


def test_codex_companion_spawns_this_trees_audit_script(tmp_path, monkeypatch):
    sys.path.insert(0, str(TREE / "hooks"))
    import codex_companion as cc
    calls = []

    class _FakeProc:
        class stdin:                                                                    # noqa: N801
            @staticmethod
            def write(_b):
                return None

            @staticmethod
            def close():
                return None

    def fake_popen(argv, **kw):
        calls.append(argv)
        return _FakeProc()
    monkeypatch.setattr(cc, "CLAUDE_DIR", tmp_path / "data")                             # Logs 落 tmp，不碰 live
    monkeypatch.setattr(cc.subprocess, "Popen", fake_popen)
    cc._spawn_audit_subprocess({"turn": 1})
    assert calls and _norm(calls[0][1]) == _norm(str(TREE / "tools" / "codex-companion" / "audit.py"))
    if _norm(str(TREE)) != _norm(str(LIVE)):
        assert not _under(calls[0][1], LIVE)                                            # 反例：不得跑 live 的 audit.py


def _hook_inputs(proj: Path, transcript: Path) -> list:
    base = {"session_id": "probe-a3-syspath", "cwd": str(proj), "transcript_path": str(transcript)}
    return [
        {**base, "hook_event_name": "SessionStart", "source": "startup"},
        {**base, "hook_event_name": "UserPromptSubmit", "prompt": "hello"},
        {**base, "hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": str(proj / "a.txt")}},
        {**base, "hook_event_name": "Stop", "stop_hook_active": False},
    ]


def test_hook_process_events_load_code_only_from_this_tree(tmp_path, empty_home):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "a.txt").write_text("x\n", encoding="utf-8")
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("", encoding="utf-8")
    guardian = TREE / "hooks" / "workflow-guardian.py"
    for i, payload in enumerate(_hook_inputs(proj, transcript)):
        dump = tmp_path / f"modules-{i}.json"
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", HOOK_RUNNER, str(dump), str(guardian)], cwd=str(proj),
                           env=_env(empty_home), input=json.dumps(payload), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120, creationflags=NO_WINDOW)
        event = payload["hook_event_name"]
        assert r.returncode == 0, f"{event} rc={r.returncode}\n{r.stderr[-3000:]}"
        assert "Traceback" not in r.stderr and "[workflow-guardian] Error in" not in r.stderr, f"{event}\n{r.stderr[-3000:]}"
        files = json.loads(dump.read_text(encoding="utf-8"))
        assert not [f for f in files if _under(f, empty_home)], event                    # 沒有模組來自 tmp 家
        if _norm(str(TREE)) != _norm(str(LIVE)):
            from_live = [f for f in files if _under(f, LIVE)]
            assert from_live == [], f"{event}: {from_live[:5]}"                         # 沒有模組來自 live ~/.claude
        for name in ("dispatcher.py", "wg_core.py"):
            hit = [f for f in files if Path(f).name == name]
            assert hit and all(_under(f, TREE / "hooks") for f in hit), (event, name, hit)

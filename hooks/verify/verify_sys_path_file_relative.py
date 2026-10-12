"""verify_sys_path_file_relative.py：hook 模組組 sys.path 用自己的檔案位置推樹根，不用 Path.home()/.claude。

做什麼：子行程把 HOME／USERPROFILE 指到 tmp，`python -P`（cwd 不進 sys.path）載入 wg_episodic、handlers.ups_context、
handlers.session_start、handlers.ups_gates、codex_companion 與三支 worker（extract-worker、user-extract-worker、vcs-sync-worker），
斷言 ① 沒有 sys.path 項目落在 tmp 家目錄 ② 載入過程新插的 sys.path 項目都在本樹 ③ `import lib.atom_access` 解析到本樹的檔。
WG_CLAUDE_DIR 設成本樹：經 wg_core.CLAUDE_DIR 組的 sys.path（吃這個覆蓋）不在本檔範圍，只驗字面 Path.home() 那幾處。
反例：家目錄放一份假的 `.claude/lib/atom_access.py`，本樹的檔仍要勝出（改回 Path.home() 會載到假檔或載入失敗）。
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
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

PROBE = r"""
import importlib.util, json, sys
tree = sys.argv[1]
before = list(sys.path)
sys.path.insert(0, tree + "/hooks")
import wg_episodic, codex_companion
import handlers.ups_context, handlers.session_start, handlers.ups_gates
for name in ("extract-worker", "user-extract-worker", "vcs-sync-worker"):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), tree + "/hooks/" + name + ".py")
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
import lib.atom_access
print("PROBE_JSON " + json.dumps({"before": before, "after": sys.path, "atom_access": lib.atom_access.__file__}))
"""


def _norm(p: str) -> str:
    return os.path.normcase(os.path.realpath(p))


def _under(p: str, root: Path) -> bool:
    a, r = _norm(p), _norm(str(root))
    return a == r or a.startswith(r + os.sep)


def _probe(home: Path) -> dict:
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "WG_CLAUDE_DIR": str(TREE),
           "PYTHONIOENCODING": "utf-8"}
    env.pop("PYTHONPATH", None)
    r = subprocess.run([sys.executable, "-X", "utf8", "-P", "-c", PROBE, str(TREE)], cwd=str(TREE), env=env,
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


def test_decoy_lib_in_home_never_wins(empty_home):
    decoy = empty_home / ".claude" / "lib"
    decoy.mkdir(parents=True)
    (decoy / "__init__.py").write_text("", encoding="utf-8")
    (decoy / "atom_access.py").write_text("raise ImportError('decoy lib loaded')\n", encoding="utf-8")
    out = _probe(empty_home)
    assert _norm(out["atom_access"]) == _norm(str(TREE / "lib" / "atom_access.py"))
    assert not any(p and _under(p, empty_home) for p in out["after"])

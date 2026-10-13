"""verify_pytest_isolation.py：repo 根 conftest.py 讓測試預設隔離使用者資料根。

做什麼：
- 本行程：WG_CLAUDE_DIR 在 wg-pytest-* 暫存目錄底下（不是本樹、不是家目錄/.claude），lib.claude_data_dir() 算出它；
  tempfile 的暫存目錄是同一個暫存目錄下的 tmp，資料根不在暫存目錄底下。
- 子行程：繼承同一個資料根（走真 hook 入口的測試靠這個）。
- @pytest.mark.live_data：該案執行期間 WG_CLAUDE_DIR 還原成 pytest 啟動時的值。
- 同一行程跑 pytest.main（run_verify.py 的跑法，連跑兩次）：每次都隔離，結束後四個變數還原、暫存目錄刪掉。
- 資料根先放本樹受版控的資料（taxonomy 與本樹同一版）。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_pytest_isolation.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parents[2]
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _n(p) -> str:
    return os.path.normcase(os.path.realpath(str(p)))


def _under(p, root) -> bool:
    a, r = _n(p), _n(root)
    return a == r or a.startswith(r + os.sep)


def _root_conftest():
    return next(m for m in list(sys.modules.values())
                if getattr(m, "__file__", None) and _n(m.__file__) == _n(TREE / "conftest.py"))


def test_in_process_data_root_is_isolated():
    data = os.environ.get("WG_CLAUDE_DIR", "")
    assert data and Path(data).parent.name.startswith("wg-pytest-"), data
    assert not _under(data, TREE) and _n(data) != _n(Path.home() / ".claude")
    sys.path.insert(0, str(TREE))
    from lib.project_root import claude_data_dir
    assert _n(claude_data_dir()) == _n(data)
    temp = tempfile.gettempdir()
    assert _n(Path(temp).parent) == _n(Path(data).parent) and not _under(data, temp), (temp, data)


def test_data_root_seeded_with_tracked_data():
    data = Path(os.environ["WG_CLAUDE_DIR"])
    rel = Path("memory") / "_meta" / "taxonomy.json"
    assert (data / rel).read_bytes() == (TREE / rel).read_bytes()
    assert (data / "memory" / "_atom_index.json").is_file() and (data / "_AIDocs" / "_atoms").is_dir()


def test_subprocess_inherits_isolated_data_root(tmp_path):
    snippet = ("import json, sys; sys.path.insert(0, sys.argv[1]); import wg_core; "
               "print(json.dumps([str(wg_core.CLAUDE_DIR), str(wg_core.WORKFLOW_DIR)]))")
    r = subprocess.run([sys.executable, "-X", "utf8", "-P", "-c", snippet, str(TREE / "hooks")], cwd=str(tmp_path),
                       capture_output=True, text=True, encoding="utf-8", timeout=60, creationflags=NO_WINDOW)
    assert r.returncode == 0, r.stderr[-2000:]
    claude_dir, workflow = json.loads(r.stdout.strip().splitlines()[-1])
    assert _n(claude_dir) == _n(os.environ["WG_CLAUDE_DIR"]) and _under(workflow, claude_dir)


@pytest.mark.live_data
def test_live_data_marker_restores_original_value():
    assert os.environ.get("WG_CLAUDE_DIR") == _root_conftest().SESSION["original"]["WG_CLAUDE_DIR"]


NESTED = r"""
import json, os, sys, pytest
keys = ("WG_CLAUDE_DIR", "TEMP", "TMP", "TMPDIR")
before = {k: os.environ.get(k) for k in keys}
temp = os.environ["TEMP"]
bases = {d for d in os.listdir(temp) if d.startswith("wg-pytest-")}
rcs = [int(pytest.main([sys.argv[1] + "::test_in_process_data_root_is_isolated", "-q", "-p", "no:cacheprovider"]))
       for _ in range(2)]
left = {d for d in os.listdir(temp) if d.startswith("wg-pytest-")} - bases
print("NESTED_JSON " + json.dumps({"rc": rcs, "same": {k: os.environ.get(k) for k in keys} == before,
                                   "left": sorted(left)}))
"""


def test_in_process_pytest_main_restores_env_and_removes_base():
    """同一行程連跑兩次 pytest.main：兩次都隔離（conftest 已快取也一樣），結束後環境還原、暫存目錄刪掉。"""
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", NESTED, str(Path(__file__))], cwd=str(TREE),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                       creationflags=NO_WINDOW)
    line = next((l for l in r.stdout.splitlines() if l.startswith("NESTED_JSON ")), None)
    assert line, f"rc={r.returncode}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}"
    got = json.loads(line[len("NESTED_JSON "):])
    assert got == {"rc": [0, 0], "same": True, "left": []}, got

"""verify_claude_dir_override.py：WG_CLAUDE_DIR 只覆蓋「使用者資料根」wg_core.CLAUDE_DIR；程式碼（lib 的 sys.path）一律跟檔案位置走。

正例：設 WG_CLAUDE_DIR 後 CLAUDE_DIR／MEMORY_DIR／WORKFLOW_DIR 跟著走；sys.path 最前面的 lib 是本樹的 lib（wg_core.CODE_DIR），
覆蓋目錄底下的 lib 不進 sys.path；wg_overview 載到的 overview_hub 是本樹的。
反例：未設（或空白）時資料根等於家目錄 ~/.claude，lib 仍是本樹的（在 live 根層兩者是同一個目錄）。
每案都開子行程（常數在 import 時決定），不受本行程已載入的模組影響。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_claude_dir_override.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_ROOT = HOOKS_DIR.parent

PROBE_CORE = (
    "import json, sys; sys.path.insert(0, sys.argv[1]); import wg_core; "
    "print(json.dumps({'claude_dir': str(wg_core.CLAUDE_DIR), 'memory_dir': str(wg_core.MEMORY_DIR), "
    "'workflow_dir': str(wg_core.WORKFLOW_DIR), 'code_dir': str(wg_core.CODE_DIR), "
    "'data_lib_in_path': str(wg_core.CLAUDE_DIR / 'lib') in sys.path, 'path0': sys.path[0]}))"
)
PROBE_OVERVIEW = (
    "import json, sys; sys.path.insert(0, sys.argv[1]); import wg_core, wg_overview, overview_hub; "
    "print(json.dumps({'claude_dir': str(wg_core.CLAUDE_DIR), 'oh_file': overview_hub.__file__, "
    "'log_path': str(wg_overview.LOG_PATH)}))"
)


def _probe(snippet: str, env_value) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "WG_CLAUDE_DIR"}
    env["PYTHONIOENCODING"] = "utf-8"
    if env_value is not None:
        env["WG_CLAUDE_DIR"] = env_value
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", snippet, str(HOOKS_DIR)],
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


# ─── 正例 ──────────────────────────────────────────────────────────────────────

def test_override_moves_data_dirs_but_lib_stays_with_code(tmp_path):
    (tmp_path / "lib").mkdir()
    got = _probe(PROBE_CORE, str(tmp_path))
    assert Path(got["claude_dir"]) == tmp_path
    assert Path(got["memory_dir"]) == tmp_path / "memory"
    assert Path(got["workflow_dir"]) == tmp_path / "workflow"
    assert Path(got["code_dir"]) == CLAUDE_ROOT
    assert Path(got["path0"]) == CLAUDE_ROOT / "lib"                     # 程式碼從本樹載
    assert got["data_lib_in_path"] is False                              # 反例：覆蓋目錄的 lib 不進 sys.path


def test_override_to_this_tree_loads_this_trees_lib():
    got = _probe(PROBE_OVERVIEW, str(CLAUDE_ROOT))
    assert Path(got["claude_dir"]) == CLAUDE_ROOT
    assert Path(got["oh_file"]).resolve() == (CLAUDE_ROOT / "lib" / "overview_hub.py").resolve()
    assert Path(got["log_path"]) == CLAUDE_ROOT / "workflow" / "_overview-hub.log"


# ─── 反例：未設＝資料在家目錄，程式碼仍在本樹 ─────────────────────────────────────

def test_unset_data_is_home_claude_code_is_this_tree():
    home_claude = Path.home() / ".claude"
    got = _probe(PROBE_CORE, None)
    assert Path(got["claude_dir"]) == home_claude
    assert Path(got["memory_dir"]) == home_claude / "memory"
    assert Path(got["workflow_dir"]) == home_claude / "workflow"
    assert Path(got["path0"]) == CLAUDE_ROOT / "lib" and Path(got["code_dir"]) == CLAUDE_ROOT


def test_blank_value_equals_unset():
    assert Path(_probe(PROBE_CORE, "   ")["claude_dir"]) == Path.home() / ".claude"

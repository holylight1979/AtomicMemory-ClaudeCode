"""verify_rut_scope.py — 覆轍／振盪提示只看本 session 自己的 episodic 池。

寫入端 wg_core.resolve_episodic_dir 依 cwd 分池（專案 → {專案}/.claude/memory/episodic，
~/.claude → memory/episodic）；讀取端（wg_evasion._detect_rut_patterns／_detect_oscillation、
oscillation_state.json）必須讀同一個池，否則專案 session 開場會被根層的覆轍清單洗版。

跑法：python -m pytest hooks/verify/verify_rut_scope.py -q
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import wg_evasion  # noqa: E402

ROOT_SIGNALS = "same_file_3x:wg_need_goal.py, same_file_3x:overview_hub.py"
PROJ_SIGNALS = "same_file_3x:MainForm.cs"


def _write_ep(ep_dir: Path, name: str, scope: str, body: str, age_s: int) -> None:
    ep_dir.mkdir(parents=True, exist_ok=True)
    f = ep_dir / f"episodic-{name}.md"
    f.write_text(
        f"# Session: {name}\n\n- Scope: {scope}\n- Created: 2026-10-0{age_s % 9 + 1}\n\n"
        f"## 知識\n\n{body}\n",
        encoding="utf-8",
    )
    t = time.time() - age_s
    os.utime(f, (t, t))


@pytest.fixture
def layout(tmp_path, monkeypatch):
    """根層池放最新的根層信號（比專案池新，舊碼取最近 3 份會全拿到根層的）；
    專案池放較舊的專案自己的信號；另有一個沒有專案記憶的 cwd。"""
    root_mem = tmp_path / "claude" / "memory"
    proj_mem = tmp_path / "proj" / ".claude" / "memory"
    root_ep, proj_ep = root_mem / "episodic", proj_mem / "episodic"
    for i in range(3):
        _write_ep(root_ep, f"root-{i}", "project:c--users-u--claude",
                  f"- [臨] 覆轍信號: {ROOT_SIGNALS}\n- 修改 atoms: root-atom", age_s=10 + i)
    for i in range(2):
        _write_ep(proj_ep, f"proj-{i}", "project:c--proj",
                  f"- [臨] 覆轍信號: {PROJ_SIGNALS}\n- 修改 atoms: proj-atom", age_s=5000 + i)

    cwd_map = {
        "C:/u/.claude": root_mem,
        "c:/u/.claude": root_mem,        # 同一根層、不同大小寫的 cwd
        "C:/proj": proj_mem,
        "C:/empty-proj": tmp_path / "empty" / ".claude" / "memory",  # 有記憶目錄、沒 episodic
        "D:/scratch": None,              # 沒有專案記憶
    }
    monkeypatch.setattr(wg_evasion, "MEMORY_DIR", root_mem)
    monkeypatch.setattr(wg_evasion, "get_project_memory_dir", lambda cwd: cwd_map.get(cwd))
    monkeypatch.setattr(wg_evasion, "WORKFLOW_DIR", tmp_path / "workflow")
    (tmp_path / "workflow").mkdir()
    return tmp_path


def _st(cwd: str, modified=None) -> dict:
    st = {"session": {"cwd": cwd}}
    if modified is not None:
        st["iteration_metrics"] = {"atoms_modified": modified}
    return st


# ─── 覆轍 ─────────────────────────────────────────────────────────────


def test_root_session_still_sees_root_ruts(layout):
    """~/.claude session 行為不變：根層信號照報（也是下面幾案「根層池確實會觸發」的前置）。"""
    msg = wg_evasion._detect_rut_patterns(_st("C:/u/.claude"), {})
    assert msg and "wg_need_goal.py" in msg and "overview_hub.py" in msg


def test_project_session_sees_only_own_ruts(layout):
    msg = wg_evasion._detect_rut_patterns(_st("C:/proj"), {})
    assert msg and "MainForm.cs" in msg, "專案自己的覆轍要照報"
    assert "wg_need_goal.py" not in msg and "overview_hub.py" not in msg, "根層檔不得出現在專案 session"


def test_project_without_episodic_gets_nothing(layout):
    """專案池沒有 episodic 時不回退到根層池。"""
    assert wg_evasion._detect_rut_patterns(_st("C:/u/.claude"), {}), "前置：根層池確實會觸發"
    assert wg_evasion._detect_rut_patterns(_st("C:/empty-proj"), {}) is None


def test_no_memory_cwd_gets_nothing(layout):
    """cwd 沒有專案記憶：寫入端落根層目錄，但讀取端不拿根層歷史提示它。"""
    assert wg_evasion._detect_rut_patterns(_st("C:/u/.claude"), {}), "前置：根層池確實會觸發"
    assert wg_evasion._detect_rut_patterns(_st("D:/scratch"), {}) is None
    assert wg_evasion._detect_rut_patterns(_st(""), {}) is None


# ─── 振盪偵測 ─────────────────────────────────────────────────────────


def test_oscillation_uses_own_pool(layout):
    root = [o["atom"] for o in wg_evasion._detect_oscillation(_st("C:/u/.claude", []), {})]
    proj = [o["atom"] for o in wg_evasion._detect_oscillation(_st("C:/proj", []), {})]
    assert "root-atom" in root
    assert "root-atom" not in proj, "專案 session 不得把根層 atom 算成振盪"


# ─── 振盪狀態檔：依池分存分讀 ─────────────────────────────────────────


_OSC = [{"atom": "proj-atom", "count": 2, "sessions": ["2026-10-01", "2026-10-02"]}]


def test_osc_state_not_shown_to_other_pool(layout):
    wg_evasion._save_oscillation_state(_OSC, _st("C:/proj"))
    assert "proj-atom" in (wg_evasion._load_oscillation_warnings(_st("C:/proj")) or "")
    assert wg_evasion._load_oscillation_warnings(_st("C:/u/.claude")) is None
    assert wg_evasion._load_oscillation_warnings(_st("D:/scratch")) is None


def test_osc_state_not_wiped_by_other_pool(layout):
    """根層 session 收尾沒有振盪（存空）不得刪掉專案的振盪狀態。"""
    wg_evasion._save_oscillation_state(_OSC, _st("C:/proj"))
    wg_evasion._save_oscillation_state([], _st("C:/u/.claude"))
    wg_evasion._save_oscillation_state([], _st("D:/scratch"))
    assert "proj-atom" in (wg_evasion._load_oscillation_warnings(_st("C:/proj")) or "")
    wg_evasion._save_oscillation_state([], _st("C:/proj"))
    assert not (layout / "workflow" / "oscillation_state.json").exists(), "全部池都清空時刪檔"


def test_osc_state_key_ignores_cwd_case(layout):
    root_osc = [{"atom": "root-atom", "count": 2, "sessions": ["a", "b"]}]
    wg_evasion._save_oscillation_state(root_osc, _st("C:/u/.claude"))
    assert "root-atom" in (wg_evasion._load_oscillation_warnings(_st("c:/u/.claude")) or "")


def test_osc_state_legacy_format_ignored(layout):
    """舊格式（全機一份、不知來源池）不再對任何 session 顯示。"""
    root_osc = [{"atom": "root-atom", "count": 2, "sessions": ["a", "b"]}]
    wg_evasion._save_oscillation_state(root_osc, _st("C:/u/.claude"))
    assert wg_evasion._load_oscillation_warnings(_st("C:/u/.claude")), "前置：新格式讀得到"
    (layout / "workflow" / "oscillation_state.json").write_text(
        json.dumps({"detected_at": "x", "oscillations": [{"atom": "old", "count": 2, "sessions": []}]}),
        encoding="utf-8",
    )
    assert wg_evasion._load_oscillation_warnings(_st("C:/u/.claude")) is None
    assert wg_evasion._load_oscillation_warnings(_st("C:/proj")) is None

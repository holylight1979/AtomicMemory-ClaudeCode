"""verify_mojibake_detect.py — 亂碼名稱（U+0080–U+00FF，如某專案的 `shared/UIºt¥X`）偵測守門。

tmp 記憶樹含 `UIºt¥X` 資料夾（空、同該專案現場）與一顆落在裡面的 atom：
  - atom-health-check --report：只對該名稱出一行 `⚠ 疑似亂碼名稱: <path>` 警告、exit 0、報告多一個
    `mojibake_names` 檢查項、裡面的 atom 不計入 total；正常 atom 照常計入。
  - sync-memory-index --check：全域樹與專案樹都不炸（exit 0／1 皆可，不得 traceback），stderr 同樣一行警告，
    索引列指向亂碼路徑者被跳過。
兩工具各自一個小判斷式（文字相同、知識不同步，不抽共用）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent
HEALTH_CHECK = CLAUDE_DIR / "tools" / "atom-health-check.py"
SYNC_MEMORY_INDEX = CLAUDE_DIR / "tools" / "sync-memory-index.py"
MOJIBAKE = "UIºt¥X"
WARN = "⚠ 疑似亂碼名稱: "
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

ATOM = ("# {name}\n\n- Scope: {scope}\n- Confidence: [臨]\n- Trigger: {name}\n\n"
        "## 知識\n\n- [臨] x\n\n## 行動\n\n- y\n")


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=ENV, timeout=120, cwd=str(CLAUDE_DIR))


def _tree(mem: Path, shared: bool) -> None:
    """mem/ 下：一顆正常 atom + `UIºt¥X/` 內一顆 atom（索引兩列都登記）。"""
    base = mem / "shared" if shared else mem
    prefix = "memory/shared/" if shared else "memory/"
    scope = "shared" if shared else "global"
    (base / "工作流").mkdir(parents=True)
    (base / "工作流" / "ok-atom.md").write_text(ATOM.format(name="ok-atom", scope=scope), encoding="utf-8")
    (base / MOJIBAKE).mkdir()
    (base / MOJIBAKE / "bad-atom.md").write_text(ATOM.format(name="bad-atom", scope=scope), encoding="utf-8")
    atoms = [{"name": "ok-atom", "path": f"{prefix}工作流/ok-atom.md", "triggers": ["ok-atom"], "scope": scope},
             {"name": "bad-atom", "path": f"{prefix}{MOJIBAKE}/bad-atom.md", "triggers": ["bad-atom"], "scope": scope}]
    (mem / "_atom_index.json").write_text(json.dumps({"version": "1.0", "atoms": atoms}, ensure_ascii=False),
                                          encoding="utf-8")


def test_health_check_warns_once_and_keeps_going(tmp_path):
    mem = tmp_path / "memory"
    _tree(mem, shared=False)
    r = _run(HEALTH_CHECK, "--report", "--json", "--memory-root", str(mem))
    assert r.returncode == 0, (r.stdout, r.stderr)
    warns = [ln for ln in r.stderr.splitlines() if ln.startswith(WARN)]
    assert len(warns) == 1 and warns[0].endswith(MOJIBAKE), r.stderr
    assert "Traceback" not in r.stderr
    rep = json.loads(r.stdout)
    assert rep["mojibake_names"] == [str(mem / MOJIBAKE)]
    assert [a["name"] for a in rep["atoms"]] == ["ok-atom"]   # 亂碼夾內的 atom 跳過、正常的照常


def test_health_check_text_report_lists_check_item(tmp_path):
    mem = tmp_path / "memory"
    _tree(mem, shared=False)
    r = _run(HEALTH_CHECK, "--report", "--memory-root", str(mem))
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "疑似亂碼名稱" in r.stdout and MOJIBAKE in r.stdout


def test_sync_memory_index_check_global_tree_does_not_crash(tmp_path):
    mem = tmp_path / "memory"
    _tree(mem, shared=False)
    (mem / "MEMORY.md").write_text("# Atom Index — Global\n", encoding="utf-8")
    r = _run(SYNC_MEMORY_INDEX, "--check", "--memory-dir", str(mem))
    assert "Traceback" not in r.stderr, r.stderr
    warns = [ln for ln in r.stderr.splitlines() if ln.startswith(WARN)]
    assert warns and all(MOJIBAKE in w for w in warns), r.stderr
    dry = _run(SYNC_MEMORY_INDEX, "--memory-dir", str(mem))
    assert dry.returncode == 0 and "Traceback" not in dry.stderr, (dry.stdout, dry.stderr)
    assert "bad-atom" not in dry.stdout and MOJIBAKE not in dry.stdout, dry.stdout


def test_sync_memory_index_check_project_tree_does_not_crash(tmp_path):
    mem = tmp_path / "proj" / ".claude" / "memory"
    _tree(mem, shared=True)
    (mem / "MEMORY.md").write_text("# Atom Index — Project\n\n<!-- atom-catalog -->\n<!-- /atom-catalog -->\n",
                                   encoding="utf-8")
    r = _run(SYNC_MEMORY_INDEX, "--check", "--memory-dir", str(mem))
    assert "Traceback" not in r.stderr, r.stderr
    warns = [ln for ln in r.stderr.splitlines() if ln.startswith(WARN)]
    assert warns and all(MOJIBAKE in w for w in warns), r.stderr
    dry = _run(SYNC_MEMORY_INDEX, "--memory-dir", str(mem))
    assert dry.returncode == 0 and "Traceback" not in dry.stderr, (dry.stdout, dry.stderr)
    assert "| 工作流 | 1 |" in dry.stdout and MOJIBAKE not in dry.stdout, dry.stdout

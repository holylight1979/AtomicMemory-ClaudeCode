"""verify_sync_memory_index_bridge.py：sync-memory-index.py 全域寫入後 spawn 的 native-memory-bridge.py 是本樹那支，資料仍寫在資料根。

做什麼：子行程跑本樹的 sync-memory-index.py --write（全域分支），--memory-dir 指 tmp家/.claude/memory、HOME 指 tmp 家；
資料根 tmp家/.claude/tools/ 放一支誘餌 native-memory-bridge.py（一跑就寫標記、exit 9）。
斷言：誘餌沒跑、stderr 沒有 bridge 失敗訊號、本樹 bridge 把橋接檔寫進 tmp 資料根的原生 memory 目錄、MEMORY.md 寫在 tmp 資料根。
反例：退回舊碼（bridge 路徑用 memory_dir.parent 拼）→ 誘餌被跑、stderr 有「[native-memory-bridge] exit 9」。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_sync_memory_index_bridge.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[2]
SCRIPT = TREE / "tools" / "sync-memory-index.py"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def test_global_write_spawns_bridge_from_code_tree_not_data_root_decoy(tmp_path):
    home = tmp_path / "home"
    data = home / ".claude"
    mem = data / "memory"
    mem.mkdir(parents=True)
    (mem / "core-note.md").write_text("# 核心筆記\n\n- Confidence: [臨]\n", encoding="utf-8")
    index = {"version": "1.0", "atoms": [{"name": "core-note", "path": "memory/core-note.md",
                                          "triggers": ["t-core"], "scope": "global"}]}
    (mem / "_atom_index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    marker = tmp_path / "decoy-ran.txt"
    (data / "tools").mkdir()
    (data / "tools" / "native-memory-bridge.py").write_text(
        f"open(r'{marker}', 'w').write('x')\nraise SystemExit(9)\n", encoding="utf-8")
    native = data / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(data)).lower() / "memory"
    native.mkdir(parents=True)                                                   # bridge 只寫已存在的原生目錄
    env = {k: v for k, v in os.environ.items() if k not in ("WG_CLAUDE_DIR", "PYTHONPATH")}
    env.update({"HOME": str(home), "USERPROFILE": str(home), "WG_CLAUDE_DIR": str(data), "PYTHONIOENCODING": "utf-8"})
    r = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "--write", "--legacy", "--memory-dir", str(mem)],
                       env=env, cwd=str(tmp_path), capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=120, creationflags=NO_WINDOW)
    assert r.returncode == 0, r.stderr[-2000:]
    assert not marker.exists(), r.stderr[-2000:]                                 # 反例：舊碼跑資料根那支誘餌
    assert "[native-memory-bridge]" not in r.stderr, r.stderr[-2000:]
    bridge = native / "atom-index-bridge.md"
    assert bridge.is_file() and "core-note" in bridge.read_text(encoding="utf-8")  # 本樹 bridge 寫進 tmp 資料根
    assert "core-note" in (mem / "MEMORY.md").read_text(encoding="utf-8")         # 索引仍寫在 tmp 資料根

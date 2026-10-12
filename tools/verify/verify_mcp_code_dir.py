"""verify_mcp_code_dir.py：MCP（node）spawn 的 Python 程式碼來自本樹（paths.CODE_DIR），資料位置仍是家目錄 .claude。

做什麼：
- node 子行程 require 本樹的 paths.js／funnel.js／atom-access.js，把 child_process.spawn 換成記錄參數的替身（不真的起 py），
  HOME／USERPROFILE 指到放了誘餌的 tmp 家（tmp家/.claude/lib/atom_io_cli.py 一跑就寫標記）。
  觸發 spawnAtomCli、spawnAtomAccess → 斷言 `python -m lib.*` 的 cwd 在本樹、TOOLS_DIR 在本樹、CLAUDE_DIR 是 tmp家/.claude、誘餌沒被跑。
- 靜態：tools/workflow-guardian-mcp 的 .js 不得出現 `cwd: CLAUDE_DIR`，也不得用 CLAUDE_DIR 接 "tools"／"hooks"／"lib"／*.py、run_verify.py。
反例：退回舊碼（cwd: CLAUDE_DIR、TOOLS_DIR 由 CLAUDE_DIR 推）兩案都紅。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_mcp_code_dir.py（需要 node）
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parents[2]
MCP = TREE / "tools" / "workflow-guardian-mcp"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

NODE_PROBE = r"""
const cp = require("child_process");
const calls = [];
cp.spawn = (cmd, args, opts) => { calls.push({ cmd, args, cwd: (opts || {}).cwd || null }); throw new Error("spawn stub"); };
const lib = process.argv[1];   // node -e：argv[0]＝node，argv[1] 起是傳入參數
const paths = require(lib + "/paths.js");
const funnel = require(lib + "/funnel.js");
const access = require(lib + "/atom-access.js");
(async () => {
  await funnel.spawnAtomCli("locate", {});
  await access.spawnAtomAccess("set", ["x"]);
  console.log("PROBE_JSON " + JSON.stringify({ CODE_DIR: paths.CODE_DIR, TOOLS_DIR: paths.TOOLS_DIR,
                                              CLAUDE_DIR: paths.CLAUDE_DIR, calls }));
})();
"""


def _n(p) -> str:
    return os.path.normcase(os.path.realpath(str(p)))


def _under(p, root) -> bool:
    a, r = _n(p), _n(root)
    return a == r or a.startswith(r + os.sep)


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_mcp_spawns_python_from_code_dir_with_home_decoy(tmp_path):
    home = tmp_path / "home"
    decoy = home / ".claude" / "lib"
    decoy.mkdir(parents=True)
    marker = tmp_path / "decoy-ran.txt"
    (decoy / "__init__.py").write_text("", encoding="utf-8")
    (decoy / "atom_io_cli.py").write_text(f"open(r'{marker}', 'w').write('x')\nraise SystemExit(9)\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "WG_CLAUDE_DIR"}
    env.update({"HOME": str(home), "USERPROFILE": str(home)})
    r = subprocess.run(["node", "-e", NODE_PROBE, str(MCP / "lib")], env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60, creationflags=NO_WINDOW)
    line = next((l for l in r.stdout.splitlines() if l.startswith("PROBE_JSON ")), None)
    assert r.returncode == 0 and line, f"rc={r.returncode}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}"
    got = json.loads(line[len("PROBE_JSON "):])
    assert _n(got["CODE_DIR"]) == _n(TREE) and _under(got["TOOLS_DIR"], TREE)
    assert _n(got["CLAUDE_DIR"]) == _n(home / ".claude")                                # 資料位置仍是家目錄
    py_calls = [c for c in got["calls"] if "-m" in c["args"]]
    assert {c["args"][c["args"].index("-m") + 1] for c in py_calls} == {"lib.atom_io_cli", "lib.atom_access"}
    for c in py_calls:
        assert c["cwd"] and _under(c["cwd"], TREE) and not _under(c["cwd"], home), c    # 反例：舊碼 cwd 是 tmp家/.claude
    assert not marker.exists()


def test_mcp_js_has_no_code_path_from_data_root():
    bad = []
    pat = re.compile(r"cwd:\s*CLAUDE_DIR\b|path\.join\(\s*CLAUDE_DIR\s*,\s*\"(?:tools|hooks|lib|run_verify\.py|[^\"]*\.py)\"")
    for p in sorted(MCP.rglob("*.js")):
        if "node_modules" in p.parts:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(line):
                bad.append(f"{p.relative_to(TREE).as_posix()}:{i}  {line.strip()}")
    assert bad == [], "\n".join(bad)

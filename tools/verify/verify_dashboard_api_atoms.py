"""verify_dashboard_api_atoms.py — dashboard /api/atoms 以 memory/_atom_index.json 為 global 層真相。

三條驗證：
  1. 真實 index、隔離埠起一個 guardian server：/api/atoms 回的 global 層筆（帶 rel_path）
     集合 == index 中檔案實際存在的 path 集合；每筆帶 layer / category(list) / realm；
     local 與 failures 層各至少一筆；knowledge_count / line_count 是 int。
  2. 純函式（不起 server）：layerFromRelPath / categorySegmentsFromRelPath / realmFromRelPath
     對四種路徑型態的推導。
  3. node --check http-api.js 語法通過。

server 在 stdin EOF 時自退（孤兒防護），所以 stdin 用 PIPE 保持開啟，收尾才 close。
埠被別人占（whoami 回的 pid 不是自己的）→ 換下一個埠重試一次，再不行 skip。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # tools/verify/ → ~/.claude
MCP_DIR = CLAUDE_DIR / "tools" / "workflow-guardian-mcp"
SERVER_JS = MCP_DIR / "server.js"
HTTP_API_JS = MCP_DIR / "lib" / "http-api.js"
ATOM_INDEX = CLAUDE_DIR / "memory" / "_atom_index.json"

PORTS = (38482, 38483)
BOOT_TIMEOUT_S = 20.0
POLL_INTERVAL_S = 0.5

NODE = shutil.which("node")


def _get_json(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _stop(proc: subprocess.Popen) -> None:
    try:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
    except OSError:
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _spawn(port: int) -> subprocess.Popen:
    env = {**os.environ, "WG_DASHBOARD_PORT": str(port)}
    return subprocess.Popen(
        [NODE, str(SERVER_JS)],
        cwd=str(MCP_DIR),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def _wait_bound(proc: subprocess.Popen, port: int) -> str:
    """回 'ok' / 'taken'（埠被別的行程持有）/ 'dead'（server 提早退出）/ 'timeout'。"""
    deadline = time.monotonic() + BOOT_TIMEOUT_S
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return "dead"
        try:
            who = _get_json(f"http://127.0.0.1:{port}/api/whoami", timeout=2.0)
        except (urllib.error.URLError, OSError, ValueError):
            time.sleep(POLL_INTERVAL_S)
            continue
        return "ok" if who.get("pid") == proc.pid else "taken"
    return "timeout"


@pytest.fixture(scope="module")
def live_server():
    """在隔離埠起 server；yield (port, proc)。埠被占換埠重試一次，都不行 skip。"""
    if not NODE:
        pytest.skip("node 不在 PATH")
    if not SERVER_JS.exists():
        pytest.skip(f"找不到 {SERVER_JS}")
    if not ATOM_INDEX.exists():
        pytest.skip(f"找不到 {ATOM_INDEX}")

    last = None
    for port in PORTS:
        proc = _spawn(port)
        state = _wait_bound(proc, port)
        if state == "ok":
            try:
                yield port, proc
            finally:
                _stop(proc)
            return
        err = ""
        try:
            _stop(proc)
            if proc.stderr:
                err = proc.stderr.read().decode("utf-8", "replace")[-800:]
        except Exception:
            pass
        last = (port, state, err)
    pytest.skip(f"隔離埠都起不來：{last}")


def _index_paths_existing() -> set[str]:
    data = json.loads(ATOM_INDEX.read_text(encoding="utf-8"))
    out = set()
    for e in data.get("atoms", []):
        rel = str(e.get("path", "")).replace("\\", "/")
        if rel and (CLAUDE_DIR / rel).exists():
            out.add(rel)
    return out


# ── 測試 1：真實 index + 隔離埠 ────────────────────────────────────────────────

def test_case1_api_atoms_matches_index(live_server):
    port, _proc = live_server
    atoms = _get_json(f"http://127.0.0.1:{port}/api/atoms", timeout=30.0)
    assert isinstance(atoms, list) and atoms, "/api/atoms 應回非空陣列"

    from_index = [a for a in atoms if "rel_path" in a]
    got = {a["rel_path"] for a in from_index}
    expected = _index_paths_existing()
    missing = sorted(expected - got)
    extra = sorted(got - expected)
    assert not missing and not extra, f"index 與 API 不一致 missing={missing} extra={extra}"

    layers = set()
    for a in from_index:
        assert a.get("layer") in ("global", "failures", "local"), a["rel_path"]
        assert isinstance(a.get("category"), list), a["rel_path"]
        assert a.get("realm") in ("core", "local"), a["rel_path"]
        assert isinstance(a.get("knowledge_count"), int), a["rel_path"]
        assert isinstance(a.get("line_count"), int), a["rel_path"]
        layers.add(a["layer"])
    assert "local" in layers, "應至少一筆 layer=local（_AIDocs/_atoms）"
    assert "failures" in layers, "應至少一筆 layer=failures（Failures 樹）"


def test_case1b_api_projects_claude_dir_counts_from_index(live_server):
    port, _proc = live_server
    projects = _get_json(f"http://127.0.0.1:{port}/api/projects", timeout=10.0)
    data = json.loads(ATOM_INDEX.read_text(encoding="utf-8"))
    entries = data.get("atoms", [])
    want_fail = sum(
        1 for e in entries
        if str(e.get("path", "")).startswith(("memory/Failures/", "_AIDocs/Failures/"))
    )
    core = [p for p in projects if p.get("has_memory")
            and Path(p.get("root", "")).resolve() == CLAUDE_DIR.resolve()]
    if not core:
        pytest.skip("registry 未登錄 ~/.claude 本身")
    assert core[0]["atom_count"] == len(entries)
    assert core[0]["failure_count"] == want_fail


# ── 測試 2：純函式 ────────────────────────────────────────────────────────────

def test_case2_path_helpers_pure():
    if not NODE:
        pytest.skip("node 不在 PATH")
    cases = [
        "memory/decisions.md",
        "memory/a/b/x.md",
        "_AIDocs/Failures/x.md",
        "_AIDocs/_atoms/a/b/x.md",
        "memory/Failures/topic/x.md",
    ]
    script = (
        'const m=require("./lib/http-api");'
        "const out={};"
        f"for (const p of {json.dumps(cases)}) "
        "out[p]={layer:m.layerFromRelPath(p),category:m.categorySegmentsFromRelPath(p),realm:m.realmFromRelPath(p)};"
        "process.stdout.write(JSON.stringify(out));"
    )
    r = subprocess.run([NODE, "-e", script], cwd=str(MCP_DIR), capture_output=True, text=True,
                       encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["memory/decisions.md"] == {"layer": "global", "category": [], "realm": "core"}
    assert out["memory/a/b/x.md"] == {"layer": "global", "category": ["a", "b"], "realm": "core"}
    assert out["_AIDocs/Failures/x.md"] == {"layer": "failures", "category": ["Failures"], "realm": "core"}
    assert out["_AIDocs/_atoms/a/b/x.md"] == {"layer": "local", "category": ["a", "b"], "realm": "local"}
    assert out["memory/Failures/topic/x.md"] == {"layer": "failures", "category": ["Failures", "topic"], "realm": "core"}


# ── 測試 3：語法 ──────────────────────────────────────────────────────────────

def test_case3_node_check():
    if not NODE:
        pytest.skip("node 不在 PATH")
    r = subprocess.run([NODE, "--check", str(HTTP_API_JS)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

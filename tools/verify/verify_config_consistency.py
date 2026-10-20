"""verify_config_consistency.py：tools/config-consistency.py 的四類各抓得到、動態鍵進「判不了」不進 (a)、尾行格式。

做法：在 pytest 的 tmp 建一棵假樹（workflow/config.json、TECH.md §12、lib/hub_config.py、幾支假 .py／.js），
以子程序跑工具（--root 假樹 --config 假 config），讀 --json 輸出與尾行斷言。真實的 ~/.claude 不碰。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_config_consistency.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "config-consistency.py"
DONE_RE = re.compile(r"^[A-Z][A-Z0-9_]* DONE( \w+=\S+)*$")

FILES = {
    "workflow/config.json": json.dumps({"bar": 1, "baz": {"enabled": True}, "known": {"x": 1}, "_doc": "不算"}),
    "TECH.md": "# t\n\n## 12. 設定總表\n\n| 鍵 | 預設 | 意義 |\n|----|------|------|\n| `techkey.a` / `b` | 1 / 2 | 文件定義 |\n\n## 13. 其他\n",
    "lib/hub_config.py": 'HUB_DEFAULTS = {"enabled": True}\n',
    "hooks/x.py": (
        "def f(config):\n"
        '    a = config.get("foo")\n'
        '    b = config.get("baz", {}).get("enabled", True)\n'
        '    c = config.get("techkey", {}).get("a")\n'
        '    d = config.get("overview_hub", {}).get("enabled")\n'
        '    return config.get("known", {}).get("x")\n'
    ),
    "tools/workflow-guardian-mcp/lib/y.js": (
        'const { loadConfig } = require("./paths");\n'
        "function g() {\n"
        "  const cfg = loadConfig();\n"
        "  return cfg.baz?.enabled ?? false;\n"
        "}\n"
    ),
    "lib/z.py": 'from pathlib import Path\nDATA = Path.home() / ".claude"\n',
    "lib/w.py": "def h(config, key):\n    return config.get(key)\n",
    "hooks/verify/verify_skip.py": 'def t(config):\n    return config.get("only_in_test")\n',
}


@pytest.fixture(scope="module")
def tree(tmp_path_factory):
    root = tmp_path_factory.mktemp("cc_tree")
    for rel, text in FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def _run(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "--root", str(root),
                           "--config", str(root / "workflow" / "config.json"), *extra],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


@pytest.fixture(scope="module")
def result(tree):
    r = _run(tree, "--json")
    assert r.returncode == 0, r.stderr[-800:]
    body, last = r.stdout.rstrip().rsplit("\n", 1)
    return json.loads(body), last


def test_a_read_not_defined_only_foo(result):
    res, _ = result
    assert [row["key"] for row in res["a"]] == ["foo"]          # techkey（TECH.md）、overview_hub（HUB_DEFAULTS）、known 都算有定義


def test_b_defined_not_read(result):
    res, _ = result
    assert [row["key"] for row in res["b"]] == ["bar"]


def test_c_default_mismatch_shows_both_sides(result):
    res, _ = result
    assert [row["key"] for row in res["c"]] == ["baz.enabled"]
    shown = " ".join(res["c"][0]["defaults"])
    assert "true @ hooks/x.py:3（py" in shown and "false @ tools/workflow-guardian-mcp/lib/y.js:4（js" in shown


def test_d_home_claude(result):
    res, _ = result
    assert [(r["file"], r["line"]) for r in res["d"]] == [("lib/z.py", 2)]
    assert 'Path.home() / ".claude"' in res["d"][0]["code"]


def test_dynamic_key_goes_to_unknown_not_a(result):
    res, _ = result
    dyn = res["unknown"]["dynamic"]
    assert [d["where"] for d in dyn] == ["lib/w.py:2"]           # 前置：動態鍵確實被看到
    assert all(row["key"] != "key" for row in res["a"])


def test_test_files_are_not_readers(result, tree):
    res, _ = result
    assert (tree / "hooks" / "verify" / "verify_skip.py").is_file()   # 前置：測試檔在樹裡
    assert all("only_in_test" not in row["key"] for row in res["a"])


def test_done_line(result):
    _, last = result
    assert DONE_RE.match(last), last
    assert last == ("CONFIG_CONSISTENCY DONE keys=" + last.split("keys=")[1].split()[0]
                    + " read_not_defined=1 defined_not_read=1 default_mismatch=1 path_self_computed=1")


def test_markdown_out_and_notes(tree, tmp_path):
    notes = tmp_path / "notes.json"
    notes.write_text(json.dumps({"a:foo": "補進 config.json", "d:*": "改走 claude_data_dir"}, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "report.md"
    r = _run(tree, "--out", str(out), "--notes", str(notes))
    assert r.returncode == 0, r.stderr[-800:]
    text = out.read_text(encoding="utf-8")
    for head in ("## (a)", "## (b)", "## (c)", "## (d)", "## 判不了"):
        assert head in text
    assert "補進 config.json" in text and "改走 claude_data_dir" in text
    assert DONE_RE.match(text.rstrip().splitlines()[-1])
    assert DONE_RE.match(r.stdout.rstrip().splitlines()[-1])


# ─── 本樹重跑：派工 002 修過的鍵與檔不再出現 ─────────────────────────────

FIXED_B = {"cross_session.enabled", "write_gate.enabled", "provenance.quote_max_chars"}
FIXED_C = {"usefulness.wilson_z", "vcs_sync.exclude", "session_context.search_timeout_ms", "sync_keywords",
           "vector_search.fallback_backend",
           "vector_search.fallback_model", "vector_search.search_min_score", "vector_search.search_timeout_ms"}
FIXED_D = {"hooks/handlers/pre_tool_use.py", "hooks/wg_core.py", "lib/vcs_ignore.py", "tools/merge-atom-index.py"}


@pytest.fixture(scope="module")
def repo_result():
    r = _run(ROOT, "--json")   # _run 的 --config 是 <樹>/workflow/config.json：本樹受版控那份，結果不受 live 變動影響
    assert r.returncode == 0, r.stderr[-800:]
    res = json.loads(r.stdout.rstrip().rsplit("\n", 1)[0])
    assert res["sources"]["py_files"] > 100                  # 前置：真的掃了本樹
    return res


def test_repo_fixed_switches_are_read(repo_result):
    assert not FIXED_B & {row["key"] for row in repo_result["b"]}


def test_repo_fixed_keys_have_one_default(repo_result):
    assert not FIXED_C & {row["key"] for row in repo_result["c"]}


def test_repo_fixed_files_use_data_root(repo_result):
    assert not FIXED_D & {row["file"] for row in repo_result["d"]}


def test_missing_config_exit_2(tree, tmp_path):
    r = subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "--root", str(tree), "--config", str(tmp_path / "nope.json")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    assert r.returncode == 2
    assert DONE_RE.match(r.stdout.rstrip().splitlines()[-1])

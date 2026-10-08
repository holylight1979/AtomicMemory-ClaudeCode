"""verify_prebuild_template.py: templates/prebuild-check.template.py 的契約（Q11）。

守住：
- 正例：fixture hub.json 三項登記檢查（PASS 哨兵、DONE 量測、sentinel_regex 映射）全過；乾淨 diff 不 FAIL；exit 0 尾行 PREBUILD_CHECK PASS。
- 反例：任一項 FAIL（exit 非 0、或尾行不符）整體 exit 1；只印 `X_CHECK` 缺字尾不算 PASS；
  defect_shape 的 shape regex 掃到 diff_bad 新增行必 FAIL（兩條形狀都抓到）、diff_ok 不 FAIL（被刪掉的病灶行不算）；
  defects_doc 指的檔不存在 FAIL（不靜默）；非法 regex FAIL。
- 端到端：tmp git repo 真 init、真 stage，含病灶形狀的改動 exit 1，乾淨改動 exit 0。
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parents[2]
TEMPLATE = CLAUDE / "templates" / "prebuild-check.template.py"
FIX = CLAUDE / "hooks" / "verify" / "fixtures" / "v6" / "prebuild"

_spec = importlib.util.spec_from_file_location("prebuild_check", TEMPLATE)
PB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PB)


def _hub() -> dict:
    return json.loads((FIX / "hub.json").read_text(encoding="utf-8"))


# ─── 哨兵判定 ───────────────────────────────────────────────────────

@pytest.mark.parametrize("out,expect,ok", [
    ("x\nUNIT_CHECK PASS\n", "PASS", True),
    ("UNIT_CHECK PASS\n\n  \n", "PASS", True),
    ("UNIT_CHECK\n", "PASS", False),            # 缺字尾
    ("UNIT_CHECK FAIL\n", "PASS", False),
    ("UNIT_CHECK PASS\nmore\n", "PASS", False),  # 哨兵不在尾行
    ("unit_check PASS\n", "PASS", False),        # 小寫
    ("SMELLS DONE files=3 smells=0\n", "DONE", True),
    ("SMELLS DONE\n", "DONE", True),
    ("SMELLS DONE files=3 smells=0\n", "PASS", False),
    ("UNIT_CHECK PASS\n", "DONE", False),
    ("", "PASS", False),
])
def test_judge_output(out, expect, ok):
    assert PB.judge_output(out, expect)[0] is ok


def test_sentinel_regex_mapping():
    assert PB.judge_output("ALL GOOD\n", "PASS", "^ALL GOOD$")[0]
    assert not PB.judge_output("ALL GOOD?\n", "PASS", "^ALL GOOD$")[0]
    assert not PB.judge_output("ALL GOOD\n", "PASS")[0]


def test_unknown_expect_is_fail():
    ok, why = PB.judge_output("X_CHECK PASS\n", "OK")
    assert not ok and "expect" in why


# ─── 登記項實跑 ─────────────────────────────────────────────────────

def test_fixture_checks_all_pass():
    for check in _hub()["prebuild_checks"]:
        ok, why = PB.run_check(check, FIX)
        assert ok, why


def test_nonzero_exit_fails_even_with_pass_sentinel():
    check = {"name": "x", "cmd": "python -X utf8 -c \"print('X_CHECK PASS'); raise SystemExit(3)\"", "expect": "PASS"}
    ok, why = PB.run_check(check, FIX)
    assert not ok and "exit 3" in why


def test_missing_suffix_fails():
    check = {"name": "x", "cmd": "python -X utf8 -c \"print('X_CHECK')\"", "expect": "PASS"}
    assert not PB.run_check(check, FIX)[0]


# ─── 病灶形狀 ───────────────────────────────────────────────────────

def test_parse_shapes_table_cell_and_standalone_line():
    shapes = PB.parse_shapes((FIX / "defects.md").read_text(encoding="utf-8"))
    assert shapes == [r"except\s*:\s*pass\b", r"lambda\b.*\blambda\b"]


def test_parse_shapes_unescapes_pipe_in_table_cell():
    assert PB.parse_shapes("| a | b | c | d | e | f | shape: foo\\|bar |") == ["foo|bar"]


def test_defect_shape_catches_bad_diff_and_passes_ok_diff():
    ok, reasons = PB.defect_shape(FIX, "defects.md", (FIX / "diff_bad.patch").read_text(encoding="utf-8"))
    assert not ok and len(reasons) == 2
    assert any("except" in r for r in reasons) and any("lambda" in r for r in reasons)
    ok, reasons = PB.defect_shape(FIX, "defects.md", (FIX / "diff_ok.patch").read_text(encoding="utf-8"))
    assert ok and reasons == []


def test_defect_shape_missing_doc_and_bad_regex_fail(tmp_path):
    ok, reasons = PB.defect_shape(tmp_path, ["nope.md"], "")
    assert not ok and "不存在" in reasons[0]
    (tmp_path / "d.md").write_text("shape: (unclosed\n", encoding="utf-8", newline="\n")
    ok, reasons = PB.defect_shape(tmp_path, "d.md", "+x\n")
    assert not ok and "合法 regex" in reasons[0]


# ─── 整體 exit code ─────────────────────────────────────────────────

def _project(tmp_path: Path, hub: dict) -> Path:
    root = tmp_path / "proj"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "overview-hub.json").write_text(json.dumps(hub), encoding="utf-8", newline="\n")
    shutil.copy(FIX / "defects.md", root / "defects.md")
    return root


def test_main_any_fail_exits_1(tmp_path, monkeypatch, capsys):
    hub = _hub()
    hub["prebuild_checks"].append({"name": "broken", "cmd": "python -X utf8 -c \"print('BROKEN_CHECK')\"", "expect": "PASS"})
    root = _project(tmp_path, hub)
    monkeypatch.setattr(PB, "staged_diff", lambda _root: (FIX / "diff_ok.patch").read_text(encoding="utf-8"))
    assert PB.main(["--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert out.rstrip().splitlines()[-1] == "PREBUILD_CHECK FAIL" and "FAIL broken" in out


def test_main_all_pass_exits_0(tmp_path, monkeypatch, capsys):
    root = _project(tmp_path, _hub())
    monkeypatch.setattr(PB, "staged_diff", lambda _root: (FIX / "diff_ok.patch").read_text(encoding="utf-8"))
    assert PB.main(["--root", str(root)]) == 0
    assert capsys.readouterr().out.rstrip().splitlines()[-1] == "PREBUILD_CHECK PASS"


def test_main_shape_hit_exits_1(tmp_path, monkeypatch, capsys):
    root = _project(tmp_path, _hub())
    monkeypatch.setattr(PB, "staged_diff", lambda _root: (FIX / "diff_bad.patch").read_text(encoding="utf-8"))
    assert PB.main(["--root", str(root)]) == 1
    assert "defect_shape: 新增行命中形狀" in capsys.readouterr().out


def _git(root: Path, *args):
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, check=True)


def test_end_to_end_real_git_stage(tmp_path):
    if shutil.which("git") is None:
        pytest.fail("git 不在 PATH，端到端案跑不了")
    root = _project(tmp_path, _hub())
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    src = root / "app.py"
    src.write_text("def load():\n    try:\n        return read()\n    except: pass\n", encoding="utf-8", newline="\n")
    _git(root, "add", "app.py")
    p = subprocess.run([sys.executable, "-X", "utf8", str(TEMPLATE), "--root", str(root)],
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 1 and p.stdout.rstrip().splitlines()[-1] == "PREBUILD_CHECK FAIL", p.stdout
    src.write_text("def load():\n    return read()\n", encoding="utf-8", newline="\n")
    _git(root, "add", "app.py")
    p = subprocess.run([sys.executable, "-X", "utf8", str(TEMPLATE), "--root", str(root)],
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0 and p.stdout.rstrip().splitlines()[-1] == "PREBUILD_CHECK PASS", p.stdout


# ─── 001 退回的 BLOCK 3 與 WARN 反例 ────────────────────────────────

def test_added_lines_keeps_plus_plus_lines_and_drops_headers():
    """BLOCK 3：hunk 裡的 `++counter;` 是合法新增行要掃；hunk 前的 `+++ b/x` 是檔頭要丟。"""
    diff = "diff --git a/x.c b/x.c\n--- a/x.c\n+++ b/x.c\n@@ -1 +1,2 @@\n foo;\n+++counter;\n+bar;\n"
    assert PB.added_lines(diff) == ["++counter;", "bar;"]
    two = diff + "diff --git a/y.c b/y.c\n--- /dev/null\n+++ b/y.c\n@@ -0,0 +1 @@\n+baz;\n"
    assert PB.added_lines(two) == ["++counter;", "bar;", "baz;"]


def test_main_missing_hub_fails(tmp_path, capsys):
    """WARN：--root 指錯（沒有 overview-hub.json）不得零檢查 PASS。"""
    assert PB.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert out.rstrip().splitlines()[-1] == "PREBUILD_CHECK FAIL" and "overview-hub.json" in out

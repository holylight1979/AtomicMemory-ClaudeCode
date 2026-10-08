"""verify_project_smells.py：候選池工具 tools/project-smells.py 四種來源與正規化規則。

正例：新報告前 N 命中（含 smells_category_map 映射）；過期報告仍回資料且表頭有 stale 行；無報告有 cmd 走 cmd；
      都沒有走 builtin；哨兵尾行 PROJECT_SMELLS DONE n=。
反例：cmd 逾時回錯誤附指示（FAIL 哨兵、exit 1）；未知類別沒映射被丟棄並列名；無理由列被丟棄並計數；
      別部位的列被過濾；非白名單類別不得出現在輸出。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_project_smells.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "hooks" / "verify" / "fixtures" / "v6" / "smells"
SCRIPT = ROOT / "tools" / "project-smells.py"


def _load():
    spec = importlib.util.spec_from_file_location("project_smells", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["project_smells"] = mod
    spec.loader.exec_module(mod)
    return mod


ps = _load()


def _project(tmp_path, hub: dict | None, report: str | None):
    root = tmp_path / "proj"
    (root / ".claude").mkdir(parents=True)
    (root / "src" / "sched").mkdir(parents=True)
    if hub is not None:
        (root / ".claude" / "overview-hub.json").write_text(json.dumps(hub, ensure_ascii=False), encoding="utf-8", newline="\n")
    if report:
        shutil.copyfile(FIX / report, root / ".claude" / "smells.json")
    return root


def _hub():
    return json.loads((FIX / "hub.json").read_text(encoding="utf-8")) | {"smells_report": ".claude/smells.json"}


def test_fresh_report_top_n_with_mapping_and_drops(tmp_path):
    root = _project(tmp_path, _hub(), "fresh.json")
    res = ps.collect(str(root / "src"), "排程器")
    assert res["source"] == "report" and res["stale"] is False and res["age_days"] == 0
    rows = res["rows"]
    assert [r["rank"] for r in rows] == [1, 2, 3, 4, 5]
    assert rows[0]["path"] == "src/sched/queue.py" and rows[0]["category"] == "hotspot"
    assert rows[1]["path"] == "src/sched/plan.py"
    assert rows[2]["path"] == "src/sched/returns.py" and rows[2]["category"] == "complexity", "god-class 經 smells_category_map 映射"
    assert all(r["category"] in ps.CATEGORIES for r in rows)
    assert all(r["reason"] for r in rows)
    assert res["dropped"] == 1, "noreason.py 無理由被丟"
    assert res["dropped_unknown_category"] == 1 and res["unknown_categories"] == ["mystery"]
    assert res["filtered_part"] == 1, "src/ui/panel.py 屬別的部位"
    assert all(r["path"] != "src/ui/panel.py" for r in rows)
    text = ps.render_text(res)
    assert not text.startswith("stale:") and "mystery" in text


def test_stale_report_still_returns_rows_with_stale_header(tmp_path):
    root = _project(tmp_path, _hub(), "stale.json")
    res = ps.collect(str(root), "排程器")
    assert res["source"] == "report" and res["stale"] is True and res["age_days"] > 7
    assert len(res["rows"]) == 3 and res["rows"][2]["category"] == "complexity"
    assert res["rows"][0]["age_days"] == res["age_days"]
    text = ps.render_text(res)
    assert text.splitlines()[0].startswith("stale: 報告已") and "請重產報告" in text.splitlines()[0]


def test_no_report_with_cmd_runs_cmd(tmp_path, monkeypatch):
    hub = _hub() | {"smells_report": None, "smells_cmd": "python gen_smells.py --json"}
    root = _project(tmp_path, hub, None)
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["kw"] = list(cmd), kw
        class CP:
            returncode = 0
            stdout = json.dumps([{"path": "src/sched/a.py", "category": "size", "reason": "900 行"},
                                 {"path": "src/sched/b.py", "category": "nonsense", "reason": "x"}])
            stderr = ""
        return CP()
    monkeypatch.setattr(subprocess, "run", fake_run)
    res = ps.collect(str(root), "排程器")
    assert res["source"] == "cmd" and seen["cmd"] == ["python", "gen_smells.py", "--json"]
    assert seen["kw"]["timeout"] == 2 and seen["kw"]["cwd"] == str(root)
    assert [r["path"] for r in res["rows"]] == ["src/sched/a.py"] and res["unknown_categories"] == ["nonsense"]


def test_cmd_timeout_returns_error_with_hint(tmp_path, monkeypatch, capsys):
    hub = _hub() | {"smells_report": None, "smells_cmd": ["python", "slow.py"]}
    root = _project(tmp_path, hub, None)

    def fake_run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(ps.SmellsError) as ei:
        ps.collect(str(root), "排程器")
    assert "逾時" in str(ei.value) and "smells_report" in str(ei.value), "錯誤要附使用者能做什麼"
    rc = ps.main(["--cwd", str(root), "--part", "排程器", "--json"])
    out = capsys.readouterr().out.splitlines()
    assert rc == 1 and out[-1].startswith("PROJECT_SMELLS FAIL reason=") and json.loads(out[0])["error"]


def test_neither_report_nor_cmd_uses_builtin(tmp_path, monkeypatch):
    root = _project(tmp_path, None, None)
    (root / ".git").mkdir()  # 沒 hub 時以 .git 當專案根
    (root / "src" / "sched" / "big.py").write_text("x" * 5000, encoding="utf-8", newline="\n")
    (root / "src" / "sched" / "small.py").write_text("y" * 10, encoding="utf-8", newline="\n")
    (root / "src" / "sched" / "pic.png").write_bytes(b"\x89" * 9000)
    (root / "src" / "other.py").write_text("z" * 7000, encoding="utf-8", newline="\n")
    monkeypatch.setattr(ps, "_git_fix_hotspots", lambda *a, **k: {"src/sched/small.py": 3, "src/other.py": 9})
    res = ps.collect(str(root / "src" / "sched"), "src/sched")
    assert res["source"] == "builtin" and res["stale"] is False and res["root"] == str(root)
    cats = {r["category"] for r in res["rows"]}
    assert cats <= {"hotspot", "size"} and all(r["reason"] for r in res["rows"])
    hot = [r for r in res["rows"] if r["category"] == "hotspot"]
    assert [r["path"] for r in hot] == ["src/sched/small.py"], "熱點只取掃描範圍（<root>/<part>）內的"
    sizes = [r["path"] for r in res["rows"] if r["category"] == "size"]
    assert sizes[0] == "src/sched/big.py" and "src/sched/pic.png" not in sizes and "src/other.py" not in sizes


def test_normalize_rules_directly():
    rows = [
        {"path": "a.py", "category": "Hotspot", "reason": "r", "score": 1},
        {"path": "b.py", "category": "god-class", "reason": "r"},
        {"path": "c.py", "category": "god-class", "reason": ""},
        {"path": "d.py", "category": "alien", "reason": "r"},
        {"path": "", "category": "size", "reason": "r"},
        {"path": "e.py", "reason": "no category"},
    ]
    n = ps.normalize_rows(rows, {"god-class": "complexity"}, "report", 3, "", 10)
    assert [(r["path"], r["category"]) for r in n["rows"]] == [("a.py", "hotspot"), ("b.py", "complexity")]
    assert n["dropped"] == 2 and n["dropped_unknown_category"] == 2 and n["unknown_categories"] == ["(空)", "alien"]
    assert all(r["source"] == "report" and r["age_days"] == 3 for r in n["rows"])
    n2 = ps.normalize_rows(rows[:2], {}, "cmd", 0, "", 10)
    assert [r["path"] for r in n2["rows"]] == ["a.py"] and n2["unknown_categories"] == ["god-class"], "沒映射就丟"


def test_main_sentinel_and_json(tmp_path, capsys):
    root = _project(tmp_path, _hub(), "fresh.json")
    rc = ps.main(["--cwd", str(root), "--part", "排程器", "--json", "--top-n", "2"])
    out = capsys.readouterr().out.rstrip("\n").splitlines()
    assert rc == 0 and out[-1] == "PROJECT_SMELLS DONE n=2"
    data = json.loads("\n".join(out[:-1]))
    assert len(data["rows"]) == 2 and set(data["rows"][0]) == {"rank", "path", "category", "reason", "source", "age_days"}
    rc2 = ps.main(["--cwd", str(root), "--part", "排程器"])
    text = capsys.readouterr().out.rstrip("\n").splitlines()
    assert rc2 == 0 and text[-1] == "PROJECT_SMELLS DONE n=5" and text[0].startswith("part=")


@pytest.mark.skipif(os.name != "nt", reason="CommandLineToArgvW 只在 Windows")
def test_split_cmd_windows_quoted_path_with_space():
    """退回修正（BLOCK 4）：Windows 引號可在 token 中段（--root="C:\\Work Space\\src" 一個 token）、引號去掉、不認單引號。"""
    assert ps._split_windows(r'python gen_smells.py --root="C:\Work Space\src" --json') == \
        ["python", "gen_smells.py", r"--root=C:\Work Space\src", "--json"]
    assert ps._split_windows('"C:\\Program Files\\Py\\python.exe" gen.py  --x="a b"') == \
        [r"C:\Program Files\Py\python.exe", "gen.py", "--x=a b"]
    assert ps._split_windows("") == [] and ps._split_windows("   ") == []
    assert ps._split_windows(r'python x.py --root="C:\Work Space') == ["python", "x.py", r"--root=C:\Work Space"], "沒關的引號吃到結尾，與 shell 同"
    assert ps._split_cmd(["python", "a b.py"]) == ["python", "a b.py"], "陣列原樣不切"
    assert ps._split_cmd(r'python gen_smells.py --root="C:\Work Space\src" --json')[2] == r"--root=C:\Work Space\src"


@pytest.mark.skipif(os.name != "nt", reason="CommandLineToArgvW 只在 Windows")
def test_split_cmd_windows_escaped_quote_keeps_tokens():
    """退回修正第二輪（BLOCK 1）：`a\\" --json b\\"` 要切成 5 個 token、--json 獨立（自家狀態機曾吞成一個 token）。"""
    got = ps._split_windows(r'python x.py a\" --json b\"')
    assert got == ["python", "x.py", 'a"', "--json", 'b"'], got
    assert len(got) == 5 and "--json" in got
    assert ps._split_windows('python x.py "" tail') == ["python", "x.py", "", "tail"], "空引號保留空 token"
    assert ps._split_windows('python x.py a"b c"d') == ["python", "x.py", "ab cd"], "token 中段引號合併"


@pytest.mark.skipif(os.name != "nt", reason="CommandLineToArgvW 只在 Windows")
def test_split_cmd_windows_leading_whitespace():
    """退回修正第三輪（BLOCK 1）：前導空白不得產生空 argv[0]（API 官方行為），尾空白、tab 同。"""
    assert ps._split_windows("  python x.py") == ["python", "x.py"]
    assert ps._split_windows("\t python x.py \t") == ["python", "x.py"]
    assert ps._split_cmd("   python gen.py --json") == ["python", "gen.py", "--json"]
    got = ps._split_windows("   ")
    assert got == [] and all(t != "" for t in ps._split_windows(" x"))

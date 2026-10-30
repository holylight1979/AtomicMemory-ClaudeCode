"""verify_turn_judgment_threshold.py：拐彎判斷只在超線時才提醒（hooks/wg_reading_path._collect 與 handlers/post_tool_batch 的提醒行；
開關 reading_path.remind_only_over_threshold，預設開）。

做什麼：背景量完的一批沒有任何條目到門檻（含只剩「量不出來」「還沒 git add」這種一句原因）→ 什麼都不送：早起的結果不存
      EARLY_NOTE、Stop 不附、PostToolBatch 沒有 TURN_JUDGMENT_REQUIRED 那行；guard-reading_path 記 event=under_threshold、原文印 stderr。
      有條目到門檻 → 結果文字照附（條目＋那一題），下一批工具回應附一行提醒、最多列 3 條名字；混合（同一批有超線有沒超線）
      只有超線的進欠項與提醒行。v6 關：PostToolBatch 一字不送、工作不收（照舊）。
每一案拿改動前的 main（35dde89f）回放：前三案紅（舊碼只要結果文字非空就送、提醒行列 4 條）、v6 關那案綠（回歸守門）。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_turn_judgment_threshold.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_reading_path as rph  # noqa: E402
from handlers import post_tool_batch as ptb  # noqa: E402

_SID = "sid-tj-threshold"
_V6 = {"v6": {"enabled": True}, "reconcile_gate": {"enabled": False},
       "sync_reminder": {"enabled": False}, "deferral_gate": {"enabled": False}, "atom_audit": {"enabled": False},
       "aec": {"scan_report_gate": False}, "pick_one": {"enabled": False}}
HEAD = "[Guardian:ReadingPath] 第 5 回合改動對閱讀路徑的影響（背景量完；尺不是判決，只量不擋）："
QUIET_TEXT = HEAD + "\n  還沒 git add 的新檔 1 個不在掃描母體（--scope git），沒量到"
_BODY = "def {0}(n):\n    k = n + 1\n    k *= 2\n    return k\n"
APP = {"app.py": "from x import a\nfrom y import b\n\n\ndef main():\n    n = a(1)\n    n += b(2)\n    return n\n",
       "x.py": _BODY.format("a"), "y.py": _BODY.format("b")}
NESTED_B = """def b(n):
    if n:
        for x in range(n):
            if x:
                while x:
                    x -= 1
    if n:
        if n > 1:
            n += 1
    return n
"""


def _item(name: str) -> dict:
    return {"kind": "函式", "name": name, "keys": [name], "nums": "巢狀 4｜條件塊 2", "fp": f"fp-{name}"}


def _mf(path, turn=5, seq=10):
    return {"path": str(path), "tool": "Edit", "session_id": _SID, "turn_seq": turn, "last_turn_seq": turn, "last_seq": seq}


def _state(code: Path, **extra) -> dict:
    return {"modified_files": [_mf(code)], "turn_seq": 5, "turn_prompts_seq": 5, **extra}


def _finished(state: dict, config: dict, res: dict) -> dict:
    """改完那批交背景量（early_start，背景行程換成不起）、背景交了結果檔：回 rec（下一次 early_start 或收尾會收）。"""
    assert rph.early_start(state, _SID, config) is True and state["reading_path"][_SID].get("job"), "改完程式那批要交背景量"
    rec = state["reading_path"][_SID]
    rph.write_result(Path(rec["job"]["out"]), {"turn_judgment": rph.TURN_JUDGMENT_DEFAULTS, **res})
    return rec


def _batch(state: dict, calls: list, config: dict, capsys, monkeypatch) -> str:
    monkeypatch.setattr(ptb, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(ptb, "_ensure_state", lambda *a, **k: state)
    with pytest.raises(SystemExit):
        ptb.handle_post_tool_batch({"session_id": _SID, "tool_calls": calls}, config)
    out = capsys.readouterr().out.strip()
    return json.loads(out.splitlines()[-1])["hookSpecificOutput"]["additionalContext"] if out else ""


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.delenv("WG_V6", raising=False)
    monkeypatch.setattr(rph, "JOB_DIR", tmp_path / "rp-jobs")
    monkeypatch.setattr(rph, "_spawn_worker", lambda path: None)


@pytest.fixture
def logs(monkeypatch):
    out: list = []
    monkeypatch.setattr(rph, "append_guard_log", lambda guard, payload: out.append((guard, payload)))
    return out


def _code(tmp_path: Path) -> Path:
    code = tmp_path / "proj" / "cli.py"
    code.parent.mkdir(parents=True)
    code.write_text("x = 1\n", encoding="utf-8")
    return code


def test_under_threshold_sends_nothing_only_log(tmp_path, capsys, logs, monkeypatch):
    """沒有條目到門檻（結果文字只剩一句「還沒 git add」）→ 早起的結果不存、Stop 不附、下一批沒有提醒行；留帳 under_threshold、原文在 stderr。"""
    code = _code(tmp_path)
    state = _state(code)
    _finished(state, _V6, {"text": QUIET_TEXT, "judgment": []})
    assert rph.early_start(state, _SID, _V6) is True, "交了結果 → 這批要收"
    rec = state["reading_path"][_SID]
    assert rph.EARLY_NOTE not in rec and "owed" not in rec and not rec.get("job"), rec
    under = [p for g, p in logs if g == "reading_path" and p.get("event") == "under_threshold"]
    assert under and under[0]["job_turn"] == 5 and under[0]["items"] == 0, logs
    assert "還沒 git add 的新檔 1 個" in capsys.readouterr().err
    ctx = _batch(state, [{"tool_name": "Read", "tool_input": {}}], _V6, capsys, monkeypatch)
    assert "TURN_JUDGMENT_REQUIRED" not in ctx and "ReadingPath" not in ctx, ctx
    fresh = _state(code)                                              # 另一個 session 同樣沒超線：Stop 那條路也不送
    rec2 = _finished(fresh, _V6, {"text": QUIET_TEXT, "judgment": []})
    note, _ = rph.reading_path_note(fresh, _SID, _V6, spawn=lambda p: None)
    assert note is None and "owed" not in rec2 and not rec2.get("job"), (note, rec2)


def test_over_threshold_sends_one_line_with_items(tmp_path, capsys, logs, monkeypatch):
    """有條目到門檻 → 結果文字照附（條目＋那一題）；下一批工具回應附一行 TURN_JUDGMENT_REQUIRED 提醒，最多列 3 條名字。"""
    code = _code(tmp_path)
    state = _state(code)
    names = [f"cli.py::f{i}" for i in range(4)]
    _finished(state, _V6, {"text": HEAD, "judgment": [_item(n) for n in names]})
    assert rph.early_start(state, _SID, _V6) is True
    rec = state["reading_path"][_SID]
    note = rec.get(rph.EARLY_NOTE) or ""
    assert note.startswith(HEAD) and "要人看的 4 條" in note and rph.JUDGMENT_QUESTION in note, note
    assert [it["name"] for it in rec["owed"]["items"]] == names
    assert not [p for g, p in logs if p.get("event") == "under_threshold"]
    ctx = _batch(state, [{"tool_name": "Read", "tool_input": {}}], _V6, capsys, monkeypatch)
    line = next((ln for ln in ctx.splitlines() if "TURN_JUDGMENT_REQUIRED" in ln), "")
    assert line.startswith("[Guardian:提醒] TURN_JUDGMENT_REQUIRED：背景量完，4 條到門檻：") and "cli.py::f2" in line, ctx
    assert "cli.py::f3" not in line and "另 1 條" in line, "一行最多列 3 條，其餘報個數"


def test_mixed_only_over_items_listed(tmp_path, capsys, logs, monkeypatch):
    """同一批有超線（y.py::b 巢狀 4）也有沒超線（x.py::a）→ 只有超線的進欠項、提醒行只列它；沒超線那條只在數據表當對照。"""
    root = tmp_path / "r"
    for rel, text in APP.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8", newline="\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([*git, "add", "-A"], check=True, capture_output=True)
    subprocess.run([*git, "commit", "-q", "-m", "init"], check=True, capture_output=True)
    (root / "y.py").write_text(NESTED_B, encoding="utf-8", newline="\n")
    (root / "x.py").write_text(_BODY.format("a").replace("k *= 2", "k *= 3"), encoding="utf-8", newline="\n")
    state = {"modified_files": [_mf(root / "y.py"), _mf(root / "x.py", seq=11)], "turn_seq": 5, "turn_prompts_seq": 5}

    def inline(path):
        job = json.loads(Path(path).read_text(encoding="utf-8"))
        rph.write_result(Path(job["out"]), rph.run_job(job))

    first, _ = rph.reading_path_note(state, _SID, _V6, spawn=inline)
    assert first is None and state["reading_path"][_SID].get("job")
    second, _ = rph.reading_path_note(state, _SID, _V6, spawn=inline)
    assert second and "y.py::b｜巢狀 4" in second and "← 要人看" in second, second
    assert "x.py::a｜巢狀 0" in second and second.count("← 要人看") == 1, "沒超線的那條只當對照，不標要人看"
    assert [it["name"] for it in state["reading_path"][_SID]["owed"]["items"]] == ["y.py::b"]
    assert not [p for g, p in logs if p.get("event") == "under_threshold"]
    ctx = _batch(state, [{"tool_name": "Read", "tool_input": {}}], _V6, capsys, monkeypatch)
    line = next((ln for ln in ctx.splitlines() if "TURN_JUDGMENT_REQUIRED" in ln), "")
    assert "1 條到門檻：y.py::b" in line and "x.py::a" not in line, ctx


def test_v6_off_unchanged(tmp_path, capsys, logs, monkeypatch):
    """v6 關：PostToolBatch 不收結果、不送任何字（超線沒超線都一樣），工作照留給誰都不動——跟改前一字不差。"""
    code = _code(tmp_path)
    for res in ({"text": QUIET_TEXT, "judgment": []}, {"text": HEAD, "judgment": [_item("cli.py::f")]}):
        state = _state(code)
        rec = _finished(state, _V6, res)
        ctx = _batch(state, [{"tool_name": "Read", "tool_input": {}}], {**_V6, "v6": {"enabled": False}}, capsys, monkeypatch)
        assert ctx == "" and rec.get("job") and Path(rec["job"]["out"]).is_file(), (ctx, rec)
        assert rph.EARLY_NOTE not in rec and "owed" not in rec, rec
    assert not [p for g, p in logs if g == "reading_path"], logs

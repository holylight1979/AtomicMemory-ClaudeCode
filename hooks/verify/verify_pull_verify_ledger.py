"""verify_pull_verify_ledger.py：驗證帳本與規則表的連鎖改形狀（會紅案例：退回改前的碼看紅、改後綠）。

守的是「修了又欠、連續修不停」的幾條：
  (d) CASE_COVERS_CHANGE：改程式 P → 改覆蓋 P 的案例 → 案例紅 → 回頭修 P → 跑綠 → 不欠（不比先後）；沒有案例覆蓋的 Q 照欠。
  CARRIED_CLAIM_ANY_TURN_RECEIPT：承接到新回合的「修好」與新說的同一個判法，認前一回合晚於最後改動、之後沒再改程式的綠收據，不要求重跑。
  RECEIPT_UNPARSED_GENERAL_ONLY：量尺前面多一段指令照認量尺；解析不了的收據不算量尺、照算一般證據、不擋、留一筆帳。
  CONFLICT_DECLARED_BY_AI：衝突宣告多寫一張不在候選裡的卡不判錯。
  流程級：被別的閘逼出的改碼 → 跑綠一次 → 收尾，(d) 不因這次改動重欠。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_pull_verify_ledger.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_release_rules as rr  # noqa: E402
import wg_verify_ledger as vl  # noqa: E402

SID = "sid-pvl"
T1, T2, T3 = "2026-10-22T10:00:00+08:00", "2026-10-22T10:05:00+08:00", "2026-10-22T10:10:00+08:00"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("WG_TEMP_RULES", "off")                    # 假專案在 pytest tmp（系統暫存目錄）底下


def _mf(path, turn, at, seq):
    return {"path": str(path), "tool": "Edit", "session_id": SID, "turn_seq": turn, "last_turn_seq": turn,
            "last_at": at, "last_seq": seq}


def _rcpt(root, cmd, turn, at, seq, verdict="PASS"):
    return {"turn_seq": turn, "tool": "Bash", "cmd": cmd, "sentinels": [{"name": "PYTEST", "verdict": verdict, "kv": {}}],
            "exit_code": 0 if verdict == "PASS" else 1, "at": at, "seq": seq, "project_root": str(root), "cwd": str(root),
            "env": {}}


def _reconcile(root, text, mods, receipts, turn=5, **kw):
    reason, _report = vl.reconcile_gate_parts(text, receipts, turn, ["Bash"], mods, vl.reconcile_cfg({}),
                                              root=lambda p: str(root), exec_this_turn=True, **kw)
    return reason or ""


def _put(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    return p


# ─── (d) CASE_COVERS_CHANGE ─────────────────────────────────────────────

def test_case_red_then_fix_code_then_green_not_owed_uncovered_code_owed(tmp_path):
    """改程式 P → 改覆蓋 P 的案例 T（內容 import P；檔名不照 P 取）→ T 紅 → 修 P → 跑整個資料夾綠 → (d) 不欠。
    舊碼：P 比 T 新就欠，綠收據沒點名 T（跑的是資料夾）清不掉 → 紅。反例：同一回合也改了 Q，沒有案例提到它 → 照欠。"""
    p = _put(tmp_path, "src/pkgcalc.py", "def f():\n    return 2\n")
    t = _put(tmp_path, "tests/test_suite.py", "from pkgcalc import f\n\ndef test_f():\n    assert f() == 2\n")
    q = _put(tmp_path, "src/other_mod.py", "X = 1\n")
    red = _rcpt(tmp_path, "python -m pytest -q tests", 5, T2, 3, "FAIL")
    green = _rcpt(tmp_path, "python -m pytest -q tests", 5, T3, 6)
    mods = [_mf(p, 5, T1, 1), _mf(t, 5, T2, 2), _mf(p, 5, T3, 5)]
    out = _reconcile(tmp_path, "全部完成。", mods[1:], [red, green])
    assert "(d)" not in out, out
    out = _reconcile(tmp_path, "全部完成。", mods[1:] + [_mf(q, 5, T3, 4)], [red, green])
    assert "(d) CASE_COVERS_CHANGE" in out and "other_mod.py" in out and "pkgcalc.py" not in out.split("證據")[0], out


def _repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True, capture_output=True)
    return root


# ─── CARRIED_CLAIM_ANY_TURN_RECEIPT ──────────────────────────────────────

def test_carried_fixed_claim_accepts_green_from_earlier_turn_after_last_edit(tmp_path):
    """回合 4 改了 widget.py、跑綠、說修好 → 擋滿留待放行；回合 6 碼沒動，承接的宣稱認回合 4 那筆晚於最後改動的綠收據。
    舊碼只認本回合收據 → (a) 照擋、逼重跑 → 紅。配對：那筆綠收據早於最後一次改動 → 照擋。"""
    code = _put(tmp_path, "src/widget.py", "W = 1\n")
    case = _put(tmp_path, "tests/test_widget.py", "from widget import W\n")
    mods = [_mf(code, 4, T1, 1), _mf(case, 4, T1, 2)]
    green = _rcpt(tmp_path, "python -m pytest -q tests/test_widget.py", 4, T2, 3)
    claims = ["widget.py 修好了，完成。"]
    out = _reconcile(tmp_path, "放行了嗎？", mods, [green], turn=6, claims=claims, pending=True, user_turn=6)
    assert "CLAIM_FIXED_NEEDS_PASS" not in out, out
    early = _rcpt(tmp_path, "python -m pytest -q tests/test_widget.py", 4, "2026-10-22T09:00:00+08:00", 0)
    out = _reconcile(tmp_path, "放行了嗎？", mods, [early], turn=6, claims=claims, pending=True, user_turn=6)
    assert "CLAIM_FIXED_NEEDS_PASS" in out, out


def test_fresh_fixed_claim_also_accepts_earlier_green_when_code_untouched(tmp_path):
    """承接的宣稱之外，本回合自己又說「修好了」→ 同一個判法：前一回合晚於最後改動的綠收據照認（碼沒動）。
    配對：綠收據之後又改了 widget.py → 擋，訊息點名 widget.py 要重跑。"""
    code = _put(tmp_path, "src/widget.py", "W = 1\n")
    case = _put(tmp_path, "tests/test_widget.py", "from widget import W\n")
    mods = [_mf(code, 4, T1, 1), _mf(case, 4, T1, 2)]
    green = _rcpt(tmp_path, "python -m pytest -q tests/test_widget.py", 4, T2, 3)
    out = _reconcile(tmp_path, "widget.py 修好了，完成。", mods, [green], turn=6, claims=["widget.py 修好了，完成。"],
                     pending=True, user_turn=6)
    assert "CLAIM_FIXED_NEEDS_PASS" not in out, out
    again = [{**_mf(code, 4, T3, 4), "last_turn_seq": 6}, mods[1]]
    out = _reconcile(tmp_path, "widget.py 修好了，完成。", again, [green], turn=6, pending=True, user_turn=6)
    assert "CLAIM_FIXED_NEEDS_PASS" in out and "之後又改了 widget.py，要重跑" in out, out


# ─── RECEIPT_UNPARSED_GENERAL_ONLY ───────────────────────────────────────

def test_ruler_with_unrelated_prefix_counts_and_unparsed_receipt_is_logged_not_blocked(tmp_path, monkeypatch):
    """量尺前面多一段無關指令、跑的是對的那支、exit 0 → 認量尺、(a) 不擋（舊碼：前面只准 cd／環境設定 → 擋 → 紅）。
    解析不了的收據（$( )）不算量尺、照算一般證據（指令提到改檔）→ 不擋，留一筆 receipt_unparsed 帳（舊碼不留帳 → 紅）。"""
    logs = []
    monkeypatch.setattr(vl, "append_guard_log", lambda g, p: logs.append((g, p)), raising=False)
    code = _put(tmp_path, "src/gauge.py", "G = 1\n")
    case = _put(tmp_path, "tests/test_gauge.py", "import gauge\n")
    mods = [_mf(code, 5, T1, 1), _mf(case, 5, T1, 2)]
    ruler = "python -X utf8 run_verify.py"
    prefixed = _rcpt(tmp_path, f"echo start; {ruler}", 5, T2, 3)
    out = _reconcile(tmp_path, "gauge.py 修好了，完成。", mods, [prefixed], measure_cmds=[ruler], sid=SID)
    assert "CLAIM_FIXED_NEEDS_PASS" not in out, out
    unparsed = _rcpt(tmp_path, "X=$(date) && python -m pytest -q tests/test_gauge.py", 5, T2, 3)
    out = _reconcile(tmp_path, "gauge.py 修好了，完成。", mods, [unparsed], measure_cmds=[ruler], sid=SID)
    assert "CLAIM_FIXED_NEEDS_PASS" not in out, out
    assert [p["event"] for g, p in logs if g == "reconcile"] == ["receipt_unparsed"], logs
    assert not vl._ruler_ran(ruler, {**unparsed, "cmd": f"X=$(date) && {ruler}"})


# ─── CONFLICT_DECLARED_BY_AI ─────────────────────────────────────────────

def test_conflict_declaration_extra_card_not_an_error():
    """衝突宣告多寫一張不在候選裡的卡 → 不判錯，收下候選那條。舊碼：不在候選也算錯 → 整份退回 → 紅。"""
    v, got = rr.conflict_declaration_verdict(["a"], [{"of": "a", "verdict": "not_conflict", "why": "範圍不同"},
                                                     {"of": "zzz", "verdict": "conflict", "why": "多看了一張"}])
    assert not v.owed and [d["of"] for d in got] == ["a"], v


# ─── 流程級 ──────────────────────────────────────────────────────────────

def test_gate_forced_code_edit_then_one_green_run_owes_nothing_again(tmp_path):
    """回合 5：改程式＋寫覆蓋它的案例、收尾宣告完成。回合 6：別的閘（病形閘）逼出一次改碼 → 跑綠一次 → 收尾：
    (d) 不因這次改動重欠（不比先後）。舊碼重欠 → 紅。"""
    root = _repo(tmp_path)
    code = [_put(root, f"src/core{i}.py", "c = 1\n") for i in range(4)]
    case = _put(root, "tests/test_all.py", "".join(f"import core{i}\n" for i in range(4)))
    mods = [_mf(c, 5, T1, i) for i, c in enumerate(code)] + [_mf(case, 5, T1, 9)]
    mods[0] = _mf(code[0], 6, T2, 20)                                  # 閘逼出的改碼
    green = _rcpt(root, "python -m pytest -q tests", 6, T3, 21)
    assert "(d)" not in _reconcile(root, "壓平了，全部完成。", mods, [green], turn=6, user_turn=6)

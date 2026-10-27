"""verify_inject_lean.py — 寫碼回合的記憶注入只送該到的：trigger 命中給整段，其餘一行，已整段送過的只指回。

怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_inject_lean.py
守住（v6 開、這則判成寫碼意圖才生效；v6 關或不是寫碼意圖照舊）：
1. CODING_TURN_FULL_ONLY_ON_TRIGGER：bm25／vector／related 命中的卡就算 hot（7 天內讀過 ≥3 次）也只給一行；trigger 命中的照樣整段。
2. POINTER_NO_NAME_ECHO：一行指標的摘要／標題只是卡名再寫一次時不重印（cold 行、budget skip 路標都是）。
3. NO_RESEND_AFTER_RESUME：本 session 最近一次壓縮之後整段送過的卡，resume 清空 injected_atoms 後再命中只給一行指回；
   壓縮之後、或之前只送過一行的，照常整段送。指回那行記 form＝seen，取用端稽核（AtomAudit）不追問。
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402
from handlers import ups_inject  # noqa: E402

TRIGGER_CARD = "verify-trigger-card"
BM25_CARD = "verify-bm25-card"


def _mk(mem: Path, name: str, title: str = "", impression: str = "", hot: bool = False) -> Path:
    body = f"# {title or name}\n\n- Confidence: [臨]\n- Trigger: x\n\n"
    if impression:
        body += f"## 印象\n\n- {impression}\n\n"
    body += "## 知識\n\n- [臨] 這張卡的內文：改程式前先跑既有測試確認基底是綠的。\n\n## 行動\n\n- 先跑測試再改\n"
    p = mem / f"{name}.md"
    p.write_text(body, encoding="utf-8")
    if hot:
        now = time.time()
        (mem / f"{name}.access.json").write_text(json.dumps({"timestamps": [now - 3600 * k for k in (1, 2, 3, 4)]}),
                                                 encoding="utf-8")
    return p


def _entry(name: str, root: Path):
    return ((name, f"memory/{name}.md", ["x"]), root)


def _run(root: Path, state: dict, names, sources, all_atoms=None):
    lines: list = []
    matched = [_entry(n, root) for n in names]
    ups_inject.assemble_injection("sid", state, {}, matched, all_atoms or [], list(state.get("injected_atoms") or []),
                                  dict(zip(names, sources)), {}, lines)
    forms = {r["name"]: r["form"] for r in state.get("injection_log") or [] if r["turn_seq"] == state.get("turn_seq", 0) + 1}
    return lines, forms


def _block(lines, name):
    return next((ln for ln in lines if ln.startswith(f"[Atom:{name}]")), "")


@pytest.fixture
def mem(tmp_path):
    m = tmp_path / "memory"
    m.mkdir()
    return m


@pytest.fixture
def v6_on(monkeypatch):
    monkeypatch.setenv("WG_V6", "1")


def _coding_state(**extra):
    return {"turn_seq": 0, "turn_intent": "feature", **extra}


# ─── 1. CODING_TURN_FULL_ONLY_ON_TRIGGER ─────────────────────────────────────

def test_coding_turn_full_only_on_trigger(mem, v6_on):
    """寫碼回合：hot 的 bm25 卡只給一行（main 給整段 → 紅）；trigger 卡照樣整段。"""
    _mk(mem, TRIGGER_CARD, hot=True)
    _mk(mem, BM25_CARD, hot=True)
    lines, forms = _run(mem.parent, _coding_state(), [TRIGGER_CARD, BM25_CARD], ["trigger", "bm25"])
    assert forms == {TRIGGER_CARD: "ok", BM25_CARD: "cold"}
    assert "## 知識" in _block(lines, TRIGGER_CARD)
    bm = _block(lines, BM25_CARD)
    assert "\n" not in bm and "(full: Read " in bm and "## 知識" not in bm


def test_coding_turn_related_spread_one_line(mem, v6_on):
    """Related 擴散的鄰居就算 hot 也只給一行（main 給整段 → 紅）。"""
    trig = _mk(mem, TRIGGER_CARD)
    trig.write_text(trig.read_text(encoding="utf-8") + "\n- Related: neighbour\n", encoding="utf-8")
    _mk(mem, "neighbour", hot=True)
    all_atoms = [_entry(TRIGGER_CARD, mem.parent), _entry("neighbour", mem.parent)]
    state = _coding_state()
    lines: list = []
    ups_inject.assemble_injection("sid", state, {"injection": {"related_gate": {"enabled": False}}},
                                  [all_atoms[0]], all_atoms, [], {TRIGGER_CARD: "trigger"}, {}, lines)
    forms = {r["name"]: r["form"] for r in state["injection_log"]}
    assert forms.get("neighbour") == "cold", forms
    assert _block(lines, "neighbour").startswith("[Atom:neighbour] (related, cold)")


def test_trigger_card_full_text_same_as_before(mem, v6_on, monkeypatch):
    """該想起的要完整送到：trigger 命中的卡，寫碼回合送的整段跟 v6 關時一字不差。"""
    _mk(mem, TRIGGER_CARD, impression="先跑既有測試")
    lean_lines, _ = _run(mem.parent, _coding_state(), [TRIGGER_CARD], ["trigger"])
    monkeypatch.setenv("WG_V6", "0")
    old_lines, _ = _run(mem.parent, _coding_state(), [TRIGGER_CARD], ["trigger"])
    assert _block(lean_lines, TRIGGER_CARD) == _block(old_lines, TRIGGER_CARD)
    assert "## 知識" in _block(lean_lines, TRIGGER_CARD)


@pytest.mark.parametrize("env,intent", [("0", "feature"), ("1", "general"), ("1", None)])
def test_off_or_not_coding_keeps_hot_full(mem, monkeypatch, env, intent):
    """v6 關、或這則不是寫碼意圖：hot 的 bm25 卡照舊給整段，一行指標照舊重印標題。"""
    monkeypatch.setenv("WG_V6", env)
    _mk(mem, BM25_CARD, hot=True)
    _mk(mem, "cold-card")
    state = {"turn_seq": 0, **({"turn_intent": intent} if intent else {})}
    lines, forms = _run(mem.parent, state, [BM25_CARD, "cold-card"], ["bm25", "bm25"])
    assert forms == {BM25_CARD: "ok", "cold-card": "cold"}
    assert _block(lines, "cold-card").startswith("[Atom:cold-card] (cold) cold-card (full: Read ")


# ─── 2. POINTER_NO_NAME_ECHO ────────────────────────────────────────────────

@pytest.mark.parametrize("title,name,echo", [
    ("交付對照的達成要有改完之後真的跑過的證據，只讀過程式就標部分", "交付對照的達成要有改完之後真的跑過的證據只讀過程式就標部分", True),
    ("Windows 新機 PATH 的 WindowsApps python.exe 是 Store 佔位程式-零輸…", "windows-新機-path-的-windowsapps-pythonexe-是-store-佔位程式-零輸出-exit", True),
    ("preferences", "preferences", True),
    ("先跑既有測試確認基底是綠的", "feedback-改程式前先跑測試", False),     # 印象行跟卡名不同 → 留著
    ("cli 子命令手切-加第三個再改查表", "cli", False),                        # 標題比卡名多資訊 → 留著
    ("", "x", False),
])
def test_title_echoes_name(title, name, echo):
    assert wg_atoms.title_echoes_name(title, name) is echo


def test_cold_line_drops_name_echo(mem, v6_on):
    """寫碼回合的 cold 行：摘要只是卡名再寫一次 → 只留卡名＋路徑；摘要是印象行（跟卡名不同）→ 留著。"""
    _mk(mem, "echo-card", title="echo card")
    _mk(mem, "impression-card", impression="改程式前先跑測試")
    lines, _ = _run(mem.parent, _coding_state(), ["echo-card", "impression-card"], ["bm25", "bm25"])
    assert _block(lines, "echo-card") == f"[Atom:echo-card] (cold) (full: Read {(mem / 'echo-card.md').as_posix()})"
    assert "(cold) 改程式前先跑測試 (full: Read " in _block(lines, "impression-card")


def test_skip_pointer_drops_name_echo(mem, v6_on):
    """budget 塞不下退成路標時，標題只是卡名再寫一次也不重印。"""
    name = "longone" + "t" * 73                    # 80 字：路標標題截到 80 字後正好是卡名
    (mem / "filler.md").write_text("# filler\n\n- [臨] " + ("word " * 800), encoding="utf-8")   # 約 1,000 tok：剩的塞不下全文、塞得下路標
    (mem / f"{name}.md").write_text("# " + name + "T" * 2920, encoding="utf-8")   # 只有標題：節錄＝全文 → skip
    lines, forms = _run(mem.parent, _coding_state(), ["filler", name], ["trigger", "trigger"])
    assert forms[name] == "skip"
    assert _block(lines, name) == f"[Atom:{name}] (full: Read {(mem / f'{name}.md').as_posix()})"


# ─── 3. NO_RESEND_AFTER_RESUME ──────────────────────────────────────────────

def _sent_before(name: str, root: Path, at: float, form: str = "ok", source: str = "trigger") -> dict:
    return {"name": name, "path": str(root / "memory" / f"{name}.md"), "rel": f"memory/{name}.md", "source": source,
            "form": form, "form_final": form, "scope": "", "turn_seq": 1, "at": at}


def test_resume_does_not_resend_full_card(mem, v6_on):
    """resume 清空 injected_atoms 後同一張卡再被 trigger 命中：只給一行指回（main 再送整段 → 紅）。"""
    _mk(mem, TRIGGER_CARD)
    state = _coding_state(turn_seq=3, injected_atoms=[],
                          injection_log=[_sent_before(TRIGGER_CARD, mem.parent, time.time() - 600)])
    lines, forms = _run(mem.parent, state, [TRIGGER_CARD], ["trigger"])
    assert forms == {TRIGGER_CARD: "seen"}
    assert _block(lines, TRIGGER_CARD) == (
        f"[Atom:{TRIGGER_CARD}] (前面已整段送過) (full: Read {(mem / f'{TRIGGER_CARD}.md').as_posix()})")


def test_resend_after_compact_or_pointer_only(mem, v6_on):
    """壓縮之後原文不在 context → 照常整段；之前只送過一行（cold）、或紀錄沒時間又有壓縮 → 照常整段。"""
    _mk(mem, TRIGGER_CARD)
    t0 = time.time() - 600
    compact_at = datetime.fromtimestamp(t0 + 60, timezone.utc).astimezone().isoformat(timespec="seconds")
    no_at = dict(_sent_before(TRIGGER_CARD, mem.parent, t0))
    no_at.pop("at")
    for extra in ({"pre_compact_snapshot": compact_at, "injection_log": [_sent_before(TRIGGER_CARD, mem.parent, t0)]},
                  {"post_compact_at": compact_at, "injection_log": [no_at]},
                  {"injection_log": [_sent_before(TRIGGER_CARD, mem.parent, t0, form="cold")]}):
        lines, forms = _run(mem.parent, _coding_state(turn_seq=3, **extra), [TRIGGER_CARD], ["trigger"])
        assert forms == {TRIGGER_CARD: "ok"}, extra
        assert "## 知識" in _block(lines, TRIGGER_CARD)


def test_resume_round_trip_through_reconcile(mem, v6_on):
    """兩則 UPS 走真的組裝＋最終結算：第一則整段送出（form_final＝ok、帶送出時間），resume 清空 injected_atoms 後第二則只指回。"""
    _mk(mem, TRIGGER_CARD)
    state = _coding_state()
    lines, _ = _run(mem.parent, state, [TRIGGER_CARD], ["trigger"])
    ups_inject.reconcile_injection_after_trim("sid", state, {}, lines)
    first = state["injection_log"][0]
    assert first["form_final"] == "ok" and isinstance(first.get("at"), float)
    state["turn_seq"] = 1
    state["injected_atoms"] = []          # SessionStart(resume) 清掉
    lines2, forms2 = _run(mem.parent, state, [TRIGGER_CARD], ["trigger"])
    assert forms2 == {TRIGGER_CARD: "seen"} and "## 知識" not in "\n".join(lines2)


def test_seen_pointer_not_audited():
    """指回那行（form＝seen）不算「trigger 命中只給一行沒 Read」：AtomAudit 不追問。"""
    from handlers.stop import _audit_pointer_atom_consumption
    rec = {"name": TRIGGER_CARD, "path": "C:/m/x.md", "source": "trigger", "turn_seq": 1}
    assert _audit_pointer_atom_consumption({"turn_seq": 5, "injection_log": [{**rec, "form": "seen"}]}) is None
    assert _audit_pointer_atom_consumption({"turn_seq": 5, "injection_log": [{**rec, "form": "cold"}]}) is not None


def test_v6_off_records_unchanged(mem, monkeypatch):
    """v6 關：注入紀錄不加送出時間、同一張卡 resume 後照舊整段重送。"""
    monkeypatch.setenv("WG_V6", "0")
    _mk(mem, TRIGGER_CARD)
    state = _coding_state(turn_seq=3, injection_log=[_sent_before(TRIGGER_CARD, mem.parent, time.time() - 600)])
    lines, forms = _run(mem.parent, state, [TRIGGER_CARD], ["trigger"])
    assert forms == {TRIGGER_CARD: "ok"}
    assert "at" not in state["injection_log"][-1]

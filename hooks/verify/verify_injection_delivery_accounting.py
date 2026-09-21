"""verify_injection_delivery_accounting.py — 注入記帳以「最終送達」為準（2026-09-21 全面檢視 Phase 1b R1）。

守住：
1. atom 段 1,200 tok 是真硬頂：cold 行、skip 路標、標頭全部計費；塞不下的記 form=dropped、不送、不進 newly_injected。
2. _truncate_context_by_activation 以「lines 的一個元素＝一個區塊」切塊：尾端 Guardian 訊息不會跟著最後一顆 atom 被裁掉。
3. reconcile_injection_after_trim：被最終裁切整塊丟掉的 atom → form_final=dropped_trim、從 injected_atoms 撤掉、
   rescue watch 撤掉它的 token、不計曝光；降成指標的 → pointer_trim 仍算送達；回傳的名單只含實際送出者。
4. skip 路標標題最多 80 字。
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402
from handlers import ups_inject  # noqa: E402
from lib import atom_access as A  # noqa: E402


def _entry(name: str, root: Path, triggers=("x",)):
    return ((name, f"memory/{name}.md", list(triggers)), root)


def _mk(mem: Path, name: str, body: str) -> Path:
    p = mem / f"{name}.md"
    p.write_text(body, encoding="utf-8")
    return p


def _atom_segment_tokens(lines) -> int:
    return sum(wg_atoms._estimate_tokens(ln) for ln in lines if ln.startswith("[Atom:"))


# ─── 1. 硬頂：全部計費、塞不下就 dropped ─────────────────────────────────────


def test_hard_cap_counts_every_atom_line(tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir()
    names = []
    for i in range(12):  # 每顆約 500 tok（2000 ASCII 字），12 顆遠超 1200
        n = f"big{i}"
        _mk(mem, n, f"# {n}\n\n- [臨] " + ("word " * 400))
        names.append(n)
    matched = [_entry(n, tmp_path) for n in names]
    src = {n: "trigger" for n in names}
    state: dict = {"turn_seq": 1}
    lines: list = []
    newly, _dirs = ups_inject.assemble_injection("sid", state, {}, matched, [], [], src, {}, lines)
    assert _atom_segment_tokens(lines) <= wg_atoms._TURN_BUDGET_LIMIT
    forms = {r["name"]: r["form"] for r in state["injection_log"]}
    # 送出的都在 newly；dropped 的不在 newly、也不在 injected_atoms
    for n, f in forms.items():
        if f == "dropped":
            assert n not in newly and n not in state["injected_atoms"]
        else:
            assert n in newly
    assert any(f == "ok" for f in forms.values())


def test_skip_pointer_title_capped(tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir()
    _mk(mem, "filler", "# filler\n\n- [臨] " + ("word " * 900))   # ~1125 tok 佔滿
    _mk(mem, "longtitle", "# " + ("T" * 3000))                      # 標題 3000 字，impression==full → skip
    matched = [_entry("filler", tmp_path), _entry("longtitle", tmp_path)]
    src = {"filler": "trigger", "longtitle": "trigger"}
    lines: list = []
    newly, _ = ups_inject.assemble_injection("sid", {"turn_seq": 1}, {}, matched, [], [], src, {}, lines)
    ptr = [ln for ln in lines if ln.startswith("[Atom:longtitle]")]
    assert ptr and "(full: Read" in ptr[0] and "longtitle" in newly
    assert len(ptr[0]) < 400  # 3000 字標題被截到 80 字以內


# ─── 2. 裁切切塊：尾端 Guardian 訊息不被裁 ───────────────────────────────────


def test_trim_does_not_swallow_trailing_guardian_line(tmp_path):
    big = "[Atom:x]\n" + ("word " * 800)
    guardian = "[Guardian:Test] 這行不是 atom，裁切後必須還在"
    out = wg_atoms._truncate_context_by_activation([big, guardian], limit=100, source_dirs={})
    assert any(ln == guardian for ln in out), out
    assert not any(ln.startswith("[Atom:x]\nword") for ln in out)  # 全文已被降級或移除


# ─── 3. reconcile：以最終 lines 為準 ─────────────────────────────────────────


def test_reconcile_drops_trimmed_atoms_from_accounting(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "_audit_log", lambda *a, **k: None)
    mem = tmp_path / "memory"
    mem.mkdir()
    keep = _mk(mem, "keep", "# keep\n\n- [臨] keeptoken alpha beta\n")
    gone = _mk(mem, "gone", "# gone\n\n- [臨] gonetoken gamma delta\n")
    state: dict = {"turn_seq": 3}
    lines: list = []
    matched = [_entry("keep", tmp_path), _entry("gone", tmp_path)]
    newly, _ = ups_inject.assemble_injection(
        "sid", state, {}, matched, [], [], {"keep": "trigger", "gone": "trigger"}, {}, lines)
    assert set(newly) == {"keep", "gone"}
    assert "_turn_inject_pending" in state
    # 模擬最終裁切：gone 整塊被移除、keep 降成指標
    final = [ln for ln in lines if not ln.startswith("[Atom:gone]")]
    final = [("[Atom:keep] (truncated) Read " + keep.as_posix()) if ln.startswith("[Atom:keep]") else ln
             for ln in final]
    final.append("[Context budget: 50/1000 tokens | trim: 1 pointer, 1 dropped]")
    delivered = ups_inject.reconcile_injection_after_trim("sid", state, {}, final)
    assert delivered == ["keep"]
    assert "_turn_inject_pending" not in state
    assert "gone" not in state["injected_atoms"] and "keep" in state["injected_atoms"]
    forms = {r["name"]: r["form_final"] for r in state["injection_log"]}
    assert forms == {"keep": "pointer_trim", "gone": "dropped_trim"}
    # rescue watch 只剩 keep 的 token
    owners = {v.split("\t", 1)[0] for v in (state.get("rescue_watch") or {}).values()}
    assert "gone" not in owners
    # 曝光只記送出者
    assert A.read_access(keep).get("read_hits", 0) == 1
    assert A.read_access(gone).get("read_hits", 0) == 0


def test_reconcile_without_pending_is_noop():
    assert ups_inject.reconcile_injection_after_trim("sid", {}, {}, ["[Guardian] x"]) == []

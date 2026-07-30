"""verify_atom_consumption_audit.py — 取用端閉環稽核（AtomAudit）+ Status 一行注入守衛

覆蓋驗收：
  A1: cold/skip 路標注入且未 Read → 稽核警示；有 Read → 不出現
  A2: 稽核輸入損毀（非 dict 條目）→ 不炸、跳過（gate 端另有 try/except fail-open）
  A3: per-atom prompted 不重複；gate 接線沿用 stop_gate_max_blocks（wiring 條件）
  B2: Status 行出現在 cold / budget-skip 一行注入輸出
  資料面: assemble_injection 落 state["injection_log"]（name/path/source/form/turn_seq）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from handlers.stop import _audit_pointer_atom_consumption, _normalize_read_path  # noqa: E402
from wg_atoms import atom_status_suffix, format_cold_inject_line  # noqa: E402


def _rec(name, form="skip", source="trigger", turn=1, path=None, rel=None):
    return {
        "name": name,
        "path": path or f"C:\\Users\\u\\.claude\\memory\\{name}.md",
        "rel": rel or f"memory/{name}.md",
        "source": source,
        "form": form,
        "turn_seq": turn,
    }


def _state(recs, accessed=None, turn_seq=3, prompted=None):
    return {
        "injection_log": recs,
        "accessed_files": [{"path": p, "at": "t"} for p in (accessed or [])],
        "turn_seq": turn_seq,
        "atom_audit_prompted": prompted or [],
    }


# ── A1：未 Read → 警示；已 Read → 無 ─────────────────────────────


def test_unread_skip_atom_fires():
    out = _audit_pointer_atom_consumption(_state([_rec("fat-atom")]))
    assert out is not None
    reason, names = out
    assert names == ["fat-atom"]
    assert "fat-atom" in reason
    assert "(a)" in reason and "(b)" in reason and "(c)" in reason


def test_unread_cold_atom_fires():
    out = _audit_pointer_atom_consumption(_state([_rec("c1", form="cold")]))
    assert out is not None


def test_read_atom_silent_exact_path():
    r = _rec("fat-atom")
    out = _audit_pointer_atom_consumption(_state([r], accessed=[r["path"]]))
    assert out is None


def test_read_atom_silent_suffix_match():
    # Read 用不同寫法的絕對路徑（正斜線/大小寫）仍算 consumed
    r = _rec("fat-atom")
    out = _audit_pointer_atom_consumption(
        _state([r], accessed=["c:/users/U/.CLAUDE/memory/FAT-ATOM.md"])
    )
    assert out is None


def test_full_injection_not_audited():
    out = _audit_pointer_atom_consumption(
        _state([_rec("a", form="ok"), _rec("b", form="fallback")])
    )
    assert out is None


def test_non_trigger_source_not_audited():
    out = _audit_pointer_atom_consumption(
        _state([_rec("v", source="vector"), _rec("r", source="related")])
    )
    assert out is None


def test_same_turn_injection_not_audited():
    # 本 turn 才注入——至少給一個完整 turn 決定要不要展開
    out = _audit_pointer_atom_consumption(_state([_rec("x", turn=3)], turn_seq=3))
    assert out is None


# ── A2：輸入損毀不炸 ────────────────────────────────────────────


def test_corrupt_log_entries_tolerated():
    st = _state([42, "junk", None, _rec("ok-one")])
    st["accessed_files"] = ["not-a-dict", {"path": None}]
    out = _audit_pointer_atom_consumption(st)
    assert out is not None and out[1] == ["ok-one"]


def test_empty_log_silent():
    assert _audit_pointer_atom_consumption(_state([])) is None
    assert _audit_pointer_atom_consumption({"injection_log": None}) is None


# ── A3：prompted 不重複 ─────────────────────────────────────────


def test_prompted_atom_not_renagged():
    out = _audit_pointer_atom_consumption(
        _state([_rec("fat-atom")], prompted=["fat-atom"])
    )
    assert out is None


def test_list_caps_at_three_but_marks_all():
    recs = [_rec(f"a{i}") for i in range(5)]
    reason, names = _audit_pointer_atom_consumption(_state(recs))
    assert len(names) == 5  # 全數標記（每 atom 一次）
    assert "另 2 顆" in reason


# ── B2：Status 行 ──────────────────────────────────────────────

_ATOM_WITH_STATUS = (
    "# fat-atom\n\n- Scope: global\n- Confidence: [觀]\n"
    "- Trigger: x, y\n- Status: 案結 2026-07-29\n\n## 知識\n\n- k\n\n## 行動\n\n- a\n"
)
_ATOM_NO_STATUS = _ATOM_WITH_STATUS.replace("- Status: 案結 2026-07-29\n", "")


def test_status_suffix_extracted():
    assert atom_status_suffix(_ATOM_WITH_STATUS) == " [Status: 案結 2026-07-29]"
    assert atom_status_suffix(_ATOM_NO_STATUS) == ""
    assert atom_status_suffix("") == ""


def test_status_suffix_capped():
    long = _ATOM_WITH_STATUS.replace("案結 2026-07-29", "長" * 60)
    s = atom_status_suffix(long)
    assert "…" in s and len(s) < 60


def test_cold_line_carries_status():
    line = format_cold_inject_line("fat-atom", _ATOM_WITH_STATUS, "memory/fat-atom.md")
    assert "[Status: 案結 2026-07-29]" in line
    assert line.endswith("(full: Read memory/fat-atom.md)")


def test_cold_line_without_status_unchanged():
    line = format_cold_inject_line("fat-atom", _ATOM_NO_STATUS, "memory/fat-atom.md")
    assert "[Status:" not in line


# ── 資料面：assemble_injection 落 injection_log ──────────────────


def test_assemble_injection_records_log(tmp_path):
    from handlers.ups_inject import assemble_injection

    mem = tmp_path / "memory"
    mem.mkdir()
    (mem / "small-atom.md").write_text(_ATOM_WITH_STATUS, encoding="utf-8")
    state = {"turn_seq": 4}
    lines = []
    newly, dirs = assemble_injection(
        "sid-test", state, {},
        [(("small-atom", "memory/small-atom.md", ["x"]), tmp_path)],
        [], [], {"small-atom": "trigger"}, {}, lines,
    )
    assert newly == ["small-atom"]
    log = state.get("injection_log")
    assert log and log[0]["name"] == "small-atom"
    assert log[0]["source"] == "trigger"
    assert log[0]["form"] == "ok"
    assert log[0]["turn_seq"] == 5  # UPS 尾段才 +1，記錄先對齊本 turn
    assert log[0]["rel"] == "memory/small-atom.md"


# ── 跨 realm 路標斷鏈防線：一行路標一律絕對路徑 ─────────────────
# rel_path 只相對 atom 自己的 realm root（~/.claude 或某專案 .claude）；
# 消費端以 cwd 解析 → 跨 realm 必斷鏈（實證：專案 atom 的
# memory/shared/ProjectWorkflow/pitfalls.md 在 ~/.claude 下 glob 不到）。


def test_pointer_path_absolute_when_atom_path_given(tmp_path):
    from wg_atoms import pointer_path

    p = tmp_path / "memory" / "shared" / "ProjectWorkflow" / "pitfalls.md"
    assert pointer_path(p) == p.as_posix()
    assert Path(pointer_path(p)).is_absolute()


def test_pointer_path_falls_back_to_rel_without_atom_path():
    from wg_atoms import pointer_path

    assert pointer_path(None, "memory/x.md", "x") == "memory/x.md"
    assert pointer_path(None, "", "x") == "x.md"


def test_cold_line_prefers_absolute_atom_path(tmp_path):
    p = tmp_path / "memory" / "shared" / "ProjectWorkflow" / "pitfalls.md"
    line = format_cold_inject_line(
        "pitfalls", _ATOM_WITH_STATUS, "memory/shared/ProjectWorkflow/pitfalls.md", p,
    )
    assert line.endswith(f"(full: Read {p.as_posix()})")


def test_assemble_injection_cold_line_absolute(tmp_path):
    """專案 realm 的 cold atom：注入行的路標必須是絕對路徑。"""
    from handlers.ups_inject import assemble_injection

    proj = tmp_path / "proj" / ".claude"
    atom = proj / "memory" / "shared" / "ProjectWorkflow" / "pitfalls.md"
    atom.parent.mkdir(parents=True)
    atom.write_text(_ATOM_WITH_STATUS, encoding="utf-8")
    lines = []
    assemble_injection(
        "sid-cold", {"turn_seq": 1}, {},
        [(("pitfalls", "memory/shared/ProjectWorkflow/pitfalls.md", ["x"]), proj)],
        [], [], {"pitfalls": "vector"}, {}, lines,
    )
    cold = [ln for ln in lines if ln.startswith("[Atom:pitfalls] (cold)")]
    assert cold, lines
    assert atom.as_posix() in cold[0]


def test_audit_message_uses_absolute_path():
    rec = _rec(
        "pitfalls",
        path="C:\\Projects\\.claude\\memory\\shared\\ProjectWorkflow\\pitfalls.md",
        rel="memory/shared/ProjectWorkflow/pitfalls.md",
    )
    out = _audit_pointer_atom_consumption(_state([rec]))
    assert out is not None
    reason, _names = out
    assert rec["path"] in reason
    assert "→ Read memory/shared" not in reason


def test_normalize_read_path():
    assert _normalize_read_path("C:\\A\\b.MD") == "c:/a/b.md"
    assert _normalize_read_path(None) == ""

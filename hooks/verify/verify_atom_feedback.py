"""verify_atom_feedback.py — 「有用/誤導」票據（lib/atom_feedback.py）守門.

用 tmp_path 假 memory root 與假 atom，不碰真實記憶庫。
跑法：python hooks/verify/verify_atom_feedback.py（尾行印 ATOM_FEEDBACK_CHECK PASS/FAIL）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parents[2]
if str(CLAUDE) not in sys.path:
    sys.path.insert(0, str(CLAUDE))

import pytest

from lib import atom_access, atom_feedback
from lib.atom_feedback import fold_votes, record_vote


@pytest.fixture(autouse=True)
def _no_global_audit(monkeypatch):
    monkeypatch.setattr(atom_access, "_audit", lambda *a, **k: "t")


def _mk(root: Path, name: str = "a") -> Path:
    p = root / "sub" / f"{name}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# a\n", encoding="utf-8")
    return p


def _ab(p: Path):
    a = atom_access.read_access(p)
    return a["useful_hits"], a["used_fail"]


def test_vote_updates_sidecar_and_file(tmp_path):
    atom = _mk(tmp_path)
    r = record_vote(atom, "helpful", by="u1", note="n", memory_root=tmp_path)
    assert r["ok"] and r["useful_hits"] == 2 and r["used_fail"] == 1
    lines = (tmp_path / "_votes" / "u1.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    v = json.loads(lines[0])
    for k in ("id", "at", "by", "atom", "path_rel", "verdict", "note", "source"):
        assert "machine" not in v  # 電腦名稱常含人名，票據檔會進版控
        assert k in v
    assert v["path_rel"] == "sub/a.md" and v["atom"] == "a"


def test_misleading_goes_to_beta(tmp_path):
    atom = _mk(tmp_path)
    record_vote(atom, "misleading", by="u1", memory_root=tmp_path)
    assert _ab(atom) == (1, 2)


def test_invalid_verdict(tmp_path):
    with pytest.raises(ValueError):
        record_vote(_mk(tmp_path), "meh", by="u1", memory_root=tmp_path)


def test_three_helpful_promote_eligible(tmp_path):
    atom = _mk(tmp_path)
    r = None
    for _ in range(3):
        r = record_vote(atom, "helpful", by="u1", memory_root=tmp_path)
    assert r["promote_eligible"] is True


def test_own_votes_not_double_applied_by_fold(tmp_path):
    atom = _mk(tmp_path)
    record_vote(atom, "helpful", by="u1", memory_root=tmp_path)
    res = fold_votes([tmp_path])
    assert res["applied"] == 0 and res["skipped"] == 1
    assert _ab(atom) == (2, 1)


def test_fold_idempotent_two_users(tmp_path):
    atom = _mk(tmp_path)
    votes = tmp_path / "_votes"
    votes.mkdir()
    for i, u in enumerate(("u1", "u2")):
        row = {"id": f"{i}-aaaaaa", "by": u, "path_rel": "sub/a.md", "verdict": "helpful"}
        (votes / f"{u}.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    first = fold_votes([tmp_path])
    second = fold_votes([tmp_path])
    assert first["applied"] == 2 and second["applied"] == 0
    assert _ab(atom) == (3, 1)


def test_missing_and_bad_lines(tmp_path):
    _mk(tmp_path)
    votes = tmp_path / "_votes"
    votes.mkdir()
    good_missing = {"id": "9-bbbbbb", "path_rel": "nope.md", "verdict": "helpful"}
    (votes / "u3.jsonl").write_text(
        "not json\n" + json.dumps(good_missing) + "\n", encoding="utf-8")
    res = fold_votes([tmp_path])
    assert res["bad_lines"] == 1 and res["missing"] == 1 and res["applied"] == 0


def test_root_follows_atom_tree(tmp_path, monkeypatch):
    """票據檔跟著卡住的樹：專案層 → 該專案 .claude/memory；local realm → _AIDocs/_atoms；其餘 → 全域。"""
    monkeypatch.setattr(atom_feedback, "GLOBAL_MEMORY_DIR", tmp_path / "g")
    monkeypatch.setattr(atom_feedback, "LOCAL_ATOMS_DIR", tmp_path / "_AIDocs" / "_atoms")
    proj = tmp_path / "proj" / ".claude" / "memory"
    assert atom_feedback._memory_root_of(_mk(proj, "p")) == proj
    local_atom = _mk(tmp_path / "_AIDocs" / "_atoms", "l")
    assert atom_feedback._memory_root_of(local_atom) == tmp_path / "_AIDocs" / "_atoms"
    assert atom_feedback._memory_root_of(_mk(tmp_path / "g", "x")) == tmp_path / "g"
    r = record_vote(local_atom, "helpful", by="u9")
    assert r["ok"] and (tmp_path / "_AIDocs" / "_atoms" / "_votes" / "u9.jsonl").exists()


def test_fold_default_roots_include_project_from_cwd(tmp_path, monkeypatch):
    monkeypatch.setattr(atom_feedback, "GLOBAL_MEMORY_DIR", tmp_path / "g")
    monkeypatch.setattr(atom_feedback, "LOCAL_ATOMS_DIR", tmp_path / "la")
    proj_mem = tmp_path / "proj" / ".claude" / "memory"
    atom = _mk(proj_mem, "p")
    (proj_mem / "_votes").mkdir()
    (proj_mem / "_votes" / "mate.jsonl").write_text(
        json.dumps({"id": "7-cccccc", "path_rel": "sub/p.md", "verdict": "misleading"}) + "\n", encoding="utf-8")
    res = fold_votes(cwd=tmp_path / "proj" / "src" / "deep") if (tmp_path / "proj" / "src" / "deep").mkdir(parents=True) is None else None
    assert res["applied"] == 1 and str(proj_mem) in res["roots"]
    assert _ab(atom) == (1, 2)


if __name__ == "__main__":
    rc = pytest.main(["-q", "-p", "no:cacheprovider", __file__])
    print("ATOM_FEEDBACK_CHECK PASS" if rc == 0 else "ATOM_FEEDBACK_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)

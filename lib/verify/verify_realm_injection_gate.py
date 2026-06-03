"""verify_realm_injection_gate.py — Phase 2 注入閘門（範疇限定）回歸測試。

驗證 `_is_under_claude_dir`（wg_core）+ `is_local_realm_path`（atom_locations）組合在
session_start「候選快取建立處」的過濾語意：
  - 外部專案（cwd∉~/.claude）→ 濾掉 index path 前綴 `_AIDocs/_atoms/` 的 local 候選；
  - core 一律保留——含物理居 `_AIDocs/Failures/` 的 feedback-*（不可誤殺）；
  - cwd∈~/.claude（含子目錄）→ local 全數保留。

純函式版 `_apply_gate` 對拍 handler 內聯實作（handlers/session_start.py：
`if is_local_realm_path is not None and not _is_under_claude_dir(cwd): ...`）。
"""

import sys
from pathlib import Path

import pytest  # noqa: F401  (pytest 收集需要)

CLAUDE = Path.home() / ".claude"
for _p in (CLAUDE / "hooks", CLAUDE / "lib", CLAUDE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from wg_core import _is_under_claude_dir, is_local_realm_path  # noqa: E402


def _apply_gate(atoms, cwd):
    """重現 session_start 的過濾邏輯（純函式版本）。"""
    if is_local_realm_path is not None and not _is_under_claude_dir(cwd):
        return [(n, p, t) for (n, p, t) in atoms if not is_local_realm_path(p)]
    return list(atoms)


ATOMS = [
    ("decisions", "memory/decisions.md", ["決策"]),                          # core
    ("feedback-x", "_AIDocs/Failures/feedback-x.md", ["handoff"]),           # core (Failures!)
    ("brain", "_AIDocs/_atoms/World/brain.md", ["腦內世界"]),                # local
    ("gdoc-harvester", "_AIDocs/_atoms/Tools/gdoc-harvester.md", ["gdoc"]),  # local
]


def test_gate_external_project_filters_local():
    out = _apply_gate(ATOMS, r"C:\Projects\SomeApp")
    names = {n for n, _, _ in out}
    assert "decisions" in names           # core 保留
    assert "feedback-x" in names          # _AIDocs/Failures/ core 保留（不誤殺）
    assert "brain" not in names           # local 濾掉
    assert "gdoc-harvester" not in names  # local 濾掉


def test_gate_under_claude_keeps_local():
    for cwd in (str(CLAUDE), str(CLAUDE / "tools"), str(CLAUDE / "lib" / "verify")):
        out = _apply_gate(ATOMS, cwd)
        names = {n for n, _, _ in out}
        assert names == {"decisions", "feedback-x", "brain", "gdoc-harvester"}, cwd


def test_is_under_claude_dir_predicate():
    assert _is_under_claude_dir(str(CLAUDE)) is True
    assert _is_under_claude_dir(str(CLAUDE / "tools")) is True
    assert _is_under_claude_dir(r"C:\Projects\X") is False
    assert _is_under_claude_dir("") is False
    # 旁系路徑 ~/.claude-foo 必不算內部（parents 比對，非 startswith）
    assert _is_under_claude_dir(str(CLAUDE.parent / (CLAUDE.name + "-foo"))) is False

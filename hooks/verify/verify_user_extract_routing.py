"""verify_user_extract_routing.py — 自動萃取（user-extract-worker）的 scope 路由與 Author。

規則（SPEC_ATOM_V5 §2）：
- cwd 在 ~/.claude → global
- 專案內、內容是「專案規則」（L2 判 shared／含專案規則標記詞／提到專案專名）→ shared，Author=使用者
- 其餘 → 本人×專案 personal
- shared 分不出範疇 → 退回 personal（不丟知識、不拒寫）
- memory-peek / memory-undo 以知識段 `<!-- src: turn -->` 辨識自動萃取 atom（Author 不再是 auto-extracted）
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_ROOT = HOOKS_DIR.parent
for p in (HOOKS_DIR, CLAUDE_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _load_worker():
    spec = importlib.util.spec_from_file_location("uew_under_test", HOOKS_DIR / "user-extract-worker.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _load_tool(name: str):
    path = CLAUDE_ROOT / "tools" / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_").replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_project_rule_signals():
    m = _load_worker()
    # 標記詞
    assert m._is_project_rule("此專案上 SVN 前必須再次向使用者確認", "x", ["svn"], "", "personal")
    assert m._is_project_rule("改完 server 或 client 後必須執行發布流程", "x", ["server"], "", "personal")
    # L2 判 shared
    assert m._is_project_rule("介面配色偏好暖色", "x", ["ui"], "", "shared")
    # 純個人偏好
    assert not m._is_project_rule("要求 AI 助手以白話條列方式溝通", "x", ["溝通"], "", "personal")
    assert not m._is_project_rule("喜歡用兩格縮排", "x", ["縮排"], "", "")


def test_routing_shared_when_project_rule(tmp_path, monkeypatch):
    m = _load_worker()
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    calls = {}

    def fake_write_atom(**kw):
        calls.update(kw)

        class R:
            ok = True
            error = ""
        return R()

    monkeypatch.setattr(m, "write_atom", fake_write_atom)
    monkeypatch.setattr(m, "_write_pending_candidate", lambda *a, **k: None)
    l2 = {"statement": "專案版本控制必須使用 GIT，禁止使用 SVN", "scope": "personal",
          "audience": "programmer", "trigger": ["git", "svn"]}
    cand = {"turn_id": "t-1", "cwd": str(proj)}
    out = m._write_atom_via_mcp(l2, cand, "sid", "holylight", {})
    assert out == "wrote"
    assert calls["scope"] == "shared"
    assert calls["author"] == "holylight"
    assert calls["domain"]  # shared 必帶範疇（版控）
    assert calls["project_cwd"] == str(proj)


def test_routing_personal_for_preference(tmp_path, monkeypatch):
    m = _load_worker()
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    calls = {}

    def fake_write_atom(**kw):
        calls.update(kw)

        class R:
            ok = True
            error = ""
        return R()

    monkeypatch.setattr(m, "write_atom", fake_write_atom)
    l2 = {"statement": "要求 AI 助手以白話條列方式溝通", "scope": "personal",
          "audience": "programmer", "trigger": ["溝通", "白話"]}
    out = m._write_atom_via_mcp(l2, {"turn_id": "t-2", "cwd": str(proj)}, "sid", "holylight", {})
    assert out == "wrote"
    assert calls["scope"] == "personal" and calls["author"] == "holylight"
    assert calls["user"] == "holylight"


def test_shared_unclassified_falls_back_to_personal(tmp_path, monkeypatch):
    m = _load_worker()
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    calls = {}

    def fake_write_atom(**kw):
        calls.update(kw)

        class R:
            ok = True
            error = ""
        return R()

    monkeypatch.setattr(m, "write_atom", fake_write_atom)
    import lib.atom_locations as al
    monkeypatch.setattr(al, "classify_category",
                        lambda *a, **k: {"status": "unsure", "category": None, "reason": "test"})
    l2 = {"statement": "此專案的 XYZ 必須先經過 QQQ", "scope": "personal",
          "audience": "programmer", "trigger": ["xyz"]}
    out = m._write_atom_via_mcp(l2, {"turn_id": "t-3", "cwd": str(proj)}, "sid", "holylight", {})
    assert out == "wrote"
    assert calls["scope"] == "personal"  # 分不出範疇 → 退回 personal，不拒寫


def test_peek_and_undo_detect_by_src_marker(tmp_path):
    peek = _load_tool("memory-peek.py")
    undo = _load_tool("memory-undo.py")
    f = tmp_path / "x.md"
    f.write_text("# x\n\n- Author: holylight\n\n## 知識\n\n- [臨] y\n<!-- src: t-9 -->\n", encoding="utf-8")
    g = tmp_path / "y.md"
    g.write_text("# y\n\n- Author: holylight\n\n## 知識\n\n- [臨] z\n", encoding="utf-8")
    assert peek._has_auto_src_marker(f) and undo._has_auto_src_marker(f)
    assert not peek._has_auto_src_marker(g) and not undo._has_auto_src_marker(g)

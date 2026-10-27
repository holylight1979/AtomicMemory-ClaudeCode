"""verify_user_extract_routing.py — 自動萃取（user-extract-worker）的 scope 路由與 Author。

規則（SPEC_ATOM_V5 §2）：
- cwd 在 ~/.claude → global
- 專案內、內容是「專案規則」（L2 判 shared／提到目前專案的專名或路徑）→ shared，Author=使用者
- 只命中線索詞（此專案／上傳／必須／禁止…）→ 規則 PROJECT_RULE_WORDS_ARE_HINTS：不定案，落 personal 並留帳 guard-scope_hint
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
    # 線索詞／字面「此專案」→ 只是提示（hint），附命中的詞；不是定案（規則 PROJECT_RULE_WORDS_ARE_HINTS）
    sig = m.project_rule_signal("此專案上 SVN 前必須再次向使用者確認", "x", ["svn"], "", "personal")
    assert sig["verdict"] == "hint" and "此專案" in sig["hits"] and "待確認" in sig["why"]
    assert m.project_rule_signal("改完 server 或 client 後必須執行發布流程", "x", ["server"], "", "personal")["verdict"] == "hint"
    # L2（LLM）判 shared → 定案
    assert m.project_rule_signal("介面配色偏好暖色", "x", ["ui"], "", "shared")["verdict"] == "rule"
    # 純個人偏好
    assert m.project_rule_signal("要求 AI 助手以白話條列方式溝通", "x", ["溝通"], "", "personal")["verdict"] == "none"
    assert m.project_rule_signal("喜歡用兩格縮排", "x", ["縮排"], "", "")["verdict"] == "none"


def test_project_name_is_fact_not_hint(tmp_path, monkeypatch):
    """反例：目前專案的專名是查得到的事實 → rule（照定案），不降成 hint。"""
    m = _load_worker()
    import lib.realm_gate as rg
    proj = tmp_path / "FooProj"
    (proj / ".git").mkdir(parents=True)
    (proj / "FooServer").mkdir()   # 專案頂層資料夾名＝realm_gate 推導的專名
    monkeypatch.setattr(rg, "_load_registry", lambda: {"projects": {}})
    monkeypatch.setattr(rg, "_org_root_names", lambda: set())
    sig = m.project_rule_signal("FooServer 的表要 regen 後才生效", "x", ["regen"], str(proj), "personal")
    assert sig["verdict"] == "rule" and "FooServer" in sig["hits"]


def test_hint_words_route_personal_and_log(tmp_path, monkeypatch):
    """會紅（規則 PROJECT_RULE_WORDS_ARE_HINTS）：舊碼「此專案／必須／禁止」字樣命中就自動寫 shared。
    現在只命中線索詞 → 落 personal、留帳 guard-scope_hint 附命中詞，等人判。"""
    m = _load_worker()
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    calls, logs = {}, []

    def fake_write_atom(**kw):
        calls.update(kw)

        class R:
            ok = True
            error = ""
        return R()

    monkeypatch.setattr(m, "write_atom", fake_write_atom)
    monkeypatch.setattr(m, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    l2 = {"statement": "此專案版本控制必須使用 GIT，禁止使用 SVN", "scope": "personal",
          "audience": "programmer", "trigger": ["git", "svn"]}
    out = m._write_atom_via_mcp(l2, {"turn_id": "t-h", "cwd": str(proj)}, "sid", "holylight", {})
    assert out == "wrote"
    assert calls["scope"] == "personal" and calls["author"] == "holylight"
    assert logs and logs[-1][0] == "scope_hint" and logs[-1][1]["rule"] == "PROJECT_RULE_WORDS_ARE_HINTS"
    assert "此專案" in logs[-1][1]["hits"] and logs[-1][1]["session_id"] == "sid"


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
    l2 = {"statement": "專案版本控制必須使用 GIT，禁止使用 SVN", "scope": "shared",   # L2（LLM）宣告 shared → 定案
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
    l2 = {"statement": "此專案的 XYZ 必須先經過 QQQ", "scope": "shared",
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

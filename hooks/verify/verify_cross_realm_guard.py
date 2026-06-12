"""verify_cross_realm_guard.py — Cross-Realm Write Guard（方案甲 2026-06-12）守門.

不變式：
1. 外部專案 session（cwd ∉ ~/.claude）寫 ~/.claude/{skills,tools,hooks,lib,rules}/ → deny。
2. 核心開發 session（cwd ∈ ~/.claude，含子目錄）寫核心層 → 放行。
3. 專案自己的 .claude 層（{proj}/.claude/skills/）→ 放行（不在 home ~/.claude 下）。
4. ~/.claude/memory/ 等非守門子目錄 → 放行（既有 atom funnel 閘管轄）。
5. config guard.cross_realm_write.enabled=false → 全放行；allowlist 子字串命中 → 放行。
6. 非 Write/Edit/NotebookEdit 工具、cwd 缺失、路徑無法解析 → fail-open。

純函式測試：check_cross_realm_write 無磁碟副作用（resolve strict=False）。
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

from wg_core import check_cross_realm_write  # noqa: E402

HOME_CLAUDE = Path.home() / ".claude"
PROJ = "C:/FakeProj/game-x" if sys.platform == "win32" else "/tmp/fakeproj/game-x"
CFG_ON = {"guard": {"cross_realm_write": {"enabled": True, "allowlist": []}}}


def _w(path) -> dict:
    return {"file_path": str(path)}


def test_project_session_write_tools_denied():
    msg = check_cross_realm_write(
        "Write", _w(HOME_CLAUDE / "tools" / "sgi-introspect-ui.cs"), PROJ, CFG_ON)
    assert msg and "CrossRealmWriteBlock" in msg


def test_project_session_write_skills_denied():
    msg = check_cross_realm_write(
        "Write", _w(HOME_CLAUDE / "skills" / "foo" / "SKILL.md"), PROJ, CFG_ON)
    assert msg and "CrossRealmWriteBlock" in msg


def test_project_session_edit_hooks_denied():
    msg = check_cross_realm_write(
        "Edit", _w(HOME_CLAUDE / "hooks" / "wg_core.py"), PROJ, CFG_ON)
    assert msg and "CrossRealmWriteBlock" in msg


def test_core_session_write_tools_allowed():
    assert check_cross_realm_write(
        "Write", _w(HOME_CLAUDE / "tools" / "x.py"), str(HOME_CLAUDE), CFG_ON) is None


def test_core_subdir_session_allowed():
    assert check_cross_realm_write(
        "Write", _w(HOME_CLAUDE / "skills" / "foo" / "SKILL.md"),
        str(HOME_CLAUDE / "hooks"), CFG_ON) is None


def test_project_own_claude_layer_allowed():
    assert check_cross_realm_write(
        "Write", _w(Path(PROJ) / ".claude" / "skills" / "foo" / "SKILL.md"),
        PROJ, CFG_ON) is None


def test_memory_dir_not_guarded():
    # memory/ 由既有 atom funnel 閘管轄，本閘不重複攔
    assert check_cross_realm_write(
        "Write", _w(HOME_CLAUDE / "memory" / "x.md"), PROJ, CFG_ON) is None


def test_disabled_config_allows():
    cfg = {"guard": {"cross_realm_write": {"enabled": False}}}
    assert check_cross_realm_write(
        "Write", _w(HOME_CLAUDE / "tools" / "x.cs"), PROJ, cfg) is None


def test_allowlist_substring_allows():
    cfg = {"guard": {"cross_realm_write": {
        "enabled": True, "allowlist": ["tools/sgi-"]}}}
    assert check_cross_realm_write(
        "Write", _w(HOME_CLAUDE / "tools" / "sgi-x.cs"), PROJ, cfg) is None
    # allowlist 未命中者仍擋
    assert check_cross_realm_write(
        "Write", _w(HOME_CLAUDE / "tools" / "other.cs"), PROJ, cfg) is not None


def test_non_write_tool_ignored():
    assert check_cross_realm_write(
        "Bash", {"command": "rm -rf ~/.claude/tools"}, PROJ, CFG_ON) is None


def test_missing_cwd_fail_open():
    assert check_cross_realm_write(
        "Write", _w(HOME_CLAUDE / "tools" / "x.cs"), "", CFG_ON) is None


def test_notebookedit_guarded():
    msg = check_cross_realm_write(
        "NotebookEdit", _w(HOME_CLAUDE / "lib" / "x.ipynb"), PROJ, CFG_ON)
    assert msg and "CrossRealmWriteBlock" in msg


def test_deny_message_guidance():
    msg = check_cross_realm_write(
        "Write", _w(HOME_CLAUDE / "tools" / "dump.png"), PROJ, CFG_ON)
    assert msg is not None
    assert "tools" in msg            # 點名被攔的核心子目錄
    assert ".claude/skills/" in msg  # 指路專案層
    assert "allowlist" in msg        # 給 escape hatch


def test_missing_guard_config_defaults_enabled():
    # config 無 guard 區 → 預設啟用（DEFAULTS 對齊）
    msg = check_cross_realm_write(
        "Write", _w(HOME_CLAUDE / "rules" / "evil.md"), PROJ, {})
    assert msg and "CrossRealmWriteBlock" in msg

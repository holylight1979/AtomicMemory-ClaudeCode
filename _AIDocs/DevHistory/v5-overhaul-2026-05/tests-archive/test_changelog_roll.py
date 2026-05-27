"""test_changelog_roll.py — changelog-roll tool + PostToolUse auto-trigger.

前 5 條：純工具邏輯（roll / preserve preamble / nothing-to-roll / dry-run / archive shell）
後 3 條：PostToolUse hook 自動觸發驗證（mock subprocess.Popen）
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"
HOOKS = REPO / "hooks"

# ─── Load changelog-roll module (file has hyphen, can't import normally) ───
def _load_roll_module():
    spec = importlib.util.spec_from_file_location(
        "changelog_roll", TOOLS / "changelog-roll.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


roll_mod = _load_roll_module()


def _make_changelog(rows: int) -> str:
    """Build a mock _CHANGELOG.md content with N data rows, newest first."""
    preamble = (
        "# 變更記錄\n\n"
        "> 保留最近 ~8 筆。舊條目移至 `_CHANGELOG_ARCHIVE.md`。\n\n"
        "---\n\n"
        "## 2026-04-02 V3.1 Token Diet — 原子記憶精簡\n"
        "- Phase 1 直刪\n"
        "- **成果**：-65.7% tokens\n\n"
    )
    header = "| 日期 | 變更 | 涉及檔案 |\n|------|------|---------|\n"
    # Generate rows with descending dates
    body_rows = []
    for i in range(rows):
        day = 30 - i  # 30, 29, 28 ...
        if day < 1:
            day = 1
        body_rows.append(
            f"| 2026-03-{day:02d} | 條目 {i+1} 內容 | `file{i+1}.py` |"
        )
    body = "\n".join(body_rows) + "\n"
    return preamble + header + body


def _make_archive_shell() -> str:
    return (
        "# 變更記錄 — 封存\n\n"
        "> 從 `_CHANGELOG.md` 滾動淘汰的歷史記錄。\n\n"
        "---\n\n"
        "| 日期 | 變更 | 涉及檔案 |\n"
        "|------|------|---------|\n"
        "| 2026-01-01 | 最早條目 | `old.py` |\n"
    )


# ─── 1: roll exceeds keep moves oldest ──────────────────────────────────

def test_roll_exceeds_keep_moves_oldest(tmp_path):
    cl = tmp_path / "_CHANGELOG.md"
    ar = tmp_path / "_CHANGELOG_ARCHIVE.md"
    cl.write_text(_make_changelog(12), encoding="utf-8")
    ar.write_text(_make_archive_shell(), encoding="utf-8")

    kept, moved = roll_mod.roll(
        changelog_path=cl, archive_path=ar, keep=8, quiet=True
    )
    assert kept == 8 and moved == 4

    new_cl = cl.read_text(encoding="utf-8")
    rows_in_main = [l for l in new_cl.splitlines() if l.startswith("| 2026-")]
    assert len(rows_in_main) == 8
    # Oldest 4 moved out (days 30-7=23 kept, 22-19 moved)
    assert "2026-03-19" not in new_cl  # oldest moved
    assert "2026-03-19" in ar.read_text(encoding="utf-8")


# ─── 2: preamble preserved ──────────────────────────────────────────────

def test_roll_preserves_preamble(tmp_path):
    cl = tmp_path / "_CHANGELOG.md"
    ar = tmp_path / "_CHANGELOG_ARCHIVE.md"
    cl.write_text(_make_changelog(12), encoding="utf-8")
    ar.write_text(_make_archive_shell(), encoding="utf-8")

    roll_mod.roll(changelog_path=cl, archive_path=ar, keep=8, quiet=True)
    out = cl.read_text(encoding="utf-8")
    assert out.startswith("# 變更記錄")
    assert "V3.1 Token Diet" in out
    assert "-65.7% tokens" in out


# ─── 3: nothing to roll ─────────────────────────────────────────────────

def test_roll_nothing_when_under_keep(tmp_path):
    cl = tmp_path / "_CHANGELOG.md"
    ar = tmp_path / "_CHANGELOG_ARCHIVE.md"
    original = _make_changelog(5)
    cl.write_text(original, encoding="utf-8")
    ar.write_text(_make_archive_shell(), encoding="utf-8")

    kept, moved = roll_mod.roll(
        changelog_path=cl, archive_path=ar, keep=8, quiet=True
    )
    assert kept == 5 and moved == 0
    assert cl.read_text(encoding="utf-8") == original


# ─── 4: dry run writes nothing ──────────────────────────────────────────

def test_dry_run_writes_nothing(tmp_path):
    cl = tmp_path / "_CHANGELOG.md"
    ar = tmp_path / "_CHANGELOG_ARCHIVE.md"
    original_cl = _make_changelog(12)
    original_ar = _make_archive_shell()
    cl.write_text(original_cl, encoding="utf-8")
    ar.write_text(original_ar, encoding="utf-8")

    mtime_cl = cl.stat().st_mtime
    mtime_ar = ar.stat().st_mtime

    kept, moved = roll_mod.roll(
        changelog_path=cl, archive_path=ar, keep=8, dry_run=True, quiet=True
    )
    assert kept == 8 and moved == 4
    # Content unchanged
    assert cl.read_text(encoding="utf-8") == original_cl
    assert ar.read_text(encoding="utf-8") == original_ar


# ─── 5: archive missing creates shell ───────────────────────────────────

def test_archive_missing_creates_shell(tmp_path):
    cl = tmp_path / "_CHANGELOG.md"
    ar = tmp_path / "_CHANGELOG_ARCHIVE.md"
    cl.write_text(_make_changelog(10), encoding="utf-8")
    assert not ar.exists()

    kept, moved = roll_mod.roll(
        changelog_path=cl, archive_path=ar, keep=8, quiet=True
    )
    assert ar.exists()
    ar_text = ar.read_text(encoding="utf-8")
    assert "# 變更記錄 — 封存" in ar_text
    assert "| 日期 | 變更 | 涉及檔案 |" in ar_text
    assert moved == 2


# ─── 6-8: PostToolUse auto-trigger ──────────────────────────────────────

def _call_post_tool_use(tool_name: str, file_path: str):
    """Invoke workflow-guardian.py::handle_post_tool_use with mock input.

    Uses runpy to load the hyphenated module file.
    """
    import runpy
    # Load wg module
    wg_mod = runpy.run_path(
        str(HOOKS / "workflow-guardian.py"),
        run_name="__wg_test__",
    )
    handle = wg_mod["handle_post_tool_use"]
    input_data = {
        "session_id": "test-session-id",
        "cwd": str(REPO),
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path, "content": ""},
        "tool_response": {"success": True},
    }
    config = wg_mod.get("load_config", lambda: {})()
    if not isinstance(config, dict):
        config = {}
    try:
        handle(input_data, config)
    except SystemExit:
        pass  # output_nothing() / output_json() call sys.exit(0)


@patch("subprocess.Popen")
def test_post_tool_use_spawns_roll_when_over_threshold(mock_popen, tmp_path):
    # Create a fake _CHANGELOG.md inline in tmp_path
    fake_cl = tmp_path / "_CHANGELOG.md"
    fake_cl.write_text(_make_changelog(10), encoding="utf-8")

    _call_post_tool_use("Edit", str(fake_cl))

    # Expect Popen called at least once with changelog-roll.py in argv
    called = False
    for call in mock_popen.call_args_list:
        args = call[0][0] if call[0] else call.kwargs.get("args", [])
        argv = args if isinstance(args, list) else [args]
        if any("changelog-roll.py" in str(a) for a in argv):
            called = True
            break
    assert called, f"Popen never called with changelog-roll.py. Calls: {mock_popen.call_args_list}"


@patch("subprocess.Popen")
def test_post_tool_use_no_spawn_when_under_threshold(mock_popen, tmp_path):
    fake_cl = tmp_path / "_CHANGELOG.md"
    fake_cl.write_text(_make_changelog(5), encoding="utf-8")

    _call_post_tool_use("Edit", str(fake_cl))

    for call in mock_popen.call_args_list:
        args = call[0][0] if call[0] else call.kwargs.get("args", [])
        argv = args if isinstance(args, list) else [args]
        assert not any("changelog-roll.py" in str(a) for a in argv), (
            f"Popen should NOT be called with changelog-roll.py when under threshold"
        )


@patch("subprocess.Popen")
def test_post_tool_use_no_spawn_on_other_files(mock_popen, tmp_path):
    other = tmp_path / "some-other-file.md"
    other.write_text("# unrelated\n", encoding="utf-8")

    _call_post_tool_use("Edit", str(other))

    for call in mock_popen.call_args_list:
        args = call[0][0] if call[0] else call.kwargs.get("args", [])
        argv = args if isinstance(args, list) else [args]
        assert not any("changelog-roll.py" in str(a) for a in argv), (
            "Popen should NOT target changelog-roll.py for non-_CHANGELOG files"
        )

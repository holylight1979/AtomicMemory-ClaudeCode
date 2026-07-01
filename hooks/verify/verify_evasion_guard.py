"""test_evasion_guard.py — wg_evasion helpers + hook integration tests.

Pure-function tests for wg_evasion (no state/hook mocking needed).
Hook integration smoke-tested via plan §5.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make hooks/ importable
HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

from wg_evasion import (  # noqa: E402
    is_test_command,
    detect_test_failure,
    claims_completion,
    detect_evasion,
    is_dismiss_prompt,
    get_last_assistant_text,
    tail_lines,
    is_core_file,
    detect_missing_scan_report,
)


# ─── is_test_command ─────────────────────────────────────────────────

@pytest.mark.parametrize("cmd, expected", [
    ("pytest tests/", True),
    ("python -m pytest tests/ -q", True),
    ("npm test", True),
    ("npm run test", True),
    ("jest --watch", True),
    ("node --check src/foo.js", True),
    ("tsc --noEmit", True),
    ("go test ./...", True),
    ("cargo test", True),
    ("ls -la", False),
    ("git log --oneline", False),
    ("python script.py", False),
    ("", False),
])
def test_is_test_command(cmd, expected):
    assert is_test_command(cmd) is expected


# ─── detect_test_failure ─────────────────────────────────────────────

def test_pytest_failure_detected():
    stdout = "tests/test_foo.py::test_bar FAILED\n======= 5 failed, 10 passed in 0.5s ======="
    r = detect_test_failure(stdout, "", False)
    assert r is not None
    assert "5 failed" in r


def test_pytest_failure_short_summary():
    stdout = "tests/a.py::t FAILED\ntests/b.py::t FAILED\n2 failed, 3 passed"
    assert detect_test_failure(stdout, "", False) is not None


def test_pytest_success_no_flag():
    stdout = "======= 15 passed in 0.5s ======="
    assert detect_test_failure(stdout, "", False) is None


def test_node_check_syntax_error():
    stderr = "/path/to/foo.js:3\nconst x = {\n         ^\nSyntaxError: Unexpected token"
    r = detect_test_failure("", stderr, False)
    assert r is not None
    assert "SyntaxError" in r


def test_tsc_error():
    stdout = "src/foo.ts(5,12): error TS2322: Type 'string' is not assignable to type 'number'."
    r = detect_test_failure(stdout, "", False)
    assert r is not None


def test_jest_failure():
    stdout = "Tests:       3 failed, 12 passed, 15 total"
    assert detect_test_failure(stdout, "", False) is not None


def test_go_test_failure():
    stdout = "--- FAIL: TestFoo (0.00s)\nFAIL\nFAIL\tfoo\t0.001s"
    assert detect_test_failure(stdout, "", False) is not None


def test_cargo_test_failure():
    stdout = "test result: FAILED. 1 passed; 1 failed; 0 ignored"
    assert detect_test_failure(stdout, "", False) is not None


def test_interrupted_returns_tail():
    stdout = "line1\nline2\nline3"
    r = detect_test_failure(stdout, "", True)
    assert r is not None
    assert "line3" in r


def test_interrupted_empty_output():
    r = detect_test_failure("", "", True)
    assert r == "(interrupted, no output)"


def test_tail_lines_limits():
    s = "\n".join(f"line{i}" for i in range(50))
    r = tail_lines(s, 5)
    assert r.count("\n") == 4
    assert "line49" in r
    assert "line45" in r
    assert "line44" not in r


# ─── claims_completion ───────────────────────────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("全部做完了，可以 commit 了", True),
    ("收尾階段，跑測試", True),
    ("done.", True),
    ("All set, moving on", True),
    ("大功告成", True),
    ("已解決 bug", True),
    ("我已修掉 3 個，剩 2 個", False),
    ("還在改", False),
    ("", False),
    (None, False),
])
def test_claims_completion(text, expected):
    assert claims_completion(text) is expected


@pytest.mark.parametrize("text", [
    # P4 #2: 進行式/否定修飾緊鄰完成詞 → 非真正終結宣告（實測 false-positive）
    "完成條件尚未滿足",
    "我總結一下但還沒做完",
    "尚未完成",
    "還沒做完",
    "先確認 X 再宣告完成",
    "細節待補",
    "這部分還沒解決",
])
def test_claims_completion_excludes_incomplete_modifier(text):
    assert claims_completion(text) is False


def test_claims_completion_only_scans_tail():
    # 前文有「完成」但 tail 2000 字沒有 → False
    head = "任務完成條件檢查。"
    filler = "x" * 2500
    text = head + filler
    assert claims_completion(text) is False


# ─── detect_evasion ──────────────────────────────────────────────────

def test_evasion_flags_out_of_scope():
    t = "這個 bug 是既有的 drift 非本次改動所致，留給未來 session 處理。"
    r = detect_evasion(t, [])
    assert r is not None
    # 文字中有多個可能命中：既有...drift / 非本次 / 留給未來 — 任一即可
    assert r["phrase"]
    assert "context_excerpt" in r


def test_evasion_flags_preexisting():
    r = detect_evasion("This is pre-existing behavior, skipping.", [])
    assert r is not None


@pytest.mark.parametrize("text", [
    "這個小問題下次再處理吧",
    "下回再修一下",
    "下一次再看",
    "之後再處理這個 drift",
    "晚點再補",
    "稍後再修",
    "有空再弄",
    "有時間再看",
    "未來處理這個",
    "未來再處理",
    "留給使用者自己處理",
    "待後續追蹤",
    "另行處理",
    "另外處理即可",
])
def test_evasion_flags_deferral_keywords(text):
    """2026-04-17 使用者指出關鍵字不夠，補完時間性延後語。"""
    r = detect_evasion(text, [])
    assert r is not None, f"未抓到退避語：{text!r}"


def test_evasion_escape_hatch_dismiss_recent():
    # 使用者近期說過「先這樣」→ 不再標記
    t = "既有的問題，非本次範圍。"
    r = detect_evasion(t, ["先這樣，留著吧"])
    assert r is None


def test_evasion_escape_hatch_last_3_only():
    # 豁免詞在第 4 則（視窗外）→ 仍標記
    t = "既有的 drift，留給未來。"
    r = detect_evasion(t, ["先這樣", "a", "b", "c"])
    assert r is not None  # 最後 3 則是 a/b/c，豁免詞被切掉 → 仍標記
    # 視窗內：最後 3 則含放行詞 → 豁免
    r2 = detect_evasion(t, ["a", "先這樣", "b"])
    assert r2 is None


def test_evasion_no_phrase_no_flag():
    assert detect_evasion("一切正常，已完成修復", []) is None


def test_evasion_empty_text():
    assert detect_evasion("", []) is None
    assert detect_evasion(None, []) is None


# ─── is_dismiss_prompt ──────────────────────────────────────────────

@pytest.mark.parametrize("prompt, expected", [
    ("先這樣吧", True),
    ("留著", True),
    ("跳過", True),
    ("known regression", True),
    ("continue", False),
    ("", False),
])
def test_is_dismiss_prompt(prompt, expected):
    assert is_dismiss_prompt(prompt) is expected


# ─── get_last_assistant_text ────────────────────────────────────────

def test_get_last_assistant_text_reads_jsonl(tmp_path):
    p = tmp_path / "transcript.jsonl"
    p.write_text(
        '{"type":"user","message":{"content":[]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"text","text":"'
        + ("First assistant reply with enough length to count here." * 2)
        + '"}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"text","text":"'
        + ("Second LAST reply long enough body abc" * 2)
        + '"}]}}\n',
        encoding="utf-8",
    )
    r = get_last_assistant_text(p)
    assert "Second LAST" in r
    assert "First assistant" not in r


def test_get_last_assistant_text_missing_file(tmp_path):
    assert get_last_assistant_text(tmp_path / "nope.jsonl") == ""


def test_get_last_assistant_text_none_path():
    assert get_last_assistant_text(None) == ""


def test_get_last_assistant_text_skips_short():
    p = HOOKS_DIR  # placeholder; override with tmp
    import tempfile, json as _j
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        _j.dump({"type": "assistant", "message": {"content": [{"type": "text", "text": "short"}]}}, f)
        f.write("\n")
        _j.dump({"type": "assistant", "message": {"content": [{"type": "text", "text": "a" * 100}]}}, f)
        f.write("\n")
        fp = f.name
    r = get_last_assistant_text(Path(fp))
    assert len(r) >= 100
    Path(fp).unlink()


# ─── is_core_file (P4 #1) ───────────────────────────────────────────

@pytest.mark.parametrize("path, expected", [
    (r"c:\Users\x\.claude\hooks\wg_evasion.py", True),
    ("c:/Users/x/.claude/lib/atom_access.py", True),
    ("c:/Users/x/.claude/tools/foo.py", True),
    (r"c:\Users\x\.claude\rules\core.md", True),
    (r"c:\Users\x\.claude\IDENTITY.md", True),
    (r"c:\Users\x\.claude\USER.md", True),
    (r"c:\Users\x\.claude\CLAUDE.md", True),
    (r"c:\Users\x\.claude\settings.json", True),
    (r"c:\Users\x\.claude\IDENTITY-holylight.md", True),
    # 非 core：純內容 / 文件
    (r"c:\Users\x\.claude\memory\foo.md", False),
    (r"c:\proj\_AIDocs\bar.md", False),
    (r"c:\proj\src\app.py", False),
    ("", False),
])
def test_is_core_file(path, expected):
    assert is_core_file(path) is expected


# ─── detect_missing_scan_report (P4 #1: 降條件觸發) ──────────────────

def _mf(*paths):
    return [{"path": p, "tool": "Edit"} for p in paths]


def test_scan_report_single_noncore_not_triggered():
    # 純單檔 / 文件小改 → 不觸發（4.8 過度觸發修正）
    assert detect_missing_scan_report(
        "全部完成了", _mf(r"c:\a\.claude\memory\foo.md"), [], 2
    ) is False


def test_scan_report_single_core_triggered():
    # 動 core 檔 → 觸發
    assert detect_missing_scan_report(
        "全部完成了", _mf(r"c:\a\.claude\hooks\x.py"), [], 2
    ) is True


def test_scan_report_multi_noncore_triggered():
    # 多檔（≥min_files）→ 觸發
    assert detect_missing_scan_report(
        "全部完成了", _mf("a/x.md", "a/y.md"), [], 2
    ) is True


def test_scan_report_dupe_paths_below_min_not_triggered():
    # 同一非 core 檔重複算一次 → unique<min → 不觸發
    assert detect_missing_scan_report(
        "全部完成了", _mf("a/x.md", "a/x.md"), [], 2
    ) is False


def test_scan_report_has_report_not_triggered():
    assert detect_missing_scan_report(
        "全部完成了 缺失發現：無", _mf(r"c:\a\.claude\hooks\x.py"), [], 2
    ) is False


def test_scan_report_no_completion_not_triggered():
    assert detect_missing_scan_report(
        "還在做", _mf(r"c:\a\.claude\hooks\x.py"), [], 2
    ) is False


def test_scan_report_dismiss_prompt_not_triggered():
    assert detect_missing_scan_report(
        "全部完成了", _mf(r"c:\a\.claude\hooks\x.py"), ["先這樣"], 2
    ) is False


def test_scan_report_empty_files_not_triggered():
    assert detect_missing_scan_report("全部完成了", [], [], 2) is False

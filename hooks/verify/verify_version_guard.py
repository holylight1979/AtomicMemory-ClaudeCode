"""verify_version_guard.py — 版本操作脈絡 warn hook 純函式守恆。

守住 version_guard 三純函式不變式（寧漏報不誤報）：
- find_version_remnants：高精度 pattern 捕捉（TP）；行內含 whitelist token 整行跳過（FP 排除）
- is_scannable_path：只掃 ~/.claude 內文字檔；正位/歸檔/fixture 路徑豁免（FP 排除）
- extract_written_text：Write/Edit/MultiEdit 三形取內容

受控字串輸入，零磁碟依賴（is_scannable_path 用 ~/.claude 真實根前綴組路徑）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest  # noqa: F401

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import version_guard as VG  # noqa: E402


# ─── find_version_remnants：true-positive 捕捉 ────────────────────────────────


@pytest.mark.parametrize(
    "text,expected_frag",
    [
        ("這是 V5 P3 遺留的邏輯", "V5 P3"),
        ("V5P3 里程碑", "V5P3"),
        ("Sprint 4 完成", "Sprint 4"),
        ("Wave 2 汰舊", "Wave 2"),
        ("採方案甲", "方案甲"),
        ("stderr 印 [v2] 前綴", "[v2]"),
        ("印 [v2.1] 版本前綴", "[v2.1]"),
        ("debug key [phase2] 前綴", "[phase2]"),
        ("spec 錨 [F12] 交叉引用", "[F12]"),
    ],
)
def test_tp_catches_version_remnants(text, expected_frag):
    found = VG.find_version_remnants(text)
    assert any(expected_frag in f for f in found), f"應捕捉 {expected_frag}，得 {found}"


# ─── find_version_remnants：false-positive 排除（whitelist token 行整行跳過）───


@pytest.mark.parametrize(
    "text",
    [
        "def _migrate_v211_to_v212(): pass  # V5 P3 同行有遷移碼→豁免",
        "SCHEMA_VERSION = 3  # 這行有 Sprint 2 也豁免",
        'json_key = obj["protocolVersion"]  # Wave 1',
        "migrated-v2.21 功能 literal [F1]",
    ],
)
def test_fp_whitelist_token_line_skipped(text):
    assert VG.find_version_remnants(text) == [], f"含 whitelist token 的行應整行豁免：{text}"


def test_fp_clean_timeless_text_no_match():
    clean = "此函式回傳注入預算；短 prompt 少注入、長 prompt 多注入。"
    assert VG.find_version_remnants(clean) == []


def test_fp_bare_phase_and_version_not_matched():
    # 寧漏報不誤報：裸 Phase N / v2.x / 日期 刻意不收（模糊、誤傷高）
    assert VG.find_version_remnants("Phase 2 效用接管晉升") == []
    assert VG.find_version_remnants("version 2.11 schema") == []
    assert VG.find_version_remnants("2026-07-02 完成") == []


# ─── is_scannable_path：只掃 ~/.claude 內、非正位/歸檔、文字檔 ─────────────────


def _p(*parts: str) -> str:
    return str(VG.CLAUDE_DIR.joinpath(*parts))


def test_scannable_live_py_in_claude():
    assert VG.is_scannable_path(_p("hooks", "wg_core.py")) is True


@pytest.mark.parametrize(
    "path",
    [
        _p("_AIDocs", "DevHistory", "v5-overhaul.md"),  # 歸檔正位
        _p("_AIDocs", "_CHANGELOG.md"),                  # 版本正位
        _p("TECH.md"),                                   # 最新版本宣告正位
        _p("_AIDocs", "Architecture.md"),
        _p("_AIDocs", "SPEC_ATOM_V5.md"),
        _p("hooks", "verify", "verify_x.py"),            # 測試 fixture
        _p("plans", "some-plan.md"),
        _p("_AIDocs", "Failures", "feedback-live-x.md"), # atom 列 pattern 作範例→豁免
        _p("hooks", "version_guard.py"),                 # 本 hook 自身→豁免
        _p("hooks", "wg_core.png"),                      # 非文字副檔名
    ],
)
def test_not_scannable_whitelisted_or_nontext(path):
    assert VG.is_scannable_path(path) is False


def test_not_scannable_outside_claude():
    assert VG.is_scannable_path("C:/Projects/game/enemy_wave.py") is False
    assert VG.is_scannable_path("/home/user/proj/src/main.py") is False


def test_not_scannable_empty():
    assert VG.is_scannable_path("") is False


# ─── extract_written_text：三工具形 ───────────────────────────────────────────


def test_extract_write():
    assert VG.extract_written_text("Write", {"content": "V5 P3"}) == "V5 P3"


def test_extract_edit():
    assert VG.extract_written_text("Edit", {"new_string": "Wave 2"}) == "Wave 2"


def test_extract_multiedit():
    ti = {"edits": [{"new_string": "a"}, {"new_string": "b"}]}
    assert VG.extract_written_text("MultiEdit", ti) == "a\nb"


def test_extract_unknown_tool_empty():
    assert VG.extract_written_text("Read", {"file_path": "x"}) == ""

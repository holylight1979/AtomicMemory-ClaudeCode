"""verify_episodic_osc_marker.py — episodic「修改 atoms:」marker 與 oscillation 掃描對拍。

wg_evasion._detect_oscillation 依賴 episodic atom 內的「修改 atoms: a, b」行做跨
session 反覆修改偵測；驗證：
  - _generate_episodic_atom 產出含該 marker 行（資料源：state.modified_files 過濾
    /memory/ 下 .md、排除 MEMORY/_CHANGELOG*）
  - marker 格式與 _detect_oscillation 的解析邏輯 round-trip（前 session episodic +
    本 session 同 atom 再修 → 偵測到 oscillation）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import wg_episodic as ep  # noqa: E402
import wg_evasion as ev  # noqa: E402

_SUMMARY = {
    "knowledge_items": [],
    "work_areas": [{"area": "hooks", "count": 2}],
    "files_modified": 2,
    "primary_area": "hooks",
    "atoms_referenced": ["decisions"],
    "session_description": "",
    "dominant_intent": "debug",
    "prompt_count": 3,
    "intent_distribution": {"debug": 3},
    "related_episodic": [],
    "accessed_files": [],
    "vcs_queries": [],
}

_STATE = {
    "session": {"id": "sid-osc", "cwd": ""},
    "modified_files": [
        {"path": "C:/Users/u/.claude/memory/foo-atom.md"},
        {"path": "C:\\Users\\u\\.claude\\memory\\bar-atom.md"},
        {"path": "C:/Users/u/.claude/memory/MEMORY.md"},        # 排除
        {"path": "C:/Users/u/.claude/memory/_CHANGELOG.md"},    # 排除
        {"path": "C:/proj/src/main.py"},                        # 非 memory
    ],
    "edit_counts": {},
    "injected_atoms": [],
    "topic_tracker": {},
}


@pytest.fixture
def generated_content(tmp_path, monkeypatch):
    """monkeypatch 閘門/摘要/落檔，擷取 _generate_episodic_atom 產出的原文。"""
    captured = {}

    def fake_write_raw(path, content, source="", op=""):
        captured["path"] = path
        captured["content"] = content

    monkeypatch.setattr(ep, "_should_generate_episodic", lambda s, c: True)
    monkeypatch.setattr(ep, "_build_episodic_summary", lambda s: dict(_SUMMARY))
    monkeypatch.setattr(ep, "_generate_triggers", lambda s, wa: ["hooks"])
    monkeypatch.setattr(ep, "_resolve_episodic_dir", lambda s: (tmp_path, "global"))
    monkeypatch.setattr(ep, "write_raw", fake_write_raw)
    name = ep._generate_episodic_atom("sid-osc", dict(_STATE), {})
    assert name and "content" in captured
    return captured["content"]


def test_marker_line_present_and_filtered(generated_content):
    lines = [l for l in generated_content.split("\n") if "修改 atoms:" in l]
    assert len(lines) == 1, "episodic 產出應含唯一一行「修改 atoms:」marker"
    atoms_part = lines[0].split("修改 atoms:")[-1].strip()
    atoms = sorted(a.strip() for a in atoms_part.split(",") if a.strip())
    assert atoms == ["bar-atom", "foo-atom"]
    # 排除項不得出現
    assert "MEMORY" not in atoms and "_CHANGELOG" not in atoms


def test_oscillation_roundtrip(generated_content, tmp_path, monkeypatch):
    """marker 與 _detect_oscillation 掃描 regex 對拍：前 session episodic（他日）+
    本 session 同 atom 再修 → 2 個 unique session date → oscillation。"""
    ep_dir = tmp_path / "episodic"
    ep_dir.mkdir()
    # 把 Created 換成過去日期（模擬前 session 的 episodic）
    import re
    old = re.sub(
        r"^- Created:\s*\d{4}-\d{2}-\d{2}", "- Created: 2000-01-01",
        generated_content, count=1, flags=re.MULTILINE,
    )
    (ep_dir / "episodic-20000101-hooks.md").write_text(old, encoding="utf-8")
    monkeypatch.setattr(ev, "MEMORY_DIR", tmp_path)

    state = {
        "session": {"cwd": ""},
        "iteration_metrics": {"atoms_modified": ["foo-atom"]},
    }
    osc = ev._detect_oscillation(state, {})
    hit = [o for o in osc if o["atom"] == "foo-atom"]
    assert hit, f"foo-atom 應被偵測為 oscillation，實得 {osc}"
    assert hit[0]["count"] >= 2

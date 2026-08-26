"""verify_doc_counts.py — sync_doc_counts.py（人讀文件計數 SoT 同步）回歸測試。

驗證：
  - compute_counts 自洽（total == 各 realm 分項加總 == _atom_index.json 實際 atom 數）；
  - _apply 只換 marker 夾心、不動其他內容、不動換行；
  - 跑完 sync(--write) 後 sync(--check) 零 drift（idempotent）。
"""

import sys
from pathlib import Path

import pytest  # noqa: F401

CLAUDE = Path.home() / ".claude"
for _p in (CLAUDE / "tools", CLAUDE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sync_doc_counts as sdc  # noqa: E402


def test_compute_counts_self_consistent():
    import json
    vals = sdc.compute_counts(CLAUDE)
    total = int(vals["total"])
    parts = int(vals["core"]) + int(vals["feedback"]) + int(vals["failmode"]) + int(vals["local"])
    assert total == parts, (vals, "total 必等於 core+feedback+失敗模式+local")
    idx = json.loads((CLAUDE / sdc.ATOM_INDEX_REL).read_text(encoding="utf-8-sig"))
    assert total == len(idx.get("atoms", [])), "total 必等於 _atom_index.json 實際 atom 數（SoT）"
    assert vals["breakdown"].startswith(f"{total} atoms："), vals["breakdown"]


def test_apply_replaces_only_marker_inner():
    vals = {"total": "99", "breakdown": "B", "core": "1", "feedback": "2",
            "failmode": "3", "local": "4"}
    src = "前 <!-- atom-total -->5<!-- /atom-total --> 後\n下一行不動"
    out, hits = sdc._apply(src, vals)
    assert hits == 1
    assert out == "前 <!-- atom-total -->99<!-- /atom-total --> 後\n下一行不動"


def test_apply_noop_when_no_marker():
    out, hits = sdc._apply("沒有任何 marker 的純文字", sdc.compute_counts(CLAUDE))
    assert hits == 0
    assert out == "沒有任何 marker 的純文字"


def test_sync_idempotent_no_drift():
    # 先寫一次把所有 marked 文件對齊 SoT，再 check 必須零 drift（自動化的核心保證）。
    sdc.sync(CLAUDE, write=True)
    drift, msgs = sdc.sync(CLAUDE, write=False)
    assert drift is False, msgs


def test_compute_counts_failures_both_prefixes(tmp_path: Path):
    """Failures 家族兩個前綴（新址 memory/Failures/、舊址 _AIDocs/Failures/）都不算 core。"""
    import json
    mem = tmp_path / "memory"
    mem.mkdir()
    (mem / "_atom_index.json").write_text(json.dumps({"version": "1.0", "atoms": [
        {"name": "a", "path": "memory/版控/a.md"},
        {"name": "feedback-old", "path": "_AIDocs/Failures/feedback-old.md"},
        {"name": "feedback-new", "path": "memory/Failures/工作流/feedback-new.md"},
        {"name": "cognitive-patterns", "path": "memory/Failures/思考與決策/cognitive-patterns.md"},
        {"name": "t", "path": "_AIDocs/_atoms/Tools/t.md"},
    ]}), encoding="utf-8")
    vals = sdc.compute_counts(tmp_path)
    assert (vals["core"], vals["feedback"], vals["failmode"], vals["local"]) == ("1", "2", "1", "1")
    assert vals["breakdown"] == "5 atoms：core 1 + feedback 2 + 失敗模式 1 + local 1〔Tools1〕"

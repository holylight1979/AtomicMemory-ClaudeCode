"""verify_conflict_write_gate.py — write-check block 資格閘守門（症狀 4）。

不變式（LLM 判定是機率性的，block 必須高把握；降級一律入 warnings 浮出）：
1. 單次 CONTRADICT 不 block：需第二次獨立判定一致；翻面 → UNSTABLE，warn。
2. 兩次一致的 CONTRADICT 照常 block（防護不因降級機制而失守）。
3. incoming 落 projects/<X> 分區時，其他分區的相似 atom 不參與 block（跨專案
   相似陳述非事實衝突），warn 浮出；同分區照常 block。
4. 高相似 LLM ERROR → fail-open warn，不再保守判 contradict（壞掉的 LLM
   不得擋下所有寫入）。
5. 降級必有 warnings 訊號（可觀測性鐵律：不得無聲吞掉）。

全程 stub vector_search / ollama_classify——守語意，不依賴 Ollama 存活。
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "memory_conflict_detector", CLAUDE / "tools" / "memory-conflict-detector.py")
det = importlib.util.module_from_spec(_spec)
sys.modules["memory_conflict_detector"] = det
_spec.loader.exec_module(det)


def _hit(atom, sim, file_path):
    return {"atom_name": atom, "score": sim, "text": f"fact of {atom}",
            "file_path": file_path, "confidence": "[觀]", "layer": "shared"}


def _run(monkeypatch, hits, labels, subdir=None, declared=None):
    """labels: list — 依 ollama_classify 呼叫順序逐次回傳。declared：AI 的衝突宣告（規則 CONFLICT_DECLARED_BY_AI），留帳收掉不落真 Logs。
    衝突宣告只在守門總開關開時要求（出廠預設關）：外面沒明設 WG_V6 就開。"""
    if "WG_V6" not in os.environ:
        monkeypatch.setenv("WG_V6", "1")
    seq = iter(labels)
    monkeypatch.setattr(det, "vector_search", lambda *a, **k: hits)
    monkeypatch.setattr(det, "ollama_classify", lambda **k: next(seq))
    monkeypatch.setattr(det._hooks_module("wg_core"), "append_guard_log", lambda *a, **k: None)
    return det.run_write_check("incoming fact", None, "shared", subdir=subdir, declared=declared)


def _conflict(name):
    return [{"of": name, "verdict": "conflict", "why": "同一件事、同一範圍，說法相反"}]


def test_single_contradict_flips_to_unstable_warn(monkeypatch):
    out = _run(monkeypatch,
               [_hit("a", 0.9, "/p/.claude/memory/shared/a.md")],
               ["CONTRADICT", "AGREE"])  # 複驗翻面
    assert out["verdict"] != "contradict", out
    assert any("unstable" in w for w in out["warnings"]), out
    assert out["matches"][0]["classification"] == "UNSTABLE(AGREE)"


def test_double_confirmed_contradict_still_blocks(monkeypatch):
    """CONFLICT_DECLARED_BY_AI：複驗一致的 CONTRADICT 只是候選——沒宣告不寫（need_declaration），AI 宣告衝突才 contradict。"""
    out = _run(monkeypatch,
               [_hit("a", 0.9, "/p/.claude/memory/shared/a.md")],
               ["CONTRADICT", "CONTRADICT"])
    assert out["verdict"] == "need_declaration", out
    out = _run(monkeypatch,
               [_hit("a", 0.9, "/p/.claude/memory/shared/a.md")],
               ["CONTRADICT", "CONTRADICT"], declared=_conflict("a"))
    assert out["verdict"] == "contradict", out


def test_cross_partition_contradict_warns_not_blocks(monkeypatch):
    out = _run(monkeypatch,
               [_hit("appb-policy", 0.92,
                     "/repo/.claude/memory/projects/AppB/appb-policy.md")],
               ["CONTRADICT", "CONTRADICT"],  # 即使穩定矛盾
               subdir="projects/GameA")
    assert out["verdict"] != "contradict", out
    assert any("cross-partition" in w for w in out["warnings"]), out


def test_same_partition_contradict_still_blocks(monkeypatch):
    """同分區的穩定 CONTRADICT 照樣是候選：沒宣告不寫，宣告衝突才 contradict。"""
    out = _run(monkeypatch,
               [_hit("cfg", 0.92,
                     "/repo/.claude/memory/projects/AppB/cfg.md")],
               ["CONTRADICT", "CONTRADICT"],
               subdir="projects/AppB")
    assert out["verdict"] == "need_declaration", out
    out = _run(monkeypatch,
               [_hit("cfg", 0.92,
                     "/repo/.claude/memory/projects/AppB/cfg.md")],
               ["CONTRADICT", "CONTRADICT"],
               subdir="projects/AppB", declared=_conflict("cfg"))
    assert out["verdict"] == "contradict", out


def test_error_high_sim_fails_open_with_warning(monkeypatch):
    out = _run(monkeypatch,
               [_hit("a", 0.9, "/p/.claude/memory/shared/a.md"),
                _hit("b", 0.9, "/p/.claude/memory/shared/b.md")],
               ["ERROR", "AGREE"])  # 高相似 ERROR + 一個正常判定
    assert out["verdict"] != "contradict", out
    assert any("fail-open" in w for w in out["warnings"]), out


def test_all_llm_error_still_skips(monkeypatch):
    out = _run(monkeypatch,
               [_hit("a", 0.9, "/p/.claude/memory/shared/a.md")],
               ["ERROR"])
    assert out["skipped"] and out["verdict"] == "ok", out


def test_partition_parsers():
    p = det._partition_of_path
    assert p("D:/AI/repo/.claude/memory/projects/X/atom.md") == "projects/X"
    assert p("D:\\AI\\repo\\.claude\\memory\\projects\\X\\atom.md") == "projects/X"  # Windows 反斜線經 as_posix 正規化
    assert p("/repo/.claude/memory/shared/Tools/atom.md") is None
    s = det._partition_of_subdir
    assert s("projects/X") == "projects/X"
    assert s("projects/X/sub") == "projects/X"
    assert s("shared/Domain") is None
    assert s(None) is None

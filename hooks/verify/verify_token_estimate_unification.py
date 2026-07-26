"""verify_token_estimate_unification.py — token 估算單一口徑 + activation 中性值。

三個過去用 chars//4 的位點統一走 wg_core._estimate_tokens（CJK-aware，中文 ~1.5
tok/字；chars//4 對 CJK 低估 6 倍）：
  - wg_core.truncate_to_tokens（JIT 切片改二分截斷，取代 text[:budget*4]）
  - wg_atoms.load_atoms_within_budget
  - wg_atoms._truncate_context_by_activation（含 [Context budget: x/y] 尾行數字）

activation：無 access log 回中性 0.0（新 atom 不被截斷優先犧牲）；
_truncate_context_by_activation fallback root 掃描只採 sidecar 實存的 root
（防缺檔 root 的 0.0 蓋掉真實負值）；截斷提示行改組真實路徑（非寫死 memory/）。
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import wg_atoms  # noqa: E402
from wg_core import _estimate_tokens, truncate_to_tokens  # noqa: E402

_CJK_400 = "測" * 400  # _estimate_tokens ≈ 600；len//4 只算 100


# ─── truncate_to_tokens ──────────────────────────────────────────────


def test_truncate_to_tokens_cjk_respects_budget():
    out = truncate_to_tokens(_CJK_400, 100)
    assert _estimate_tokens(out) <= 100
    assert _CJK_400.startswith(out) and len(out) < len(_CJK_400)


def test_truncate_to_tokens_noop_when_within():
    assert truncate_to_tokens("short ascii", 100) == "short ascii"


# ─── load_atoms_within_budget ────────────────────────────────────────


def test_load_atoms_within_budget_cjk_aware(tmp_path):
    """CJK 重內容：len//4（≈100 tok）會誤判塞得下 150 budget；_estimate_tokens
    （≈600 tok）正確判超支 → 落 1-line 摘要而非全文。"""
    (tmp_path / "cjk.md").write_text(f"# 標題\n{_CJK_400}", encoding="utf-8")
    lines, injected, used = wg_atoms.load_atoms_within_budget(
        [("cjk", "", ["kw"])], tmp_path, 150, [],
    )
    assert injected == ["cjk"]
    assert "(full: Read" in lines[0], "CJK 超支內容應退 1-line 摘要"
    assert used == 0


# ─── _truncate_context_by_activation ─────────────────────────────────


def _write_access(d: Path, name: str, ts_list):
    (d / f"{name}.access.json").write_text(
        json.dumps({"timestamps": ts_list}), encoding="utf-8")


def test_budget_tail_line_uses_estimator():
    lines = ["中文內容測試行 with ascii tail"]
    expect = _estimate_tokens(lines[0])
    out = wg_atoms._truncate_context_by_activation(list(lines), limit=10_000)
    m = re.search(r"\[Context budget: (\d+)/10000 tokens\]", out[-1])
    assert m and int(m.group(1)) == expect


def test_new_atom_neutral_not_sacrificed_first(tmp_path):
    """old atom（遠古 access → 負 activation）先被截；new atom（無 sidecar → 0.0）保留。"""
    d_old, d_new = tmp_path / "old", tmp_path / "new"
    d_old.mkdir(), d_new.mkdir()
    _write_access(d_old, "aa", [time.time() - 30 * 86400])  # 遠古 → activation < 0
    assert wg_atoms.compute_activation("aa", d_old) < 0
    assert wg_atoms.compute_activation("bb", d_new) == 0.0

    lines = [f"[Atom:aa]\n{_CJK_400}", f"[Atom:bb]\n{_CJK_400}"]
    src = {"aa": d_old, "bb": d_new}
    out = wg_atoms._truncate_context_by_activation(list(lines), limit=700, source_dirs=src)
    joined = "\n".join(out)
    assert "[Atom:aa] (truncated" in joined, "低 activation（old）應先被截"
    assert "[Atom:bb] (truncated" not in joined, "新 atom（中性 0.0）不該優先犧牲"


def test_truncation_hint_uses_real_path(tmp_path):
    """截斷提示不再寫死 memory/<name>.md——用 source_dirs 組真實路徑。"""
    d = tmp_path / "elsewhere"
    d.mkdir()
    lines = [f"[Atom:zz]\n{_CJK_400}"]
    out = wg_atoms._truncate_context_by_activation(
        list(lines), limit=50, source_dirs={"zz": d},
    )
    joined = "\n".join(out)
    assert "(truncated" in joined
    assert str(d / "zz.md") in joined.replace("/", "\\") or (d / "zz.md").as_posix() in joined


def test_fallback_root_skips_missing_sidecar(tmp_path, monkeypatch):
    """無 source_dirs 時：只採 sidecar 實存 root 的 activation——缺檔 root 的中性
    0.0 不得蓋掉真實負值（截斷行 activation 顯示 < 0）。"""
    mem, epi = tmp_path / "memory", tmp_path / "memory" / "episodic"
    epi.mkdir(parents=True)
    _write_access(mem, "cc", [time.time() - 30 * 86400])
    monkeypatch.setattr(wg_atoms, "MEMORY_DIR", mem)
    monkeypatch.setattr(wg_atoms, "EPISODIC_DIR", epi)
    monkeypatch.setattr(wg_atoms, "discover_all_project_memory_dirs", lambda: [])

    out = wg_atoms._truncate_context_by_activation([f"[Atom:cc]\n{_CJK_400}"], limit=50)
    m = re.search(r"activation=(-?\d+\.\d+)", "\n".join(out))
    assert m, "應出現截斷行含 activation 值"
    assert float(m.group(1)) < 0, "實存 sidecar 的負 activation 不該被缺檔 root 的 0.0 蓋掉"

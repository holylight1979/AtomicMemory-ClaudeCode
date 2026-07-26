"""verify_kw_match_fastpath.py — trigger keyword 比對快路徑（UPS CPU 熱點修補）。

契約（wg_atoms）：
- _kw_match 語意不變：ASCII word-boundary（"fix" 不中 "prefix"/"fix-up" 型連字）、
  CJK 子字串
- 子字串預篩零誤差：kw 非 prompt 子字串 → False（與 regex 必然一致）
- _kw_pattern lru_cache：同 kw 回同一 compiled pattern（不再觸發 re 內建
  512 cache 反覆整包重編譯）
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest  # noqa: F401

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402


def test_ascii_word_boundary_semantics():
    assert wg_atoms._kw_match("fix", "please fix this")
    assert not wg_atoms._kw_match("fix", "the prefix here")   # 前貼字元
    assert not wg_atoms._kw_match("fix", "run fixup now")     # 後貼字元
    assert not wg_atoms._kw_match("fix", "a fix-up thing")    # 連字號視同字元
    assert wg_atoms._kw_match("fix", "fix")                   # 全字串
    assert wg_atoms._kw_match("fix", "(fix)")                 # 標點邊界


def test_substring_prefilter_no_false_negative():
    # 預篩只擋「kw 非子字串」——該情況 regex 也必不中
    assert not wg_atoms._kw_match("vector", "完全無關的內容")
    assert wg_atoms._kw_match("vector", "the vector service")


def test_cjk_substring():
    assert wg_atoms._kw_match("記憶", "原子記憶系統")
    assert not wg_atoms._kw_match("記憶", "原子系統")


def test_pattern_memoized():
    wg_atoms._kw_pattern.cache_clear()
    p1 = wg_atoms._kw_pattern("somekeyword")
    p2 = wg_atoms._kw_pattern("somekeyword")
    assert p1 is p2
    info = wg_atoms._kw_pattern.cache_info()
    assert info.hits == 1 and info.misses == 1

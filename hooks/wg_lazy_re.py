"""wg_lazy_re.py — 模組層的正規表示式改成第一次用到才編譯（HOOK_IMPORT_ON_USE）。

為什麼：每個 hook 事件都是新起的 Python 行程，wg_release_rules、wg_evasion 等模組 import 時就把上百條 re.compile 全編一次
（re 的快取只活在行程裡），一次事件約 50 ms，多數樣式這次事件根本用不到。
怎麼用：`X_RE = lazy_re(r"...", re.I)`，用法同編好的 Pattern（.search／.match／.sub／.finditer…）；.pattern 不編譯就拿得到
（組合別的樣式用）。不能當成 re.sub(X_RE, …) 的第一個參數或 isinstance(X_RE, re.Pattern)——要那樣用就叫 .compiled。
"""
from __future__ import annotations

import re
from typing import Any


class LazyPattern:
    __slots__ = ("_src", "_flags", "_rx")

    def __init__(self, pattern: str, flags: int = 0) -> None:
        self._src, self._flags, self._rx = pattern, flags, None

    @property
    def pattern(self) -> str:
        return self._src

    @property
    def compiled(self) -> "re.Pattern[str]":
        if self._rx is None:
            self._rx = re.compile(self._src, self._flags)
        return self._rx

    def __getattr__(self, name: str) -> Any:
        return getattr(self.compiled, name)

    def __repr__(self) -> str:
        return f"lazy_re({self._src!r}, {self._flags})"


def lazy_re(pattern: str, flags: int = 0) -> LazyPattern:
    return LazyPattern(pattern, flags)

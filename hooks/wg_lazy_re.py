"""wg_lazy_re.py — 模組層的正規表示式與模組改成第一次用到才編譯／載入（HOOK_IMPORT_ON_USE）。

為什麼：每個 hook 事件都是新起的 Python 行程，wg_release_rules、wg_evasion 等模組 import 時就把上百條 re.compile 全編一次
（re 的快取只活在行程裡），一次事件約 50 ms，多數樣式這次事件根本用不到。寫碼守門的模組（連鎖斷路器、改舊測試、動資料檔…）
也一樣：守門關、或這次事件跟寫程式無關時一行都不跑，卻每次在 handler 頂端整包載入。
怎麼用：
- `X_RE = lazy_re(r"...", re.I)`，用法同編好的 Pattern（.search／.match／.sub／.finditer…）；.pattern 不編譯就拿得到
  （組合別的樣式用）。不能當成 re.sub(X_RE, …) 的第一個參數或 isinstance(X_RE, re.Pattern)——要那樣用就叫 .compiled。
- `chain_store = lazy_module("chain_store")` 取代模組層的 `import chain_store`：第一次取它的屬性才真的執行模組。
"""
from __future__ import annotations

import re
import sys
import types
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


def lazy_module(name: str) -> types.ModuleType:
    """回模組 name，第一次取屬性才執行（標準庫 importlib.util.LazyLoader）；已經載過就直接回 sys.modules 那一份。
    回的就是模組本身、登記在 sys.modules：別處 `import name` 拿到同一份，測試 monkeypatch.setattr(mod.X, …) 照常生效。
    找不到模組當下就丟 ModuleNotFoundError（同 import）；模組執行時才出的錯延到第一次取屬性才丟。"""
    mod = sys.modules.get(name)
    if mod is not None:
        return mod
    import importlib.util   # 只用正規表示式的模組（wg_core 等）不必付這一份
    spec = importlib.util.find_spec(name)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)
    spec.loader = importlib.util.LazyLoader(spec.loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

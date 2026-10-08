#!/usr/bin/env python3
"""preserve-check.py: 行為保持重構的等值證法。預期值來自舊源碼（或舊產物），實際值來自新產物，兩邊來源必不同。

用法:
  python preserve-check.py --expected-from <舊源碼或 .json 預期表> --actual-from <新產物 .py>
                           --mutation <order|side_effect|boundary> --func <查表函式>
                           [--order-func <回序列的函式>] [--effect <副作用函式名，預設 log>]
                           [--actual-cmd "<指令，{key} 代入>"]

三類變異各跑一次（每次都先比對所有列出的 case→值，常數改壞任何一次都 FAIL）：
  order        --order-func 回的序列必須逐項同序。
  side_effect  每個 case 觸發的副作用（--effect 函式的引數）必須相同；守衛跑到別的 case 就 FAIL。
  boundary     沒列在舊碼 case 裡的值（整數鍵取 min-1、max+1；字串鍵取 "" 與 "__unlisted__"）必須落到同一個預設值。

預期表怎麼來（不手抄）：
  .py／.cs 等源碼：regex 解析 --func 函式體的 `if/elif/case X == K:`／`case K:`／`else:`／`default:` 與其下的
  `return V`、`--effect(...)` 呼叫；--order-func 函式體的 `return [...]`。源碼只被讀，不被執行。
  .json：{"values": {key: value}, "default": value, "effects": {key: [args]}, "order": [...]}（別的工具解析好的表，
  例如從 roslyn 或 svn BASE 產出；json 的 key 一律字串，比對時用 str() 對齊）。

實際值怎麼來（必跑，不讀碼）：
  預設 import --actual-from 的 .py，逐 key 呼叫 --func；--effect 被換成記錄器；--order-func 直接呼叫。
  --actual-cmd：改用外部指令，{key} 代入，取 stdout 最後一個非空行當值；order 取全部非空行；
  side_effect 在這個執行器不支援（會明說並 FAIL）。

輸出：差異逐條列出，尾行 `PRESERVE_CHECK PASS` 或 `PRESERVE_CHECK FAIL`。exit 0 相同、1 有差異、2 拒收。
拒收（不是行為差異、但也不放行）：同路徑；預期表零 case；舊源碼函式體裡有解析器不認的分支寫法（`if x in …`、`match`、巢狀條件）；
外部執行器任一次非零 exit；--actual-cmd 跑 side_effect。
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

MUTATIONS = ("order", "side_effect", "boundary")
_KEY_RE = re.compile(r"^\s*(?:if|elif|else if|case)\b[^:]*?==\s*([^\s:]+)\s*:|^\s*case\s+([^\s:]+)\s*:")
_DEFAULT_RE = re.compile(r"^\s*(?:else|default)\s*:")
_RETURN_RE = re.compile(r"^\s*return\s+(.+?)\s*;?\s*$")
_DEF_RE = re.compile(r"^(\s*)(?:def\s+|(?:public|private|static|internal|protected|override|\s)*\w+\s+)(\w+)\s*\(")
_SEQ_RE = re.compile(r"return\s+(\[.*?\]|\(.*?\))\s*;?\s*$", re.DOTALL)
_BRANCH_RE = re.compile(r"^\s*(?:if|elif|else if|case|match)\b")


class Reject(Exception):
    """拒收：用法或材料不合，不是行為差異。"""


def _lit(s: str):
    try:
        return ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return s.strip().strip(";")


def _body(lines: list, func: str) -> list:
    """取 func 的函式體行（到下一個同層或更外層的函式定義為止）。"""
    start, indent = None, ""
    for i, line in enumerate(lines):
        m = _DEF_RE.match(line)
        if m and m.group(2) == func:
            start, indent = i + 1, m.group(1)
            break
    if start is None:
        raise Reject(f"舊源碼裡找不到函式 {func}")
    body = []
    for line in lines[start:]:
        m = _DEF_RE.match(line)
        if m and len(m.group(1)) <= len(indent):
            break
        body.append(line)
    return body


def parse_expected_source(text: str, func: str, order_func: str, effect: str) -> dict:
    lines = text.splitlines()
    values, effects, default, cur = {}, {}, None, None
    effect_re = re.compile(r"\b" + re.escape(effect) + r"\((.*)\)")
    for line in _body(lines, func):
        m = _KEY_RE.match(line)
        if m:
            cur = _lit(m.group(1) or m.group(2))
            continue
        if _DEFAULT_RE.match(line):
            cur = "__default__"
            continue
        if _BRANCH_RE.match(line):
            raise Reject(f"舊源碼 {func} 有解析器不認的分支寫法，不能宣稱全枚舉：{line.strip()!r}（先用專案工具解析成 .json 再餵）")
        m = effect_re.search(line)
        if m and cur is not None and cur != "__default__":
            effects.setdefault(cur, []).append(_lit(m.group(1)))
            continue
        m = _RETURN_RE.match(line)
        if m and cur is not None:
            if cur == "__default__":
                default = _lit(m.group(1))
            else:
                values.setdefault(cur, _lit(m.group(1)))
            cur = None
    order = None
    if order_func:
        m = _SEQ_RE.search("\n".join(_body(lines, order_func)))
        if not m:
            raise Reject(f"舊源碼 {order_func} 裡找不到 return [...] 序列")
        order = list(_lit(m.group(1)))
    return {"values": values, "default": default, "effects": effects, "order": order}


def load_expected(path: Path, func: str, order_func: str, effect: str) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        d = json.loads(text)
        table = {"values": dict(d.get("values", {})), "default": d.get("default"),
                 "effects": {k: list(v) for k, v in (d.get("effects") or {}).items()}, "order": d.get("order")}
    else:
        table = parse_expected_source(text, func, order_func, effect)
    if not table["values"]:
        raise Reject(f"預期表 {path.name} 裡沒有任何 case→值（零 case 不能當證明）")
    return table


def boundary_probes(keys: list) -> list:
    if keys and all(isinstance(k, int) and not isinstance(k, bool) for k in keys):
        return [min(keys) - 1, max(keys) + 1]
    return ["", "__unlisted__"]


class PyRunner:
    """import 新產物，逐 key 實跑。"""

    def __init__(self, path: Path, func: str, order_func: str, effect: str):
        spec = importlib.util.spec_from_file_location("_preserve_actual_" + path.stem, path)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        if not hasattr(self.mod, func):
            raise Reject(f"新產物裡沒有函式 {func}")
        self.func, self.order_func, self.effect = func, order_func, effect

    def value(self, key):
        return getattr(self.mod, self.func)(key)

    def effects_of(self, key) -> list:
        seen = []
        setattr(self.mod, self.effect, lambda *a: seen.append(a[0] if len(a) == 1 else a))
        getattr(self.mod, self.func)(key)
        return seen

    def order(self) -> list:
        if not self.order_func or not hasattr(self.mod, self.order_func):
            raise Reject("order 變異要 --order-func，且新產物要有這個函式")
        return list(getattr(self.mod, self.order_func)())


class CmdRunner:
    """外部指令當執行器：{key} 代入。"""

    def __init__(self, cmd: str, cwd: Path):
        self.cmd, self.cwd = cmd, cwd

    def _run(self, key) -> list:
        proc = subprocess.run(self.cmd.replace("{key}", str(key)), shell=True, cwd=str(self.cwd),
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise Reject(f"外部執行器 key={key!r} exit {proc.returncode}，結果不可信：{proc.stderr.strip()[-200:]}")
        return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]

    def value(self, key):
        out = self._run(key)
        return out[-1] if out else None

    def effects_of(self, key):
        raise Reject("--actual-cmd 執行器不支援 side_effect 變異（看不到副作用）；用 Python 執行器或另寫執行器")

    def order(self) -> list:
        return self._run("")


def _same(exp, act) -> bool:
    return exp == act or str(exp) == str(act)


def compare(expected: dict, runner, mutation: str) -> list:
    diffs = []
    for key, exp in expected["values"].items():
        act = runner.value(_lit(str(key)) if isinstance(key, str) else key)
        if not _same(exp, act):
            diffs.append(f"值不同 key={key!r}: 預期 {exp!r} 實際 {act!r}")
    if mutation == "boundary":
        keys = [_lit(str(k)) if isinstance(k, str) else k for k in expected["values"]]
        for probe in boundary_probes(keys):
            act = runner.value(probe)
            if not _same(expected["default"], act):
                diffs.append(f"邊界不同 key={probe!r}: 預期預設 {expected['default']!r} 實際 {act!r}")
    elif mutation == "side_effect":
        keys = [_lit(str(k)) if isinstance(k, str) else k for k in expected["values"]]
        for key in keys:
            exp = expected["effects"].get(key, expected["effects"].get(str(key), []))
            act = runner.effects_of(key)
            if [str(e) for e in exp] != [str(a) for a in act]:
                diffs.append(f"副作用不同 key={key!r}: 預期 {exp!r} 實際 {act!r}")
    elif mutation == "order":
        exp, act = expected["order"], runner.order()
        if exp is None:
            raise Reject("預期表沒有 order（源碼要給 --order-func，json 要有 order）")
        if [str(e) for e in exp] != [str(a) for a in act]:
            diffs.append(f"順序不同: 預期 {exp!r} 實際 {act!r}")
    return diffs


def run(args) -> int:
    a, b = Path(args.expected_from), Path(args.actual_from)
    if os.path.realpath(a) == os.path.realpath(b):
        raise Reject("expected 與 actual 是同一路徑：預期與實際必須來自不同來源，否則證的是自己等於自己")
    if not a.is_file() or not b.is_file():
        raise Reject(f"檔案不存在：{a if not a.is_file() else b}")
    expected = load_expected(a, args.func, args.order_func, args.effect)
    runner = CmdRunner(args.actual_cmd, b.parent) if args.actual_cmd else PyRunner(b, args.func, args.order_func, args.effect)
    diffs = compare(expected, runner, args.mutation)
    for d in diffs:
        print("  - " + d)
    print(f"  cases={len(expected['values'])} mutation={args.mutation} expected_from={a.name} actual_from={b.name}")
    print("PRESERVE_CHECK " + ("PASS" if not diffs else "FAIL"))
    return 0 if not diffs else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="行為保持等值證法：舊源碼解析預期表 vs 新產物實跑")
    ap.add_argument("--expected-from", required=True, help="舊源碼（.py/.cs...）或 .json 預期表")
    ap.add_argument("--actual-from", required=True, help="新產物 .py（或 --actual-cmd 的工作目錄所在檔）")
    ap.add_argument("--mutation", required=True, choices=MUTATIONS)
    ap.add_argument("--func", required=True, help="查表函式名")
    ap.add_argument("--order-func", default="", help="回序列的函式名（order 變異用）")
    ap.add_argument("--effect", default="log", help="副作用函式名（side_effect 變異用）")
    ap.add_argument("--actual-cmd", default="", help="外部執行器指令，{key} 代入")
    args = ap.parse_args(argv)
    try:
        return run(args)
    except Reject as e:
        print("  拒收：" + str(e))
        print("PRESERVE_CHECK FAIL")
        return 2
    except Exception as e:  # 內部錯誤也不得靜默放行
        print(f"  內部錯誤：{type(e).__name__}: {e}", file=sys.stderr)
        print("PRESERVE_CHECK FAIL")
        return 2


if __name__ == "__main__":
    sys.exit(main())

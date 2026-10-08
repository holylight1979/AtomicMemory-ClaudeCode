#!/usr/bin/env python3
"""prebuild-check.template.py: 打包前檢查樣板。拷到專案（例 `<專案根>/_tools/prebuild_check.py`），接在打包／CI 的第一步。

做什麼：讀 `<專案根>/.claude/overview-hub.json` 的 `prebuild_checks[]`，依序跑每一項，任一項不符預期就 exit 1，
後面的項目照跑（一次把全部 FAIL 列完），尾行印 `PREBUILD_CHECK PASS` 或 `PREBUILD_CHECK FAIL`。

怎麼跑：
  python prebuild_check.py                 # 專案根＝目前目錄
  python prebuild_check.py --root <專案根>

overview-hub.json 要有的鍵：
  "prebuild_checks": [
    {"name": "equiv",  "cmd": "python _tools/check_equivalence.py", "expect": "PASS"},
    {"name": "smells", "cmd": "python _tools/scan_smells.py",       "expect": "DONE"},
    {"name": "legacy", "cmd": "python _tools/old_checker.py", "expect": "PASS",
     "sentinel_regex": "^ALL GOOD$"}
  ],
  "defects_doc": "Server/defects.md"      # 字串或字串陣列；內建項 defect_shape 讀它

每項怎麼判：
  - cmd 在專案根以 shell 執行；exit code 非 0 → FAIL。
  - expect "PASS"：輸出最後一個非空行必須完整符合 `^[A-Z][A-Z0-9_]*_CHECK PASS$`；只印 `X_CHECK` 缺字尾不算。
  - expect "DONE"：最後一個非空行必須完整符合 `^[A-Z][A-Z0-9_]* DONE( \\w+=\\S+)*$`（量測類，數字是尺不是判決）。
  - 有 sentinel_regex：改用它判最後一個非空行（既有工具尾行格式不同時用，不改工具）。
  - 內建項 defect_shape（不用登記，defects_doc 有設就跑）：把病灶文件裡每條 `shape:` 當 regex，掃 `git diff --cached`
    的新增行（去掉行首 +），任一命中 → FAIL 並列出命中行；defects_doc 指的檔不存在 → FAIL（不靜默）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

HUB_REL = ".claude/overview-hub.json"
SENTINEL = {
    "PASS": re.compile(r"^[A-Z][A-Z0-9_]*_CHECK PASS$"),
    "DONE": re.compile(r"^[A-Z][A-Z0-9_]* DONE( \w+=\S+)*$"),
}
_SHAPE_LINE = re.compile(r"^\s*(?:[-*]\s*)?shape:\s*(.+?)\s*$")
_ROW_SPLIT = re.compile(r"(?<!\\)\|")


def load_hub(root: Path) -> dict:
    p = root / HUB_REL
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def last_nonempty_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        if line.strip():
            return line.rstrip()
    return ""


def judge_output(output: str, expect: str, sentinel_regex: str = "") -> tuple:
    """回 (ok, 理由)。只看最後一個非空行。"""
    tail = last_nonempty_line(output)
    if sentinel_regex:
        ok = re.search(sentinel_regex, tail) is not None
        return ok, f"尾行 {tail!r} 不符 sentinel_regex {sentinel_regex!r}" if not ok else ""
    pat = SENTINEL.get(expect)
    if pat is None:
        return False, f"expect 只能是 PASS 或 DONE，得到 {expect!r}"
    ok = pat.match(tail) is not None
    return ok, "" if ok else f"尾行 {tail!r} 不符 expect={expect}"


def run_check(check: dict, root: Path) -> tuple:
    """跑一項登記的檢查；回 (ok, 理由)。"""
    name = check.get("name", "?")
    cmd = check.get("cmd", "")
    if not cmd:
        return False, f"{name}: 沒有 cmd"
    proc = subprocess.run(cmd, shell=True, cwd=str(root), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
    if proc.returncode != 0:
        return False, f"{name}: exit {proc.returncode}（尾行 {last_nonempty_line(output)!r}）"
    ok, why = judge_output(proc.stdout, str(check.get("expect", "PASS")), check.get("sentinel_regex", ""))
    return ok, "" if ok else f"{name}: {why}"


def parse_shapes(defects_text: str) -> list:
    """病灶文件裡的 shape：表格第 7 欄 `shape: <regex>`（`\\|` 讀成 `|`），或單獨一行 `shape: <regex>`。"""
    shapes = []
    for line in defects_text.splitlines():
        if line.lstrip().startswith("|"):
            for cell in _ROW_SPLIT.split(line):
                cell = cell.strip().strip("`").strip()
                if cell.startswith("shape:"):
                    shapes.append(cell[len("shape:"):].strip().strip("`").replace("\\|", "|"))
            continue
        m = _SHAPE_LINE.match(line)
        if m:
            shapes.append(m.group(1).strip("`"))
    return [s for s in shapes if s and s != "無"]


def added_lines(diff_text: str) -> list:
    return [ln[1:] for ln in diff_text.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


def staged_diff(root: Path) -> str:
    proc = subprocess.run(["git", "diff", "--cached"], cwd=str(root), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError("git diff --cached 失敗：" + proc.stderr.strip())
    return proc.stdout


def defect_shape(root: Path, defects_docs, diff_text: str) -> tuple:
    """內建項：病灶形狀掃 staged diff 新增行。回 (ok, 理由列表)。"""
    docs = [defects_docs] if isinstance(defects_docs, str) else list(defects_docs or [])
    reasons = []
    shapes = []
    for rel in docs:
        p = root / rel
        if not p.is_file():
            reasons.append(f"defect_shape: 病灶文件不存在 {rel}")
            continue
        shapes += parse_shapes(p.read_text(encoding="utf-8"))
    lines = added_lines(diff_text)
    for shape in shapes:
        try:
            pat = re.compile(shape)
        except re.error as e:
            reasons.append(f"defect_shape: shape 不是合法 regex {shape!r}（{e}）")
            continue
        hits = [ln for ln in lines if pat.search(ln)]
        if hits:
            reasons.append(f"defect_shape: 新增行命中形狀 {shape!r}：" + " ‖ ".join(h.strip() for h in hits[:5]))
    return not reasons, reasons


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="打包前檢查：prebuild_checks[] 任一不符就 exit 1")
    ap.add_argument("--root", default=".", help="專案根（含 .claude/overview-hub.json）")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    failures = []
    try:
        hub = load_hub(root)
        for check in hub.get("prebuild_checks", []) or []:
            ok, why = run_check(check, root)
            print(("  ok   " if ok else "  FAIL ") + str(check.get("name", "?")) + ("" if ok else "：" + why))
            if not ok:
                failures.append(why)
        if hub.get("defects_doc"):
            ok, reasons = defect_shape(root, hub["defects_doc"], staged_diff(root))
            print("  ok   defect_shape" if ok else "  FAIL defect_shape")
            for r in reasons:
                print("         " + r)
            failures += reasons
    except Exception as e:  # 任何內部錯誤都算 FAIL，不得靜默放行
        print(f"  FAIL 內部錯誤：{e}")
        failures.append(str(e))
    print("PREBUILD_CHECK " + ("PASS" if not failures else "FAIL"))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())

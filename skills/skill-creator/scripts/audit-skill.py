#!/usr/bin/env python3
"""audit-skill: 稽核 Claude Code skill 是否符合官方格式與 skill-creator 本機規範。

用法:
  python audit-skill.py <skill 根目錄>
  python audit-skill.py <skill 根目錄> --strict          # warning 升 fail
  python audit-skill.py <skill 根目錄> --scope project   # 專案 skill：不檢絕對路徑／evals

輸出 JSON 到 stdout (UTF-8)，exit 0 = 通過，1 = fail。

兩級判定（每筆附 src 欄：official / local）：
  fails    — 真格式問題：SKILL.md 不存在、frontmatter 解析失敗、缺 description
             （官方所有欄位皆非必填、description 為 recommended 且是自動觸發唯一依據，
             本機把它列硬性；name 官方預設目錄名，缺了只警告）。
  warnings — 官方 Tip（500 行）與本機建議（triggers / pattern / evals / 分層 / 腳本衛生 /
             非官方拼法如 userInvocable）。不影響 exit code，除非 --strict。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

try:
    import yaml  # pyyaml：有就用，沒有退容錯的逐行解析
except Exception:  # pragma: no cover
    yaml = None

# --- 常數 ---
LINE_OFFICIAL_LIMIT = 500   # 官方 Tip：「Keep SKILL.md under 500 lines」— 建議，非紅線
LINE_SOFT_LIMIT = 200       # 本機目標
DESC_MIN_CHARS = 30
TRIGGERS_MIN = 3
REFS_TOC_THRESHOLD = 300
INLINE_CODE_BLOCK_LINES = 30
VALID_PATTERNS = ["tool-wrapper", "generator", "reviewer", "inversion", "pipeline"]
# 官方 frontmatter 欄位（code.claude.com/docs/en/skills）
OFFICIAL_FIELDS = {
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable", "allowed-tools", "disallowed-tools",
    "model", "effort", "context", "agent", "background", "hooks", "paths", "shell",
    "metadata", "license", "compatibility",
}
# 本機自訂欄位（skill-creator 用：觸發關鍵字 / 設計模式），harness 不讀
LOCAL_FIELDS = {"triggers", "pattern"}
# 非官方拼法 → 官方拼法（harness 不認舊拼法；user-invocable 預設 true 所以行為未壞，但應對齊）
LEGACY_SPELLINGS = {
    "userInvocable": "user-invocable",
    "disableModelInvocation": "disable-model-invocation",
}
# 跨環境通用的「絕對路徑」偵測 — 抓形式，不寫死特定專案 / 使用者
ABS_PATH_PATTERNS = [
    r"[A-Za-z]:\\[A-Za-z0-9_\-一-鿿][A-Za-z0-9_\\\-一-鿿]{2,}",  # Windows: C:\xxx\
    r"/(Users|home)/[A-Za-z0-9_\-]+/",                                            # Unix: /Users/x/ /home/x/
]
PATH_PLACEHOLDER_HINT = "<project> / <workspace> / ~/ / ./src/..."


def _fail(id_: str, msg: str, src: str = "official") -> dict:
    return {"id": id_, "msg": msg, "src": src}


def _warn(id_: str, msg: str, src: str = "local") -> dict:
    return {"id": id_, "msg": msg, "src": src}


def _scalar(v) -> str:
    """frontmatter 值統一成字串：list → 逗號串、bool → true/false、None → ''。"""
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return ", ".join(_scalar(x) for x in v)
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v).strip()


def _parse_frontmatter_lines(body: str) -> dict:
    """容錯逐行解析（無 pyyaml 時）：key: value；`>` / `|` / 縮排續行併回上一個 key。"""
    fm: dict = {}
    last_key = None
    for raw in body.split("\n"):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        kv = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if kv and not line.startswith((" ", "\t")):
            last_key = kv.group(1)
            val = kv.group(2).strip()
            fm[last_key] = "" if val in (">", "|", ">-", "|-") else val
            continue
        if last_key is not None:
            fm[last_key] = (fm[last_key] + " " + line.strip()).strip()
    return fm


def parse_frontmatter(text: str) -> tuple:
    """回 (frontmatter dict, 結束行號, error)。無 frontmatter → ({}, 0, None)；解析失敗 → ({}, n, msg)。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", text, re.DOTALL)
    if not m:
        return {}, 0, None
    body = m.group(1)
    end_line = text[: m.end()].count("\n")
    if yaml is None:
        return _parse_frontmatter_lines(body), end_line, None
    try:
        data = yaml.safe_load(body)
    except Exception as e:
        return {}, end_line, f"YAML 解析失敗：{str(e).splitlines()[0]}"
    if data is None:
        return {}, end_line, None
    if not isinstance(data, dict):
        return {}, end_line, "frontmatter 不是 key: value 映射"
    return {str(k): _scalar(v) for k, v in data.items()}, end_line, None


def check_skill_md(skill_dir: Path, scope: str) -> tuple:
    fails, warns = [], []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        fails.append(_fail("missing-skill-md", f"SKILL.md not found in {skill_dir}"))
        return fails, warns

    text = skill_md.read_text(encoding="utf-8")
    lines = text.split("\n")
    line_count = len(lines)

    # --- Fail（官方格式）：frontmatter 解析 / description ---
    fm, _, fm_err = parse_frontmatter(text)
    if fm_err:
        fails.append(_fail("frontmatter-unparseable", f"frontmatter {fm_err}"))
    elif not fm:
        fails.append(_fail(
            "frontmatter-missing",
            "SKILL.md 無 YAML frontmatter（--- ... --- 區塊）；description 是自動觸發唯一依據，本機列必填",
        ))
    elif not fm.get("description"):
        fails.append(_fail(
            "frontmatter-missing-description",
            "frontmatter 缺 description（官方 recommended、自動觸發唯一依據；本機列必填）",
        ))

    if fm and not fm.get("name"):
        warns.append(_warn("frontmatter-missing-name",
                           "frontmatter 缺 name（官方預設用目錄名；建議顯式寫，與目錄同名）", src="official"))
    if fm and fm.get("name") and fm["name"] != skill_dir.name:
        warns.append(_warn(
            "name-dir-mismatch",
            f"name={fm['name']!r} 與目錄名 {skill_dir.name!r} 不同（`/` 選單以 name 顯示，易混淆）",
            src="official",
        ))

    # --- Warning（官方拼法）---
    for legacy, official in LEGACY_SPELLINGS.items():
        if legacy in fm:
            warns.append(_warn(
                "frontmatter-legacy-spelling",
                f"frontmatter 用 `{legacy}`，官方拼法是 `{official}`（harness 不讀舊拼法，等同未設定）",
                src="official",
            ))
    unknown = sorted(k for k in fm if k not in OFFICIAL_FIELDS | LOCAL_FIELDS | set(LEGACY_SPELLINGS))
    if unknown:
        warns.append(_warn(
            "frontmatter-unknown-fields",
            f"frontmatter 含非官方、非本機欄位 {unknown}（harness 忽略；自訂資料建議放 `metadata:`）",
            src="official",
        ))

    # --- Warning（官方 Tip）：SKILL.md 行數 ---
    if line_count > LINE_OFFICIAL_LIMIT:
        warns.append(_warn(
            "skill-md-over-500",
            f"SKILL.md {line_count} 行 > {LINE_OFFICIAL_LIMIT}（官方 Tip：keep under 500 lines，細節移 references/）",
            src="official",
        ))
    elif line_count > LINE_SOFT_LIMIT:
        warns.append(_warn("skill-md-large", f"SKILL.md {line_count} 行 > {LINE_SOFT_LIMIT} 本機目標，建議抽 references/"))

    # --- Warning（本機）：絕對路徑（僅 global scope）---
    if scope == "global":
        hits = []
        for pat in ABS_PATH_PATTERNS:
            for m in re.finditer(pat, text):
                line_no = text[: m.start()].count("\n") + 1
                hits.append(f"line {line_no}: {m.group()!r}")
        if hits:
            warns.append(_warn(
                "absolute-path",
                f"SKILL.md 含絕對路徑（{len(hits)} 處），全域 skill 建議改佔位符（{PATH_PLACEHOLDER_HINT}）：{hits[:3]}",
            ))

    # --- Warning（本機）：description 字數 ---
    desc = fm.get("description", "")
    if desc and len(desc) < DESC_MIN_CHARS:
        warns.append(_warn("description-short", f"description 僅 {len(desc)} 字 < {DESC_MIN_CHARS}（可能 undertrigger）"))

    # --- Warning（本機建議）：triggers ---
    triggers_raw = fm.get("triggers", "")
    triggers = [t.strip() for t in triggers_raw.split(",") if t.strip()] if triggers_raw else []
    if fm and not triggers:
        warns.append(_warn(
            "triggers-missing",
            "frontmatter 無 `triggers`（本機自訂欄位，harness 不讀；skill-creator 用它列觸發措辭變體，建議補 ≥ 3 個）",
        ))
    elif 0 < len(triggers) < TRIGGERS_MIN:
        warns.append(_warn("triggers-few", f"triggers 僅 {len(triggers)} 個 < {TRIGGERS_MIN}（覆蓋面不足）"))

    # --- Warning（本機建議）：pattern ---
    pattern = fm.get("pattern", "").strip()
    if fm and not pattern:
        warns.append(_warn("pattern-missing", f"frontmatter 無 `pattern`（本機自訂欄位；建議標 5 模式之一：{VALID_PATTERNS}）"))
    elif pattern and pattern not in VALID_PATTERNS:
        warns.append(_warn("pattern-invalid", f"pattern={pattern!r} 不在白名單，建議用標準模式：{VALID_PATTERNS}"))

    # --- Warning（本機）：疑似重複規則 ---
    repeat = find_repeated_lines(lines)
    if repeat:
        warns.append(_warn("possible-duplicates", f"疑似重複段落（出現 ≥ 3 次的非瑣碎行）：{repeat[:5]}"))

    # --- Warning（本機）：inline 模板過大 ---
    big_block = find_large_code_blocks(lines)
    if big_block:
        warns.append(_warn(
            "large-inline-block",
            f"連續 ≥ {INLINE_CODE_BLOCK_LINES} 行的 code/table block 出現在 line {big_block}，建議抽 assets/",
        ))

    return fails, warns


def find_repeated_lines(lines: list) -> list:
    """找重複出現 ≥ 3 次的非瑣碎行（排除空行 / 純標點 / 短行 < 20 字 / markdown 結構符號）"""
    counter: dict = {}
    for ln in lines:
        s = ln.strip()
        if len(s) < 20:
            continue
        if s.startswith(("#", "-", "*", "|", "```", ">", "<!--")):
            continue
        if re.match(r"^[-=_*]+$", s):
            continue
        counter[s] = counter.get(s, 0) + 1
    return [s[:60] + ("..." if len(s) > 60 else "") for s, n in counter.items() if n >= 3]


def find_large_code_blocks(lines: list):
    """找連續 ≥ N 行的 code block (``` 之間)。回首行行號（1-based），無則 None。"""
    in_block = False
    block_start = 0
    block_lines = 0
    for i, ln in enumerate(lines, 1):
        if ln.strip().startswith("```"):
            if not in_block:
                in_block = True
                block_start = i
                block_lines = 0
            else:
                if block_lines >= INLINE_CODE_BLOCK_LINES:
                    return block_start
                in_block = False
        elif in_block:
            block_lines += 1
    return None


def check_structure(skill_dir: Path) -> tuple:
    """SKILL.md 偏大時該分層（progressive disclosure）。"""
    fails, warns = [], []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return fails, warns
    line_count = skill_md.read_text(encoding="utf-8").count("\n") + 1
    has_subdir = any((skill_dir / d).is_dir() for d in ("scripts", "references", "assets"))
    if line_count > LINE_SOFT_LIMIT and not has_subdir:
        warns.append(_warn(
            "no-progressive-disclosure",
            f"SKILL.md {line_count} 行 > {LINE_SOFT_LIMIT}，但無 scripts/ / references/ / assets/ 任一子目錄 — 該抽分層",
        ))
    return fails, warns


def check_scripts(skill_dir: Path) -> tuple:
    fails, warns = [], []
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.exists():
        return fails, warns
    for py in scripts_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "sys.stdout.reconfigure" not in text and "# -*- coding: utf-8" not in text:
            warns.append(_warn("script-utf8-missing", f"{py.name}: 缺 UTF-8 stdout 強制處理（Windows 中文亂碼風險）"))
        if not re.search(r"\btry\s*:", text) or not re.search(r"\bexcept\b", text):
            warns.append(_warn("script-no-error-handling", f"{py.name}: 主程式無 try/except 包（silent failure 風險）"))
    return fails, warns


def check_evals(skill_dir: Path) -> tuple:
    """建議全域 skill 提供 evals/triggers.json 以驗證 description 觸發精準度。"""
    fails, warns = [], []
    evals_json = skill_dir / "evals" / "triggers.json"
    if not evals_json.exists():
        warns.append(_warn(
            "no-trigger-evals",
            "缺 evals/triggers.json — 無法客觀驗證 description 觸發精準度，建議補（new-skill.py 預設會生成起點）",
        ))
        return fails, warns
    try:
        data = json.loads(evals_json.read_text(encoding="utf-8"))
        queries = data.get("queries", [])
        if len(queries) < 5:
            warns.append(_warn(
                "trigger-evals-too-few",
                f"evals/triggers.json 只 {len(queries)} 個查詢，建議 ≥ 10（5 應觸發 + 5 不應觸發）",
            ))
        placeholders = [q for q in queries if "<" in q.get("query", "")]
        if placeholders:
            warns.append(_warn("trigger-evals-placeholders", f"evals/triggers.json 仍有 {len(placeholders)} 個未填的佔位符查詢"))
    except Exception as e:
        warns.append(_warn("trigger-evals-malformed", f"evals/triggers.json 解析失敗：{e}"))
    return fails, warns


def check_references(skill_dir: Path) -> tuple:
    fails, warns = [], []
    refs_dir = skill_dir / "references"
    if not refs_dir.exists():
        return fails, warns
    for md in refs_dir.glob("*.md"):
        text = md.read_text(encoding="utf-8")
        line_count = text.count("\n") + 1
        if line_count >= REFS_TOC_THRESHOLD:
            if not re.search(r"^##\s*(目錄|Table of Contents|TOC)\s*$", text, re.MULTILINE):
                warns.append(_warn("ref-no-toc", f"references/{md.name} 共 {line_count} 行 ≥ {REFS_TOC_THRESHOLD}，但無 TOC 章節"))
    return fails, warns


def audit(skill_dir: Path, scope: str) -> dict:
    if not skill_dir.is_dir():
        return {"status": "error", "reason": f"not a directory: {skill_dir}"}

    fails, warns = [], []
    checkers = [check_skill_md, check_structure, check_scripts, check_references]
    if scope == "global":
        checkers.append(check_evals)  # 專案 skill 可不必有 evals
    for fn in checkers:
        try:
            if fn is check_skill_md:
                f, w = fn(skill_dir, scope)
            else:
                f, w = fn(skill_dir)
            fails.extend(f)
            warns.extend(w)
        except Exception as e:
            warns.append(_warn("checker-error", f"{fn.__name__} 內部錯誤：{e}"))

    return {
        "skill_path": str(skill_dir),
        "scope": scope,
        "fails": fails,
        "warnings": warns,
        "fail_count": len(fails),
        "warning_count": len(warns),
    }


def main():
    p = argparse.ArgumentParser(description="稽核 Claude Code skill：官方格式錯誤（fail）與本機建議（warning）分開")
    p.add_argument("path", type=str, help="skill 根目錄絕對路徑")
    p.add_argument("--strict", action="store_true", help="warning 升 fail")
    p.add_argument("--scope", choices=["global", "project"], default="global",
                   help="global=檢絕對路徑與 evals（預設）/ project=不檢")
    args = p.parse_args()

    try:
        result = audit(Path(args.path), args.scope)
        if result.get("status") == "error":
            print(json.dumps(result, ensure_ascii=False, indent=2))
            sys.exit(1)

        result["strict"] = args.strict
        effective_fail = result["fail_count"] + (result["warning_count"] if args.strict else 0)
        result["status"] = "fail" if effective_fail > 0 else "ok"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1 if effective_fail > 0 else 0)
    except Exception as e:
        print(json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

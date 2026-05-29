#!/usr/bin/env python3
"""audit-skill: 稽核 Claude Code skill 是否符合 skill-creator 規範。

用法:
  python audit-skill.py <skill 根目錄>
  python audit-skill.py <skill 根目錄> --strict          # warning 升 fail
  python audit-skill.py <skill 根目錄> --scope project   # 不檢專案 hardcode

輸出 JSON 到 stdout (UTF-8)，exit 0 = 通過，1 = fail。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# --- 常數 ---
LINE_HARD_LIMIT = 500
LINE_SOFT_LIMIT = 200
DESC_MIN_CHARS = 30
TRIGGERS_MIN = 3
REFS_TOC_THRESHOLD = 300
INLINE_CODE_BLOCK_LINES = 30
VALID_PATTERNS = ["tool-wrapper", "generator", "reviewer", "inversion", "pipeline"]
# 跨環境通用的「絕對路徑」偵測 — 抓形式，不寫死特定專案 / 使用者
# 命中時降為 warning（絕對路徑可能是合理示範，但建議改佔位符）
ABS_PATH_PATTERNS = [
    r"[A-Za-z]:\\[A-Za-z0-9_\-一-鿿][A-Za-z0-9_\\\-一-鿿]{2,}",  # Windows: C:\xxx\
    r"/(Users|home)/[A-Za-z0-9_\-]+/",                                            # Unix: /Users/x/ /home/x/
]
# 推薦的佔位符 / 相對路徑寫法（提示用）
PATH_PLACEHOLDER_HINT = "<project> / <workspace> / ~/ / ./src/..."


def parse_frontmatter(text: str) -> tuple[dict, int]:
    """回 (frontmatter dict, frontmatter 結束行號)。失敗回 ({}, 0)。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}, 0
    fm: dict = {}
    body = m.group(1)
    for line in body.split("\n"):
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        kv = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if kv:
            fm[kv.group(1)] = kv.group(2).strip()
    end_line = text[: m.end()].count("\n")
    return fm, end_line


def check_skill_md(skill_dir: Path, scope: str) -> tuple[list, list]:
    fails, warns = [], []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        fails.append({"id": "missing-skill-md", "msg": f"SKILL.md not found in {skill_dir}"})
        return fails, warns

    text = skill_md.read_text(encoding="utf-8")
    lines = text.split("\n")
    line_count = len(lines)

    # --- Fail：frontmatter 必要欄位 ---
    fm, _ = parse_frontmatter(text)
    if not fm:
        fails.append({"id": "frontmatter-missing", "msg": "SKILL.md 無 YAML frontmatter（--- ... --- 區塊）"})
    else:
        for key in ("name", "description", "triggers"):
            if key not in fm or not fm[key]:
                fails.append({"id": f"frontmatter-missing-{key}", "msg": f"frontmatter 缺 {key}"})

    # --- Fail：SKILL.md 行數 > 500 ---
    if line_count > LINE_HARD_LIMIT:
        fails.append({"id": "skill-md-too-long", "msg": f"SKILL.md {line_count} 行 > {LINE_HARD_LIMIT}（Anthropic 紅線）"})
    elif line_count > LINE_SOFT_LIMIT:
        warns.append({"id": "skill-md-large", "msg": f"SKILL.md {line_count} 行 > {LINE_SOFT_LIMIT} 軟上限，建議抽 references/"})

    # --- Warning：絕對路徑（僅 global scope；專案 skill 可有自己的路徑）---
    if scope == "global":
        hits = []
        for pat in ABS_PATH_PATTERNS:
            for m in re.finditer(pat, text):
                line_no = text[: m.start()].count("\n") + 1
                hits.append(f"line {line_no}: {m.group()!r}")
        if hits:
            warns.append({
                "id": "absolute-path",
                "msg": f"SKILL.md 含絕對路徑（{len(hits)} 處），全域 skill 建議改佔位符（{PATH_PLACEHOLDER_HINT}）：{hits[:3]}",
            })

    # --- Warning：description 字數 ---
    desc = fm.get("description", "")
    if desc and len(desc) < DESC_MIN_CHARS:
        warns.append({"id": "description-short", "msg": f"description 僅 {len(desc)} 字 < {DESC_MIN_CHARS}（可能 undertrigger）"})

    # --- Warning：triggers 數量 ---
    triggers_raw = fm.get("triggers", "")
    triggers = [t.strip() for t in triggers_raw.split(",") if t.strip()] if triggers_raw else []
    if 0 < len(triggers) < TRIGGERS_MIN:
        warns.append({"id": "triggers-few", "msg": f"triggers 僅 {len(triggers)} 個 < {TRIGGERS_MIN}（覆蓋面不足）"})

    # --- Warning：pattern 欄位 ---
    pattern = fm.get("pattern", "").strip()
    if not pattern:
        warns.append({
            "id": "pattern-missing",
            "msg": f"frontmatter 缺 `pattern` 欄位（建議標 5 模式之一：{VALID_PATTERNS}）",
        })
    elif pattern not in VALID_PATTERNS:
        warns.append({
            "id": "pattern-invalid",
            "msg": f"pattern={pattern!r} 不在白名單，建議用標準模式：{VALID_PATTERNS}",
        })

    # --- Warning：疑似重複規則 ---
    repeat = find_repeated_lines(lines)
    if repeat:
        warns.append({
            "id": "possible-duplicates",
            "msg": f"疑似重複段落（出現 ≥ 3 次的非瑣碎行）：{repeat[:5]}",
        })

    # --- Warning：inline 模板過大 ---
    big_block = find_large_code_blocks(lines)
    if big_block:
        warns.append({
            "id": "large-inline-block",
            "msg": f"連續 ≥ {INLINE_CODE_BLOCK_LINES} 行的 code/table block 出現在 line {big_block}，建議抽 assets/",
        })

    return fails, warns


def find_repeated_lines(lines: list[str]) -> list[str]:
    """找重複出現 ≥ 3 次的非瑣碎行（排除空行 / 純標點 / 短行 < 20 字 / markdown 結構符號）"""
    counter: dict[str, int] = {}
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


def find_large_code_blocks(lines: list[str]) -> int | None:
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


def check_structure(skill_dir: Path) -> tuple[list, list]:
    """檢查目錄結構是否符合 progressive disclosure（SKILL.md 偏大時該分層）。"""
    fails, warns = [], []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return fails, warns
    line_count = skill_md.read_text(encoding="utf-8").count("\n") + 1
    has_subdir = any((skill_dir / d).is_dir() for d in ("scripts", "references", "assets"))
    if line_count > LINE_SOFT_LIMIT and not has_subdir:
        warns.append({
            "id": "no-progressive-disclosure",
            "msg": f"SKILL.md {line_count} 行 > {LINE_SOFT_LIMIT} 軟上限，但無 scripts/ / references/ / assets/ 任一子目錄 — 該抽分層（progressive disclosure）",
        })
    return fails, warns


def check_scripts(skill_dir: Path) -> tuple[list, list]:
    fails, warns = [], []
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.exists():
        return fails, warns
    for py in scripts_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        # UTF-8 stdout
        if "sys.stdout.reconfigure" not in text and "# -*- coding: utf-8" not in text:
            warns.append({
                "id": "script-utf8-missing",
                "msg": f"{py.name}: 缺 UTF-8 stdout 強制處理（Windows 中文亂碼風險）",
            })
        # 錯誤處理
        if not re.search(r"\btry\s*:", text) or not re.search(r"\bexcept\b", text):
            warns.append({
                "id": "script-no-error-handling",
                "msg": f"{py.name}: 主程式無 try/except 包（silent failure 風險）",
            })
    return fails, warns


def check_evals(skill_dir: Path) -> tuple[list, list]:
    """建議全域 skill 提供 evals/triggers.json 以驗證 description 觸發精準度。"""
    fails, warns = [], []
    evals_json = skill_dir / "evals" / "triggers.json"
    if not evals_json.exists():
        warns.append({
            "id": "no-trigger-evals",
            "msg": "缺 evals/triggers.json — 無法客觀驗證 description 觸發精準度，建議補（new-skill.py 預設會生成起點）",
        })
        return fails, warns
    try:
        data = json.loads(evals_json.read_text(encoding="utf-8"))
        queries = data.get("queries", [])
        if len(queries) < 5:
            warns.append({
                "id": "trigger-evals-too-few",
                "msg": f"evals/triggers.json 只 {len(queries)} 個查詢，建議 ≥ 10（5 應觸發 + 5 不應觸發）",
            })
        placeholders = [q for q in queries if "<" in q.get("query", "")]
        if placeholders:
            warns.append({
                "id": "trigger-evals-placeholders",
                "msg": f"evals/triggers.json 仍有 {len(placeholders)} 個未填的佔位符查詢",
            })
    except Exception as e:
        warns.append({"id": "trigger-evals-malformed", "msg": f"evals/triggers.json 解析失敗：{e}"})
    return fails, warns


def check_references(skill_dir: Path) -> tuple[list, list]:
    fails, warns = [], []
    refs_dir = skill_dir / "references"
    if not refs_dir.exists():
        return fails, warns
    for md in refs_dir.glob("*.md"):
        text = md.read_text(encoding="utf-8")
        line_count = text.count("\n") + 1
        if line_count >= REFS_TOC_THRESHOLD:
            if not re.search(r"^##\s*(目錄|Table of Contents|TOC)\s*$", text, re.MULTILINE):
                warns.append({
                    "id": "ref-no-toc",
                    "msg": f"references/{md.name} 共 {line_count} 行 ≥ {REFS_TOC_THRESHOLD}，但無 TOC 章節",
                })
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
            warns.append({"id": "checker-error", "msg": f"{fn.__name__} 內部錯誤：{e}"})

    return {
        "skill_path": str(skill_dir),
        "scope": scope,
        "fails": fails,
        "warnings": warns,
        "fail_count": len(fails),
        "warning_count": len(warns),
    }


def main():
    p = argparse.ArgumentParser(description="稽核 Claude Code skill 是否符合 skill-creator 規範")
    p.add_argument("path", type=str, help="skill 根目錄絕對路徑")
    p.add_argument("--strict", action="store_true", help="warning 升 fail")
    p.add_argument("--scope", choices=["global", "project"], default="global",
                   help="global=檢專案 hardcode（預設）/ project=不檢")
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

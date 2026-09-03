#!/usr/bin/env python3
"""skill-index.py — skills/ 計數單一真相（SoT）工具（鏡像 sync-memory-index.py 模式）

SoT = `skills/*/SKILL.md`（Claude Code 自動發現 skill 的來源，檔案系統即真相）。
本工具消除「人讀文件散落硬編 skill 數」的 chronic drift：
  - 掃 `skills/*/SKILL.md`，抽 frontmatter name/description，產機器鏡像
    `skills/_skill_index.json`（count + 清單，勿手改）
  - 同步散落計數：重寫各文件的 `<!-- skill-count -->N<!-- /skill-count -->` marker

模式：
  --check  drift 偵測（_skill_index.json count 或任一 doc marker ≠ 實檔數 → stderr
           列差異、exit 1）；SessionStart 防呆與 verify 用
  --write  重生 _skill_index.json + 重寫所有 registered doc 的 marker（冪等）
  (default) dry-run，stdout 顯示實檔數 + 列出 drift

防 drift 串接：增刪改 SKILL.md 由 PostToolUse hook 自動跑 --write；SessionStart
跑 --check 當防呆（抓 Bash 刪除等 hook 漏接的情況）。控管規則見 atom（local/MemDev）
`skill-計數單一來源-skill-index`。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

CLAUDE_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = CLAUDE_DIR / "skills"

# 散落 skill 計數的人讀文件（相對 CLAUDE_DIR）。marker 只包住純數字，
# 其餘策展文字（「19 遷移自…」「含外部 karpathy」）保持人工維護、工具不動。
MARKED_DOCS = [
    "TECH.md",
    "Install-forAI.md",
    "_AIDocs/Architecture.md",
    "_AIDocs/_INDEX.md",
    "_AIDocs/DocIndex-System.md",
]
MARKER_RE = re.compile(r"(<!-- skill-count -->)\s*\d+\s*(<!-- /skill-count -->)")


def _frontmatter(text: str) -> Tuple[str, str]:
    """抽 SKILL.md YAML frontmatter 的 name/description（不依賴 yaml 套件）。"""
    name = desc = ""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        fm = text[3:end] if end > 0 else ""
        for line in fm.splitlines():
            s = line.strip()
            if s.startswith("name:") and not name:
                name = s[5:].strip().strip("\"'")
            elif s.startswith("description:") and not desc:
                desc = s[12:].strip().strip("\"'")
    return name, desc


def scan_skills(skills_dir: Path = SKILLS_DIR) -> List[Dict[str, str]]:
    """掃 skills/*/SKILL.md，回傳 sorted [{name, dir, description}]。
    name 缺 → 退回目錄名。_skill_index.json 在 skills/ 根、非 */SKILL.md，不計入。"""
    out: List[Dict[str, str]] = []
    for sk in sorted(skills_dir.glob("*/SKILL.md")):
        try:
            text = sk.read_text(encoding="utf-8-sig")
        except OSError:
            text = ""
        name, desc = _frontmatter(text)
        out.append({"name": name or sk.parent.name, "dir": sk.parent.name,
                    "description": desc})
    return out


def build_index(skills: List[Dict[str, str]]) -> Dict:
    return {
        "_doc": "skills/ 計數 SoT 機器鏡像。由 tools/skill-index.py 生成，勿手改。"
                "SoT=skills/*/SKILL.md。改 skill 後 PostToolUse hook 自動 --write。",
        "generated_from": "skills/*/SKILL.md",
        "count": len(skills),
        "skills": skills,
    }


def _read(p: Path):
    try:
        return p.read_text(encoding="utf-8-sig")
    except OSError:
        return None


def check(skills_dir: Path = SKILLS_DIR, claude_dir: Path = CLAUDE_DIR) -> Tuple[bool, List[str]]:
    """回傳 (ok, problems[])。problems 空 = 無 drift。"""
    true_n = len(scan_skills(skills_dir))
    problems: List[str] = []

    idx_path = skills_dir / "_skill_index.json"
    if not idx_path.exists():
        problems.append(f"_skill_index.json 不存在（實檔 {true_n}）")
    else:
        try:
            j = json.loads(idx_path.read_text(encoding="utf-8-sig"))
            if j.get("count") != true_n:
                problems.append(
                    f"_skill_index.json count={j.get('count')} ≠ 實檔 {true_n}")
        except (json.JSONDecodeError, OSError) as e:
            problems.append(f"_skill_index.json 讀取失敗: {e}")

    for rel in MARKED_DOCS:
        text = _read(claude_dir / rel)
        if text is None:
            continue
        for m in MARKER_RE.finditer(text):
            digits = re.search(r"\d+", m.group(0))
            if digits and int(digits.group(0)) != true_n:
                problems.append(f"{rel}: marker={digits.group(0)} ≠ 實檔 {true_n}")
    return (not problems), problems


def write(skills_dir: Path = SKILLS_DIR, claude_dir: Path = CLAUDE_DIR) -> Tuple[int, List[str]]:
    """重生 _skill_index.json + 重寫所有 marker。回傳 (count, changed_rel_paths[])。冪等。"""
    skills = scan_skills(skills_dir)
    n = len(skills)
    changed: List[str] = []

    idx_path = skills_dir / "_skill_index.json"
    new_json = json.dumps(build_index(skills), ensure_ascii=False, indent=2) + "\n"
    if _read(idx_path) != new_json:
        # newline="\n"：repo 全部 LF，關掉 Windows 的 \n→\r\n 轉譯
        idx_path.write_text(new_json, encoding="utf-8", newline="\n")
        changed.append(str(idx_path.relative_to(claude_dir)).replace("\\", "/"))

    repl = r"\g<1>" + str(n) + r"\g<2>"
    for rel in MARKED_DOCS:
        p = claude_dir / rel
        text = _read(p)
        if text is None:
            continue
        new = MARKER_RE.sub(repl, text)
        if new != text:
            p.write_text(new, encoding="utf-8", newline="\n")  # 見上：防 LF→CRLF flip
            changed.append(rel)
    return n, changed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="skills/ 計數 SoT 同步")
    ap.add_argument("--check", action="store_true", help="drift 偵測，有 drift exit 1")
    ap.add_argument("--write", action="store_true", help="重生 json + 重寫 marker")
    args = ap.parse_args(argv)

    if args.write:
        n, changed = write()
        print(f"[skill-index] count={n}；更新 {len(changed)} 檔："
              f"{', '.join(changed) or '無（已同步）'}")
        return 0

    ok, problems = check()
    if args.check:
        if ok:
            print(f"[skill-index] OK，{len(scan_skills())} skills，無 drift")
            return 0
        for p in problems:
            print(f"[skill-index][drift] {p}", file=sys.stderr)
        return 1

    # dry-run（預設）
    print(f"[skill-index] 實檔 {len(scan_skills())} skills；marker 文件 {len(MARKED_DOCS)} 份")
    if problems:
        print("drift：")
        for p in problems:
            print("  -", p)
    else:
        print("無 drift")
    return 0


if __name__ == "__main__":
    sys.exit(main())

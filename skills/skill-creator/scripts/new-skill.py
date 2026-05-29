#!/usr/bin/env python3
"""new-skill: 從 assets/patterns/<pattern>.md 生成 skill 骨架。

【設計哲學】主 agent 應先走 Inversion 訪談（見 SKILL.md「工作流 A」），
把 4 個核心問題問完使用者後，才呼叫本腳本帶完整參數。
本腳本不做互動，純粹參數→骨架的機械操作（Tool Wrapper 模式）。

用法:
  python new-skill.py \\
    --name <slug> \\
    --pattern <tool-wrapper|generator|reviewer|inversion|pipeline> \\
    --description "<≥30 字>" \\
    --triggers "<關鍵字1>, <關鍵字2>, <關鍵字3>, ..." \\
    --output <父目錄> \\
    [--scope global|project]

輸出 JSON 到 stdout (UTF-8)。exit 0 = 成功，1 = 業務失敗，2 = 內部錯誤。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

SKILL_CREATOR_ROOT = Path(__file__).resolve().parent.parent
PATTERNS_DIR = SKILL_CREATOR_ROOT / "assets" / "patterns"
SCRIPT_TEMPLATE = SKILL_CREATOR_ROOT / "assets" / "script-template.py"
AUDIT_SCRIPT = SKILL_CREATOR_ROOT / "scripts" / "audit-skill.py"

VALID_PATTERNS = ["tool-wrapper", "generator", "reviewer", "inversion", "pipeline"]
MIN_DESC_CHARS = 30
MIN_TRIGGERS = 3
MIN_TRIGGER_LEN = 2


def validate_inputs(name: str, pattern: str, description: str, triggers: list[str]) -> str | None:
    if not re.match(r"^[a-z][a-z0-9-]{1,40}$", name):
        return f"slug 必須 kebab-case (小寫 + 數字 + 連字號)，長度 2-41，得：{name!r}"
    if pattern not in VALID_PATTERNS:
        return f"pattern 必須是 {VALID_PATTERNS} 之一，得：{pattern!r}"
    if len(description) < MIN_DESC_CHARS:
        return f"description 至少 {MIN_DESC_CHARS} 字，得 {len(description)} 字：{description!r}"
    if len(triggers) < MIN_TRIGGERS:
        return f"triggers 至少 {MIN_TRIGGERS} 個，得 {len(triggers)} 個"
    bad = [t for t in triggers if len(t) < MIN_TRIGGER_LEN]
    if bad:
        return f"triggers 每個至少 {MIN_TRIGGER_LEN} 字，過短的：{bad}"
    return None


def create_skill(name: str, pattern: str, description: str, triggers: list[str],
                 output: Path, scope: str) -> dict:
    err = validate_inputs(name, pattern, description, triggers)
    if err:
        return {"status": "error", "reason": err}

    template_path = PATTERNS_DIR / f"{pattern}.md"
    if not template_path.exists():
        return {"status": "error", "reason": f"pattern template missing: {template_path}"}

    target = output / name
    if target.exists():
        return {"status": "error", "reason": f"target already exists: {target}"}

    target.mkdir(parents=True)
    for sub in ("scripts", "references", "assets"):
        (target / sub).mkdir()

    content = template_path.read_text(encoding="utf-8")
    # 替換 frontmatter / 標題的 <skill-name>
    content = content.replace("<skill-name>", name)
    # 替換 description（模板第一個 <30+ 字...> 佔位符）
    content = re.sub(r"description:\s*<30\+[^>\n]+>", f"description: {description}", content, count=1)
    # 替換 triggers
    triggers_str = ", ".join(triggers)
    content = re.sub(r"triggers:\s*<[^>\n]+>(,\s*<[^>\n]+>)*", f"triggers: {triggers_str}", content, count=1)
    # scope project 加註明
    if scope == "project":
        marker = f"# Skill：{name}"
        if marker in content:
            content = content.replace(
                marker,
                f"{marker}\n\n> **限定範圍**：專案 skill。本 skill 含專案特定路徑 / 規範，不適用其他環境。",
                1,
            )

    skill_md = target / "SKILL.md"
    skill_md.write_text(content, encoding="utf-8")

    # 生成 evals/triggers.json 起點（精準觸發驗證用）
    evals_dir = target / "evals"
    evals_dir.mkdir()
    evals_starter = {
        "_comment": "20 個觸發評估查詢：10 應觸發 + 10 不應觸發。先填 should_trigger:true 的 8-10 個（不同措辭），再填 false 的 8-10 個（近似但不該觸發）",
        "skill_name": name,
        "queries": [
            {"query": "<填入：典型觸發語句 1>", "should_trigger": True, "note": "明確要求"},
            {"query": "<填入：典型觸發語句 2>", "should_trigger": True, "note": "另一措辭"},
            {"query": "<填入：邊界觸發語句>", "should_trigger": True, "note": "未明確命名但應觸發"},
            {"query": "<填入：近似但不該觸發 1>", "should_trigger": False, "note": "共享關鍵字但需其他工具"},
            {"query": "<填入：近似但不該觸發 2>", "should_trigger": False, "note": "模糊表達不該強行觸發"},
        ],
    }
    (evals_dir / "triggers.json").write_text(
        json.dumps(evals_starter, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "status": "ok",
        "skill_path": str(target),
        "skill_md": str(skill_md),
        "pattern": pattern,
        "evals_starter": str(evals_dir / "triggers.json"),
        "next_steps": [
            f"1. 編輯 {skill_md.name} 填入具體步驟（模板已標註 <變數> 佔位符）",
            f"2. 補完 evals/triggers.json 的 5+ 個查詢（測 description 精準度）",
            f"3. 寫對應 scripts/（複製 {SCRIPT_TEMPLATE} 開始）",
            f"4. 大段 SOP 抽 references/；模板抽 assets/",
            f"5. 驗證: python {AUDIT_SCRIPT} {target} --scope {scope}",
        ],
    }


def main():
    p = argparse.ArgumentParser(
        description="從模式特化模板生成 Claude Code skill 骨架",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--name", required=True, help="skill slug (kebab-case)")
    p.add_argument("--pattern", required=True, choices=VALID_PATTERNS, help="設計模式")
    p.add_argument("--description", required=True, help=f"description（≥ {MIN_DESC_CHARS} 字）")
    p.add_argument("--triggers", required=True,
                   help=f"觸發關鍵字，逗號分隔（≥ {MIN_TRIGGERS} 個）")
    p.add_argument("--output", required=True, help="父目錄絕對路徑")
    p.add_argument("--scope", choices=["global", "project"], default="global")
    args = p.parse_args()

    try:
        triggers = [t.strip() for t in args.triggers.split(",") if t.strip()]
        out_path = Path(args.output).expanduser().resolve()
        result = create_skill(args.name, args.pattern, args.description, triggers, out_path, args.scope)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("status") == "ok" else 1)
    except Exception as e:
        print(json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

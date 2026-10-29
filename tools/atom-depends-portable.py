"""atom-depends-portable.py：把記憶卡（atom .md）的 path 型 Depends 從作者機絕對路徑改成可攜寫法。

卡片跨機器用版控共享，`- Depends: path:C:/Users/<誰>/.claude/...` 在別台機器驗不到會被健檢當壞滅緣。
改法：在資料根（~/.claude）下的 → `~/.claude/<rel>`；在專案根下的 → 專案相對；其餘不動。只改 Depends 那一行。
怎麼跑（在任何專案 session 都可以，不用 cd 進根層）：
  python -X utf8 ~/.claude/tools/atom-depends-portable.py --memory-dir <專案>/.claude/memory            # 預覽
  python -X utf8 ~/.claude/tools/atom-depends-portable.py --memory-dir <專案>/.claude/memory --apply    # 套用
完整參數 --help。尾行 `ATOM_DEPENDS_PORTABLE DONE scanned=<張> changed=<張> applied=<0|1>`。
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.atom_spec import depends_base_for_file, parse_depends, portable_depends_path  # noqa: E402
from lib.project_root import claude_data_dir  # noqa: E402

DEP_RE = re.compile(r"^- Depends:[ \t]*(.*?)[ \t]*$")


def rewrite_line(line: str, md: Path, claude_dir: Path, project_root: Path) -> str:
    m = DEP_RE.match(line)
    if not m:
        return line
    out = []
    for it in parse_depends(m.group(1)):
        v = str(it.get("value") or "").strip()
        if it.get("type") != "path" or not v or v.startswith("~/") or not Path(v).is_absolute():
            out.append(it["value"] if it.get("type") != "path" else f"path:{v}")
            continue
        out.append(f"path:{portable_depends_path(Path(v), project_root=project_root, claude_dir=claude_dir)}")
    return "- Depends: " + ", ".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--memory-dir", required=True, help="要掃的記憶目錄（例 <專案>/.claude/memory）")
    ap.add_argument("--claude-dir", default=str(claude_data_dir()), help="本機資料根（預設 ~/.claude）")
    ap.add_argument("--apply", action="store_true", help="真的寫檔；不帶只預覽")
    a = ap.parse_args()
    mem, claude_dir = Path(a.memory_dir), Path(a.claude_dir)
    scanned = changed = 0
    for md in sorted(mem.rglob("*.md")):
        scanned += 1
        text = md.read_bytes().decode("utf-8")
        nl = "\r\n" if "\r\n" in text else "\n"
        lines = text.split(nl)
        project_root = depends_base_for_file(md)
        for i, line in enumerate(lines):
            new = rewrite_line(line, md, claude_dir, project_root)
            if new == line:
                continue
            print(f"{md.relative_to(mem)}\n    舊 {line}\n    新 {new}")
            lines[i] = new
            changed += 1
            if a.apply:
                md.write_bytes(nl.join(lines).encode("utf-8"))
            break
    print(f"ATOM_DEPENDS_PORTABLE DONE scanned={scanned} changed={changed} applied={int(a.apply)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

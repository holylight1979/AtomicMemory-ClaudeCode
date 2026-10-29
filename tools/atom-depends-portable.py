"""atom-depends-portable.py：把記憶卡（atom .md）的 path 型 Depends 從絕對路徑改成可攜寫法。

卡片跨機器用版控共享，`- Depends: path:C:/Users/<誰>/.claude/...`、`path:C:/Projects/<專案>/...` 在別台機器驗不到，
健檢會當壞滅緣。只改 Depends 那一行裡「絕對路徑」的條目，已是相對或 ~/ 的不動。每條依序試四條規則：
  R1 在本機資料根（~/.claude）下 → ~/.claude/<rel>
  R2 在本機專案根下、且那個相對路徑真的存在 → 專案相對
  R3 其餘（別台電腦的根、或舊目錄配置多一層）：從左邊逐段剝掉，取「在本機專案根下存在的最長尾段」當專案相對
     例 C:/Projects/TSLG/Develop/Tools/CodeReview/src/cli.js → Tools/CodeReview/src/cli.js
  R4 找不到存在的尾段：在專案根下的照 R2 轉專案相對（如實變 missing）；不在根下的原樣不動，預覽另列「無法對應」
專案根＝卡片所在 <專案>/.claude/memory 往上兩層（lib.atom_spec.depends_base_for_file）。
怎麼跑（在任何專案 session 都可以，不用 cd 進根層）：
  python -X utf8 ~/.claude/tools/atom-depends-portable.py --memory-dir <專案>/.claude/memory            # 預覽
  python -X utf8 ~/.claude/tools/atom-depends-portable.py --memory-dir <專案>/.claude/memory --apply    # 套用
  專案層健檢：python -X utf8 ~/.claude/tools/atom-health-check.py --deps-check --memory-root <專案>/.claude/memory
完整參數 --help。尾行 `ATOM_DEPENDS_PORTABLE DONE scanned=<張> changed=<張> unmapped=<條> applied=<0|1>`。
"""
import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.atom_spec import depends_base_for_file, parse_depends  # noqa: E402
from lib.project_root import claude_data_dir  # noqa: E402

DEP_RE = re.compile(r"^- Depends:[ \t]*(.*?)[ \t]*$")


def _rel_under(p: Path, root: Optional[Path]) -> Optional[str]:
    """p 在 root 之下 → 相對 posix 路徑；不在或沒給 root → None。不 resolve（不存在的路徑也要比得出來）。"""
    if root is None:
        return None
    try:
        return Path(str(p)).relative_to(Path(str(root))).as_posix()
    except ValueError:
        return None


def map_abs_path(value: str, claude_dir: Path, project_root: Optional[Path]) -> Tuple[Optional[str], str]:
    """一條絕對路徑 → (新寫法或 None, 走哪條規則 R1/R2/R3/R4/R4-unmapped)。"""
    p = Path(value.replace("\\", "/"))
    rel = _rel_under(p, claude_dir)
    if rel is not None:
        return "~/.claude/" + rel, "R1"
    in_root = _rel_under(p, project_root)
    if in_root is not None and project_root is not None and (project_root / in_root).exists():
        return in_root, "R2"
    if project_root is not None:
        parts = p.parts[1:]                                   # 去掉磁碟機／根
        for i in range(1, len(parts)):                        # 從左邊逐段剝，第一個存在的就是最長尾段
            tail = "/".join(parts[i:])
            if (project_root / tail).exists():
                return tail, "R3"
    if in_root is not None:
        return in_root, "R4"
    return None, "R4-unmapped"


def rewrite_line(line: str, claude_dir: Path, project_root: Optional[Path]) -> Tuple[str, List[str], List[str]]:
    """Depends 那一行 → (新行, 每條改動的說明, 無法對應的原值)。不是 Depends 行原樣回。"""
    m = DEP_RE.match(line)
    if not m:
        return line, [], []
    out, notes, unmapped = [], [], []
    for it in parse_depends(m.group(1)):
        v = str(it.get("value") or "").strip()
        if it.get("type") != "path":
            out.append(it["value"])
            continue
        if not v or v.startswith("~/") or not Path(v).is_absolute():
            out.append(f"path:{v}")
            continue
        new, rule = map_abs_path(v, claude_dir, project_root)
        if new is None:
            unmapped.append(v)
            out.append(f"path:{v}")
            continue
        notes.append(f"[{rule}] {v} → {new}")
        out.append(f"path:{new}")
    return "- Depends: " + ", ".join(out), notes, unmapped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--memory-dir", required=True, help="要掃的記憶目錄（例 <專案>/.claude/memory）")
    ap.add_argument("--claude-dir", default=str(claude_data_dir()), help="本機資料根（預設 ~/.claude）")
    ap.add_argument("--apply", action="store_true", help="真的寫檔；不帶只預覽")
    a = ap.parse_args()
    mem, claude_dir = Path(a.memory_dir), Path(a.claude_dir)
    scanned = changed = 0
    unmapped_all: List[Tuple[str, str]] = []
    for md in sorted(mem.rglob("*.md")):
        scanned += 1
        text = md.read_bytes().decode("utf-8")
        nl = "\r\n" if "\r\n" in text else "\n"
        lines = text.split(nl)
        project_root = depends_base_for_file(md)
        for i, line in enumerate(lines):
            new, notes, unmapped = rewrite_line(line, claude_dir, project_root)
            unmapped_all += [(str(md.relative_to(mem)), u) for u in unmapped]
            if new == line:
                continue
            print(f"{md.relative_to(mem)}")
            for n in notes:
                print(f"    {n}")
            lines[i] = new
            changed += 1
            if a.apply:
                md.write_bytes(nl.join(lines).encode("utf-8"))
            break
    if unmapped_all:
        print("## 無法對應（不在本機專案根下、也找不到存在的尾段；原樣保留，要人工改）")
        for card, v in unmapped_all:
            print(f"    {card}｜{v}")
    print(f"ATOM_DEPENDS_PORTABLE DONE scanned={scanned} changed={changed} unmapped={len(unmapped_all)} applied={int(a.apply)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

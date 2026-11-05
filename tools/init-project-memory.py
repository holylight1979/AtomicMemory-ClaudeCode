#!/usr/bin/env python3
"""init-project-memory.py — 一鍵建好專案的原子記憶層（跑一次；重跑只補缺的，不覆寫任何既有內容）。

建什麼（{專案根}/.claude/memory/ 之下，已存在一律跳過）：
  MEMORY.md（只有 atom-catalog 區塊由系統維護）、.gitignore、README.md（給沒裝根層的隊友）、
  _atom_index.json（空索引）、目錄 shared/ failures/ personal/ _staging/ episodic/，
  shared/ 與 failures/ 各放 .gitkeep（git 不收空目錄）。最後登記進專案清單。
隊友 pull 專案後裝好根層即接上，這支不管那段。

怎麼跑：python tools/init-project-memory.py [--cwd <目錄>] [--dry-run]
結尾哨兵：INIT_PROJECT_MEMORY DONE root=<路徑> created=<n> existed=<n> dry_run=<0|1>
  路徑裡的空白換成 %20（哨兵格式不容許空白）。
exit：0 成功／2 這個目錄不該建（~/.claude、家目錄、暫存區）／1 例外（印到 stderr）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent
for p in (CODE_DIR, CODE_DIR / "hooks", CODE_DIR / "lib"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from wg_core import CLAUDE_DIR, find_project_root, is_transient_project_root, register_project  # noqa: E402
from lib.atom_index_json import _empty_index, save_atom_index_json  # noqa: E402

CATALOG_BEGIN = "<!-- atom-catalog -->"
CATALOG_END = "<!-- /atom-catalog -->"
GITIGNORE = "_atom_index.json\n_ATOM_INDEX.md\n_staging/\nepisodic/\nvector-db/\n"
DIRS = ("shared", "failures", "personal", "_staging", "episodic")
KEEP_DIRS = ("shared", "failures")

README = """# 這個目錄是什麼

Claude Code「原子記憶」的專案層。這個專案的決策與踩坑寫成一張張記憶卡，放在 `shared/`、`failures/`，隨專案版控共享給所有隊友。

# 怎麼接上

裝好根層後，pull 這個專案就自動接上，不必另外設定。安裝步驟見根層 repo 的 Install.md：<根層 repo 網址>

# 注意

不要手改 `_atom_index.json`：它是系統從卡片衍生的索引（已在 `.gitignore`），手改會被覆蓋。
"""


def memory_md(root_name: str) -> str:
    return (f"# Atom Index — {root_name}\n\n"
            f"這是專案的記憶卡索引，`{CATALOG_BEGIN}` 區塊由系統維護，其他地方可手寫分區規則。\n\n"
            f"{CATALOG_BEGIN}\n{CATALOG_END}\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="一鍵建好專案的原子記憶層；已存在的一律跳過、絕不覆寫。")
    ap.add_argument("--cwd", default=".", help="專案內任一目錄（預設目前目錄）；專案根自動往上找")
    ap.add_argument("--dry-run", action="store_true", help="只印會建什麼，不落檔")
    ap.add_argument("--allow-transient", action="store_true", help="允許暫存區內的目錄（只給測試用）")
    args = ap.parse_args()

    root = Path(find_project_root(str(Path(args.cwd).resolve()))).resolve()
    # 資料根可被 WG_CLAUDE_DIR 改走，所以程式碼根與家目錄下的 .claude 也一併擋
    if root in (CLAUDE_DIR.resolve(), CODE_DIR.resolve(), (Path.home() / ".claude").resolve(), Path.home().resolve()):
        print(f"拒絕：{root} 是根層或家目錄，不是專案")
        return 2
    if is_transient_project_root(root) and not args.allow_transient:
        print(f"拒絕：{root} 在暫存區")
        return 2
    if not ((root / ".git").exists() or (root / ".svn").exists()):
        print("提醒：這個目錄沒有版控，隊友拿不到")

    mem = root / ".claude" / "memory"
    counts = {"created": 0, "existed": 0}

    def ensure(path: Path, content: str | None) -> None:
        """content=None 建目錄，否則建檔。已存在就跳過。"""
        rel = path.relative_to(root).as_posix()
        if path.exists():
            counts["existed"] += 1
            print(f"existed  {rel}")
            return
        counts["created"] += 1
        print(f"created  {rel}")
        if args.dry_run:
            return
        if content is None:
            path.mkdir(parents=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

    ensure(mem, None)
    ensure(mem / "MEMORY.md", memory_md(root.name))
    ensure(mem / ".gitignore", GITIGNORE)
    ensure(mem / "README.md", README)
    for d in DIRS:
        ensure(mem / d, None)
    for d in KEEP_DIRS:
        ensure(mem / d / ".gitkeep", "")

    index = mem / "_atom_index.json"
    if index.exists():
        counts["existed"] += 1
        print("existed  .claude/memory/_atom_index.json")
    else:
        counts["created"] += 1
        print("created  .claude/memory/_atom_index.json")
        if not args.dry_run:
            save_atom_index_json(mem, _empty_index())

    if not args.dry_run:
        register_project(str(root))

    shown = str(root).replace(" ", "%20")
    print(f"INIT_PROJECT_MEMORY DONE root={shown} created={counts['created']} "
          f"existed={counts['existed']} dry_run={int(args.dry_run)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 不吞：印到 stderr、exit 1
        print(f"INIT_PROJECT_MEMORY 失敗：{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

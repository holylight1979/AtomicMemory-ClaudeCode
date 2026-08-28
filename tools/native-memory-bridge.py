#!/usr/bin/env python3
"""native-memory-bridge.py — 核心 atom 索引 → CC harness 原生 memory 指標鏡像。

把 memory/_atom_index.json 的核心 atom（path 在 memory/ 下者）以**指標行**鏡像成
原生 memory 目錄（projects/<slug>/memory/）的一個橋接檔，讓 harness 原生記憶召回
也能導向 atom 系統，兩系統互不吞併。

硬約束（verify_native_memory_dir_guard 不變式 + 撞名辨識 atom）：
  - 絕不在原生目錄放 _atom_index.json / _ATOM_INDEX.md
  - MEMORY.md 只寫 harness 清單格式行（`- [Title](file.md) — hook`），
    絕不含 `| Atom` trigger 表頭 → 原生目錄不會被 atom 掃描誤納
  - 橋接檔標明機器生成勿手編；每次執行整檔重寫（冪等）
  - 本腳本為獨立子程序寫入（PreToolUse P1 deny 只攔 Claude 的 Write/Edit
    工具呼叫，導流至 atom_write——橋接檔屬機器鏡像，非該 gate 的導流對象）

用法：python tools/native-memory-bridge.py [--slug <slug>] [--dry-run]
（無 --slug 時由 cwd 推導；僅在目標原生目錄已存在時寫入，不越權建樹。）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent
ATOM_INDEX = CLAUDE_DIR / "memory" / "_atom_index.json"
BRIDGE_FILENAME = "atom-index-bridge.md"
MEMORY_MD_LINE = (
    f"- [Atom index bridge]({BRIDGE_FILENAME}) — 核心 atom 指標鏡像（機器生成勿手編）"
)


def _slug_from_cwd(cwd: Path) -> str:
    # harness slug 規則：每個非英數字元各轉一個 '-'（不合併）、磁碟代號小寫
    # c:\Users\x\.claude → c--Users-x--claude（":" 與 "\" 各一個 '-'，"." 也是 '-'）
    import re
    s = re.sub(r"[^A-Za-z0-9]", "-", str(cwd))
    return s[0].lower() + s[1:] if s else s


def _core_atoms() -> list[dict]:
    data = json.loads(ATOM_INDEX.read_text(encoding="utf-8"))
    return [
        a for a in data.get("atoms", [])
        if str(a.get("path", "")).replace("\\", "/").startswith("memory/")
    ]


def render_bridge(atoms: list[dict]) -> str:
    L = [
        "---",
        "name: atom-index-bridge",
        "description: 核心 atom 索引指標鏡像（機器生成，來源 memory/_atom_index.json，勿手編）",
        "metadata:",
        "  type: reference",
        "---",
        "",
        "# Atom Index Bridge（機器生成勿手編）",
        "",
        "> 由 `tools/native-memory-bridge.py` 鏡像。需要細節時 Read 對應 atom 檔，",
        "> 或直接依 trigger 詞觸發 hook 注入；勿把本檔內容當完整知識。",
        "",
    ]
    for a in sorted(atoms, key=lambda x: x.get("name", "")):
        trig = ", ".join(a.get("triggers", [])[:5])
        L.append(f"- [[{a['name']}]] → Read `{a['path']}`（trigger: {trig}）")
    L.append("")
    return "\n".join(L)


def sync(native_mem: Path, atoms: list[dict], dry_run: bool = False,
         create: bool = False) -> dict:
    """寫橋接檔 + 確保 MEMORY.md 指標行（冪等）。回結果摘要。

    目錄不存在預設拒寫（防錯 slug 長垃圾樹）；--create 顯式放行
    （harness 惰性建目錄，首次橋接需自建）。"""
    if not native_mem.is_dir():
        if not (create and not dry_run):
            return {"written": False, "reason": f"原生目錄不存在：{native_mem}"}
        native_mem.mkdir(parents=True, exist_ok=True)
    bridge = native_mem / BRIDGE_FILENAME
    content = render_bridge(atoms)
    mem_md = native_mem / "MEMORY.md"
    old = mem_md.read_text(encoding="utf-8") if mem_md.exists() else ""
    need_line = MEMORY_MD_LINE not in old
    if "| Atom" in old:
        # 該 dir 竟是 atom 索引 dir（不該發生）——寫入會加劇撞名，拒絕
        return {"written": False, "reason": "目標 MEMORY.md 含 atom 索引表頭，拒寫（撞名防護）"}
    if not dry_run:
        bridge.write_text(content, encoding="utf-8")
        if need_line:
            new = (old.rstrip("\n") + "\n" if old.strip() else "") + MEMORY_MD_LINE + "\n"
            mem_md.write_text(new, encoding="utf-8")
    return {
        "written": not dry_run,
        "bridge": str(bridge),
        "atom_count": len(atoms),
        "memory_md_line_added": need_line,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--create", action="store_true",
                    help="目標原生目錄不存在時允許建立（首次橋接用）")
    args = ap.parse_args()
    # 預設鏡像到 ~/.claude 自己的原生 memory 目錄（核心 atom 屬 ~/.claude 知識），
    # 不依呼叫者 cwd——由 MCP / sync-memory-index 子程序呼叫時 cwd 常是外部專案。
    slug = args.slug or _slug_from_cwd(CLAUDE_DIR)
    native_mem = CLAUDE_DIR / "projects" / slug / "memory"
    result = sync(native_mem, _core_atoms(), dry_run=args.dry_run,
                  create=args.create)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result.get("written") or args.dry_run else 1


if __name__ == "__main__":
    sys.exit(main())

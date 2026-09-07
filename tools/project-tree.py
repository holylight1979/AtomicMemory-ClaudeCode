#!/usr/bin/env python3
"""project-tree.py — 專案根宣告檔（.claude/project-tree.json）的查看與增刪改。

做什麼：子專案的 Claude session 要把記憶歸到核心根層，靠各層 `.claude/project-tree.json` 宣告
（根層列 subs、子層指 root）。hook 只讀這些檔，所有寫入都走本工具或手改 JSON。
怎麼跑（--cwd 預設目前目錄；寫入子命令皆可 --dry-run 只印不寫）：
  show                         本層與上層宣告檔內容 + 目前生效的解析
  explain [<cwd>] [--json]     解析過程：hops / claimed_by / candidates / warnings / infos
  set-root <path> [--abs]      本層 root（相對化寫入；--abs 另寫 root_abs 供本機用）
  unset-root                   移除本層 root / root_abs
  add-sub <rel>...             本層 subs 增加（冪等）
  remove-sub <rel>...          本層 subs 移除
  standalone on|off            本層獨立（停止向上認領、不再提問）
  claim --root <path> [--sub-path <rel>] [--both]
                               雙向一次完成：根層 subs 追加本層在根層下的第一段路徑；
                               本層已有 .claude/ 才同時寫 root（--both 強制寫）
  pick                         彈原生資料夾視窗選根層，選定後等同 claim --root <選定>
完整參數以 --help 為準。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

CLAUDE_DIR = Path(__file__).resolve().parent.parent
if str(CLAUDE_DIR / "lib") not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR / "lib"))

from project_root import (  # noqa: E402
    DECL_NAME, clear_cache, declaration_path, describe, load_declaration, resolve_project_root,
)

ORDER = ("root", "root_abs", "subs", "standalone")


# ─── 讀寫 ─────────────────────────────────────────────────────────────────────


def _read_raw(layer: Path) -> Dict[str, Any]:
    p = declaration_path(layer)
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        sys.exit(f"錯誤：{p} 不是有效 JSON（{e}）。請先手動修好再用本工具。")
    if not isinstance(raw, dict):
        sys.exit(f"錯誤：{p} 頂層必須是物件 {{}}。")
    return raw


def _dump(raw: Dict[str, Any]) -> str:
    ordered = {k: raw[k] for k in ORDER if k in raw}
    ordered.update({k: v for k, v in raw.items() if k not in ordered})
    return json.dumps(ordered, ensure_ascii=False, indent=2) + "\n"


def _write_raw(layer: Path, raw: Dict[str, Any], dry_run: bool) -> None:
    """只動呼叫端改過的欄位，未知鍵原樣保留；tmp + 原子 replace。"""
    p = declaration_path(layer)
    before = p.read_text(encoding="utf-8-sig") if p.is_file() else ""
    after = _dump(raw)
    print(f"{'[dry-run] ' if dry_run else ''}{p}")
    if before.strip() == after.strip():
        print("  （內容無變化）")
        return
    if before:
        print("  前：" + before.strip().replace("\n", "\n      "))
    print("  後：" + after.strip().replace("\n", "\n      "))
    if dry_run:
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(after, encoding="utf-8", newline="\n")
    os.replace(tmp, p)
    clear_cache()


def _layer(args) -> Path:
    return Path(os.path.normpath(os.path.abspath(args.cwd or os.getcwd())))


def _rel_from(layer: Path, target: Path) -> str:
    return Path(os.path.relpath(str(target), str(layer))).as_posix()


def _is_ancestor(target: Path, layer: Path) -> bool:
    t, l = target.resolve(), layer.resolve()
    return t != l and t in l.parents


# ─── 子命令 ───────────────────────────────────────────────────────────────────


def cmd_show(args) -> None:
    layer = _layer(args)
    print(f"WhoAmI : {layer}")
    p = layer
    seen_any = False
    while True:
        d = load_declaration(p)
        if d is not None:
            seen_any = True
            state = "有效" if d.valid else f"無效：{d.error}"
            print(f"\n{d.path}  [{state}]")
            print("  " + (d.path.read_text(encoding="utf-8-sig").strip().replace("\n", "\n  ") or "{}"))
        if p.parent == p or p.resolve() == Path.home().resolve():
            break
        p = p.parent
    if not seen_any:
        print("\n（本層與上層都沒有宣告檔）")
    print("\n目前生效：")
    res = resolve_project_root(str(layer))
    for line in describe(res, str(layer)):
        print("  " + line)


def cmd_explain(args) -> None:
    cwd = os.path.abspath(args.path or args.cwd or os.getcwd())
    res = resolve_project_root(cwd)
    if args.json:
        payload = {
            "cwd": cwd, "root": str(res.path) if res.path else None, "claimed_by": res.claimed_by,
            "via": str(res.via) if res.via else None, "nearest": str(res.nearest) if res.nearest else None,
            "candidates": [str(c) for c in res.candidates], "hops": [str(h) for h in res.hops],
            "standalone": res.standalone, "fork_atoms": res.fork_atoms, "fingerprint": res.fingerprint,
            "warnings": res.warnings, "infos": res.infos,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for line in describe(res, cwd):
        print(line)


def cmd_set_root(args) -> None:
    layer = _layer(args)
    target = Path(os.path.normpath(os.path.abspath(args.path)))
    if not target.is_dir():
        sys.exit(f"錯誤：{target} 不是目錄。")
    raw = _read_raw(layer)
    if _is_ancestor(target, layer):
        raw["root"] = _rel_from(layer, target)
        if args.abs:
            raw["root_abs"] = str(target)
        else:
            raw.pop("root_abs", None)
    else:
        if not args.abs:
            sys.exit(f"錯誤：{target} 不是 {layer} 的祖先；root 只准指祖先。"
                     f"要指向別的樹請加 --abs（只在本機有效，寫成 root_abs）。")
        raw.pop("root", None)
        raw["root_abs"] = str(target)
    _write_raw(layer, raw, args.dry_run)
    _after_write_hint()


def cmd_unset_root(args) -> None:
    layer = _layer(args)
    raw = _read_raw(layer)
    raw.pop("root", None)
    raw.pop("root_abs", None)
    _write_raw(layer, raw, args.dry_run)
    _after_write_hint()


def _norm_sub(value: str) -> str:
    return "*" if value == "*" else Path(value).as_posix().strip("/")


def cmd_add_sub(args) -> None:
    layer = _layer(args)
    raw = _read_raw(layer)
    subs: List[str] = list(raw.get("subs") or [])
    for v in args.rel:
        s = _norm_sub(v)
        if s != "*" and (os.path.isabs(s) or ".." in Path(s).parts):
            sys.exit(f"錯誤：subs 只收相對本層、不含 .. 的路徑：{v!r}")
        if s not in subs:
            subs.append(s)
    raw["subs"] = subs
    _write_raw(layer, raw, args.dry_run)
    _after_write_hint()


def cmd_remove_sub(args) -> None:
    layer = _layer(args)
    raw = _read_raw(layer)
    subs: List[str] = list(raw.get("subs") or [])
    wanted = {_norm_sub(v) for v in args.rel}
    raw["subs"] = [s for s in subs if _norm_sub(s) not in wanted]
    _write_raw(layer, raw, args.dry_run)
    _after_write_hint()


def cmd_standalone(args) -> None:
    layer = _layer(args)
    raw = _read_raw(layer)
    if args.mode == "on":
        raw["standalone"] = True
    else:
        raw.pop("standalone", None)
    _write_raw(layer, raw, args.dry_run)
    _after_write_hint()


def _claim(layer: Path, root: Path, sub_path: Optional[str], both: bool, dry_run: bool) -> None:
    if not root.is_dir():
        sys.exit(f"錯誤：{root} 不是目錄。")
    if not _is_ancestor(root, layer):
        sys.exit(f"錯誤：{root} 不是 {layer} 的祖先；認領的根層必須在本層上方。")
    rel_to_root = Path(os.path.relpath(str(layer), str(root)))
    sub = _norm_sub(sub_path) if sub_path else rel_to_root.parts[0]
    sub_layer = root / sub
    between = sub_layer.is_dir() and (_is_ancestor(sub_layer, layer) or sub_layer.resolve() == layer.resolve())
    if not between:
        sys.exit(f"錯誤：--sub-path {sub!r} 不在 {root} 與 {layer} 之間。")
    # 根層：subs 追加
    raw_root = _read_raw(root)
    subs: List[str] = list(raw_root.get("subs") or [])
    if "*" not in subs and sub not in subs:
        subs.append(sub)
    raw_root["subs"] = subs
    _write_raw(root, raw_root, dry_run)
    # 子層：已有 .claude/ 才寫 root（不散落新目錄）；--both 強制
    if (sub_layer / ".claude").is_dir() or both:
        raw_sub = _read_raw(sub_layer)
        raw_sub["root"] = _rel_from(sub_layer, root)
        _write_raw(sub_layer, raw_sub, dry_run)
    else:
        print(f"{sub_layer} 沒有 .claude/，不建立子層宣告（要雙向都寫請加 --both）")
    _after_write_hint()
    if not dry_run:
        res = resolve_project_root(str(layer))
        print(f"解析結果：{layer} → {res.path}（{res.claimed_by}）")


def cmd_claim(args) -> None:
    _claim(_layer(args), Path(os.path.normpath(os.path.abspath(args.root))), args.sub_path, args.both, args.dry_run)


def cmd_pick(args) -> None:
    layer = _layer(args)
    res = resolve_project_root(str(layer))
    initial = str(res.candidates[0]) if res.candidates else str(layer.parent)
    try:
        if os.environ.get("PROJECT_TREE_NO_GUI"):      # 測試／headless 明示關閉視窗
            raise RuntimeError("PROJECT_TREE_NO_GUI 已設定")
        import tkinter
        from tkinter import filedialog
        tk = tkinter.Tk()
        tk.withdraw()
        tk.attributes("-topmost", True)
        chosen = filedialog.askdirectory(title=f"選擇 {layer} 所屬的核心根層", initialdir=initial, mustexist=True)
        tk.destroy()
    except Exception as e:  # 無桌面 / 無 tkinter
        sys.exit(f"無法開啟資料夾視窗（{e}）。請改用：python ~/.claude/tools/project-tree.py claim --root <根層路徑> --cwd \"{layer}\"")
    if not chosen:
        print("已取消，未寫入任何檔案。")
        return
    _claim(layer, Path(os.path.normpath(chosen)), args.sub_path, args.both, args.dry_run)


def _after_write_hint() -> None:
    print("提示：hook 每個事件會重算；已開著的 session 要重開才會依新宣告注入。")


# ─── 入口 ─────────────────────────────────────────────────────────────────────


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(prog="project-tree.py", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cwd", help="要操作的層（預設目前目錄）")
    ap.add_argument("--dry-run", action="store_true", help="只印出將寫入的內容，不落檔")
    sp = ap.add_subparsers(dest="cmd", required=True)

    sp.add_parser("show", help="本層與上層宣告檔 + 生效解析").set_defaults(fn=cmd_show)
    p = sp.add_parser("explain", help="解析過程")
    p.add_argument("path", nargs="?")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_explain)
    p = sp.add_parser("set-root", help="設定本層 root")
    p.add_argument("path")
    p.add_argument("--abs", action="store_true", help="同時寫 root_abs（本機用）；指向非祖先時必帶")
    p.set_defaults(fn=cmd_set_root)
    sp.add_parser("unset-root", help="移除本層 root / root_abs").set_defaults(fn=cmd_unset_root)
    p = sp.add_parser("add-sub", help="本層 subs 增加")
    p.add_argument("rel", nargs="+")
    p.set_defaults(fn=cmd_add_sub)
    p = sp.add_parser("remove-sub", help="本層 subs 移除")
    p.add_argument("rel", nargs="+")
    p.set_defaults(fn=cmd_remove_sub)
    p = sp.add_parser("standalone", help="本層獨立 on|off")
    p.add_argument("mode", choices=("on", "off"))
    p.set_defaults(fn=cmd_standalone)
    p = sp.add_parser("claim", help="雙向認領根層")
    p.add_argument("--root", required=True)
    p.add_argument("--sub-path", help="根層 subs 要記的相對路徑（預設本層在根層下的第一段）")
    p.add_argument("--both", action="store_true", help="子層沒有 .claude/ 也建立並寫 root")
    p.set_defaults(fn=cmd_claim)
    p = sp.add_parser("pick", help="彈資料夾視窗選根層後 claim")
    p.add_argument("--sub-path")
    p.add_argument("--both", action="store_true")
    p.set_defaults(fn=cmd_pick)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()

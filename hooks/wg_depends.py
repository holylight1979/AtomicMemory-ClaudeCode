"""wg_depends：路徑→卡片召回（H3／A3.5）：讀到某個檔時，把索引 depends 有 `path:` 指到它（或它所在目錄）的卡列成一行一卡指標。

做什麼：PostToolUse（Read／Bash 讀檔）在 OverviewHub 的 on_read 之後呼叫 on_read_depends；對每個讀到的路徑查
lib.atom_spec.atoms_depending_on（全域索引以 ~/.claude 為根、專案索引以專案根為根），命中的卡一行一條
「[Guardian:Depends] 讀到 <檔> → 卡 `<卡名>`（<卡路徑>）：<條目>」；同一張卡一個 session 只提一次（state["depends_hints"]）。
讀到文件／計畫檔（authority_map 的樣式命中）且 authority_map 非空 → 一次性注入該部位權威地圖（state["authority_map_injected"]）。
每事件落一行 jsonl 到 workflow/_overview-hub.log（事件 depends_hint／authority_map），量 S5 用。全程 fail-open：索引讀不到就不提。
"""

from __future__ import annotations

import fnmatch
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import CLAUDE_DIR, MEMORY_DIR
from wg_overview import _cfg, _log, _project_root_of

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))   # 程式碼用本檔位置，CLAUDE_DIR 只定位資料
from atom_spec import atoms_depending_on  # noqa: E402
from overview_hub import read_paths_from_tool  # noqa: E402

_DOC_SUFFIXES = (".md", ".txt", ".rst", ".adoc")


def _mem_dirs(state: Dict[str, Any]) -> List[Tuple[Path, Path]]:
    """要查的索引：(索引目錄, Depends 相對路徑的根)。全域＝(~/.claude/memory, ~/.claude)；專案＝(<root>/.claude/memory, <root>)。"""
    out: List[Tuple[Path, Path]] = [(MEMORY_DIR, CLAUDE_DIR)]
    pmd = (state.get("atom_index") or {}).get("project_memory_dir") or ""
    if pmd:
        p = Path(pmd)
        root = p.parent.parent if p.parent.name == ".claude" else p.parent
        if (p / "_atom_index.json").is_file():
            out.append((p, root))
    return out


def _hint_lines(state: Dict[str, Any], session_id: str, path: str, mem_dirs: List[Tuple[Path, Path]]) -> List[str]:
    hinted: List[str] = state.setdefault("depends_hints", [])
    lines: List[str] = []
    for hit in atoms_depending_on(path, mem_dirs):
        if hit["name"] in hinted:
            continue
        hinted.append(hit["name"])
        lines.append(f"[Guardian:Depends] 讀到 {path} → 這個檔是卡 `{hit['name']}` 的壞滅緣（{hit['dep']}）；改它前先讀卡：{hit['card']}")
        _log("depends_hint", session_id, path=path, card=hit["name"], card_path=hit["card"], dep=hit["dep"])
    return lines


def _authority_map_for(path: str, cfg: Dict[str, Any], root: Optional[Path]) -> Optional[Tuple[str, Path]]:
    """path 命中 authority_map 的哪個樣式 → (樣式, 地圖路徑)；樣式對檔名或相對專案根路徑（正斜線、不分大小寫）。"""
    am = cfg.get("authority_map") or {}
    if not isinstance(am, dict) or not am:
        return None
    # 先 normpath 消解 `..`／`.`：docs/../src/a.md 是 src/a.md，不得命中 docs/*.md（fnmatch 的 * 會吃 /）
    norm = os.path.normpath(path).replace("\\", "/")
    name = norm.rsplit("/", 1)[-1]
    rel = None
    if root is not None:
        r = os.path.normpath(str(root)).replace("\\", "/").rstrip("/")
        if norm.lower().startswith(r.lower() + "/"):
            rel = norm[len(r) + 1:]
    for pat, target in am.items():
        p = str(pat).replace("\\", "/")
        if fnmatch.fnmatch(name.lower(), p.lower()) or (rel is not None and fnmatch.fnmatch(rel.lower(), p.lower())):
            mp = Path(str(target))
            if not mp.is_absolute() and root is not None:
                mp = root / mp
            return (str(pat), mp)
    return None


def _authority_map_text(state: Dict[str, Any], session_id: str, path: str, cfg: Dict[str, Any], root: Optional[Path]) -> Optional[str]:
    if state.get("authority_map_injected"):
        return None
    if not path.lower().endswith(_DOC_SUFFIXES):
        return None
    hit = _authority_map_for(path, cfg, root)
    if hit is None:
        return None
    pat, mp = hit
    try:
        body = mp.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        body = f"（地圖讀不到：{e}）"
    limit = int(cfg.get("max_card_chars") or 6000)
    if len(body) > limit:
        body = body[:limit] + f"\n…（超過 {limit} 字截斷，整張見 {mp}）"
    state["authority_map_injected"] = True
    _log("authority_map", session_id, path=path, pattern=pat, map=str(mp), chars=len(body))
    return (f"[Guardian:AuthorityMap] 讀到文件／計畫檔 {path}（命中 authority_map 樣式「{pat}」）。這一層的權威地圖只注入這一次，"
            f"改文件前先對照它：{mp}\n{body}")


def on_read_depends(state: Dict[str, Any], sid: str, tool_name: str, tool_input: Dict[str, Any],
                    cwd: str, config: Dict[str, Any]) -> Optional[str]:
    """PostToolUse（Read／Bash）：回要附給模型的文字（一行一卡指標＋可能的權威地圖），沒東西回 None。"""
    paths = read_paths_from_tool(tool_name, tool_input, cwd)
    if not paths:
        return None
    mem_dirs = _mem_dirs(state)
    out: List[str] = []
    for p in paths:
        out.extend(_hint_lines(state, sid, p, mem_dirs))
        root = _project_root_of(p)
        cfg = _cfg(config, root)
        if not cfg["enabled"]:
            continue
        am = _authority_map_text(state, sid, p, cfg, root)
        if am:
            out.append(am)
    return "\n".join(out) if out else None

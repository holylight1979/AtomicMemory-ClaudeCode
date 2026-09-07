"""project_root.py — 從 cwd 推導「記憶要歸哪個專案根」。

做什麼：沿祖先目錄讀 `.claude/project-tree.json` 宣告——根層列 `subs`、子層指 `root`——
決定 cwd 屬於哪個核心根層。沒有任何宣告時退回舊規則「最近四標記、最多 4 層」，行為不變。
怎麼跑：程式呼叫 resolve_project_root(cwd)；人用 `python tools/project-tree.py explain <cwd>`。

宣告檔欄位：root（相對本層、只准指祖先）、root_abs（本機絕對路徑，目錄存在時優先）、
subs（相對本層的路徑前綴，"*" 表全部）、standalone（true＝獨立、停止向上、不提問）。
路徑規則：沿字面路徑往上走，比對時才 resolve；回傳路徑保持字面形式。
排除：家目錄、~/.claude 本身、磁碟根永不當專案根，走到就停。
本模組只讀不寫；宣告檔的增刪改在 tools/project-tree.py。
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
MEMORY_INDEX = "MEMORY.md"
DECL_NAME = "project-tree.json"
MAX_ROOT_HOPS = 3
LEGACY_MAX_LEVELS = 4
DECLARED_KINDS = ("self", "own-root", "ancestor-root", "ancestor-subs")
CLAIM_LABEL = {
    "self": "本層即根層",
    "own-root": "本層 root",
    "ancestor-root": "上層 root",
    "ancestor-subs": "根層 subs",
}


@dataclass
class Declaration:
    path: Path
    valid: bool
    root: Optional[str] = None
    root_abs: Optional[str] = None
    subs: List[str] = field(default_factory=list)
    standalone: bool = False
    error: str = ""
    warnings: List[str] = field(default_factory=list)
    raw: Dict = field(default_factory=dict)

    @property
    def declares_root(self) -> bool:
        return bool(self.root or self.root_abs)


@dataclass
class Resolution:
    path: Optional[Path]
    claimed_by: str                      # self | own-root | ancestor-root | ancestor-subs | nearest | none
    nearest: Optional[Path]
    via: Optional[Path] = None           # 認領依據所在的層（印宣告行用）
    candidates: List[Path] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    infos: List[str] = field(default_factory=list)
    hops: List[Path] = field(default_factory=list)
    standalone: bool = False
    fork_atoms: int = 0
    fingerprint: str = ""
    decl_files: List[Tuple[str, float]] = field(default_factory=list)

    @property
    def declared(self) -> bool:
        return self.claimed_by in DECLARED_KINDS


# ─── 路徑小工具 ───────────────────────────────────────────────────────────────


def _literal(p: str) -> Path:
    """字面絕對路徑（不解 junction、不展 8.3），只做 normpath。"""
    return Path(os.path.normpath(os.path.abspath(p)))


def _norm(p: Path) -> Path:
    try:
        return p.resolve()
    except OSError:
        return p


def _same(a: Path, b: Path) -> bool:
    return _norm(a) == _norm(b)


def _within(child: Path, parent: Path) -> bool:
    """child 等於 parent 或位於其下（resolve 後逐元件比對，Windows 不分大小寫）。"""
    c, p = _norm(child), _norm(parent)
    return c == p or p in c.parents


def _excluded(p: Path) -> bool:
    n = _norm(p)
    return n == _norm(HOME) or n == _norm(CLAUDE_DIR) or n.parent == n


def _has_memory(layer: Path) -> bool:
    return (layer / ".claude" / "memory" / MEMORY_INDEX).exists()


def declaration_path(layer: Path) -> Path:
    return layer / ".claude" / DECL_NAME


def _rel_ok(value: str) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    if os.path.isabs(value):
        return False
    return ".." not in Path(value).parts


def load_declaration(layer: Path) -> Optional[Declaration]:
    """讀本層宣告。無檔 → None；有檔但壞 → valid=False（呼叫端印 ⚠️、當無檔處理）。"""
    p = declaration_path(layer)
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        return Declaration(path=p, valid=False, error=f"JSON 解析失敗：{e}")
    if not isinstance(raw, dict):
        return Declaration(path=p, valid=False, error="頂層必須是物件 {}")
    d = Declaration(path=p, valid=True, raw=raw)
    for key in ("root", "root_abs"):
        v = raw.get(key)
        if v is None:
            continue
        if not isinstance(v, str) or not v.strip():
            return Declaration(path=p, valid=False, error=f"{key} 必須是非空字串")
        setattr(d, key, v.strip())
    subs = raw.get("subs")
    if subs is not None:
        if not isinstance(subs, list):
            return Declaration(path=p, valid=False, error="subs 必須是字串陣列")
        for s in subs:
            if s == "*":
                d.subs.append("*")
            elif _rel_ok(s):
                d.subs.append(s.strip())
            else:
                d.warnings.append(f"{p}：subs 項目 {s!r} 含 .. 或為絕對路徑，略過")
    st = raw.get("standalone")
    if st is not None:
        if not isinstance(st, bool):
            return Declaration(path=p, valid=False, error="standalone 必須是 true/false")
        d.standalone = st
    return d


def _subs_cover(layer: Path, decl: Declaration, cwd: Path) -> bool:
    if "*" in decl.subs:
        return True
    return any(_within(cwd, layer / s) for s in decl.subs if s != "*")


def _declared_target(layer: Path, decl: Declaration, out: Resolution) -> Optional[Path]:
    """本層 root/root_abs 指向的目錄；規則：root_abs 存在優先，root 只准指祖先。"""
    abs_target = None
    if decl.root_abs:
        cand = _literal(decl.root_abs)
        if cand.is_dir():
            abs_target = cand
    rel_target = None
    if decl.root:
        cand = Path(os.path.normpath(str(layer / decl.root)))
        if _within(layer, cand) and not _same(layer, cand):
            rel_target = cand
        else:
            out.warnings.append(f"{decl.path}：root={decl.root!r} 不是本層的祖先，不採用（root 只准指祖先）")
    if abs_target and rel_target and not _same(abs_target, rel_target):
        out.warnings.append(f"{decl.path}：root_abs={abs_target} 與 root 解析出的 {rel_target} 不同，採 root_abs")
    return abs_target or rel_target


def _follow_root_chain(layer: Path, decl: Declaration, out: Resolution) -> Optional[Path]:
    """跟著 root 鏈往上找終點根；失敗原因已寫進 out.warnings / out.infos。"""
    cur_layer, cur_decl = layer, decl
    seen = {_norm(layer)}
    for _ in range(MAX_ROOT_HOPS):
        target = _declared_target(cur_layer, cur_decl, out)
        if target is None:
            return None
        if _excluded(target):
            out.warnings.append(f"{cur_decl.path}：root 指向 {target}（家目錄／~/.claude／磁碟根），不採用")
            return None
        if _norm(target) in seen:
            out.warnings.append(f"{cur_decl.path}：root 鏈成環於 {target}，不採用")
            return None
        seen.add(_norm(target))
        if not (target / ".claude").is_dir():
            out.infos.append(f"上層 {target} 未 checkout（無 .claude/），記憶留本層")
            return None
        if _has_memory(target):
            return target
        tdecl = load_declaration(target)
        if tdecl is not None:
            out.decl_files.append(_decl_sig(tdecl))
        if tdecl is None or not tdecl.valid:
            why = tdecl.error if tdecl else "無 memory/MEMORY.md 也無有效宣告檔"
            out.warnings.append(f"{cur_decl.path}：root 指向 {target}，但該層 {why}，不採用")
            return None
        if tdecl.declares_root:
            cur_layer, cur_decl = target, tdecl
            continue
        out.infos.append(f"根層 {target} 的 memory 尚未同步，首次寫入會就地建樹")
        return target
    out.warnings.append(f"{decl.path}：root 鏈超過 {MAX_ROOT_HOPS} 跳仍未到達根層，不採用")
    return None


def _cross_check_terminal(layer: Path, root: Path, out: Resolution) -> None:
    tdecl = load_declaration(root)
    if tdecl is not None:
        out.decl_files.append(_decl_sig(tdecl))   # 根層宣告改了也要讓指紋／快取失效
    if tdecl is None or not tdecl.valid or not tdecl.subs:
        return
    if not _subs_cover(root, tdecl, layer):
        rel = os.path.relpath(str(layer), str(root))
        out.warnings.append(
            f"根層 {root} 的 subs 未列本層（可 `python ~/.claude/tools/project-tree.py add-sub {rel} --cwd {root}`）")


def _decl_sig(decl: Declaration) -> Tuple[str, float]:
    try:
        return (str(decl.path), decl.path.stat().st_mtime)
    except OSError:
        return (str(decl.path), 0.0)


def _fork_atom_count(layer: Path) -> int:
    idx = layer / ".claude" / "memory" / "_atom_index.json"
    if not idx.is_file():
        return 0
    try:
        data = json.loads(idx.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    atoms = data.get("atoms") if isinstance(data, dict) else None
    return len(atoms) if isinstance(atoms, (list, dict)) else 0


# ─── 舊規則（無宣告時的 fallback）─────────────────────────────────────────────


def has_project_marker(root: Path) -> bool:
    """四標記 ∪ 有效宣告檔。取代 wg_core / atom_io 各自複製的判斷。"""
    if (root / ".claude" / "memory" / MEMORY_INDEX).exists():
        return True
    if (root / "_AIDocs").is_dir():
        return True
    if (root / ".git").exists() or (root / ".svn").exists():
        return True
    d = load_declaration(root)
    return bool(d and d.valid)


def _legacy_nearest(start: Path) -> Optional[Path]:
    """舊規則：最近四標記、最多 4 層。家目錄與磁碟根永不當專案根（~/.claude 本身仍可，核心層語意）。"""
    p = start
    for _ in range(LEGACY_MAX_LEVELS):
        if _norm(p) == _norm(HOME) or p.parent == p:
            break
        if has_project_marker(p):
            return p
        p = p.parent
    return None


# ─── 主流程 ───────────────────────────────────────────────────────────────────

_CACHE: Dict[str, Resolution] = {}


def clear_cache() -> None:
    _CACHE.clear()


def _cache_valid(res: Resolution) -> bool:
    for path, mtime in res.decl_files:
        try:
            if Path(path).stat().st_mtime != mtime:
                return False
        except OSError:
            if mtime != 0.0:
                return False
    return True


def resolve_project_root(cwd: Optional[str]) -> Resolution:
    if not cwd:
        return Resolution(path=None, claimed_by="none", nearest=None)
    start = _literal(cwd)
    hit = _CACHE.get(str(start))
    if hit is not None and _cache_valid(hit):
        return hit
    res = _resolve(start)
    _CACHE[str(start)] = res
    return res


def _resolve(start: Path) -> Resolution:
    out = Resolution(path=None, claimed_by="none", nearest=_legacy_nearest(start))
    layers: List[Path] = []
    p = start
    while True:
        if _excluded(p):
            break
        layers.append(p)
        if p.parent == p:
            break
        p = p.parent

    self_subs_only: Optional[Path] = None
    for idx, layer in enumerate(layers):
        is_self = idx == 0
        decl = load_declaration(layer)
        if decl is None:
            if not is_self and _has_memory(layer):
                out.candidates.append(layer)
            continue
        out.hops.append(layer)
        out.decl_files.append(_decl_sig(decl))
        if not decl.valid:
            out.warnings.append(f"{decl.path}：{decl.error}（視為無宣告）")
            if not is_self and _has_memory(layer):
                out.candidates.append(layer)
            continue
        out.warnings.extend(decl.warnings)

        if decl.standalone:
            out.standalone = True
            break

        if self_subs_only is not None:
            # 本層已自立為根；只檢查外層是否也列了它（矛盾提示），不再認領。
            if decl.subs and _subs_cover(layer, decl, self_subs_only):
                out.warnings.append(
                    f"{self_subs_only} 自立為根（只有 subs），但外層 {layer} 的 subs 也列了它；以本層為準")
            continue

        if decl.declares_root:
            # 宣告 root 的層是子專案：它自己與底下全部都歸那個根
            target = _follow_root_chain(layer, decl, out)
            if target is None:
                if not is_self and _has_memory(layer):
                    out.candidates.append(layer)
                continue
            out.path = target
            out.claimed_by = "own-root" if is_self else "ancestor-root"
            out.via = layer
            _cross_check_terminal(layer, target, out)
            break

        if is_self:
            out.path = layer
            out.claimed_by = "self"
            out.via = layer
            if decl.subs:
                self_subs_only = layer
                continue
            break
        if decl.subs and _subs_cover(layer, decl, start):
            out.path = layer
            out.claimed_by = "ancestor-subs"
            out.via = layer
            break
        if _has_memory(layer):
            out.candidates.append(layer)

    if out.path is None:
        out.path = out.nearest
        out.claimed_by = "nearest" if out.nearest else "none"
    # 候選＝「有記憶層但沒宣告關係、且不是目前生效根」的上層；等於生效根就沒什麼可問
    out.candidates = [c for c in out.candidates if out.path is None or not _same(c, out.path)]

    if out.declared and out.path is not None:
        if not _has_memory(out.path) and not any("尚未同步" in i for i in out.infos):
            out.infos.append(f"根層 {out.path} 的 memory 尚未同步，首次寫入會就地建樹")
        if out.nearest is not None and not _same(out.nearest, out.path):
            out.fork_atoms = _fork_atom_count(out.nearest)
            if out.fork_atoms:
                out.warnings.append(
                    f"子專案 {out.nearest} 已有 {out.fork_atoms} 顆分叉 atom，"
                    f"請用 MCP atom_move 併回 {out.path}")

    h = hashlib.sha1()
    h.update(f"{start}|{out.path}|{out.claimed_by}|".encode("utf-8", "replace"))
    for path, mtime in out.decl_files:
        h.update(f"{path}:{mtime};".encode("utf-8", "replace"))
    out.fingerprint = h.hexdigest()[:16]
    return out


def describe(res: Resolution, cwd: str) -> List[str]:
    """人看的解析摘要（tools/project-tree.py explain / show 用）。"""
    lines = [f"cwd        : {cwd}",
             f"root       : {res.path}",
             f"claimed_by : {res.claimed_by}" + (f"（{CLAIM_LABEL[res.claimed_by]} @ {res.via}）" if res.via else ""),
             f"nearest    : {res.nearest}",
             f"standalone : {res.standalone}",
             f"fingerprint: {res.fingerprint}"]
    if res.hops:
        lines.append("hops       : " + " → ".join(str(h) for h in res.hops))
    if res.candidates:
        lines.append("candidates : " + ", ".join(str(c) for c in res.candidates))
    for i in res.infos:
        lines.append(f"info       : {i}")
    for w in res.warnings:
        lines.append(f"warning    : {w}")
    return lines

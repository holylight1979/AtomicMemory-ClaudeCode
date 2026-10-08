"""realm_gate.py — 「專案專屬內容不得落 global」寫入閘（單一來源）。

呼叫端：`atom_io.write_atom`（py funnel）、`atom_io_cli` action=realm_check（MCP js 端
atom_write 對 scope=global 的 create/append/replace 一律先問這裡，`skip_gate` 只跳
品質/去重閘、跳不過本閘）。

判定：呼叫端 cwd（`project_cwd`，缺則 MCP 進程 cwd）上溯到專案 root；root 不存在或
就是 ~/.claude → 本閘不啟動。啟動後掃 title / triggers / knowledge / actions，命中任何
「專案專名」→ 拒寫，回訊附可直接重呼叫的 `scope=shared, project_cwd=<root>` 與落點。

專名來源（全部機械化推導，不寫死任何專案名）：
  1. 專案 root 的頂層資料夾名（含 `_` 前綴者）
  2. 專案 CLAUDE.md 與 _AIDocs/Workspace_Map.md 表格首欄的 `` `name/` `` 成員
  3. 專案 repo-paths atom 內的 `{code}` 路徑代號
  4. 以專案 root 為前綴的絕對路徑（drive-letter 路徑，pattern 比對、非清單）
  5. 字面「此專案」「本專案」「這個專案」「這專案」

  6. 本機已登記專案的名字（`memory/project-registry.json`：專案根資料夾名＋ASCII 別名＋
     `project_names` 手列名單）。registry 不進版控，根層版控檔因此不必寫任何專案名。

啟動條件：
  - cwd 在專案內 → 1–6 全掃。
  - cwd 在 ~/.claude（或沒有 cwd）→ 只掃 6 與「已登記專案根底下的絕對路徑」。根層 session
    寫全域卡片時最容易把別的專案名帶進來，這條路以前完全不檢查。

排除規則（避免泛詞誤殺）：與 ~/.claude 頂層同名者（`_AIDocs`、`tools`… 全域也有，不具
辨識力；區分大小寫，故 `Tools` 仍算專名）；`.` 開頭；純小寫 ASCII 且短於 4 字（web 之類）。

比對規則：ASCII 專名 → 區分大小寫 + 字邊界（前後皆非 [A-Za-z0-9_]）；含 CJK 或非 ASCII
的專名與字面片語 → 子字串。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

CLAUDE_DIR = Path.home() / ".claude"

# 字面「專案指涉」片語（泛用，非專案名）
PROJECT_LITERALS = ("此專案", "本專案", "這個專案", "這專案")

_MEMBER_CELL_RE = re.compile(r"`([^`\s|]+?)/`")          # 表格內 `name/`
_REPO_CODE_RE = re.compile(r"\{([A-Za-z0-9_\-]+)\}")     # {game_server}
_ABS_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"'`|<>)\]]*")
_WORD_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")

REGISTRY_PATH = CLAUDE_DIR / "memory" / "project-registry.json"

# 資料夾名或別名是這些泛詞時不當專名（tmp、Projects、Client 這類容器資料夾）
_GENERIC_NAMES = {
    "projects", "project", "client", "server", "tools", "tool", "tmp", "temp", "office",
    "docs", "doc", "game", "games", "src", "dev", "test", "tests", "data", "app", "apps",
    "web", "common", "shared", "work", "code", "repo", "main", "home", "users",
}

# 掃描欄位順序（訊息用）
_FIELDS = ("title", "triggers", "knowledge", "actions")


def project_root_of(cwd: Optional[str]) -> Optional[Path]:
    """cwd 上溯專案 root（對拍 atom_io._find_project_root；lazy import 避免循環）。"""
    if not cwd:
        return None
    try:
        from .atom_io import _find_project_root
    except ImportError:  # 頂層模組載入
        from atom_io import _find_project_root  # type: ignore
    return _find_project_root(cwd)


def is_core_root(root: Optional[Path]) -> bool:
    """root 是 ~/.claude 本身或其子樹 → 核心環境，本閘不啟動。"""
    if root is None:
        return True
    try:
        r = root.resolve()
        home = CLAUDE_DIR.resolve()
    except OSError:
        return False
    return r == home or home in r.parents


def _is_ascii(s: str) -> bool:
    return all(ord(ch) < 128 for ch in s)


def _claude_top_names() -> set:
    try:
        return {p.name for p in CLAUDE_DIR.iterdir()}
    except OSError:
        return set()


def _accept_term(name: str, claude_names: set) -> bool:
    name = name.strip().rstrip("/\\")
    if not name or name.startswith(".") or len(name) < 2 or "://" in name:
        return False
    if name in claude_names:                       # 全域也有 → 不具辨識力（區分大小寫）
        return False
    if _is_ascii(name) and name.islower() and len(name) < 4:   # web / src 類泛詞
        return False
    return True


def _member_names_from_tables(path: Path) -> List[str]:
    """markdown 表格列（`|` 開頭）內的 `` `name/` `` 成員名。"""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return []
    out: List[str] = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        out.extend(_MEMBER_CELL_RE.findall(line))
    return out


def _repo_paths_atom(root: Path) -> Optional[Path]:
    """專案 memory 內的 repo-paths atom（索引 path 優先，其次 rglob）。"""
    mem = root / ".claude" / "memory"
    if not mem.is_dir():
        return None
    try:
        import json
        data = json.loads((mem / "_atom_index.json").read_text(encoding="utf-8-sig"))
        for a in data.get("atoms", []):
            if a.get("name") == "repo-paths" and a.get("path"):
                p = mem.parent / a["path"]
                if p.exists():
                    return p
    except (OSError, ValueError):
        pass
    for hit in mem.rglob("repo-paths.md"):
        return hit
    return None


def project_terms(root: Path) -> Dict[str, str]:
    """專名 → 來源說明。root 必須是專案 root（非 ~/.claude）。"""
    claude_names = _claude_top_names()
    terms: Dict[str, str] = {}

    def add(name: str, source: str) -> None:
        name = name.strip().rstrip("/\\")
        if _accept_term(name, claude_names) and name not in terms:
            terms[name] = source

    # 1. 頂層資料夾
    try:
        for p in root.iterdir():
            if p.is_dir():
                add(p.name, "頂層資料夾")
    except OSError:
        pass
    # 2. CLAUDE.md / Workspace_Map.md 表格成員
    for rel in ("CLAUDE.md", "_AIDocs/Workspace_Map.md"):
        for name in _member_names_from_tables(root / rel):
            add(name, f"{rel} 成員表")
    # 3. repo-paths atom 的 {code} 代號
    rp = _repo_paths_atom(root)
    if rp is not None:
        try:
            for code in _REPO_CODE_RE.findall(rp.read_text(encoding="utf-8-sig")):
                terms.setdefault("{" + code + "}", "repo-paths 路徑代號")
        except OSError:
            pass
    return terms


def _load_registry() -> Dict[str, Any]:
    try:
        import json
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _org_root_names() -> set:
    """公司層 repo 的資料夾名：它是記憶系統的設定對象，不是專案，根層文件可以提。"""
    names = {"CompanyAtomsMem"}
    try:
        import json
        cfg = json.loads((CLAUDE_DIR / "workflow" / "config.json").read_text(encoding="utf-8-sig"))
        org = cfg.get("org_memory") or {}
        for r in [org.get("default_root", "")] + list(org.get("roots") or []):
            if r:
                names.add(Path(str(r).replace("~", str(Path.home()))).name)
    except (OSError, ValueError, AttributeError):
        pass
    return names


def _registry_name_ok(name: str) -> bool:
    """registry 推導的候選名是否夠具辨識力。CJK 別名多半是路由用泛詞（遊戲後端、辦公），不收。"""
    if not name or name.startswith(".") or not _is_ascii(name) or len(name) < 3:
        return False
    return name.lower() not in _GENERIC_NAMES


def known_project_names() -> List[Tuple[str, str, bool]]:
    """本機已登記專案的名字 → [(名字, 來源, 是否不分大小寫)]。

    registry 推導的名字不分大小寫比對（別名常是小寫，例 abc 要擋到 ABC）；
    `project_names` 手列名單照寫法比對（例 名單寫 Qux 只擋 Qux，不擋同字母的泛稱 QUX）。"""
    reg = _load_registry()
    skip = _org_root_names()
    out: List[Tuple[str, str, bool]] = []
    seen = set()

    def add(name: str, source: str, ci: bool) -> None:
        name = (name or "").strip().rstrip("/\\")
        key = name.lower() if ci else name
        if not name or name in skip or key in seen:
            return
        seen.add(key)
        out.append((name, source, ci))

    for entry in (reg.get("projects") or {}).values():
        if not isinstance(entry, dict):
            continue
        root = str(entry.get("root") or "")
        cands = [Path(root).name] if root else []
        cands += [str(a) for a in (entry.get("aliases") or [])]
        for c in cands:
            if _registry_name_ok(c.strip()):
                add(c, "已登記專案", True)
    for name in reg.get("project_names") or []:
        if str(name).strip():
            add(str(name), "本機專案名單", False)
    return out


def known_project_roots() -> List[str]:
    """已登記專案根（正規化）。tmp、Projects 這類容器資料夾也算，因為底下就是專案。"""
    reg = _load_registry()
    skip = {n.lower() for n in _org_root_names()}
    roots = []
    for entry in (reg.get("projects") or {}).values():
        if not isinstance(entry, dict):
            continue
        root = str(entry.get("root") or "")
        if root and Path(root).name.lower() not in skip:
            roots.append(_norm_path(root))
    return roots


def anonymize_projects(text: str) -> str:
    """把已登記專案根底下的絕對路徑換成「<專案路徑>」、專案名換成「某專案」。
    給自動抄錄進根層卡片的欄位用（例：Quote 抄的是使用者原話，原話常帶專案名與路徑）。"""
    if not text:
        return text
    roots = known_project_roots()

    def _path(m: "re.Match") -> str:
        cand = _norm_path(m.group(0))
        return "<專案路徑>" if any(cand == r or cand.startswith(r + "/") for r in roots) else m.group(0)

    out = _ABS_PATH_RE.sub(_path, text)
    for name, _src, ci in sorted(known_project_names(), key=lambda t: -len(t[0])):
        out = _name_pattern(name, ci).sub("某專案", out)
    return out


# 已登記專案名的字邊界不含底線：專案名常當前綴出現（`Abc_Hotfix`、`abc_server`），也要算命中
_NAME_BOUNDARY = r"(?<![A-Za-z0-9]){}(?![A-Za-z0-9])"


def _name_pattern(name: str, ci: bool) -> "re.Pattern":
    if not _is_ascii(name):
        return re.compile(re.escape(name))
    return re.compile(_NAME_BOUNDARY.format(re.escape(name)), re.IGNORECASE if ci else 0)


def _contains_name(text: str, name: str, ci: bool) -> bool:
    return bool(_name_pattern(name, ci).search(text))


def _contains_term(text: str, term: str) -> bool:
    if not _is_ascii(term):
        return term in text
    start = 0
    while True:
        i = text.find(term, start)
        if i < 0:
            return False
        before = text[i - 1] if i > 0 else ""
        after = text[i + len(term)] if i + len(term) < len(text) else ""
        if before not in _WORD_CHARS and after not in _WORD_CHARS:
            return True
        start = i + 1


def _norm_path(s: str) -> str:
    return s.replace("\\", "/").rstrip("/").lower()


def _iter_field_texts(fields: Dict[str, Any]):
    for field_name in _FIELDS:
        raw = fields.get(field_name)
        if raw is None:
            continue
        items: Iterable[str] = [raw] if isinstance(raw, str) else [str(x) for x in raw]
        for text in items:
            if text:
                yield field_name, text


def scan_known_projects(fields: Dict[str, Any]) -> List[Dict[str, str]]:
    """只掃本機已登記專案的名字與專案根底下的絕對路徑（根層 cwd 也適用）。"""
    names = known_project_names()
    roots = known_project_roots()
    hits: List[Dict[str, str]] = []
    seen = set()
    for field_name, text in _iter_field_texts(fields):
        for name, source, ci in names:
            if (field_name, name.lower()) not in seen and _contains_name(text, name, ci):
                seen.add((field_name, name.lower()))
                hits.append({"field": field_name, "term": name, "source": source,
                             "excerpt": text.strip()[:80]})
        for m in _ABS_PATH_RE.finditer(text):
            cand = _norm_path(m.group(0))
            if (field_name, cand) in seen:
                continue
            if any(cand == r or cand.startswith(r + "/") for r in roots):
                seen.add((field_name, cand))
                hits.append({"field": field_name, "term": m.group(0), "source": "已登記專案路徑",
                             "excerpt": text.strip()[:80]})
    return hits


def scan_texts(root: Path, fields: Dict[str, Any], terms: Optional[Dict[str, str]] = None) -> List[Dict[str, str]]:
    """掃描各欄位文字，回命中清單 [{field, term, source, excerpt}]。"""
    if terms is None:
        terms = project_terms(root)
    root_norm = _norm_path(str(root))
    hits: List[Dict[str, str]] = []
    seen = set()

    def push(field_name: str, term: str, source: str, text: str) -> None:
        key = (field_name, term)
        if key in seen:
            return
        seen.add(key)
        hits.append({"field": field_name, "term": term, "source": source,
                     "excerpt": text.strip()[:80]})

    for field_name in _FIELDS:
        raw = fields.get(field_name)
        if raw is None:
            continue
        items: Iterable[str] = [raw] if isinstance(raw, str) else [str(x) for x in raw]
        for text in items:
            if not text:
                continue
            for term, source in terms.items():
                if _contains_term(text, term):
                    push(field_name, term, source, text)
            for lit in PROJECT_LITERALS:
                if lit in text:
                    push(field_name, lit, "字面專案指涉", text)
            for m in _ABS_PATH_RE.finditer(text):
                cand = _norm_path(m.group(0))
                if cand == root_norm or cand.startswith(root_norm + "/"):
                    push(field_name, m.group(0), "專案絕對路徑", text)
    return hits


def _suggest_landing(root: Path, title: str, domain: Optional[str]) -> str:
    try:
        from .atom_spec import slugify
    except ImportError:
        from atom_spec import slugify  # type: ignore
    slug = slugify(title or "")
    dom = domain or "<Lv1>[/<Lv2>]"
    base = root / ".claude" / "memory"
    if slug.startswith("feedback-"):
        return str(base / "failures" / dom / f"{slug}.md")
    return str(base / "shared" / dom / f"{slug}.md")


def check_global_write(
    project_cwd: Optional[str],
    *,
    title: str,
    triggers: Optional[Iterable[str]] = None,
    knowledge: Optional[Iterable[str]] = None,
    actions: Optional[Iterable[str]] = None,
    domain: Optional[str] = None,
) -> Optional[str]:
    """根層（scope=global、本人跨專案 personal）寫入前的範疇閘。回 None=放行；回字串=拒寫理由。"""
    root = project_root_of(project_cwd)
    fields = {"title": title, "triggers": list(triggers or []),
              "knowledge": list(knowledge or []), "actions": list(actions or [])}
    core = is_core_root(root)
    hits = [] if core else scan_texts(root, fields)
    have = {(h["field"], h["term"].lower()) for h in hits}
    hits += [h for h in scan_known_projects(fields) if (h["field"], h["term"].lower()) not in have]
    if not hits:
        return None
    shown = hits[:6]
    where = "根層" if core else f"專案「{root.name}」"
    lines = [
        f"realm gate: scope=global rejected — 內容含專案專名或專案路徑（寫入端：{where}）。"
        "根層只放跨專案的經驗與知識，不得帶專案名。",
        "命中：" + "；".join(
            f"{h['field']}『{h['term']}』({h['source']})" for h in shown)
        + ("…" if len(hits) > len(shown) else ""),
        "改寫原則：①專案名不是必要就拔掉，只寫核心要點或具體現象 ②真要指涉時寫「某專案」"
        "③用代稱也不寫電腦路徑 ④拔名後事實描述不能走樣。",
    ]
    if core:
        lines.append("專案專屬知識改寫到該專案（scope=shared＋該專案 project_cwd）或公司層（scope=org）。")
    else:
        lines.append(f"專案專屬知識改用：scope=\"shared\", project_cwd=\"{root}\"（domain 照給）"
                     f"→ 落 {_suggest_landing(root, title, domain)}")
    lines += ["（本閘不受 skip_gate 影響；append/replace 帶專名的新內容同樣擋。）",
              f"[gate cwd={project_cwd}]"]
    return "\n".join(lines)

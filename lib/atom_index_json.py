"""atom_index_json.py — _atom_index.json single source of truth.

Schema:
    {
      "version": "1.0",
      "atoms": [
        {"name": str, "path": str, "triggers": [str], "scope": str, "last_used": str?, "depends": [str]?,
         "related": [str]?, "aka": [str]?, "entry": [str]?}
      ]
    }

depends（optional）：卡片 frontmatter `- Depends:` 的條目（`path:<檔或目錄>` 或自由文字），frontmatter 為真相；
讀到 path: 指到的檔時由 hooks/wg_depends 召回一行指標（lib.atom_spec.atoms_depending_on）。
entry（optional）：卡片 frontmatter `- Entry:` 的切入點代號（workflow/entrypoints.json），frontmatter 為真相；
程式在那個切入點問 LLM 時先送 entry 命中的卡（hooks/wg_entrypoint.cards_for_entry）。

責任：
- load_atom_index_json(mem_dir, strict=False) -> {atoms: [...]}（strict：檔在卻讀不到 → OSError，整份寫回的呼叫端用）
- upsert_atom(mem_dir, name, path, triggers, scope, last_used, depends) -> bool（depends 未傳保留、[] 清空）
- apply_upsert(data, ...) -> bool：同一套語意只改記憶體裡的 data（整批補登用，最後 save_index_with_mirror 一次落檔）
- delete_atom(mem_dir, name, path=None) -> bool（給 path 時只刪 name+path 都相符的條目）
- save_index_with_mirror(mem_dir, data)：JSON 先、md 鏡像後，兩份由同一份 data 產生
- regenerate_atom_index_md(mem_dir) -> 同步重生 _ATOM_INDEX.md 作為人類可讀 deprecated view

換檔與讀檔對 PermissionError 稍等重試（Windows：別的行程正開著索引讀時 os.replace 會 WinError 5，
剛被換掉的檔讀起來也會短暫拒絕存取）。

舊 _ATOM_INDEX.md 仍由本模組生成（保留人類可讀視圖過渡期），
但唯一機器源是 JSON；hooks/MCP/lib 統一走本模組。

讀取容錯：JSON 不存在或損毀 → 回 {"atoms": []}（caller 自行 fallback _ATOM_INDEX.md）。
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


ATOM_INDEX_JSON = "_atom_index.json"
ATOM_INDEX_MD = "_ATOM_INDEX.md"
SCHEMA_VERSION = "1.0"
TRIGGER_MAX_LEN = 30  # validate_index 與 write funnel 共用（寫入當下即驗，不留到後續操作才爆）
BUSY_RETRIES = 5      # 索引被別的行程開著時最多試幾次
BUSY_WAIT_S = 0.2     # 每次之間等多久


def retry_busy(op: Callable[[], Any]) -> Any:
    """PermissionError（WinError 5／Errno 13：別的行程正開著、或檔剛被換掉）稍等重試，試滿仍不行就原樣丟出。
    FileNotFoundError 等其他錯誤不是「忙」，不重試。"""
    for attempt in range(BUSY_RETRIES):
        try:
            return op()
        except PermissionError:
            if attempt == BUSY_RETRIES - 1:
                raise
            time.sleep(BUSY_WAIT_S)


def find_index_dir(path: Path) -> Optional[Path]:
    """從 path 往上找最近含 _atom_index.json 的祖先 = index root（memory root）。

    單一來源：edit_metadata（專案層 atom 的索引歸屬）與 tools/atom-move.py 共用，
    取代各處硬編 ~/.claude 或自刻上溯。找不到回 None。
    """
    try:
        cur = Path(path).resolve(strict=False)
    except OSError:
        cur = Path(path)
    while True:
        if (cur / ATOM_INDEX_JSON).exists():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def _write_text_lf(path: Path, content: str) -> None:
    """tmp + rename 落檔，內容一律 LF（與 atom_io.write_text_lf 同規則；本模組只依賴 stdlib 故自帶一份）。

    索引檔每次 upsert 都整檔 regen；newline="" 關掉平台轉譯，Windows 才不會把 \\n 翻成 \\r\\n。
    tmp 後綴帶 PID+TID：索引檔全系統共用，併發 session upsert 不互踩。
    """
    body = content.replace("\r\n", "\n").replace("\r", "\n")
    import threading as _threading
    tmp = path.with_suffix(
        f"{path.suffix}.tmp.{os.getpid()}.{_threading.get_ident()}"
    )
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(body)
        retry_busy(lambda: tmp.replace(path))
    except OSError:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def _empty_index() -> Dict[str, Any]:
    return {"version": SCHEMA_VERSION, "atoms": []}


def load_atom_index_json(mem_dir: Path, *, strict: bool = False) -> Dict[str, Any]:
    """Load _atom_index.json; missing／JSON 壞／形狀不對 → empty.

    檔在卻讀不到（重試完仍被別的行程鎖著、權限）：預設回空索引（讀取端 fallback）；strict=True 改丟 OSError——
    要整份寫回的呼叫端拿空索引去寫，等於把一份好好的索引抹掉。內容壞掉（合併衝突標記、手改壞）兩種模式都回空索引：
    那份本來就讀不回條目，--add-from-frontmatter／--rebuild 從磁碟重生是文件寫明的復原路徑（MultiMachineMemorySync.md）。"""
    p = mem_dir / ATOM_INDEX_JSON
    if not p.exists():
        return _empty_index()
    try:
        text = retry_busy(lambda: p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as e:
        if strict and isinstance(e, OSError):
            raise OSError(f"{p} 讀不到（{e}）；不拿空索引覆寫，等佔用它的行程放開後重跑") from e
        return _empty_index()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return _empty_index()
    if not isinstance(data, dict) or not isinstance(data.get("atoms"), list):
        return _empty_index()
    return data


def save_atom_index_json(mem_dir: Path, data: Dict[str, Any]) -> None:
    p = mem_dir / ATOM_INDEX_JSON
    born = not p.exists()
    p.parent.mkdir(parents=True, exist_ok=True)
    _write_text_lf(
        p, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False)
    )
    if born:
        _on_index_born(mem_dir)


def _on_index_born(mem_dir: Path) -> None:
    """索引首次落檔＝衍生檔誕生的那一刻：順手把它排除在專案版控外（svn:ignore／.gitignore）。

    只對專案記憶庫（~/.claude 自己的記憶由根層 repo 規則管）；無 VCS 零子行程；fail-open，失敗只 stderr。
    「已被版控」的告警交 SessionStart（lib/vcs_ignore.advisory_lines）。
    """
    try:
        try:
            from .vcs_ignore import ensure_ignore, under_claude_dir
        except ImportError:  # 頂層模組載入（wg_core / CLI sys.path.insert）
            from vcs_ignore import ensure_ignore, under_claude_dir
        if under_claude_dir(mem_dir):
            return
        for rep in ensure_ignore(mem_dir):
            if rep.get("error") and rep.get("skipped") != "no-cli":
                print(f"[atom_index_json] {rep['vcs']} ignore 未設：{rep['error']}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"[atom_index_json] vcs ignore skipped: {e}", file=sys.stderr)


def dedup_triggers(triggers, *, lower: bool = False) -> List[str]:
    """strip + 去空 + 大小寫不敏感保序去重（首見者勝）；lower=True 時輸出一律小寫。

    讀寫兩側共用：索引若同時含 "foobar" 與 "FooBar"，讀取側 .lower() 後會變成
    兩顆相同 trigger，count_trigger_hits 對單字回 2 而灌水越過跨專案 >=2 門檻。
    """
    out: List[str] = []
    seen = set()
    for t in triggers or []:
        if not isinstance(t, str):
            continue
        t = t.strip()
        if not t:
            continue
        key = t.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(t.lower() if lower else t)
    return out


def validate_depends(depends: Any) -> List[str]:
    """索引 depends 欄：list[str]，每條 strip 後非空；其他型別／元素一律 ValueError（寫入當下即拒，不留到 validate_index 才爆）。"""
    if not isinstance(depends, list):
        raise ValueError(f"depends must be a list of str, got {type(depends).__name__}")
    out: List[str] = []
    for d in depends:
        if not isinstance(d, str):
            raise ValueError(f"depends item must be str, got {type(d).__name__}: {d!r}")
        s = d.strip()
        if s and s not in out:
            out.append(s)
    return out


def upsert_atom(
    mem_dir: Path,
    name: str,
    path: str,
    triggers: List[str],
    scope: str = "global",
    last_used: Optional[str] = None,
    depends: Optional[List[str]] = None,
    related: Optional[List[str]] = None,
    aka: Optional[List[str]] = None,
    entry: Optional[List[str]] = None,
) -> bool:
    """Insert or update an atom entry. Returns True if changed.

    depends（optional，`path:<檔>` 或自由文字）：None＝未傳 → 沿用既有條目的 depends（4 參數的舊呼叫者不丟欄）；
    `[]` → 清空（移除鍵）；非空清單 → 取代。型別不對直接 ValueError。

    `related` ＝該 atom 自己寫的**正向**連結。反向連結不存檔：注入端讀本索引後在記憶體反轉
    （`wg_atoms.load_link_graph`）。存兩份的話，新增一顆連到 hub 的 atom 就得去改 hub 那個檔——
    那是別人的檔，多人共用時必衝突。

    `aka` ＝這顆用過的舊檔名，來自 atom 的 `- Aka:` 行。連結以檔名為鍵，改名時靠它讓舊連結
    續存，改名者只動自己這一顆。兩者都是加法欄位：舊版工具讀不到就當沒有，故 schema 不升版。

    `entry` ＝這顆是哪幾個切入點的判準卡，來自 atom 的 `- Entry:` 行；同 related：None＝沿用既有、`[]`＝移除鍵。
    """
    data = load_atom_index_json(mem_dir)
    if not apply_upsert(data, name, path, triggers, scope, last_used=last_used, depends=depends,
                        related=related, aka=aka, entry=entry):
        return False
    save_index_with_mirror(mem_dir, data)
    return True


def apply_upsert(
    data: Dict[str, Any],
    name: str,
    path: str,
    triggers: List[str],
    scope: str = "global",
    last_used: Optional[str] = None,
    depends: Optional[List[str]] = None,
    related: Optional[List[str]] = None,
    aka: Optional[List[str]] = None,
    entry: Optional[List[str]] = None,
) -> bool:
    """upsert_atom 的語意，只改記憶體裡的 data、不落檔；回有沒有改到。整批補登逐顆套完再一次落檔。"""
    atoms = data["atoms"]
    triggers = dedup_triggers(triggers)
    depends_list = validate_depends(depends) if depends is not None else None
    new_entry: Dict[str, Any] = {
        "name": name,
        "path": path,
        "triggers": triggers,
        "scope": scope,
    }
    existing = next((a for a in atoms if a.get("name") == name), None)
    keep = related if related is not None else (existing or {}).get("related")
    if keep:
        new_entry["related"] = list(dict.fromkeys(keep))
    keep_aka = aka if aka is not None else (existing or {}).get("aka")
    if keep_aka:
        new_entry["aka"] = list(dict.fromkeys(keep_aka))
    keep_entry = entry if entry is not None else (existing or {}).get("entry")
    if keep_entry:
        new_entry["entry"] = list(dict.fromkeys(keep_entry))
    if last_used:
        new_entry["last_used"] = last_used

    for i, a in enumerate(atoms):
        if a.get("name") == name:
            if depends_list is None:
                prev = a.get("depends")
                if isinstance(prev, list) and prev:
                    new_entry["depends"] = list(prev)
            elif depends_list:
                new_entry["depends"] = depends_list
            if a == new_entry:
                return False
            atoms[i] = new_entry
            return True

    if depends_list:
        new_entry["depends"] = depends_list
    atoms.append(new_entry)
    return True


def build_alias_map(data: Dict[str, Any]) -> Dict[str, str]:
    """{舊名: 現名}。現存的 name 不會被別名蓋掉（同名時以真實 atom 為準）。"""
    names = {a.get("name") for a in data.get("atoms", [])}
    alias: Dict[str, str] = {}
    for a in data.get("atoms", []):
        for old in a.get("aka", []) or []:
            if old and old not in names:
                alias.setdefault(old, a.get("name", ""))
    return alias


def resolve_name(name: str, alias: Dict[str, str]) -> str:
    """把連結裡寫的名字解析成現名；不是別名就原樣回傳。"""
    return alias.get(name, name)


def _norm_index_path(p: object) -> str:
    """索引 path 比對用：分隔符統一 /、去掉開頭 ./；非字串回空字串（視為無 path）。"""
    if not isinstance(p, str):
        return ""
    s = p.strip().replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s


def delete_atom(mem_dir: Path, name: str, path: Optional[str] = None) -> bool:
    """刪索引條目。path=None → 刪所有同名條目（搬移／重建索引等 caller 自己已確認唯一）；
    給 path → 只刪 name 與 path 都相符的條目：shared/dup.md 與 personal/u/dup.md 同名共存時，
    退役其中一顆不能把另一顆的索引條目一起抹掉。"""
    data = load_atom_index_json(mem_dir)
    atoms = data["atoms"]
    before = len(atoms)
    want = _norm_index_path(path) if path is not None else None

    def _hit(a: Dict[str, Any]) -> bool:
        if a.get("name") != name:
            return False
        return want is None or _norm_index_path(a.get("path")) == want

    data["atoms"] = [a for a in atoms if not _hit(a)]
    if len(data["atoms"]) == before:
        return False
    save_index_with_mirror(mem_dir, data)
    return True


def save_index_with_mirror(mem_dir: Path, data: Dict[str, Any]) -> None:
    """JSON（真相）與 md 鏡像一起落檔；兩份內容在任何換檔之前就由同一份 data 算好。

    順序 JSON 先、md 後：中途失敗時磁碟上要嘛全舊、要嘛「JSON 新、鏡像舊」，鏡像不會跑在真相前面；
    鏡像每次都由整份 data 重生，下一次任何索引寫入（或 sync-atom-index --add-from-frontmatter 重跑）就補回。
    不回頭重讀 JSON 產生鏡像：重讀撞上別的行程搶檔會讀成空索引，生出一份空鏡像。"""
    md_text = render_atom_index_md(data)
    save_atom_index_json(mem_dir, data)
    try:
        _write_text_lf(mem_dir / ATOM_INDEX_MD, md_text)
    except OSError as e:
        print(f"[atom_index_json] {ATOM_INDEX_JSON} 已更新，{ATOM_INDEX_MD} 鏡像沒換成（{e}）；"
              f"下次任何索引寫入或重跑 sync-atom-index --add-from-frontmatter 會重生", file=sys.stderr)
        raise


def atom_index_md_stale(mem_dir: Path, data: Dict[str, Any]) -> bool:
    """md 鏡像跟 data 不一致（缺檔、上次換到一半）→ True。讀不到也當不一致，交給重寫。"""
    md = mem_dir / ATOM_INDEX_MD
    try:
        cur = retry_busy(lambda: md.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return True
    return cur.replace("\r\n", "\n") != render_atom_index_md(data)


def regenerate_atom_index_md(mem_dir: Path) -> None:
    """Regenerate _ATOM_INDEX.md from JSON (human-readable mirror, deprecated)."""
    _write_text_lf(mem_dir / ATOM_INDEX_MD, render_atom_index_md(load_atom_index_json(mem_dir)))


def render_atom_index_md(data: Dict[str, Any]) -> str:
    """索引 data → _ATOM_INDEX.md 全文（LF）。"""
    # Depends 欄只在索引裡至少一條有 depends 時才出現：沒人用 depends 的索引 mirror byte 不變，
    # 多機不會因為 mirror 格式換版而在合併時各自重生、互相衝突（索引三檔合併必衝突的教訓）。
    has_depends = any(isinstance(a.get("depends"), list) and a["depends"] for a in data["atoms"])
    lines = [
        "# Atom Trigger Index — Global",
        "",
        "> **Deprecated mirror.** Machine source: `_atom_index.json`.",
        "> 本檔由 lib/atom_index_json.py 自動生成；勿手改。",
        "",
        "| Atom | Path | Trigger | Scope | Depends |" if has_depends else "| Atom | Path | Trigger | Scope |",
        "|------|------|---------|-------|---------|" if has_depends else "|------|------|---------|-------|",
    ]
    for a in data["atoms"]:
        name = a.get("name", "")
        path = a.get("path", "")
        triggers = ", ".join(a.get("triggers", []))
        scope = a.get("scope", "global")
        row = f"| {name} | {path} | {triggers} | {scope} |"
        if has_depends:
            row += " " + ", ".join(d for d in (a.get("depends") or []) if isinstance(d, str)) + " |"
        lines.append(row)
    lines.append("")
    return "\n".join(lines)


# ─── Migration: parse legacy _ATOM_INDEX.md → JSON ──────────────────────────


_TABLE_HEADER_RE = re.compile(r"^\|\s*Atom\s*\|", re.IGNORECASE)


def parse_legacy_atom_index_md(md_path: Path) -> List[Dict[str, Any]]:
    """One-shot migration helper: parse _ATOM_INDEX.md table → atom dicts."""
    if not md_path.exists():
        return []
    try:
        text = md_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []

    atoms: List[Dict[str, Any]] = []
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if not in_table:
            if _TABLE_HEADER_RE.match(stripped):
                in_table = True
            continue
        if stripped.startswith("|---") or stripped.startswith("| ---"):
            continue
        if not stripped.startswith("|"):
            if not stripped:
                continue
            break
        cells = [c.strip() for c in stripped.split("|") if c.strip()]
        if len(cells) < 3:
            continue
        name = cells[0]
        path = cells[1]
        triggers = dedup_triggers(cells[2].split(","))
        scope = cells[3] if len(cells) >= 4 else "global"
        atoms.append({
            "name": name,
            "path": path,
            "triggers": triggers,
            "scope": scope,
        })
    return atoms


def migrate_md_to_json(mem_dir: Path, *, overwrite: bool = False) -> Dict[str, Any]:
    """Build _atom_index.json from existing _ATOM_INDEX.md. Idempotent."""
    json_path = mem_dir / ATOM_INDEX_JSON
    if json_path.exists() and not overwrite:
        return load_atom_index_json(mem_dir)
    md_path = mem_dir / ATOM_INDEX_MD
    atoms = parse_legacy_atom_index_md(md_path)
    data = {"version": SCHEMA_VERSION, "atoms": atoms}
    save_atom_index_json(mem_dir, data)
    return data


def validate_index(mem_dir: Path) -> List[str]:
    """Return list of validation errors (empty = ok). Used by pre-commit hook."""
    errors: List[str] = []
    json_path = mem_dir / ATOM_INDEX_JSON
    if not json_path.exists():
        errors.append(f"missing: {json_path}")
        return errors
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        errors.append(f"json parse error: {e}")
        return errors

    if not isinstance(data, dict):
        errors.append("root is not object")
        return errors
    if data.get("version") != SCHEMA_VERSION:
        errors.append(f"version mismatch: expected {SCHEMA_VERSION}, got {data.get('version')!r}")
    atoms = data.get("atoms")
    if not isinstance(atoms, list):
        errors.append("atoms is not a list")
        return errors

    all_names = {a.get("name") for a in atoms if isinstance(a, dict)}
    seen_names = set()
    seen_paths = set()
    for i, a in enumerate(atoms):
        if not isinstance(a, dict):
            errors.append(f"atoms[{i}] is not object")
            continue
        for k in ("name", "path", "triggers", "scope"):
            if k not in a:
                errors.append(f"atoms[{i}] missing key: {k}")
        name = a.get("name")
        if name in seen_names:
            errors.append(f"duplicate name: {name}")
        seen_names.add(name)
        path = a.get("path")
        if path in seen_paths:
            errors.append(f"duplicate path: {path}")
        seen_paths.add(path)
        for old in a.get("aka", []) or []:
            if old in all_names:
                errors.append(f"aka collides with an existing atom name: {name}: {old!r}")
        if not isinstance(a.get("triggers"), list):
            errors.append(f"atoms[{i}] triggers not list")
        else:
            for t in a["triggers"]:
                if len(t) > TRIGGER_MAX_LEN:
                    errors.append(f"trigger too long (>{TRIGGER_MAX_LEN}): {name}: {t!r}")
        if "depends" in a:
            try:
                validate_depends(a["depends"])
            except ValueError as e:
                errors.append(f"atoms[{i}] depends invalid: {name}: {e}")
    return errors


# ─── For wg_atoms compatibility (AtomEntry tuple format) ────────────────────


def to_atom_entries(data: Dict[str, Any]) -> List[tuple]:
    """Convert JSON atoms → list of (name, path, triggers_lowercase) tuples.

    Matches wg_atoms.AtomEntry contract.
    """
    entries = []
    for a in data.get("atoms", []):
        name = a.get("name", "")
        path = a.get("path", "")
        triggers = dedup_triggers(a.get("triggers", []), lower=True)
        entries.append((name, path, triggers))
    return entries

#!/usr/bin/env python3
"""Atom Health Check — 原子記憶依賴健康度檢查工具

Usage:
  python atom-health-check.py --validate-refs   檢查 Related 完整性
  python atom-health-check.py --fix-refs        （已無動作，反向連結由索引計算）
  python atom-health-check.py --stale-check     列出 Last-used > 60 天的 atoms
  python atom-health-check.py --deps-check      壞滅緣檢查（path 型 Depends 存在性＋依賴比卡新：依賴改動時刻看版控，非版控才看 mtime）
  python atom-health-check.py --report          生成完整健康報告
  python atom-health-check.py --report --json   JSON 格式輸出
"""

import sys, io
# Force UTF-8 stdout on Windows (cp950 codepage causes mojibake in JSON output)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

# Single source of truth: lib/atom_spec.py
CODE_DIR = Path(__file__).resolve().parent.parent   # 程式碼根：lib.* 從本樹載
sys.path.insert(0, str(CODE_DIR))
from lib.project_root import claude_data_dir  # noqa: E402
from lib.atom_spec import (  # noqa: E402
    is_atom_file, REQUIRED_METADATA, parse_depends, resolve_depends_path, classify_depends_path, depends_base_for_file,
    find_related_line, split_related, has_conflict_markers,
)
from lib.atom_locations import iter_atom_files_multi, atom_search_roots  # noqa: E402
from lib.atom_io import write_raw  # noqa: E402  走 funnel：EOL-preserving + audit（杜絕 bypass 裸寫）
from lib.atom_access import read_access  # noqa: E402  計數欄居 sidecar <atom>.access.json

CLAUDE_DIR = claude_data_dir()   # 使用者資料根（WG_CLAUDE_DIR 或 ~/.claude），和 hooks 同一支算法
MEMORY_ROOT = CLAUDE_DIR / "memory"
GLOBAL_MEMORY_ROOT = CLAUDE_DIR / "memory"
AIDOCS_ROOT = CLAUDE_DIR / "_AIDocs"
EXTRA_SCAN_ROOTS: list[Path] = []  # populated from CLI; searched as fallback for ref resolution
# Central hub atoms — skip reverse-link warnings for these
# (hub docs don't back-reference every detail doc that points to them)
# - decisions / decisions-architecture / spec：全域決策與規範 hub
# - feedback-pointer-atom：指標型 atom 設計原則 meta-rule，被多個 atoms 引用作為設計依據
CENTRAL_HUBS = {"decisions", "decisions-architecture", "spec", "feedback-pointer-atom"}

# Shadow detection: atom 段落抄 _AIDocs md 子段落 → warning
SHADOW_THRESHOLD_DEFAULT = 0.7
SHADOW_SECTIONS = ("印象", "知識")
SHADOW_MIN_LEN = 80  # 太短的段落比對結果不可信 (e.g. "(none)" 或單句)
NOISE_LINE_PATTERNS = [
    re.compile(r'^\s*[-*]?\s*.*?→\s*_AIDocs/[^\s]+\.md.*$'),  # pointer 行
    re.compile(r'^\s*@_AIDocs/.*$'),                           # @import 行
    re.compile(r'^\s*_AIDocs/[^\s]+\.md\s*$'),                 # 純路徑行
    re.compile(r'^\s*>\s*$'),                                  # 空 blockquote
]


def parse_memory_index(root: Path) -> dict[str, str]:
    """Parse MEMORY.md to build alias→stem mapping (e.g. spec→SPEC_Atomic_Memory_System)."""
    index_path = root / "MEMORY.md"
    aliases = {}
    if not index_path.exists():
        return aliases
    text = index_path.read_text(encoding="utf-8")
    # Match table rows: | alias | path | ...
    for m in re.finditer(r"\|\s*(\S+)\s*\|\s*([\w/.-]+\.md)\s*\|", text):
        alias = m.group(1).strip()
        filepath = m.group(2).strip()
        stem = Path(filepath).stem
        if alias != stem:
            aliases[alias] = stem
    return aliases


def find_atoms(root: Path) -> dict[str, Path]:
    """yield {stem: path} for all atom .md.

    root 為全域 memory 時委派 lib.atom_locations 多根掃描（memory/ 含 memory/Failures/，
    加舊址 _AIDocs/Failures/ 與 _AIDocs/_atoms/，不存在的根自動略過）。
    其他 root 維持單根 rglob + is_atom_file。
    """
    atoms: dict[str, Path] = {}
    try:
        is_global = root.resolve() == GLOBAL_MEMORY_ROOT.resolve()
    except OSError:
        is_global = False
    if is_global:
        for md in iter_atom_files_multi():
            atoms[md.stem] = md
    else:
        for md in root.rglob("*.md"):
            if is_atom_file(md, root):
                atoms[md.stem] = md
    return atoms


# 亂碼名稱：名稱含 U+0080–U+00FF（Big5 位元組被當 cp1252 解碼的典型，如 `UIºt¥X`＝`UI演出`）。
# 寫入端（lib/atom_spec slugify、atom_locations _clean_segment）本就拒收這段字元，所以樹上一旦出現必是
# 外部工具（手動 svn add 等）帶進來的，只警告、跳過，不嘗試修。
_MOJIBAKE_RE = re.compile(r"[\u0080-\u00ff]")


def mojibake_names(root: Path) -> list[Path]:
    """root 下名稱疑似亂碼的檔／夾；每項 stderr 一行警告。"""
    out = [p for p in root.rglob("*") if _MOJIBAKE_RE.search(p.name)]
    for p in out:
        print(f"⚠ 疑似亂碼名稱: {p}", file=sys.stderr)
    return out


def _under_mojibake(path: Path, root: Path) -> bool:
    """只看 root（或資料根）以下的路徑段，使用者家目錄本身含 Latin-1 字不算。"""
    rel = Path(path.name)
    for base in (root, CLAUDE_DIR):
        try:
            rel = path.relative_to(base)
            break
        except ValueError:
            continue
    return any(_MOJIBAKE_RE.search(part) for part in rel.parts)


def parse_frontmatter(path: Path) -> dict:
    """Parse atom frontmatter fields into a dict."""
    text = path.read_text(encoding="utf-8")
    fm = {}

    # Detect Claude-native frontmatter (--- delimited YAML)
    yaml_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if yaml_match:
        for line in yaml_match.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip()
        fm["_format"] = "claude-native"
        return fm

    # Detect atom-style frontmatter (- Key: Value lines at top)。只讀第一個 `## ` 之前；
    # 同名欄位取第一個——與 find_related_line 的寫入定位一致，去重才擋得住重複追加。
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## "):
            break
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^-\s+(.+?):[ \t]*(.*)$", line)
        if m and m.group(1) not in fm:
            fm[m.group(1)] = m.group(2)
    fm["_format"] = "atom"
    return fm


def parse_related(fm: dict) -> list[str]:
    """Extract Related atom names from frontmatter (handles both 'Related' and 'related')."""
    return split_related(fm.get("Related", "") or fm.get("related", ""))


def resolve_ref(ref: str, atoms: dict[str, Path], aliases: dict[str, str]) -> str | None:
    """Resolve a Related reference to an atom name. Returns atom name or None."""
    if ref in atoms:
        return ref
    # Check if ref is a MEMORY.md alias
    if ref in aliases:
        stem = aliases[ref]
        if stem in atoms:
            return stem
        # Alias target might be in SKIP_FILES but still valid on disk
        for md in MEMORY_ROOT.rglob(f"{stem}.md"):
            return stem
    # Check reverse alias (stem mentioned but alias is canonical)
    for alias, stem in aliases.items():
        if ref == stem and alias in atoms:
            return alias
    # Last resort: check if file exists on disk (covers SKIP_FILES entries)
    for md in MEMORY_ROOT.rglob(f"{ref}.md"):
        return ref
    # Cross-layer: fall back to extra roots (project → global up-ref is valid)
    for extra in EXTRA_SCAN_ROOTS:
        for md in extra.rglob(f"{ref}.md"):
            return ref
    return None


def validate_refs(atoms: dict[str, Path], aliases: dict[str, str] | None = None) -> list[dict]:
    """Check that all Related references point to existing atoms."""
    aliases = aliases or {}
    issues = []
    for name, path in sorted(atoms.items()):
        fm = parse_frontmatter(path)
        related = parse_related(fm)
        for ref in related:
            if resolve_ref(ref, atoms, aliases) is None:
                issues.append({
                    "atom": name,
                    "missing_ref": ref,
                    "file": str(path),
                })
    return issues


def auto_fix_broken_refs(broken: list[dict]) -> list[dict]:
    """Remove broken refs from their source atom's Related field.

    Returns list of applied fixes. A broken ref means the target doesn't exist
    in MEMORY_ROOT nor any EXTRA_SCAN_ROOTS, so removal is safe.
    """
    fixes = []
    for b in broken:
        path = Path(b["file"])
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if has_conflict_markers(text):
            continue
        m = find_related_line(text)
        if not m:
            continue
        items = split_related(m.group(1))
        missing = b["missing_ref"]
        new_items = [i for i in items if i != missing]
        if len(new_items) == len(items):
            continue
        new_line = f"- Related: {', '.join(new_items) if new_items else '(none)'}"
        # 走 funnel：write_text_lf（一律 LF）+ audit
        write_raw(path, text.replace(m.group(0), new_line, 1),
                  source="tool:atom-health-check", op="broken-ref-remove")
        fixes.append({"atom": b["atom"], "removed_ref": missing, "file": str(path)})
    return fixes


def check_reverse_refs(atoms: dict[str, Path], aliases: dict[str, str] | None = None) -> list[dict]:
    """恆回空清單：A → B 就代表兩顆相連，B 的檔裡不必也寫一次。

    反向連結由 `sync-atom-index` 收進索引、注入時在記憶體反轉（`wg_atoms.load_link_graph`）。
    把它存成 B 檔裡的一行，等於每新增一顆連到 hub 的 atom 就要去改 hub 那個檔——
    那是別人的檔，多人共用同一個版控庫時必衝突。

    保留函式與回傳形狀，舊呼叫端（health-weekly / heal-review / atom-heal）照跑不必改。
    """
    return []


def stale_check(atoms: dict[str, Path], days: int = 60) -> list[dict]:
    """Find atoms with Last-used older than threshold."""
    cutoff = datetime.now() - timedelta(days=days)
    stale = []
    for name, path in sorted(atoms.items()):
        last_used = read_access(path).get("last_used") or ""
        if not last_used:
            continue
        try:
            dt = datetime.strptime(last_used.strip(), "%Y-%m-%d")
            if dt < cutoff:
                age = (datetime.now() - dt).days
                stale.append({
                    "atom": name,
                    "last_used": last_used.strip(),
                    "days_ago": age,
                    "file": str(path),
                })
        except ValueError:
            pass
    return stale


def _depends_by_level(atoms: dict[str, Path]) -> dict[str, list[dict]]:
    """每張卡的 path 型 Depends 分級（atom_spec.classify_depends_path；相對路徑以卡片所在層的根解析）：
    missing＝壞滅緣、foreign＝別台機器的絕對路徑（本機不可驗，只列資訊）。無 Depends 欄的 atom 一律靜默（向後相容）。"""
    out: dict[str, list[dict]] = {"missing": [], "foreign": []}
    for name, path in sorted(atoms.items()):
        fm = parse_frontmatter(path)
        raw = fm.get("Depends", "")
        if not raw:
            continue
        base = depends_base_for_file(path)
        for e in parse_depends(raw):
            if e["type"] != "path" or not e["value"]:
                continue
            level, resolved = classify_depends_path(e["value"], base=base)
            if level in out:
                out[level].append({"atom": name, "dep": e["value"], "resolved": str(resolved), "file": str(path)})
    return out


def check_stale_deps(atoms: dict[str, Path]) -> list[dict]:
    """壞滅緣（validity conditions）檢查：path 型 Depends 指向本機該在卻不在的路徑。

    只驗 path 型條目（自由文字型不可驗，僅展示）。warning 級：
    知識失效是真值問題，非時間問題 — 依賴的路徑消失 = 該 atom 知識可能已壞滅。
    別台機器的絕對路徑（C:/Projects/…、C:/Users/<別人>/…）不算：本機驗不到，歸 check_foreign_deps。
    """
    return _depends_by_level(atoms)["missing"]


def check_foreign_deps(atoms: dict[str, Path]) -> list[dict]:
    """path 型 Depends 是別台機器的絕對路徑（作者機寫進卡片、跨機共享後本機驗不到）：資訊級，不是壞滅緣。"""
    return _depends_by_level(atoms)["foreign"]


_VERIFIED_FIELDS = ("Verified-at", "Last-verified", "驗證日期", "Created-at")
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _atom_verified_date(fm: dict, path: Path) -> tuple[datetime, str]:
    """atom 的「最近驗證」日期：Verified-at → Last-verified → 驗證日期 → Created-at（取欄位裡第一個 YYYY-MM-DD），
    都沒有退檔案 mtime。回 (日期, 來源欄名)。"""
    for key in _VERIFIED_FIELDS:
        m = _DATE_RE.search(str(fm.get(key, "") or ""))
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y-%m-%d"), key
            except ValueError:
                continue
    try:
        return datetime.fromtimestamp(path.stat().st_mtime), "mtime"
    except OSError:
        return datetime.now(), "now"


# ─── 依賴「最後一次真的改動」：版控優先，本機有未提交修改或沒進版控才看 mtime ─────────────────────
# svn／git 的 update、checkout 會把檔案 mtime 設成當下：只看 mtime，「程式沒改、只是這台剛 update」也會被報過期。

_VCS_TIMEOUT = 20
_VCS_BATCH = 100      # 一次 svn／git 呼叫最多帶幾條路徑（Windows 命令列上限 32K 字元）
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_SVN_UNCHANGED = {"normal", "external", "none", "unversioned", "ignored"}


@dataclass(frozen=True)
class _Moment:
    """檔案改動的時刻。at＝本地時間；vcs／rev／repo 只在讀到版控時有。
    比先後：同一個 svn repo 比版號，其餘（git、跨 repo、mtime）比時間。"""
    at: datetime
    source: str
    vcs: str | None = None
    rev: int | None = None
    repo: str | None = None

    def later_than(self, other: "_Moment") -> bool:
        if self.rev is not None and other.rev is not None and self.repo == other.repo:
            return self.rev > other.rev
        return self.at > other.at


def _key(p) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


def _mtime_moment(path: Path, why: str = "") -> _Moment | None:
    try:
        at = datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None
    return _Moment(at, f"mtime（{why}）" if why else "mtime")


def _svn_time(text: str) -> datetime:
    """svn 的 UTC ISO 時間 → 本地 naive datetime（和 Verified-at、mtime 同一個口徑）。"""
    return datetime.fromisoformat(text.strip().replace("Z", "+00:00")).astimezone().replace(tzinfo=None)


def _svn_argv_ok(s: str) -> bool:
    """svn.exe 以 ANSI 碼頁收 argv，碼頁外的字會被 best-fit 成別的路徑 → 這種路徑不交給 svn（mbcs 嚴格模式不做 best-fit）。"""
    if sys.platform != "win32":
        return True
    try:
        s.encode("mbcs")
        return True
    except UnicodeEncodeError:
        return False


def _run_vcs(cmd: list[str]) -> tuple[int, str, str]:
    """跑 svn／git，回 (exit code, stdout, stderr)；沒裝或逾時丟 OSError，由呼叫端退 mtime 並報原因。"""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=_VCS_TIMEOUT, creationflags=_NO_WINDOW)
    except subprocess.TimeoutExpired as e:
        raise OSError(f"{cmd[0]} 逾時 {_VCS_TIMEOUT}s") from e
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace").strip()


def _run_vcs_all(cmds: list[list[str]]) -> list[tuple[int, str, str]]:
    """幾條互不相依的 svn／git 指令同時跑（各開子行程，等待時間疊在一起）；任一條丟 OSError 就整組丟。"""
    with ThreadPoolExecutor(max_workers=min(8, len(cmds))) as ex:
        return list(ex.map(_run_vcs, cmds))


class _ChangeClock:
    """一次 check_depends_mtime 內的版控查詢。建構時把路徑按 VCS 分批一次查完：svn 全部合成一批（info＋status 同時跑，
    巢狀工作副本可混在同一批）、git 每個 repo 一批（status＋log 同時跑，log 順便留下卡片的進版紀錄）；
    同日分先後要的 svn 卡片進版紀錄（svn log 要連伺服器）由 preload_histories 一次同時查，查過記住。
    讀不到版控的退 mtime、原因寫進 source；整批讀不到在 stderr 印一行，不靜默。"""

    def __init__(self, paths: list[Path]):
        self._roots: dict[Path, tuple[str, Path] | None] = {}
        self._last: dict[str, _Moment] = {}      # 最後一次進版
        self._edit: dict[str, _Moment] = {}      # 本機未提交修改（取修改中最新的 mtime）
        self._why: dict[str, str] = {}           # 退 mtime 的原因
        self._histories: dict[str, list[_Moment] | str] = {}
        svn: list[Path] = []
        git: dict[Path, list[Path]] = {}
        for p in dict.fromkeys(paths):
            hit = self._root_of(p)
            if hit is None:
                continue
            kind, root = hit
            if kind == "git":
                git.setdefault(root, []).append(p)
            elif _svn_argv_ok(str(p)):
                svn.append(p)
            else:
                self._why[_key(p)] = "路徑含 ANSI 碼頁外字元，svn 收不到"
        for i in range(0, len(svn), _VCS_BATCH):
            self._load_svn(svn[i:i + _VCS_BATCH])
        for root, ps in git.items():
            for i in range(0, len(ps), _VCS_BATCH):
                self._load_git(root, ps[i:i + _VCS_BATCH])

    def moment(self, path: Path) -> _Moment | None:
        """path 最後一次改動：本機有未提交修改 → 該 mtime；版控乾淨 → 最後變更的版號／commit；沒進版控或讀不到 → mtime（附原因）。"""
        k = _key(path)
        return self._edit.get(k) or self._last.get(k) or _mtime_moment(path, self._why.get(k, ""))

    def card_anchor(self, card: Path, day: date) -> tuple[_Moment | None, str]:
        """同日分先後時卡片那一端＝驗證日當天起卡片第一次被記下的時刻：先找進版紀錄（卡片新建當天驗證＝第一次進版），
        當天起沒進過版才用本機未提交修改／沒進版控的 mtime。查不到回 (None, 原因)。"""
        k = _key(card)
        last = self._last.get(k)
        hist = self._history(card) if last else []
        if isinstance(hist, str):
            return None, hist
        local = self._edit.get(k) or (None if last else _mtime_moment(card, self._why.get(k, "")))
        for m in [*hist, local]:
            if m is not None and m.at.date() >= day:
                return m, ""
        return None, f"卡片在 {day} 起沒有進版或本機修改紀錄"

    def _root_of(self, path: Path) -> tuple[str, Path] | None:
        """離 path 最近、含 .svn 或 .git 的上層目錄；同一層兩個都有取 svn（git overlay 疊在 svn 上時 svn 才是團隊正本）。"""
        d = path if path.is_dir() else path.parent
        walked = []
        while d not in self._roots:
            walked.append(d)
            if (d / ".svn").is_dir():
                self._roots[d] = ("svn", d)
            elif (d / ".git").exists():
                self._roots[d] = ("git", d)
            elif d.parent == d:
                self._roots[d] = None
            else:
                d = d.parent
        for w in walked:
            self._roots[w] = self._roots[d]
        return self._roots[d]

    def _load_svn(self, paths: list[Path]) -> None:
        """一次 svn info（最後變更版號、日期、repo uuid）＋一次 svn status -q（本機未提交修改）。"""
        args = [str(p) for p in paths]
        try:
            (_, info_out, info_err), (_, st_out, st_err) = _run_vcs_all([
                ["svn", "info", "--xml", "--non-interactive", *args],
                ["svn", "status", "-q", "--xml", "--non-interactive", *args]])
            info, status = ET.fromstring(info_out), ET.fromstring(st_out)
        except OSError as e:
            return self._fail("svn", paths, str(e))
        except ET.ParseError:
            return self._fail("svn", paths, (info_err or st_err)[:200])
        edited = {}
        for e in status.iter("entry"):
            st = e.find("wc-status")
            if st is not None and (st.get("item") not in _SVN_UNCHANGED or st.get("props") == "modified"):
                edited[_key(e.get("path"))] = e.get("path")
        committed = {}
        for e in info.iter("entry"):
            c = e.find("commit")
            when = c.findtext("date") if c is not None else None
            if when:
                rev = int(c.get("revision"))
                committed[_key(e.get("path"))] = _Moment(_svn_time(when), f"svn r{rev}", "svn", rev,
                                                         e.findtext("repository/uuid"))
        self._settle(paths, edited, committed)

    def _load_git(self, root: Path, paths: list[Path]) -> None:
        """一次 git status（本機未提交修改）＋一次 git log --name-only（各路徑全部 commit，新→舊；目錄看底下任一檔）。"""
        rels = {_key(p): p.relative_to(root).as_posix() for p in paths}
        git = ["git", "-C", str(root), "-c", "core.quotepath=off", "--literal-pathspecs"]
        try:
            (rc1, st_out, err1), (rc2, log_out, err2) = _run_vcs_all([
                [*git, "status", "--porcelain=v1", "-z", "--", *rels.values()],
                [*git, "log", "--pretty=format:%x1e%ct%x1f%h", "--name-only", "--", *rels.values()]])
        except OSError as e:
            return self._fail("git", paths, str(e))
        if rc1 or rc2:
            return self._fail("git", paths, (err1 or err2)[:200])
        edited = {}
        tokens = iter(st_out.split("\0"))
        for tok in tokens:
            if len(tok) < 4 or tok.startswith("??"):
                continue
            edited[_key(root / tok[3:])] = str(root / tok[3:])
            if tok[0] in "RC":
                next(tokens, None)    # 改名／複製時下一段是原路徑
        want = {k: rel.casefold() for k, rel in rels.items()}
        hist: dict[str, list[_Moment]] = {k: [] for k in want}
        for block in log_out.split("\x1e"):
            head, _, files = block.partition("\n")
            ct, _, sha = head.partition("\x1f")
            if not ct.isdigit():
                continue
            names = {f.strip().casefold() for f in files.splitlines() if f.strip()}
            for k, rel in want.items():
                if any(n == rel or n.startswith(rel + "/") for n in names):
                    hist[k].append(_Moment(datetime.fromtimestamp(int(ct)), f"git {sha.strip()}", "git"))
        for k, h in hist.items():
            if h:
                self._histories[k] = h[::-1]
        self._settle(paths, edited, {k: h[0] for k, h in hist.items() if h})

    def _settle(self, paths: list[Path], edited: dict[str, str], committed: dict[str, _Moment]) -> None:
        """每條路徑定案：底下有未提交修改 → 記修改中最新的 mtime；有進版紀錄 → 記最後一筆；兩者都沒有 → 未進版控。"""
        for p in paths:
            k = _key(p)
            t = k + os.sep
            hits = [Path(raw) for ek, raw in edited.items() if ek == k or ek.startswith(t)]
            moments = [m for m in (_mtime_moment(h, "本機未提交修改") for h in hits) if m is not None]
            if moments:
                self._edit[k] = max(moments, key=lambda m: m.at)
            elif hits:
                self._edit[k] = _mtime_moment(p, "本機未提交修改")
            if k in committed:
                self._last[k] = committed[k]
            elif not hits:
                self._why[k] = "未進版控"

    def _fail(self, vcs: str, paths: list[Path], why: str) -> None:
        print(f"⚠ 依賴比卡新：{vcs} 讀不到（{why}），{len(paths)} 條改看 mtime", file=sys.stderr)
        for p in paths:
            self._why[_key(p)] = f"{vcs} 讀不到"

    def preload_histories(self, cards: list[Path]) -> None:
        """同日分先後要用的卡片進版紀錄：git 的批次 log 已填好；svn log 要連伺服器，這裡一次同時查完。"""
        todo = [c for c in dict.fromkeys(cards) if _key(c) in self._last and _key(c) not in self._histories]
        if todo:
            with ThreadPoolExecutor(max_workers=min(8, len(todo))) as ex:
                list(ex.map(self._history, todo))

    def _history(self, card: Path) -> list[_Moment] | str:
        """卡片的進版紀錄（舊→新）；git 的在 _load_git 已填好，走到查詢的只有 svn。讀不到回原因字串。"""
        k = _key(card)
        if k not in self._histories:
            repo = self._last[k].repo
            try:
                rc, out, err = _run_vcs(["svn", "log", "-q", "--xml", "--non-interactive", str(card)])
                if rc:
                    raise OSError(err)
                hist = [_Moment(_svn_time(e.findtext("date")), f"svn r{e.get('revision')}", "svn",
                                int(e.get("revision")), repo)
                        for e in ET.fromstring(out).iter("logentry") if e.findtext("date")]
                self._histories[k] = sorted(hist, key=lambda m: m.rev)
            except (OSError, ET.ParseError, ValueError) as e:
                self._histories[k] = f"svn log 讀不到：{str(e)[:200]}"
        return self._histories[k]


def check_depends_mtime(atoms: dict[str, Path]) -> list[dict]:
    """壞滅緣第二型：path 型 Depends 指向的檔在 atom 最近驗證之後改過 → 這張卡可能過期（依賴改了、卡沒重驗）。
    依賴的改動時刻見 _ChangeClock（版控乾淨看最後變更、本機有未提交修改或沒進版控看 mtime）。改動日晚於驗證日 → 報；
    同一天 → 比卡片驗證日當天起第一次進版（或本機修改）的版號／時間，依賴較晚才報，分不出也報並寫原因。
    只看存在的路徑（不存在的歸 check_stale_deps）；無 Depends 靜默。"""
    rows = []   # (atom 名, 卡片路徑, 驗證日, 驗證日來源欄, Depends 原值, 解析後路徑)
    for name, path in sorted(atoms.items()):
        fm = parse_frontmatter(path)
        raw = fm.get("Depends", "")
        if not raw:
            continue
        verified, src = _atom_verified_date(fm, path)
        base = depends_base_for_file(path)
        for e in parse_depends(raw):
            if e["type"] != "path" or not e["value"]:
                continue
            resolved = resolve_depends_path(e["value"], base=base)
            if resolved.exists():
                rows.append((name, path, verified, src, e["value"], resolved))
    clock = _ChangeClock([r[5] for r in rows] + [r[1] for r in rows])
    moments = [clock.moment(r[5]) for r in rows]
    clock.preload_histories([r[1] for r, m in zip(rows, moments) if m and m.at.date() == r[2].date()])
    issues = []
    for (name, path, verified, src, dep, resolved), changed in zip(rows, moments):
        if changed is None or changed.at.date() < verified.date():
            continue
        same_day = ""
        if changed.at.date() == verified.date():
            anchor, why = clock.card_anchor(path, verified.date())
            if anchor is not None and not changed.later_than(anchor):
                continue
            same_day = f"同日，依賴晚於卡片 {anchor.source}" if anchor else f"同日分不出先後（{why}）"
        issues.append({
            "atom": name,
            "dep": dep,
            "resolved": str(resolved),
            "dep_changed": changed.at.strftime("%Y-%m-%d"),
            "dep_source": changed.source,
            "verified_at": verified.strftime("%Y-%m-%d"),
            "verified_source": src,
            "same_day": same_day,
            "file": str(path),
        })
    return issues


def depends_coverage(atoms: dict[str, Path]) -> dict:
    """Depends 覆蓋率：有 path 型 Depends 的 atom 數／總數（過程數字，只進健檢報表）。"""
    total = len(atoms)
    with_dep = 0
    for _name, path in atoms.items():
        raw = parse_frontmatter(path).get("Depends", "")
        if raw and any(e["type"] == "path" and e["value"] for e in parse_depends(raw)):
            with_dep += 1
    return {"with_depends": with_dep, "total": total, "ratio": round(with_dep / total, 4) if total else 0.0}


def _strip_noise_lines(text: str) -> str:
    """Remove pointer / @import / pure-path lines so they don't inflate ratios."""
    kept = []
    for line in text.splitlines():
        if any(p.match(line) for p in NOISE_LINE_PATTERNS):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _extract_section(text: str, heading: str) -> str:
    """Extract content of `## {heading}` section (until next `## ` or EOF)."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def extract_atom_sections(atom_path: Path) -> dict[str, str]:
    """Return {section_name: cleaned_text} for SHADOW_SECTIONS present in atom.
    Empty / too-short sections are skipped.
    """
    text = atom_path.read_text(encoding="utf-8")
    out = {}
    for sec in SHADOW_SECTIONS:
        body = _extract_section(text, sec)
        if not body:
            continue
        cleaned = _strip_noise_lines(body)
        if len(cleaned) < SHADOW_MIN_LEN:
            continue
        out[sec] = cleaned
    return out


def split_md_subsections(md_path: Path) -> list[tuple[str, str]]:
    """Split _AIDocs md by `## ` heading. Return [(heading, body), ...].
    Body before the first `## ` (under H1) is included as ('(preamble)', body).
    """
    text = md_path.read_text(encoding="utf-8")
    sections: list[tuple[str, str]] = []
    parts = re.split(r"^(##\s+.+)$", text, flags=re.MULTILINE)
    # parts[0] = preamble (before first ## ); then alternating (heading, body)
    if parts and parts[0].strip():
        preamble = parts[0].strip()
        if len(preamble) >= SHADOW_MIN_LEN:
            sections.append(("(preamble)", preamble))
    for i in range(1, len(parts), 2):
        heading = parts[i].lstrip("#").strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if len(body) >= SHADOW_MIN_LEN:
            sections.append((heading, body))
    return sections


def _ratio_fast(a: str, b: str, threshold: float) -> float:
    """SequenceMatcher.ratio with length-prefix early-exit.
    If size disparity already precludes reaching threshold, return 0 without computing.
    """
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0
    # Upper bound: 2 * min(la, lb) / (la + lb)
    upper = (2 * min(la, lb)) / (la + lb)
    if upper < threshold:
        return 0.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def detect_shadow_atoms(
    atoms: dict[str, Path],
    aidocs_root: Path,
    threshold: float = SHADOW_THRESHOLD_DEFAULT,
    dry_run: bool = False,
) -> list[dict]:
    """For each (atom_section × md_subsection), compute SequenceMatcher.ratio.
    - dry_run=True: return all pairs sorted by ratio desc (for distribution analysis)
    - dry_run=False: return only pairs with ratio >= threshold (warnings)
    """
    if not aidocs_root.is_dir():
        return []

    md_subs: list[tuple[Path, str, str]] = []
    for md in aidocs_root.rglob("*.md"):
        # Skip _CHANGELOG / _CHANGELOG_ARCHIVE etc.; keep _INDEX.md (atoms may shadow it)
        if md.name.startswith("_") and md.name != "_INDEX.md":
            continue
        for heading, body in split_md_subsections(md):
            md_subs.append((md, heading, body))

    results: list[dict] = []
    for atom_name, atom_path in sorted(atoms.items()):
        sections = extract_atom_sections(atom_path)
        for sec_name, sec_text in sections.items():
            for md_path, md_heading, md_body in md_subs:
                # dry-run: use threshold=0 to capture full distribution
                effective_thr = 0.0 if dry_run else threshold
                r = _ratio_fast(sec_text, md_body, effective_thr)
                if r >= (threshold if not dry_run else 0.0):
                    if dry_run and r < 0.3:
                        continue  # noise floor for dry-run report
                    try:
                        md_rel = str(md_path.relative_to(aidocs_root))
                    except ValueError:
                        md_rel = str(md_path)
                    results.append({
                        "atom": atom_name,
                        "section": sec_name,
                        "md_path": md_rel,
                        "md_heading": md_heading,
                        "ratio": round(r, 3),
                    })

    results.sort(key=lambda x: x["ratio"], reverse=True)
    return results


def full_report(atoms: dict[str, Path], aliases: dict[str, str] | None = None,
                shadow_atoms: list[dict] | None = None,
                mojibake: list[Path] | None = None) -> dict:
    """Generate complete health report."""
    aliases = aliases or {}
    report = {
        "generated": datetime.now().isoformat(),
        "total_atoms": len(atoms),
        "aliases": aliases,
        "atoms": [],
        "broken_refs": validate_refs(atoms, aliases),
        "missing_reverse_refs": check_reverse_refs(atoms, aliases),
        "stale_atoms": stale_check(atoms),
        "stale_deps": check_stale_deps(atoms),
        "foreign_deps": check_foreign_deps(atoms),
        "stale_mtime_deps": check_depends_mtime(atoms),
        "depends_coverage": depends_coverage(atoms),
        "shadow_atoms": shadow_atoms or [],
        "mojibake_names": [str(p) for p in (mojibake or [])],
    }

    for name, path in sorted(atoms.items()):
        fm = parse_frontmatter(path)
        acc = read_access(path)  # 計數欄居 sidecar <atom>.access.json
        related = parse_related(fm)
        # atom 可居 memory/ 樹外（舊址 _AIDocs/Failures/、_AIDocs/_atoms/）→ 退相對資料根計算
        try:
            file_rel = str(path.relative_to(MEMORY_ROOT))
        except ValueError:
            file_rel = str(path.relative_to(CLAUDE_DIR))
        entry = {
            "name": name,
            "file": file_rel,
            "format": fm.get("_format", "unknown"),
            "confidence": fm.get("Confidence", "—"),
            "last_used": acc.get("last_used") or "—",
            "confirmations": acc.get("confirmations", "—"),
            "readhits": acc.get("read_hits", "—"),
            "related": related,
            "issues": [],
        }

        # Check for missing standard fields
        if fm.get("_format") == "atom":
            # REQUIRED_METADATA from atom_spec — single source of truth
            for k in REQUIRED_METADATA:
                if not fm.get(k):
                    entry["issues"].append(f"missing {k}")
            # Tracking fields live in sidecar <atom>.access.json.
            # confirmations=0 is normal for a tracked atom; only a missing
            # sidecar (never tracked → first_seen is None) warrants a warning.
            if acc.get("first_seen") is None:
                entry["issues"].append("no access.json (never tracked)")
        elif fm.get("_format") == "claude-native":
            entry["issues"].append("claude-native format (no Last-used/Confirmations/Related)")

        report["atoms"].append(entry)

    return report


def single_atom_report(name: str, atoms: dict[str, Path],
                       aliases: dict[str, str] | None = None) -> dict:
    """Filter full-library health results down to a single atom NAME.

    Runs the existing whole-library detectors (validate_refs / check_reverse_refs /
    stale_check) unchanged, then filters their output to items involving NAME.
    Output is --report --json compatible (same keys: broken_refs /
    missing_reverse_refs / stale_atoms), so callers can reuse the same parser.
    """
    aliases = aliases or {}

    # broken_refs: only refs whose SOURCE atom == NAME (NAME pointing at a missing ref)
    broken = [b for b in validate_refs(atoms, aliases) if b["atom"] == name]

    # missing_reverse_refs: any reverse-ref issue involving NAME on either side
    reverse = [r for r in check_reverse_refs(atoms, aliases)
               if r["atom_a"] == name or r["atom_b"] == name]

    # stale_atoms: NAME if it is in the stale list, else empty
    stale = [s for s in stale_check(atoms) if s["atom"] == name]

    # stale_deps: NAME 的壞滅緣觸發（path 型 Depends 指向已消失路徑）
    deps = [d for d in check_stale_deps(atoms) if d["atom"] == name]
    # 依賴比卡新只看這張卡自己的 Depends：不必為一張卡去查全庫的版控（atom-heal 會逐張重掃）
    mtime_deps = check_depends_mtime({name: atoms[name]}) if name in atoms else []

    return {
        "generated": datetime.now().isoformat(),
        "atom": name,
        "exists": name in atoms,
        "broken_refs": broken,
        "missing_reverse_refs": reverse,
        "stale_atoms": stale,
        "stale_deps": deps,
        "stale_mtime_deps": mtime_deps,
    }


def print_text_report(report: dict):
    """Pretty-print the report."""
    print(f"=== Atom Health Report ({report['generated'][:10]}) ===")
    print(f"Total atoms: {report['total_atoms']}\n")

    # Per-atom status
    print("── Atom Status ──")
    for a in report["atoms"]:
        status = "✅" if not a["issues"] else "⚠️"
        related_str = ", ".join(a["related"]) if a["related"] else "(none)"
        print(f"  {status} {a['name']}")
        print(f"     File: {a['file']} | Confidence: {a['confidence']}")
        print(f"     Last-used: {a['last_used']} | Confirmations: {a['confirmations']} | ReadHits: {a['readhits']}")
        print(f"     Related: {related_str}")
        if a["issues"]:
            print(f"     Issues: {', '.join(a['issues'])}")
        print()

    # Broken refs
    if report["broken_refs"]:
        print("── Broken References ──")
        for b in report["broken_refs"]:
            print(f"  ❌ {b['atom']} → {b['missing_ref']} (not found)")
        print()
    else:
        print("── Broken References: None ✅ ──\n")

    # Reverse refs
    if report["missing_reverse_refs"]:
        print("── Missing Reverse References ──")
        for r in report["missing_reverse_refs"]:
            print(f"  ⚠️ {r['direction']}")
        print()
    else:
        print("── Reverse References: All OK ✅ ──\n")

    # Stale
    if report["stale_atoms"]:
        print("── Stale Atoms (>60 days) ──")
        for s in report["stale_atoms"]:
            print(f"  🕐 {s['atom']} — last used {s['last_used']} ({s['days_ago']}d ago)")
        print()
    else:
        print("── Stale Atoms: None ✅ ──\n")

    # 壞滅緣（validity conditions）— warning 級
    if report.get("stale_deps"):
        print("── 壞滅緣（Stale Depends）──")
        for d in report["stale_deps"]:
            print(f"  ⚠️ 壞滅緣觸發：atom {d['atom']} 依賴 {d['dep']} 已不存在")
        print()
    if report.get("foreign_deps"):
        print(f"── 他機路徑的 Depends（本機不可驗、不算壞滅緣）：{len(report['foreign_deps'])} 筆 ──\n")
    else:
        print("── 壞滅緣（Stale Depends）: None ✅ ──\n")

    # 疑似亂碼名稱（warning 級、不計入 issues_count；修法：svn revert／改名，見 vcs-sync）
    if report.get("mojibake_names"):
        print("── 疑似亂碼名稱（U+0080–U+00FF）──")
        for p in report["mojibake_names"]:
            print(f"  ⚠️ {p}")
        print()
    else:
        print("── 疑似亂碼名稱: None ✅ ──\n")

    # Shadow atoms (warning level — does NOT count toward issues_count)
    if report.get("shadow_atoms"):
        print("── Shadow Atoms (vs _AIDocs) ──")
        for s in report["shadow_atoms"]:
            print(f"  ⚠️  {s['atom']}::{s['section']}  ratio={s['ratio']:.2f}  → {s['md_path']}#{s['md_heading']}")
        print()
    elif "shadow_atoms" in report:
        # Empty list means check ran but found nothing
        # Skip the "(none)" line when --shadow-check was not requested at all.
        pass

    # Summary
    issues_count = (
        len(report["broken_refs"])
        + len(report["missing_reverse_refs"])
        + len(report["stale_atoms"])
        + len(report.get("stale_deps", []))
        + sum(1 for a in report["atoms"] if a["issues"])
    )
    if issues_count == 0:
        print("🎉 All atoms healthy!")
    else:
        print(f"⚠️ {issues_count} issue(s) found.")


def main():
    parser = argparse.ArgumentParser(description="Atom Health Check")
    parser.add_argument("--validate-refs", action="store_true", help="Check Related references exist")
    parser.add_argument("--fix-refs", action="store_true", help="（已無動作）反向連結由索引計算，不寫進被連的檔")
    parser.add_argument("--auto-fix-broken", action="store_true", help="Auto-remove broken Related refs from source atoms (unresolvable targets)")
    parser.add_argument("--stale-check", action="store_true", help="List atoms with Last-used > 60 days")
    parser.add_argument("--deps-check", action="store_true",
                        help="壞滅緣檢查：path 型 Depends 指向不存在路徑的 atoms＋依賴比卡新（版控最後變更日，非版控退 mtime）")
    parser.add_argument("--stale-days", type=int, default=60, help="Stale threshold in days (default: 60)")
    parser.add_argument("--shadow-check", action="store_true",
                        help="Detect atom sections (## 印象 / ## 知識) shadowing _AIDocs md subsections")
    parser.add_argument("--shadow-threshold", type=float, default=SHADOW_THRESHOLD_DEFAULT,
                        help=f"Shadow similarity threshold (default: {SHADOW_THRESHOLD_DEFAULT})")
    parser.add_argument("--shadow-dry-run", action="store_true",
                        help="Print full ratio distribution (≥0.3) instead of filtering by threshold")
    parser.add_argument("--report", action="store_true", help="Full health report")
    parser.add_argument("--atom", type=str, default=None,
                        help="Report health issues for a single atom only (broken_refs/missing_reverse_refs/stale_atoms filtered to NAME)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--memory-root", type=str, default=None, help="Override memory root path")
    args = parser.parse_args()

    global MEMORY_ROOT, EXTRA_SCAN_ROOTS
    if args.memory_root:
        MEMORY_ROOT = Path(args.memory_root)

    if not MEMORY_ROOT.exists():
        print(f"Error: {MEMORY_ROOT} does not exist", file=sys.stderr)
        sys.exit(1)

    # Auto-enable cross-layer ref resolution when scanning a non-global root:
    # project-layer atoms may legitimately reference global atoms (up-ref).
    # Does NOT affect down-ref detection (global→project refs still flagged when
    # scanning global, since MEMORY_ROOT will be global and project not in extras).
    try:
        if MEMORY_ROOT.resolve() != GLOBAL_MEMORY_ROOT.resolve():
            # 全域 atom 不只居 memory/（含 memory/Failures/），亦含舊址 _AIDocs/Failures/ 與
            # _AIDocs/_atoms/（local realm，可深層子目錄如 Tools/.../dotnet/）。
            # 只放 global memory 會讓專案 atom 對這些他層 atom 的 up-ref 全被誤報 broken。
            # 用 atom_search_roots() 涵蓋全部根（existing dirs only），與 find_atoms 全域掃描範圍對齊；
            # 真正不存在的 ref（任一根都找不到）仍正確回報。
            EXTRA_SCAN_ROOTS = [r for r in atom_search_roots() if r.is_dir()]
    except OSError:
        pass

    atoms = find_atoms(MEMORY_ROOT)
    mojibake = mojibake_names(MEMORY_ROOT)
    atoms = {k: v for k, v in atoms.items() if not _under_mojibake(v, MEMORY_ROOT)}
    aliases = parse_memory_index(MEMORY_ROOT)

    if not any([args.validate_refs, args.fix_refs, args.auto_fix_broken,
                args.stale_check, args.deps_check, args.shadow_check,
                args.report, args.atom]):
        parser.print_help()
        sys.exit(0)

    if args.atom:
        report = single_atom_report(args.atom, atoms, aliases)
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            if not report["exists"]:
                print(f"⚠️ atom '{args.atom}' not found in {MEMORY_ROOT}")
            print(f"=== Atom Health: {args.atom} ===")
            if report["broken_refs"]:
                for b in report["broken_refs"]:
                    print(f"❌ {b['atom']} → {b['missing_ref']} (not found)")
            else:
                print("✅ No broken references.")
            if report["missing_reverse_refs"]:
                for r in report["missing_reverse_refs"]:
                    print(f"⚠️ {r['direction']}")
            else:
                print("✅ No missing reverse references.")
            if report["stale_atoms"]:
                for s in report["stale_atoms"]:
                    print(f"🕐 {s['atom']} — {s['last_used']} ({s['days_ago']}d ago)")
            else:
                print("✅ Not stale.")
            if report["stale_deps"]:
                for d in report["stale_deps"]:
                    print(f"⚠️ 壞滅緣觸發：atom {d['atom']} 依賴 {d['dep']} 已不存在")
            else:
                print("✅ No stale depends.")
        sys.exit(0)

    if args.fix_refs:
        msg = "反向連結改由索引計算（sync-atom-index → wg_atoms.load_link_graph），不再寫進被連的檔。"
        print(json.dumps({"fixes": [], "count": 0, "not_applied": [], "note": msg},
                         indent=2, ensure_ascii=False) if args.json else f"✅ {msg}")
        sys.exit(0)

    if args.auto_fix_broken:
        broken = validate_refs(atoms, aliases)
        fixes = auto_fix_broken_refs(broken)
        if args.json:
            print(json.dumps({"fixes": fixes, "count": len(fixes)}, indent=2, ensure_ascii=False))
        elif fixes:
            for f in fixes:
                print(f"✅ {f['atom']} — removed broken ref: {f['removed_ref']}")
            print(f"\nRemoved {len(fixes)} broken reference(s).")
        else:
            print("✅ No broken references to fix.")
        sys.exit(0)

    if args.validate_refs:
        broken = validate_refs(atoms, aliases)
        reverse = check_reverse_refs(atoms, aliases)
        if args.json:
            print(json.dumps({"broken_refs": broken, "missing_reverse_refs": reverse}, indent=2, ensure_ascii=False))
        else:
            if broken:
                for b in broken:
                    print(f"❌ {b['atom']} → {b['missing_ref']} (not found)")
            else:
                print("✅ All Related references valid.")
            if reverse:
                print()
                for r in reverse:
                    print(f"⚠️ {r['direction']}")
            else:
                print("✅ All reverse references OK.")

    elif args.stale_check:
        stale = stale_check(atoms, args.stale_days)
        if args.json:
            print(json.dumps(stale, indent=2, ensure_ascii=False))
        elif stale:
            for s in stale:
                print(f"🕐 {s['atom']} — {s['last_used']} ({s['days_ago']}d ago)")
        else:
            print(f"✅ No atoms older than {args.stale_days} days.")

    elif args.deps_check:
        deps = check_stale_deps(atoms)
        foreign = check_foreign_deps(atoms)
        mtime_deps = check_depends_mtime(atoms)
        if args.json:
            print(json.dumps({"stale_deps": deps, "foreign_deps": foreign, "stale_mtime_deps": mtime_deps,
                              "depends_coverage": depends_coverage(atoms)}, indent=2, ensure_ascii=False))
        else:
            for d in deps:
                print(f"⚠️ 壞滅緣觸發：atom {d['atom']} 依賴 {d['dep']} 已不存在")
            for d in foreign:
                print(f"ℹ️ 他機路徑（本機不可驗、不算壞滅緣）：atom {d['atom']} 依賴 {d['dep']}")
            for d in mtime_deps:
                tie = f"；{d['same_day']}" if d["same_day"] else ""
                print(f"🕐 依賴比卡新：atom {d['atom']} 依賴 {d['dep']} 改於 {d['dep_changed']}（{d['dep_source']}），"
                      f"卡最近驗證 {d['verified_at']}（{d['verified_source']}）{tie}")
            cov = depends_coverage(atoms)
            print(f"Depends 覆蓋率 {cov['with_depends']}/{cov['total']} = {cov['ratio']:.1%}")
            if not deps and not mtime_deps:
                print("✅ No stale depends.")

    elif args.shadow_check:
        shadow = detect_shadow_atoms(
            atoms, AIDOCS_ROOT,
            threshold=args.shadow_threshold,
            dry_run=args.shadow_dry_run,
        )
        if args.json:
            print(json.dumps(shadow, indent=2, ensure_ascii=False))
        elif args.shadow_dry_run:
            print(f"=== Shadow Distribution (≥0.30, top {len(shadow)}) ===")
            print(f"AIDocs root: {AIDOCS_ROOT}\n")
            buckets = {"0.9+": 0, "0.8-0.9": 0, "0.7-0.8": 0, "0.5-0.7": 0, "0.3-0.5": 0}
            for s in shadow:
                r = s["ratio"]
                if r >= 0.9: buckets["0.9+"] += 1
                elif r >= 0.8: buckets["0.8-0.9"] += 1
                elif r >= 0.7: buckets["0.7-0.8"] += 1
                elif r >= 0.5: buckets["0.5-0.7"] += 1
                else: buckets["0.3-0.5"] += 1
            print("── Bucket counts ──")
            for k, v in buckets.items():
                print(f"  {k}: {v}")
            print("\n── Top 30 pairs ──")
            for s in shadow[:30]:
                print(f"  {s['ratio']:.3f}  {s['atom']}::{s['section']}  → {s['md_path']}#{s['md_heading']}")
        elif shadow:
            print(f"⚠️ {len(shadow)} shadow warning(s) (threshold={args.shadow_threshold}):")
            for s in shadow:
                print(f"  {s['atom']}::{s['section']}  ratio={s['ratio']:.2f}  → {s['md_path']}#{s['md_heading']}")
        else:
            print(f"✅ No shadow atoms above threshold {args.shadow_threshold}.")

    elif args.report:
        shadow = []
        if args.shadow_check or args.shadow_dry_run:
            shadow = detect_shadow_atoms(atoms, AIDOCS_ROOT,
                                         threshold=args.shadow_threshold,
                                         dry_run=args.shadow_dry_run)
        report = full_report(atoms, aliases, shadow_atoms=shadow, mojibake=mojibake)
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print_text_report(report)


if __name__ == "__main__":
    main()

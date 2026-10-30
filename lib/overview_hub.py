"""overview_hub — 部位表（`<專案根>/.claude/overview-map.md`）的查表、導讀卡位置、transcript 三管道與讀檔路徑解析（純函式）。

做什麼：專案在 `<專案根>/.claude/overview-map.md` 放一張「路徑前綴 → 部位 → 導讀卡」表（專案自己寫，根層只讀）。
往上找最近的那張表（find_map），用最長前綴命中決定部位（match_row）；導讀卡在哪（card_mem_dir／resolve_card）、
卡的「已知病灶」段（defect_bullets）；AI 寫的內容分三管道讀（LOCATE_CHANNELS／assistant_text_after，宣告行共用）；
工具呼叫讀了哪些檔（read_paths_from_tool）。

表格式（兩個專案各自的寫法都吃）：markdown 表格，每列至少有一格含反引號路徑（前綴）、緊接的一格是部位名、
某格含反引號的卡名（無路徑分隔符）、某格以「有／部分／索引／無」開頭當狀態；「同上」「同第 N 列」沿用別列的卡。
"""

from __future__ import annotations

import fnmatch
import json
import os
import posixpath
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MAP_REL = ".claude/overview-map.md"
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_SAME_ROW_RE = re.compile(r"同第\s*(\d+)\s*列")
_STATUS_HEADS = ("有", "部分", "索引", "骨架", "無")
_TWO_CHAR_STATUS = ("部分", "索引", "骨架")
# 部位類別：code＝寫碼部位（欠 (d) 案例）；knowledge＝知識部位（文件、記憶、信件匣：不欠案例）
KIND_CODE = "code"
KIND_KNOWLEDGE = "knowledge"
_KNOWLEDGE_WORDS = ("knowledge", "知識")
# 擴欄：表頭關鍵字 → row 鍵；只認表頭，沒表頭的舊四欄表這些鍵全空（類別沒欄＝code）
_EXTRA_COLUMNS = (
    ("病灶", "defects_doc"), ("量尺", "measure"), ("檢查器", "checkers"), ("讀路徑", "sample_paths"),
    ("第四問", "extra_q"), ("權威", "authority"), ("上游", "upstream"), ("下游", "downstream"), ("層", "layer"),
    ("類別", "kind"),
)
_EMPTY_EXTRA: Dict[str, Any] = {
    "defects_doc": "", "measure": {}, "checkers": [], "sample_paths": "", "extra_q": "",
    "layer": "", "authority": "", "upstream": "", "downstream": "", "kind": KIND_CODE,
}
# 「層」欄裡的閱讀路徑層號（tools/reading-path.py 的宣告層次軸）；由程式依路徑推，R5 不要求根因層那行寫它
LAYER_AXIS_RE = re.compile(r"第\s*(\d+)\s*層")
_MEASURE_SPLIT_RE = re.compile(r"\s*[｜]\s*")
_LIST_SPLIT_RE = re.compile(r"\s*[;；、,]\s*")
# bypass 模式下讀檔走 Bash：讀檔指令開頭；參數到本段結束（; | & ) 換行）為止，一段裡的每個路徑參數都算 Read
_BASH_READ_RE = re.compile(
    r'(?:^|[;&|(]\s*)(cat|head|tail|less|more|grep|sed\s+-n\s+\S+|svn\s+cat|svn\s+diff|git\s+show|git\s+diff)(?=\s)',
    re.MULTILINE,            # 每一行行首都算指令開頭（宣告行放 # 註解後，下一行的 head 照認；註解行由 hooks 層先剝掉）
)
_BASH_SEG_END_RE = re.compile(r"[;|&)\n]")
_BASH_REDIRECT_RE = re.compile(r"^\d*(?:<<?|>>?)")     # > >> < << 2> 開頭的 token：本身或下一個是重導向目標，不是讀的檔
_BASH_REV_PREFIX_RE = re.compile(r"^(?:[0-9a-f]{7,40}|HEAD[~^0-9]*):")   # git show <rev>:<路徑>
# PowerShell 讀檔 cmdlet（含常用別名）＋到本段結束（; | & 換行 ) }）為止的參數字串
_PS_READ_RE = re.compile(
    r'(?:^|[;|&({=\n])\s*(get-content|gc|cat|type|select-string|sls|import-csv)(?=\s|$)([^;|&\n)}]*)',
    re.IGNORECASE,
)
_PS_TOKEN_RE = re.compile(r'-[\w-]+:(?:"[^"]*"|\'[^\']*\'|\S+)|"[^"]*"|\'[^\']*\'|\S+')   # -Name:'含空白的值' 是一個 token
_PS_PATH_PARAMS = ("-path", "-literalpath", "-pspath", "-lp")
# 帶值的具名參數：值不是路徑，也不能被當成第一個位置參數
_PS_VALUE_PARAMS = ("-encoding", "-totalcount", "-head", "-first", "-tail", "-last", "-readcount", "-delimiter",
                    "-pattern", "-filter", "-include", "-exclude", "-stream", "-header", "-context", "-culture",
                    "-erroraction", "-ea", "-errorvariable", "-ev", "-outvariable", "-ov")


# 分片：導讀卡五片（what／authority／ask／defects／verify）；標籤同義詞依優先序 authority > ask > defects > verify > what 映射
_SLICE_SYNONYMS = (
    ("authority", ("權威", "真相", "正本", "存哪", "誰說了算", "資料源")),
    ("ask", ("必問", "先問", "動手前", "第四問", "改前")),
    ("defects", ("病灶", "踩坑", "前例", "病徵", "壞味道", "教訓")),
    ("verify", ("驗法", "驗證", "量尺", "怎麼驗", "測試", "檢查器", "驗收")),
    ("what", ("做什麼", "導讀入口", "本卡是", "導航入口", "邊界", "上下游", "上游", "下游", "讀路徑", "閱讀序",
              "分支", "先分清", "概觀", "全貌", "結構", "入口")),
)
_STRUCTURAL_HEADINGS = ("知識", "印象", "知識（節錄）")      # atom 結構標題，不是卡片的段
_HEADING_RE = re.compile(r"^(#{2,4})\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^- (?:\[[臨觀固]\]\s*)?(?:\*\*(.+?)\*\*)?(.*)$")


def _norm(p: str) -> str:
    return p.replace("\\", "/").strip().lower()


# ─── 找表 ───────────────────────────────────────────────────────────

def _home() -> Path:
    """家目錄（獨立成函式讓 verify 能 monkeypatch 成 tmp，證明界線不越過家目錄）。"""
    return Path.home()


def _same_dir(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except (OSError, ValueError):
        return _norm(str(a)) == _norm(str(b))


def find_map(path: str, stop_at: Optional[Path] = None) -> Optional[Tuple[Path, Path]]:
    """從 path 往上找最近的 `<root>/.claude/overview-map.md`；回 (root, map_path)，沒有回 None。

    界線：走到家目錄或磁碟根直接回 None（那一層不檢查，所以根層自己的表要放 ~/.claude/.claude/、
    pytest 的 tmp 永遠找不到家目錄下的東西）；給 stop_at 時檢查完 stop_at 那層就停。
    """
    if not path:
        return None
    try:
        cur = Path(path)
        if not cur.is_absolute():
            return None
        cur = cur if cur.is_dir() else cur.parent
    except OSError:
        return None
    home = _home()
    while True:
        if cur.parent == cur or _same_dir(cur, home):
            return None
        cand = cur / MAP_REL
        try:
            if cand.is_file():
                return (cur, cand)
        except OSError:
            return None
        if stop_at is not None and _same_dir(cur, stop_at):
            return None
        cur = cur.parent


# ─── 解析表 ─────────────────────────────────────────────────────────

def _is_path_token(tok: str) -> bool:
    return ("/" in tok or "\\" in tok) and not tok.startswith("http")


_EXT_ONLY_GLOB_RE = re.compile(r"^\*(?:\.[0-9A-Za-z_]+)+$")


def _is_card_token(tok: str) -> bool:
    """導讀卡欄的 token 是不是卡名。含 `*` 的一律當卡名 glob（`戰鬥*`、`*Missing`、`Missing.v2*`：找不到就由缺卡閘擋，
    不能在解析時消失）；只有純副檔名樣式（`*.bytes`）與含路徑分隔字元的才是檔案樣式，照舊不當卡。"""
    if _is_path_token(tok):
        return False
    if "*" in tok:
        return not _EXT_ONLY_GLOB_RE.match(tok)
    return not tok.endswith((".cs", ".ps1", ".md", ".json"))


def _header_columns(cells: List[str]) -> Dict[str, int]:
    """表頭格 → {row 鍵: 欄索引}；一格只配第一個命中的關鍵字，「層」只配整格就是「層」或以「層」開頭的格。"""
    out: Dict[str, int] = {}
    for i, h in enumerate(cells):
        for kw, key in _EXTRA_COLUMNS:
            if key in out:
                continue
            hit = (h == kw or h.startswith(kw)) if kw == "層" else kw in h
            if hit:
                out[key] = i
                break
    return out


def _cell_text(cell: str) -> str:
    return "" if cell in ("", "無") else cell


def _first_backtick_or_text(cell: str) -> str:
    toks = _BACKTICK_RE.findall(cell)
    return toks[0] if toks else _cell_text(cell)


def _parse_measure(cell: str) -> Dict[str, str]:
    """量尺格「量法｜`指令`｜門檻」以全形豎線切；空格或「無」回 {}。"""
    cell = _cell_text(cell)
    if not cell:
        return {}
    parts = _MEASURE_SPLIT_RE.split(cell) + ["", "", ""]
    return {"method": parts[0], "cmd": _first_backtick_or_text(parts[1]), "threshold": parts[2]}


def _parse_list(cell: str) -> List[str]:
    """清單格：有反引號就取每個反引號；沒有就用 ;／、／, 切。"""
    cell = _cell_text(cell)
    if not cell:
        return []
    toks = _BACKTICK_RE.findall(cell)
    return toks if toks else [t for t in _LIST_SPLIT_RE.split(cell) if t]


def _extra_fields(cells: List[str], cols: Dict[str, int]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(_EMPTY_EXTRA)
    for key, idx in cols.items():
        cell = cells[idx] if idx < len(cells) else ""
        if key == "measure":
            out[key] = _parse_measure(cell)
        elif key == "kind":   # 只認 knowledge／知識；空格、無、拼錯一律 code（fail-closed）
            out[key] = KIND_KNOWLEDGE if cell.strip("` ").lower() in _KNOWLEDGE_WORDS else KIND_CODE
        elif key == "checkers":
            out[key] = _parse_list(cell)
        elif key in ("defects_doc", "authority"):
            out[key] = _first_backtick_or_text(cell)
        else:
            out[key] = _cell_text(cell)
    return out


_DRIVE_RE = re.compile(r"^[a-z]:")


def _norm_prefix(tok: str) -> Tuple[str, bool]:
    """表列前綴 → (根相對的正規化前綴, 放得進根相對位置嗎)。小寫、/、消 `./` 與 `a/../b`、去尾斜線，與 part_kind 對輸入路徑的
    normpath 同一套（`./docs/build/`、`docs/x/../build/` 都是 `docs/build`）。消完是整個根（`.`）、往上跳出根（`..` 開頭）、
    絕對路徑或磁碟代號 → 放不進，回字面正規化與 False。"""
    raw = _norm(tok).rstrip("/")
    q = posixpath.normpath(raw) if raw else raw
    if not q or q in (".", "..") or q.startswith(("../", "/")) or _DRIVE_RE.match(q):
        return raw, False
    return q, True


def parse_map(text: str) -> List[Dict[str, Any]]:
    """表 → rows：[{prefixes, unsafe_prefix, part, part_short, card, cards, status, line, defects_doc, measure, checkers,
    sample_paths, extra_q, layer, authority, upstream, downstream, kind}]。前綴已正規化（小寫、/、消 `./` 與 `..`、去尾斜線，
    見 _norm_prefix）；unsafe_prefix＝這列有放不進根相對位置的前綴。

    前四欄（前綴／部位／導讀卡／狀態）照位置解析；擴欄照表頭關鍵字定位（_EXTRA_COLUMNS），
    沒表頭時擴欄全為空值（""／{}／[]）。
    """
    rows: List[Dict[str, Any]] = []
    cols: Dict[str, int] = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or all(set(c) <= set("-: ") for c in cells):
            continue
        prefix_idx = next(
            (i for i, c in enumerate(cells) if any(_is_path_token(t) for t in _BACKTICK_RE.findall(c))),
            None,
        )
        if prefix_idx is None:
            if not rows and not cols:
                cols = _header_columns(cells)      # 第一個沒路徑的表列＝表頭
            continue
        normed = [_norm_prefix(t) for t in _BACKTICK_RE.findall(cells[prefix_idx]) if _is_path_token(t)]
        prefixes = [p for p, _ in normed]
        part = cells[prefix_idx + 1] if prefix_idx + 1 < len(cells) else ""
        part = part.replace("（", "(").split("(")[0].strip()
        part_short = re.split(r"[／/]", part)[0].strip() or part
        # 欄位固定：前綴｜部位｜導讀卡｜狀態｜（之後可擴欄：病灶清單、量尺、檢查器…）
        # 卡只從「導讀卡」欄取，擴欄裡的 `指令` 反引號不會被誤當卡名
        cards: List[str] = []          # 一列可掛多張卡（如大地圖列＝導讀卡＋根因層卡），全注
        card_cell = cells[prefix_idx + 2] if prefix_idx + 2 < len(cells) else ""
        cards = [t.replace("…", "*") for t in _BACKTICK_RE.findall(card_cell) if _is_card_token(t)]
        if not cards:
            m = _SAME_ROW_RE.search(card_cell)
            if m and 0 < int(m.group(1)) <= len(rows):
                cards = list(rows[int(m.group(1)) - 1]["cards"])
            elif card_cell.startswith("同上") and rows:
                cards = list(rows[-1]["cards"])
        status = ""
        status_cell = cells[prefix_idx + 3] if prefix_idx + 3 < len(cells) else ""
        if status_cell.startswith(_STATUS_HEADS) and len(status_cell) <= 24:
            status = status_cell[:2] if status_cell.startswith(_TWO_CHAR_STATUS) else status_cell[0]
        rows.append({
            "prefixes": [p for p in prefixes if p],
            "unsafe_prefix": any(not ok for _, ok in normed),
            "part": part,
            "part_short": part_short,
            "card": cards[0] if cards else None,
            "cards": cards,
            "status": status,
            "line": line.strip(),
            **_extra_fields(cells, cols),
        })
    return rows


def unread_rows(text: str) -> List[str]:
    """表格裡看起來是資料列、卻因路徑前綴沒用反引號包（或沒有 / 的根目錄單檔）被 parse_map 整列略過的列。
    判法：表頭之後、不是分隔線、第一格有字（不是「無」）、整列沒有一個 parse_map 認得的路徑 token。"""
    out: List[str] = []
    seen_header = False
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or all(set(c) <= set("-: ") for c in cells):
            continue
        if any(_is_path_token(t) for c in cells for t in _BACKTICK_RE.findall(c)):
            seen_header = True
            continue
        if not seen_header:
            seen_header = True      # 第一個沒路徑的表列＝表頭
            continue
        if cells[0] and cells[0] != "無":
            out.append(line.strip())
    return out


def unread_rows_note(map_path: Path) -> Optional[str]:
    """部位表有被整列略過的資料列 → 一句提醒（病形閘與綜觀閘共用）；沒有或讀不到檔回 None。"""
    try:
        rows = unread_rows(Path(map_path).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    if not rows:
        return None
    return (f"部位表 {map_path} 有 {len(rows)} 列的路徑前綴沒用反引號包（或是沒有 / 的根目錄單檔），整列沒被讀到，"
            f"那幾個部位的病灶清單、導讀卡、類別都不生效：{rows[0][:80]}；前綴寫成 `notify/` 這樣才認得")


def layer_number(row: Optional[Dict[str, Any]]) -> Optional[int]:
    """「層」欄恰好一個「第 N 層」→ N（閱讀路徑層次軸的層號）；沒有（例：單層）或不只一個 → None（沒宣告）。"""
    found = LAYER_AXIS_RE.findall((row or {}).get("layer") or "")
    return int(found[0]) if len(found) == 1 else None


# ─── 命中 ───────────────────────────────────────────────────────────

def match_row(path: str, root: Path, rows: List[Dict[str, Any]], anchored: bool = False) -> Optional[Dict[str, Any]]:
    """最長前綴命中；錨在專案根的命中優先於子字串命中；同分取先列。anchored＝只認錨在專案根的命中。
    子字串命中只看專案根以下的相對路徑：根目錄本身的名字（根層 repo 就叫 .claude）、根以上的目錄名都不參與。"""
    p = _norm(path)
    r = _norm(str(root)).rstrip("/")
    below = p[len(r):] if p.startswith(r + "/") else p          # 以 / 開頭；不在根底下就照整條比
    best, best_score = None, -1
    for row in rows:
        for pre in row["prefixes"]:
            if "*" in pre:
                if fnmatch.fnmatch(p, r + "/" + pre):
                    score = 1000 + len(pre)      # glob 錨在專案根，跟一般前綴同權重
                elif fnmatch.fnmatch(below, "*/" + pre):
                    score = len(pre)
                else:
                    score = -1
            elif p.startswith(r + "/" + pre + "/") or p == r + "/" + pre:
                score = 1000 + len(pre)
            elif ("/" + pre + "/") in below or below.endswith("/" + pre):
                score = len(pre)
            else:
                score = -1
            if anchored and score < 1000:
                continue
            if score > best_score:
                best, best_score = row, score
    return best


_SHORT_NAME_RE = re.compile(r"~\d")


def part_kind(path: str, root: Path, rows: List[Dict[str, Any]]) -> str:
    """path 屬哪一類部位：錨在專案根的最長前綴命中列的「類別」；沒命中、沒標、只有子字串命中（tools/memory/x.py 撞到
    `memory/`）→ code。先消 . 與 ..（docs/../tools/a.py 是 tools 的檔）；根以下帶 8.3 短名（`BUILD~1`）時長名寫的
    子部位比不到、可能落到外層的 knowledge 列，判不出就算 code。"""
    p, r = os.path.normpath(str(path)), os.path.normpath(str(root))
    np_, nr = _norm(p), _norm(r).rstrip("/")
    if np_.startswith(nr + "/") and _SHORT_NAME_RE.search(np_[len(nr):]):
        return KIND_CODE
    row = match_row(p, Path(r), rows, anchored=True)
    kind = row.get("kind", KIND_CODE) if row else KIND_CODE
    if kind == KIND_KNOWLEDGE and any(x.get("unsafe_prefix") and x.get("kind") != KIND_KNOWLEDGE for x in rows):
        return KIND_CODE    # 表上有放不進根相對位置的寫碼列：判不出它是不是這條路徑的子列，不落回 knowledge
    return kind


def path_kind(path: str, stop_at: Optional[Path] = None) -> Optional[str]:
    """從 path 往上找最近的部位表（find_map，停在 stop_at），用整張表回 part_kind；沒有部位表回 None（呼叫端照無表行為）。
    表存在卻讀不到 → code（fail-closed），stderr 說一聲。寫碼查核（wg_verify_ledger.is_excluded）與 OverviewHub 共用這一份判法。"""
    if not path:
        return None
    path = os.path.normpath(str(path))
    found = find_map(path, stop_at)
    if not found:
        return None
    root, map_path = found
    try:
        rows = parse_map(map_path.read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        print(f"[overview_hub] 部位表 {map_path} 讀不到，{path} 照寫碼部位算：{type(e).__name__}: {e}", file=sys.stderr)
        return KIND_CODE
    return part_kind(path, root, rows)


# ─── 卡片 ───────────────────────────────────────────────────────────

def _strip_long(s: str) -> str:
    s = s.replace("\\", "/")
    head = s[:8].lower()
    if head == "//?/unc/":
        return "//" + s[8:]
    return s[4:] if head.startswith("//?/") else s


def _is_unc(p: Path) -> bool:
    """網路路徑（`\\\\server\\share`、`\\\\?\\UNC\\…`，前綴不分大小寫）；`\\\\?\\C:\\` 與 `\\\\.\\` 裝置路徑不算。"""
    s = str(p).replace("\\", "/")
    low = s.lower()
    return low.startswith("//?/unc/") or (s.startswith("//") and not low.startswith(("//?/", "//./")))


def _norm_dir(p: Path) -> str:
    """realpath＋反斜線轉正＋小寫，剝 `\\\\?\\`、`\\\\?\\UNC\\` 長路徑前綴（前綴不分大小寫）；
    網路路徑不呼叫 realpath（伺服器不在時會卡數秒），只做字串正規化。"""
    if _is_unc(p):
        return _strip_long(str(p)).rstrip("/").lower()
    return _strip_long(os.path.realpath(_strip_long(str(p)))).rstrip("/").lower()


def _same_dir_norm(a: Path, b: Path) -> bool:
    """兩個路徑是不是同一目錄（_norm_dir 後相等）；只給 is_root_worktree／card_mem_dir 用，find_map 用上面的 _same_dir。"""
    return _norm_dir(a) == _norm_dir(b)


def _gitdir_of(root: Path) -> Optional[Path]:
    """`<root>/.git` 是檔案時，第一個 `gitdir:` 行指的路徑（相對路徑以 root 為基準）；不是檔案、讀不到、沒有這行或值空 → None。"""
    dot = root / ".git"
    try:
        if not dot.is_file():
            return None
        for line in dot.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("gitdir:"):
                value = line[len("gitdir:"):].strip()
                if not value:
                    return None
                p = Path(value)
                return p if p.is_absolute() else root / p
    except OSError as e:
        msg = " ".join(f"{type(e).__name__}: {e}".split())
        print(f"[overview_hub] 讀不到 {dot}：{msg}；當成非根層 worktree", file=sys.stderr)
        return None
    return None


def _read_git_pointer(path: Path) -> Optional[Path]:
    """git 管理檔（worktrees/<名>/gitdir、commondir）的第一行路徑；相對路徑以該檔所在目錄為基準；不存在、讀不到、空 → None。"""
    try:
        first = path.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
    except (OSError, IndexError):
        return None
    if not first:
        return None
    p = Path(first)
    return p if p.is_absolute() else path.parent / p


def is_root_worktree(root: Path, claude_dir: Path) -> bool:
    """root 是「根層（~/.claude）的 git worktree」，三條同時成立才是：
    1. root 與 claude_dir 不是同一目錄；
    2. `<root>/.git` 是檔案，第一個 `gitdir:` 行指到 `<claude_dir>/.git/worktrees/` 之下（與 CommitOrder 認記憶系統 worktree 同一判法）；
    3. 那個管理目錄真的登記了這棵樹：它的 `gitdir` 檔反向指回 `<root>/.git`，`commondir` 指到 `<claude_dir>/.git`
       （只寫一個 `.git` 檔指過去、管理目錄不存在或指向別處 → 不是）。
    不看部位表：在 worktree 裡改了根層部位表，這個 worktree 仍是根層（量尺認 PYTEST_MEASURE、卡讀 live）。
    任一邊是網路路徑 → 直接不是（網路路徑不可能是 ~/.claude 的 worktree），不碰檔案系統。純函式，不碰 state。"""
    try:
        r, c = Path(root), Path(claude_dir)
        if _is_unc(r) or _is_unc(c) or _same_dir_norm(r, c):
            return False
        gitdir = _gitdir_of(r)
        if gitdir is None or not _norm_dir(gitdir).startswith(_norm_dir(c / ".git" / "worktrees") + "/"):
            return False
        back, common = _read_git_pointer(gitdir / "gitdir"), _read_git_pointer(gitdir / "commondir")
        return (back is not None and _same_dir_norm(back, r / ".git")
                and common is not None and _same_dir_norm(common, c / ".git"))
    except OSError:
        return False


def main_worktree_of(root: Path) -> Optional[Path]:
    """root 是某個 repo 已登記的 git worktree 時回主工作樹目錄，否則 None：
    `<root>/.git` 是檔案、指到的管理目錄的 `gitdir` 反向指回 `<root>/.git`、`commondir` 指到某個 `.git` 目錄（主工作樹＝它的上一層）。
    只寫一個 `.git` 檔指過去而管理目錄沒登記、bare repo（commondir 不叫 .git）、網路路徑 → None。純函式，只讀指標檔不起 git。"""
    try:
        r = Path(root)
        if _is_unc(r):
            return None
        gitdir = _gitdir_of(r)
        if gitdir is None:
            return None
        back, common = _read_git_pointer(gitdir / "gitdir"), _read_git_pointer(gitdir / "commondir")
        if back is None or common is None or not _same_dir_norm(back, r / ".git"):
            return None
        common = Path(os.path.normpath(str(common)))
        return common.parent if common.name.lower() == ".git" else None
    except OSError:
        return None


def is_root_git_worktree(root: Path, claude_dir: Path) -> bool:
    """同 is_root_worktree（資料歸屬用的舊名，追蹤帳本等呼叫端仍用這個名字）。"""
    return is_root_worktree(root, claude_dir)


def card_mem_dir(root: Path, claude_dir: Path) -> Path:
    """某個根的導讀卡住在哪個 memory 目錄（hook 注入與第二意見工具共用這一份）：
    root 就是 claude_dir，或 root 是根層 worktree → `claude_dir/memory`（卡片是資料，由 atom_write 寫進 live；
    worktree 的 memory/ 只是開分支當時的副本）；其他 → `root/.claude/memory`。
    root 是網路路徑 → 直接 `root/.claude/memory`，不呼叫 realpath。"""
    r, c = Path(root), Path(claude_dir)
    if _is_unc(r):
        return r / ".claude" / "memory"
    if _same_dir_norm(r, c) or is_root_worktree(r, c):
        return c / "memory"
    return r / ".claude" / "memory"


def resolve_card(root: Path, card: Optional[str], mem_dir: Optional[Path] = None) -> Optional[Path]:
    """卡名 → `<mem_dir>/**/<卡名>.md`，mem_dir 預設 `<root>/.claude/memory`（呼叫端用 card_mem_dir 算好再傳）；
    某些專案卡名的底線會被索引正規化成連字號，兩種都試。"""
    if not card:
        return None
    mem = mem_dir if mem_dir is not None else root / ".claude" / "memory"
    try:
        for name in (card, card.replace("_", "-")):
            hits = sorted(mem.rglob(name + ".md"))
            if hits:
                return hits[0]
    except OSError:
        return None
    return None


# ─── 分片 ───────────────────────────────────────────────────────────

def slice_of_label(label: str) -> Optional[str]:
    """段標籤 → 片名；依 _SLICE_SYNONYMS 優先序，對不上回 None。"""
    for name, words in _SLICE_SYNONYMS:
        if any(w in label for w in words):
            return name
    return None


def split_card_sections(body: str) -> Dict[str, Any]:
    """卡片原文 → {"head": 首段（標題與 meta 列）, "slices": {片名: 原文}, "others": {標題: 原文}}。

    段的邊界：##／### 標題，或 ## 知識 之下的每個頂層 bullet（`- [臨] **標籤**：…`，子 bullet／表格跟著上一段）。
    標籤（標題文字、或 bullet 的粗體標籤）經同義詞映射到五片；對不上、或 bullet 沒粗體標籤的進 others（鍵＝標題或前 20 字）；
    同片多段串接。
    ## 知識／## 印象 是 atom 結構標題，不算段；## 行動 當一段進 others。沒有任何段 → slices 與 others 皆空、全文在 head。
    """
    head: List[str] = []
    segs: List[Tuple[Optional[str], List[str]]] = []
    in_knowledge = False
    for line in body.splitlines():
        hm = _HEADING_RE.match(line)
        if hm:
            title = hm.group(2)
            if title in _STRUCTURAL_HEADINGS:
                in_knowledge = True
                continue
            in_knowledge = False
            segs.append((title, [line]))
            continue
        bm = _BULLET_RE.match(line) if in_knowledge else None
        if bm:
            segs.append((bm.group(1), [line]))        # 沒粗體標籤的 bullet 不映射片（label None → others）
            continue
        (segs[-1][1] if segs else head).append(line)
    slices: Dict[str, str] = {}
    others: Dict[str, str] = {}
    for label, lines in segs:
        text = "\n".join(lines).strip()
        if not text:
            continue
        name = slice_of_label(label) if label else None
        if name:
            slices[name] = f"{slices[name]}\n{text}" if name in slices else text
        else:
            others[label or text.lstrip("- ").lstrip("[臨觀固] ")[:20]] = text
    return {"head": "\n".join(head).strip(), "slices": slices, "others": others}


def defect_bullets(body: str) -> List[str]:
    """導讀卡「已知病灶」片裡的頂層 bullet（`- ` 開頭的行，原樣含 `- `）；沒有這片回 []。"""
    sec = split_card_sections(body)["slices"].get("defects") or ""
    return [s for s in (line.strip() for line in sec.splitlines()) if s.startswith("- ")]


LOCATE_CHANNELS = ("text", "tool_input", "thinking")


def assistant_text_after(transcript_path: str, byte_offset: int, channel: str = "text") -> str:
    """transcript（jsonl）從 byte_offset 之後的 assistant 內容，串成一段。fail-open 回 ""。

    channel：text＝回覆文字塊；tool_input＝工具呼叫的參數（字串化）；thinking＝思考塊。
    harness 偶爾不把「先文字、再呼叫工具」那段文字寫進 transcript（根層與某專案各自驗到），
    所以宣告行要三個管道都認。
    """
    if not transcript_path:
        return ""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(max(0, byte_offset))
            data = f.read().decode("utf-8", errors="ignore")
    except OSError:
        return ""
    out: List[str] = []
    for raw in data.splitlines():
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict) or obj.get("type") != "assistant":
            continue
        for block in obj.get("message", {}).get("content", []) or []:
            if not isinstance(block, dict):
                continue
            bt = block.get("type")
            if channel == "text" and bt == "text":
                out.append(block.get("text", ""))
            elif channel == "thinking" and bt == "thinking":
                out.append(block.get("thinking", ""))
            elif channel == "tool_input" and bt == "tool_use":
                out.extend(_string_values(block.get("input", {})))
    return "\n".join(out)


def _string_values(obj: Any) -> List[str]:
    """工具參數裡所有字串值（遞迴），每個自成一段，行首就是內容（json.dumps 會把鍵名黏在行首）。"""
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _string_values(v)]
    if isinstance(obj, list):
        return [s for v in obj for s in _string_values(v)]
    return []


def transcript_size(transcript_path: str) -> int:
    try:
        return Path(transcript_path).stat().st_size if transcript_path else 0
    except OSError:
        return 0


# ─── 工具呼叫裡的讀檔路徑 ──────────────────────────────────────────

def _ps_read_args(cmdlet: str, args: str) -> List[str]:
    """PowerShell 讀檔 cmdlet 的路徑參數：-Path／-LiteralPath（具名，含 -Path:值）或第一個位置參數
    （Select-String 的第一個位置參數是 Pattern，只認具名）。回原樣 token（引號未剝）。"""
    toks = _PS_TOKEN_RE.findall(args)
    positional = cmdlet not in ("select-string", "sls")
    out: List[str] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if not t.startswith("-"):
            if positional:
                out.append(t)
                positional = False
            i += 1
            continue
        name, colon, inline = t.partition(":")
        name = name.lower()
        if name in _PS_PATH_PARAMS:
            val = inline if colon else (toks[i + 1] if i + 1 < len(toks) else "")
            out.append(val)
            i += 1 if colon else 2
            continue
        i += 2 if name in _PS_VALUE_PARAMS and not colon else 1
    return out


_GLOB_CHARS = frozenset("*?[")
# for V in 清單 ; do 本體 ; done（清單與 do、本體與 done 之間可以是 ; 或換行）
_BASH_FOR_RE = re.compile(r"\bfor\s+([A-Za-z_]\w*)\s+in\s+([^;\n]*?)\s*(?:;|\n)\s*do\b(.*?)(?:;|\n)\s*done\b", re.DOTALL)


def _bash_read_paths(text: str, cwd: str) -> List[str]:
    """一段 Bash 文字裡每個讀檔指令的路徑參數（相對路徑補 cwd）：$ 開頭的不收；glob 照 cwd 展開成實檔；
    沒斜線的 token 只有 cwd 下真有這個檔才收（數字、樣式、指令名不算路徑）。"""
    out: List[str] = []
    for m in _BASH_READ_RE.finditer(text):
        rest = text[m.end():]
        end = _BASH_SEG_END_RE.search(rest)
        for tok in _bash_read_args(m.group(1).split()[0], rest[:end.start()] if end else rest):
            if not tok or tok.startswith("$"):
                continue
            if _GLOB_CHARS & set(tok) and not _quoted_in(tok, rest):     # 加了引號的 glob bash 不展開，照字面（不是實檔就不算）
                out.extend(_bash_glob(tok, cwd))
                continue
            if not _is_path_token(tok) and not (cwd and (Path(cwd) / tok).is_file()):
                continue
            out.append(tok if Path(tok).is_absolute() or not cwd else str(Path(cwd) / tok))
    return out


def _bash_glob(tok: str, cwd: str) -> List[str]:
    """Bash 的 glob 照 cwd 展開成實檔（排序、去目錄）；展不出東西回空——bash 會原樣傳字面，那不是讀到的檔。"""
    import glob as _glob
    pattern = tok if Path(tok).is_absolute() or not cwd else str(Path(cwd) / tok)
    return [p for p in sorted(_glob.glob(pattern)) if os.path.isfile(p)]


# 迴圈本體裡的跳出指令：只認指令位置（行首、; & | ( { 之後、do／then／else 之後）；引號裡的字樣（echo "exit=$?"）不算
_BASH_LOOP_EXIT_RE = re.compile(r"(?:^|[;&|({]|\bdo\b|\bthen\b|\belse\b)\s*(?:break|continue|exit|return)\b", re.MULTILINE)
# 規則 BASH_UNREACHED_READ_NOT_COUNTED 的切法：一條指令先照 ; 與換行切成一串一串，每串再照 && ／|| 切段
_BASH_STMT_SPLIT_RE = re.compile(r"(;|\n)")
_BASH_CHAIN_SPLIT_RE = re.compile(r"(&&|\|\|)")
# 回 true／false 當判斷用的指令：它後面的 && 段不一定跑（整條指令的結束碼看不出來）
_BASH_COND_RE = re.compile(r"^\s*(?:!|false\b|test\b|\[\[?\s|grep\s+(?:-\w*\s+)*-\w*q|command\s+-v\b)")
_BASH_LOOP_SKIP_RE = re.compile(r"^\s*(?:(?:do|then|else|\{)\s+)?(?:break|continue)\b")
_BASH_DONE_RE = re.compile(r"^\s*done\b")
_BASH_LEAVE_RE = re.compile(r"^\s*(?:exit|return)\b")
_BASH_HEREDOC_OPEN_RE = re.compile(r"(?<!<)<<-?\s*['\"]?(\w+)")


def _bash_live_text(text: str) -> str:
    """規則 BASH_UNREACHED_READ_NOT_COUNTED：把執行不到（或不一定跑）的區段挖掉，剩下的才交給讀檔解析。不做完整 shell 解析
    （引號裡的 ; && || 照樣當分隔，跟讀檔解析的段尾判法一致）：
    - || 後面到這串結束不算（前段成功就不跑）；
    - && 串裡出現判斷指令（false、test、[、[[、!、grep -q、command -v）之後到這串結束不算；前段是一般指令照算
      （它失敗會讓結束碼非零，交結束碼篩掉）；
    - 一串開頭是 break／continue → 到 done 之前不算；開頭是 exit／return、或串裡會跑到的段是 exit／return（`true && exit 0`）
      → 之後全部不算（`|| exit 1` 的 exit 在 || 後段、不一定跑，照第一條不算、也不截斷）。
    heredoc 內文（到結束標記那一行）原樣保留、不套上面幾條：那是餵給別的程式的資料（python 的 return 不是 shell 的）。"""
    out: List[str] = []
    skip_to_done, heredoc, pending = False, "", ""
    parts = _BASH_STMT_SPLIT_RE.split(text)
    for i in range(0, len(parts), 2):
        stmt, sep = parts[i], parts[i + 1] if i + 1 < len(parts) else ""
        if heredoc:
            out.append(stmt + sep)
            heredoc = "" if stmt.strip() == heredoc else heredoc
            continue
        tag = _BASH_HEREDOC_OPEN_RE.search(stmt)
        pending = tag.group(1) if tag else pending
        if _BASH_LEAVE_RE.match(stmt) and not skip_to_done:
            break
        skip_to_done = (skip_to_done and not _BASH_DONE_RE.match(stmt)) or bool(_BASH_LOOP_SKIP_RE.match(stmt))
        live, leaves = ("", False) if skip_to_done else _bash_live_chain(stmt)
        out.append(live + sep)
        if leaves:              # 串裡會跑到的 exit／return（`true && exit 0`）：之後都不算
            break
        if pending and sep == "\n":
            heredoc, pending = pending, ""
    return "".join(out)


def _bash_live_chain(stmt: str) -> Tuple[str, bool]:
    """一串（; 或換行之間）裡會跑的前段：|| 之後、判斷指令接 && 之後都不算。回 (會跑的前段, 前段裡有沒有 exit／return)。"""
    segs = _BASH_CHAIN_SPLIT_RE.split(stmt)
    live, leaves = segs[0], False
    for j in range(1, len(segs), 2):
        if segs[j] == "||" or _BASH_COND_RE.match(segs[j - 1]):
            break
        live += segs[j] + segs[j + 1]
        leaves = leaves or bool(_BASH_LEAVE_RE.match(segs[j + 1]))
    return live, leaves


def _quoted_in(tok: str, text: str) -> bool:
    """tok 在 text 裡是用引號包著寫的（'…' 或 "…"）。"""
    return bool(re.search(r"(['\"])" + re.escape(tok) + r"\1", text))


def bash_for_bodies(command: str, cwd: str) -> List[str]:
    """規則 BASH_READONLY_COUNTS_AS_READ 的迴圈展開：清單每一項都是字面（沒加引號的 glob 照 cwd 展開，加了引號的照字面）時，
    本體裡的 $V／${V}／"$V" 換成每一項（單引號包住）各產一份，交給同一套讀檔指令解析。清單含 $、反引號、$(…)，
    或本體有 break／continue／exit／return（後面的讀檔指令不一定跑）的迴圈不展開。"""
    out: List[str] = []
    for m in _BASH_FOR_RE.finditer(command):
        var, items, body = m.group(1), m.group(2), m.group(3).strip()
        if "$" in items or "`" in items or _BASH_LOOP_EXIT_RE.search(body):
            continue
        try:
            toks = shlex.split(items, posix=False)                     # 保留引號：分得出加了引號的 glob
        except ValueError:
            continue
        values: List[str] = []
        for t in toks:
            if t[:1] in "'\"" and t[-1:] == t[:1] and len(t) >= 2:
                values.append(t[1:-1])
            else:
                values.extend(_bash_glob(t, cwd) if _GLOB_CHARS & set(t) else [t])
        ref = re.compile(r'"?\$(?:\{' + var + r'\}|' + var + r'\b)"?')
        out.extend(ref.sub(lambda _m, v=v: f"'{v}'", body) for v in values if "'" not in v)
    return out


def _bash_read_args(cmd: str, rest: str) -> List[str]:
    """一段 Bash 讀檔指令的路徑參數（原樣 token、引號已剝）：旗標、重導向與其目標不算；grep 只在帶 -n（行號）時算讀檔，
    第一個非旗標參數是樣式不算；git show 的 `<rev>:` 前綴剝掉。"""
    try:
        toks = shlex.split(rest, posix=True)
    except ValueError:
        toks = rest.split()
    flags = [t for t in toks if t.startswith("-")]
    if cmd == "grep" and not any(t == "--line-number" or (not t.startswith("--") and "n" in t[1:]) for t in flags):
        return []
    out: List[str] = []
    pattern_pending = cmd == "grep"
    skip_next = False
    for t in toks:
        if skip_next:
            skip_next = False
            continue
        if _BASH_REDIRECT_RE.match(t):
            skip_next = _BASH_REDIRECT_RE.sub("", t) == ""      # 運算子單獨一個 token → 下一個是目標
            continue
        if t.startswith("-"):
            continue
        if pattern_pending:
            pattern_pending = False
            continue
        out.append(_BASH_REV_PREFIX_RE.sub("", t))
    return out


def read_paths_from_tool(tool_name: str, tool_input: Dict[str, Any], cwd: str) -> List[str]:
    """Read 的 file_path；Bash 裡 cat/head/tail/less/more/sed -n/grep -n/svn cat/git show 一段裡的每個路徑參數；PowerShell 裡
    Get-Content／gc／cat／type／Select-String -Path／Import-Csv 的路徑參數（相對路徑補 cwd）。Bash 沒斜線的 token 只有 cwd 下
    真有這個檔才收（數字、樣式、指令名不算路徑）。只解析指令字面；算不算讀過（變數、glob、指令失敗、不是實檔）由
    hooks/wg_release_rules.BASH_READONLY_COUNTS_AS_READ 判。"""
    if tool_name == "Read":
        fp = tool_input.get("file_path", "")
        return [fp] if fp else []
    command = tool_input.get("command", "") or ""
    out: List[str] = []
    if tool_name == "Bash":
        for text in [command, *bash_for_bodies(command, cwd)]:
            out.extend(_bash_read_paths(_bash_live_text(text), cwd))
        return out
    if tool_name != "PowerShell":
        return []
    for m in _PS_READ_RE.finditer(command):
        for raw in _ps_read_args(m.group(1).lower(), m.group(2)):
            for tok in ([raw] if raw[:1] in ("'", '"') else raw.split(",")):     # 引號內的逗號是路徑的一部分
                tok = tok.strip().strip("\"'")
                if not tok or "$" in tok or tok.startswith("-") or tok.startswith("http"):
                    continue
                out.append(tok if Path(tok).is_absolute() or not cwd else str(Path(cwd) / tok))
    return out


def top_dir(path: str, root: Path) -> str:
    """量測用：檔案相對專案根的第一段目錄。"""
    p, r = _norm(path), _norm(str(root)).rstrip("/")
    if p.startswith(r + "/"):
        rel = p[len(r) + 1:]
        return rel.split("/")[0] if "/" in rel else "(root)"
    return "(outside)"

"""overview_hub — 「第一次改某部位的檔之前，整張注入該部位導讀卡」的查表與判定（純函式）。

做什麼：專案在 `<專案根>/.claude/overview-map.md` 放一張「路徑前綴 → 部位 → 導讀卡」表（專案自己寫，
根層只讀）。hook 碰到 Read／Edit／提示詞裡的路徑時，往上找最近的那張表，用最長前綴命中決定部位，
把導讀卡整張原文組成注入文字；Edit 前再查 AI 有沒有在回覆裡交出「定位三行」。

表格式（兩個專案各自的寫法都吃）：markdown 表格，每列至少有一格含反引號路徑（前綴）、緊接的一格是部位名、
某格含反引號的卡名（無路徑分隔符）、某格以「有／部分／索引／無」開頭當狀態；「同上」「同第 N 列」沿用別列的卡。

定位三行（AI 在回覆裡寫的）：
    定位｜部位：<部位>——這次改的是哪一塊
    定位｜根因層：修根因還是症狀；根因在哪層
    定位｜前例：這個部位以前摔過什麼
"""

from __future__ import annotations

import fnmatch
import json
import os
import posixpath
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

MAP_REL = ".claude/overview-map.md"
LOCATE_RE = re.compile(   # 行首可帶 # 或 // 註解符號（三行放在 Bash 參數裡時）；「目標」是有需求目標樹時的第四行
    r"^\s*(?:#+\s*|//\s*)?定位\s*[｜|]\s*(部位|根因層?|前例|目標)\s*[:：]\s*(.+?)\s*[\"']?,?$", re.MULTILINE
)
GOAL_NODE_PLACEHOLDER = "<節點編號>"
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_SAME_ROW_RE = re.compile(r"同第\s*(\d+)\s*列")
_STATUS_HEADS = ("有", "部分", "索引", "骨架", "無")
_TWO_CHAR_STATUS = ("部分", "索引", "骨架")
# 部位類別：code＝寫碼部位（改了要定位三行、欠 (d) 案例）；knowledge＝知識部位（文件、記憶、派工信箱：只要卡已注入、不欠案例）
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
# bypass 模式下讀檔走 Bash：cat / head / tail / sed -n / less 後面的路徑也算 Read
_BASH_READ_RE = re.compile(
    r'(?:^|[;&|(]\s*)(?:cat|head|tail|less|sed\s+-n\s+\S+|svn\s+cat|svn\s+diff|git\s+show|git\s+diff)'
    r'\s+(?:-[a-zA-Z0-9=]+\s+)*(?:[0-9a-f]{7,40}:|HEAD[~^0-9]*:)?"?([^"\s;|&)]+)"?',
    re.MULTILINE,            # 每一行行首都算指令開頭（定位三行放 # 註解後，下一行的 head 照認；註解行由 hooks 層先剝掉）
)
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


# 分片（預計畫第二節）：導讀卡五片；標籤同義詞依優先序 authority > ask > defects > verify > what 映射
SLICE_NAMES = ("what", "authority", "ask", "defects", "verify")
SLICE_LABELS = {"what": "做什麼與上下游", "authority": "權威在哪", "ask": "動手前必問", "defects": "已知病灶", "verify": "驗法"}
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
ROOT_CAUSE_SENTENCE = "找到第一個根因後再找第二個；找不到就寫為什麼不存在"


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


def layer_number(row: Optional[Dict[str, Any]]) -> Optional[int]:
    """「層」欄恰好一個「第 N 層」→ N（閱讀路徑層次軸的層號）；沒有（例：單層）或不只一個 → None（沒宣告）。"""
    found = LAYER_AXIS_RE.findall((row or {}).get("layer") or "")
    return int(found[0]) if len(found) == 1 else None


# ─── 命中 ───────────────────────────────────────────────────────────

def match_row(path: str, root: Path, rows: List[Dict[str, Any]], anchored: bool = False) -> Optional[Dict[str, Any]]:
    """最長前綴命中；錨在專案根的命中優先於子字串命中；同分取先列。anchored＝只認錨在專案根的命中。"""
    p = _norm(path)
    r = _norm(str(root)).rstrip("/")
    best, best_score = None, -1
    for row in rows:
        for pre in row["prefixes"]:
            if "*" in pre:
                if fnmatch.fnmatch(p, r + "/" + pre):
                    score = 1000 + len(pre)      # glob 錨在專案根，跟一般前綴同權重
                elif fnmatch.fnmatch(p, "*/" + pre):
                    score = len(pre)
                else:
                    score = -1
            elif p.startswith(r + "/" + pre + "/") or p == r + "/" + pre:
                score = 1000 + len(pre)
            elif ("/" + pre + "/") in p or p.endswith("/" + pre):
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
    不看部位表：工作 session 照派工改了根層部位表，這個 worktree 仍是根層（量尺認 PYTEST_MEASURE、卡讀 live）。
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


DEFAULT_LOCATE_TEMPLATE = [
    "這次改的是哪一塊",
    "修根因還是症狀；根因在哪層",
    "這個部位以前摔過什麼（卡片病灶段對得上哪條）",
]


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


def _card_body_for(parsed: Dict[str, Any], used: List[str], cp: Path) -> str:
    """選中的片全文、其餘段只列標題（整張路徑附上），讓模型知道還有什麼沒送。"""
    rest = [SLICE_LABELS[s] for s in SLICE_NAMES if s in parsed["slices"] and s not in used] + list(parsed["others"])
    out = [parsed["head"]] + [f"[{SLICE_LABELS[s]}]\n{parsed['slices'][s]}" for s in used]
    if rest:
        out.append(f"其餘段落只列標題（整張見 {cp}）：" + "；".join(rest))
    return "\n".join(x for x in out if x)


def build_injection_ex(row: Dict[str, Any], card_paths: List[Path], hit_path: str, max_chars: int,
                       locate_template: Optional[List[str]] = None, locate_extra: Optional[str] = None,
                       slices: Optional[List[str]] = None, lens: str = "", ask_first: str = "",
                       knowledge: bool = False) -> Tuple[str, List[str]]:
    """同 build_injection，另回實際送出的片名（依 slices 順序、只含卡裡切得出的片；沒選片或沒命中回 []）。

    slices：依意圖要先送的片；命中就「選中片全文＋其餘段標題清單」，整張切不出任何選中片就退回整卡（不得注得更少）。
    lens／ask_first：視角與先問的那一題，加在 head。max_chars 只截**每張卡的正文**（選片後或整卡），
    head（定位三行說明）與卡片分隔行不計入；整段注入文字＝head＋每張卡各 ≤ max_chars。
    knowledge：知識類部位（part_kind）：head 不要求定位三行，卡照注。
    """
    part = row["part"] or row["part_short"]
    t = list(locate_template or [])
    t = (t + DEFAULT_LOCATE_TEMPLATE[len(t):])[:3]
    if knowledge:
        head = (f"[Guardian:OverviewHub] 本 session 第一次碰到【{part}】部位的檔（{hit_path}）。"
                f"這是知識類部位（部位表類別 knowledge）：不要求定位三行，下面的導讀卡讀完即可改。")
    else:
        head = (
            f"[Guardian:OverviewHub] 本 session 第一次碰到【{part}】部位的檔（{hit_path}）。"
            f"改這個部位的檔之前先把下面的導讀卡讀完，並交出定位三行（三行都要，格式照抄；寫在回覆文字最好，"
            f"但本機 transcript 偶爾會掉「先文字再呼叫工具」那段，保險做法是同時放進下一個工具呼叫的參數，例如 Bash 開頭的註解）：\n"
            f"定位｜部位：{row['part_short']}——{t[0]}\n"
            f"定位｜根因層：{t[1]}；{ROOT_CAUSE_SENTENCE}\n"
            f"定位｜前例：{t[2]}"
            + (f"\n定位｜加問：{locate_extra}" if locate_extra else "")
        )
    head += (f"\n視角：{lens}" if lens else "") + (f"\n先問：{ask_first}" if ask_first else "")
    if not card_paths:
        why = f"卡片狀態「{row['status'] or '未標'}」" if row["cards"] else "表上沒有卡"
        return f"{head}\n---- 此部位目前沒有可注入的導讀卡（{why}）；表列原文：{row['line']} ----", []
    note = "" if row["status"] == "有" else f"（注意：表上標此卡狀態「{row['status']}」，不是完整導讀，注入前專案要求先補驗）"
    parts = [head]
    used_all: List[str] = []
    for cp in card_paths:
        try:
            body = cp.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            parts.append(f"---- 導讀卡讀取失敗：{cp}（{e}）----")
            continue
        used: List[str] = []
        if slices:
            parsed = split_card_sections(body)
            used = [s for s in slices if s in parsed["slices"]]
            if used:
                body = _card_body_for(parsed, used, cp)
                used_all.extend(s for s in used if s not in used_all)
        if len(body) > max_chars:
            body = body[:max_chars] + f"\n…（超過 {max_chars} 字截斷，整張見 {cp}）"
        tag = f"（依意圖先送：{'、'.join(SLICE_LABELS[s] for s in used)}）" if used else ""
        parts.append(f"---- 導讀卡{note}{tag}：{cp.stem}（{cp}）----\n{body}")
    return "\n".join(parts), used_all


def build_injection(row: Dict[str, Any], card_paths: List[Path], hit_path: str, max_chars: int,
                    locate_template: Optional[List[str]] = None, locate_extra: Optional[str] = None,
                    slices: Optional[List[str]] = None, lens: str = "", ask_first: str = "") -> str:
    """card_paths：該列所有找得到的卡（可多張，全注）。locate_template：專案換定位三行問法（順序＝部位／根因層／前例）。
    locate_extra：專案對這個部位的第四問（只提醒，不納入三行檢查）。slices／lens／ask_first 見 build_injection_ex。"""
    return build_injection_ex(row, card_paths, hit_path, max_chars, locate_template, locate_extra, slices, lens, ask_first)[0]


# ─── 定位三行 ───────────────────────────────────────────────────────

_TEMPLATE_PHRASES = ("這次改的是哪一塊", "修根因還是症狀；根因在哪層", "這個部位以前摔過什麼", ROOT_CAUSE_SENTENCE,
                     GOAL_NODE_PLACEHOLDER)
# 「待規格：<理由>」是合法填法（規格不存在、要人拍板）；只有光禿的「待規格」沒理由才當沒填
_BARE_PENDING_SPEC_RE = re.compile(r"^待規格\s*[:：]?\s*$")
_NONE_PRECEDENT_RE = re.compile(r"^(?:無|沒有|none|n/?a)(?:[\s，。；;,:：（(].*)?$", re.IGNORECASE | re.DOTALL)
_PRECEDENT_SPLIT_RE = re.compile(r"[\s，。；、,;:：()（）\[\]【】「」『』→/／-]+")


def locate_groups(text: str, template: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """text 裡的定位三行分組：每遇到「部位」行就開一組，同一回覆交兩個部位各一組都算；
    照抄注入範本的佔位句（預設、固定句或專案自訂）那一行不算交。鍵＝部位／根因／前例，有交第四行時另有「目標」。"""
    phrases = tuple(_TEMPLATE_PHRASES) + tuple(s for s in (template or []) if s)
    groups: List[Dict[str, str]] = []
    for m in LOCATE_RE.finditer(text):
        key, val = m.group(1)[:2], m.group(2).strip()
        if any(t in val for t in phrases) or _BARE_PENDING_SPEC_RE.match(val):
            continue
        if key == "部位" or not groups:
            groups.append({})
        groups[-1][key] = val
    return groups


def locate_values(text: str, part_short: str, template: Optional[List[str]] = None,
                  exclude: Sequence[str] = ()) -> Optional[Dict[str, str]]:
    """這個部位**最後一組**完整定位三行（部位行提到 part_short；被擋後補交的那組才是現行）；沒交或缺行回 None。
    exclude：同表裡包含 part_short 的更長部位名（UI 之於 UI 設定），部位行提到它們的那組屬於別的部位，不算。"""
    for g in reversed(locate_groups(text, template)):
        where = g.get("部位", "").lower()
        if ({"部位", "根因", "前例"} <= set(g) and part_short.lower() in where
                and not any(x.lower() in where for x in exclude)):
            return g
    return None


def locate_present(text: str, part_short: str, template: Optional[List[str]] = None) -> bool:
    """text 裡有沒有完整的定位三行（部位／根因／前例），且部位那行提到這個部位。"""
    return locate_values(text, part_short, template) is not None


def locate_quality(text: str, part_short: str, cards: List[str], template: Optional[List[str]] = None) -> str:
    """前例那行填的品質：none＝寫「無」；card＝對得上卡片原文（值裡任一 ≥4 字片段出現在任一張卡）；free＝自由文字。沒交也回 free。"""
    g = locate_values(text, part_short, template)
    if not g:
        return "free"
    val = g["前例"].strip()
    if _NONE_PRECEDENT_RE.match(val):
        return "none"
    chunks = [c for c in _PRECEDENT_SPLIT_RE.split(val) if len(c) >= 4]
    if any(c in card for c in chunks for card in cards):
        return "card"
    return "free"


LOCATE_CHANNELS = ("text", "tool_input", "thinking")


def assistant_text_after(transcript_path: str, byte_offset: int, channel: str = "text") -> str:
    """transcript（jsonl）從 byte_offset 之後的 assistant 內容，串成一段。fail-open 回 ""。

    channel：text＝回覆文字塊；tool_input＝工具呼叫的參數（字串化）；thinking＝思考塊。
    harness 偶爾不把「先文字、再呼叫工具」那段文字寫進 transcript（根層與某專案各自驗到），
    所以定位三行要三個管道都認，記下是哪個管道。
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


def locate_channel(transcript_path: str, byte_offset: int, part_short: str,
                   template: Optional[List[str]] = None) -> Optional[str]:
    """定位三行在哪個管道交的：依 LOCATE_CHANNELS 順序找，找到回管道名，都沒有回 None。"""
    for ch in LOCATE_CHANNELS:
        if locate_present(assistant_text_after(transcript_path, byte_offset, ch), part_short, template):
            return ch
    return None


def transcript_size(transcript_path: str) -> int:
    try:
        return Path(transcript_path).stat().st_size if transcript_path else 0
    except OSError:
        return 0


def transcript_readable(transcript_path: str) -> Tuple[bool, str]:
    """transcript 真的讀得到嗎：真開檔讀 1 byte。回 (讀得到, 原因)；原因 ∈ empty_path／missing／unreadable／empty。
    只 stat 不夠：檔在但被鎖或無權限時 stat 正常、open 才炸。"""
    if not transcript_path:
        return False, "empty_path"
    p = Path(transcript_path)
    try:
        if not p.exists():
            return False, "missing"
        with open(p, "rb") as f:
            head = f.read(1)
    except OSError:
        return False, "unreadable"
    return (True, "") if head else (False, "empty")


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


def read_paths_from_tool(tool_name: str, tool_input: Dict[str, Any], cwd: str) -> List[str]:
    """Read 的 file_path；Bash 裡 cat/head/tail/sed -n 的路徑；PowerShell 裡 Get-Content／gc／cat／type／Select-String -Path／
    Import-Csv 的路徑參數（相對路徑補 cwd）。Bash 沒斜線的 token 只有 cwd 下真有這個檔才收（旗標、指令名不算路徑）；
    含變數（$）的路徑跳過。"""
    if tool_name == "Read":
        fp = tool_input.get("file_path", "")
        return [fp] if fp else []
    command = tool_input.get("command", "") or ""
    out: List[str] = []
    if tool_name == "Bash":
        for m in _BASH_READ_RE.finditer(command):
            tok = m.group(1)
            if tok.startswith(("$", "-")):
                continue
            if not _is_path_token(tok) and not (cwd and (Path(cwd) / tok).is_file()):
                continue
            out.append(tok if Path(tok).is_absolute() or not cwd else str(Path(cwd) / tok))
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

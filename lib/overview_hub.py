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
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MAP_REL = ".claude/overview-map.md"
LOCATE_RE = re.compile(   # 行首可帶 # 或 // 註解符號（三行放在 Bash 參數裡時）
    r"^\s*(?:#+\s*|//\s*)?定位\s*[｜|]\s*(部位|根因層?|前例)\s*[:：]\s*(.+?)\s*[\"']?,?$", re.MULTILINE
)
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_SAME_ROW_RE = re.compile(r"同第\s*(\d+)\s*列")
_STATUS_HEADS = ("有", "部分", "索引", "骨架", "無")
_TWO_CHAR_STATUS = ("部分", "索引", "骨架")
# 擴欄：表頭關鍵字 → row 鍵；只認表頭，沒表頭的舊四欄表這些鍵全空
_EXTRA_COLUMNS = (
    ("病灶", "defects_doc"), ("量尺", "measure"), ("檢查器", "checkers"), ("讀路徑", "sample_paths"),
    ("第四問", "extra_q"), ("權威", "authority"), ("上游", "upstream"), ("下游", "downstream"), ("層", "layer"),
)
_EMPTY_EXTRA: Dict[str, Any] = {
    "defects_doc": "", "measure": {}, "checkers": [], "sample_paths": "", "extra_q": "",
    "layer": "", "authority": "", "upstream": "", "downstream": "",
}
_MEASURE_SPLIT_RE = re.compile(r"\s*[｜]\s*")
_LIST_SPLIT_RE = re.compile(r"\s*[;；、,]\s*")
# bypass 模式下讀檔走 Bash：cat / head / tail / sed -n / less 後面的路徑也算 Read
_BASH_READ_RE = re.compile(
    r'(?:^|[;&|(]\s*)(?:cat|head|tail|less|sed\s+-n\s+\S+|svn\s+cat|svn\s+diff|git\s+show|git\s+diff)'
    r'\s+(?:-[a-zA-Z0-9=]+\s+)*(?:[0-9a-f]{7,40}:|HEAD[~^0-9]*:)?"?([^"\s;|&)]+)"?'
)


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


def _is_card_token(tok: str) -> bool:
    return not _is_path_token(tok) and "*" not in tok and not tok.endswith((".cs", ".ps1", ".md", ".json"))


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
        elif key == "checkers":
            out[key] = _parse_list(cell)
        elif key in ("defects_doc", "authority"):
            out[key] = _first_backtick_or_text(cell)
        else:
            out[key] = _cell_text(cell)
    return out


def parse_map(text: str) -> List[Dict[str, Any]]:
    """表 → rows：[{prefixes, part, part_short, card, cards, status, line, defects_doc, measure, checkers,
    sample_paths, extra_q, layer, authority, upstream, downstream}]。前綴已正規化（小寫、/、去尾斜線）。

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
        prefixes = [
            _norm(t).rstrip("/") for t in _BACKTICK_RE.findall(cells[prefix_idx]) if _is_path_token(t)
        ]
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
            "part": part,
            "part_short": part_short,
            "card": cards[0] if cards else None,
            "cards": cards,
            "status": status,
            "line": line.strip(),
            **_extra_fields(cells, cols),
        })
    return rows


# ─── 命中 ───────────────────────────────────────────────────────────

def match_row(path: str, root: Path, rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """最長前綴命中；錨在專案根的命中優先於子字串命中；同分取先列。"""
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
            if score > best_score:
                best, best_score = row, score
    return best


# ─── 卡片 ───────────────────────────────────────────────────────────

def _same_dir_norm(a: Path, b: Path) -> bool:
    """兩個路徑是不是同一目錄（realpath＋反斜線轉正＋小寫，剝 `\\\\?\\`、`\\\\?\\UNC\\` 長路徑前綴，前綴不分大小寫）；
    只給 is_root_worktree／card_mem_dir 用，find_map 用上面的 _same_dir。"""
    def strip_long(s: str) -> str:
        s = s.replace("\\", "/")
        head = s[:8].lower()
        if head == "//?/unc/":
            return "//" + s[8:]
        return s[4:] if head.startswith("//?/") else s

    def norm(p: Path) -> str:
        return strip_long(os.path.realpath(strip_long(str(p)))).rstrip("/").lower()
    return norm(a) == norm(b)


def is_root_worktree(root: Path, claude_dir: Path) -> bool:
    """root 是「根層（~/.claude）的 worktree」：root ≠ claude_dir，且兩邊的 .claude/overview-map.md 位元組相同。
    任一表不存在、或兩者是同一目錄 → False。純函式，不碰 state。"""
    try:
        r, c = Path(root), Path(claude_dir)
        if _same_dir_norm(r, c):
            return False
        return (r / MAP_REL).read_bytes() == (c / MAP_REL).read_bytes()
    except OSError:
        return False


def card_mem_dir(root: Path, claude_dir: Path) -> Path:
    """某個根的導讀卡住在哪個 memory 目錄（hook 注入與第二意見工具共用這一份）：
    root 就是 claude_dir → `claude_dir/memory`；root 是根層 worktree → `root/memory`；其他 → `root/.claude/memory`。"""
    r, c = Path(root), Path(claude_dir)
    if _same_dir_norm(r, c):
        return c / "memory"
    if is_root_worktree(r, c):
        return r / "memory"
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
                       slices: Optional[List[str]] = None, lens: str = "", ask_first: str = "") -> Tuple[str, List[str]]:
    """同 build_injection，另回實際送出的片名（依 slices 順序、只含卡裡切得出的片；沒選片或沒命中回 []）。

    slices：依意圖要先送的片；命中就「選中片全文＋其餘段標題清單」，整張切不出任何選中片就退回整卡（不得注得更少）。
    lens／ask_first：視角與先問的那一題，加在 head。max_chars 只截**每張卡的正文**（選片後或整卡），
    head（定位三行說明）與卡片分隔行不計入；整段注入文字＝head＋每張卡各 ≤ max_chars。
    """
    part = row["part"] or row["part_short"]
    t = list(locate_template or [])
    t = (t + DEFAULT_LOCATE_TEMPLATE[len(t):])[:3]
    head = (
        f"[Guardian:OverviewHub] 本 session 第一次碰到【{part}】部位的檔（{hit_path}）。"
        f"改這個部位的檔之前先把下面的導讀卡讀完，並交出定位三行（三行都要，格式照抄；寫在回覆文字最好，"
        f"但本機 transcript 偶爾會掉「先文字再呼叫工具」那段，保險做法是同時放進下一個工具呼叫的參數，例如 Bash 開頭的註解）：\n"
        f"定位｜部位：{row['part_short']}——{t[0]}\n"
        f"定位｜根因層：{t[1]}；{ROOT_CAUSE_SENTENCE}\n"
        f"定位｜前例：{t[2]}"
        + (f"\n定位｜加問：{locate_extra}" if locate_extra else "")
        + (f"\n視角：{lens}" if lens else "")
        + (f"\n先問：{ask_first}" if ask_first else "")
    )
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

_TEMPLATE_PHRASES = ("這次改的是哪一塊", "修根因還是症狀；根因在哪層", "這個部位以前摔過什麼", ROOT_CAUSE_SENTENCE)
# 「待規格：<理由>」是合法填法（規格不存在、要人拍板）；只有光禿的「待規格」沒理由才當沒填
_BARE_PENDING_SPEC_RE = re.compile(r"^待規格\s*[:：]?\s*$")
_NONE_PRECEDENT_RE = re.compile(r"^(?:無|沒有|none|n/?a)(?:[\s，。；;,:：（(].*)?$", re.IGNORECASE | re.DOTALL)
_PRECEDENT_SPLIT_RE = re.compile(r"[\s，。；、,;:：()（）\[\]【】「」『』→/／-]+")


def locate_groups(text: str, template: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """text 裡的定位三行分組：每遇到「部位」行就開一組，同一回覆交兩個部位各一組都算；
    照抄注入範本的佔位句（預設、固定句或專案自訂）那一行不算交。鍵＝部位／根因／前例。"""
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


def locate_values(text: str, part_short: str, template: Optional[List[str]] = None) -> Optional[Dict[str, str]]:
    """這個部位**最後一組**完整定位三行（部位行提到 part_short；被擋後補交的那組才是現行）；沒交或缺行回 None。"""
    for g in reversed(locate_groups(text, template)):
        if {"部位", "根因", "前例"} <= set(g) and part_short.lower() in g["部位"].lower():
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

def read_paths_from_tool(tool_name: str, tool_input: Dict[str, Any], cwd: str) -> List[str]:
    """Read 的 file_path；Bash 裡 cat/head/tail/sed -n 的路徑（相對路徑補 cwd）。"""
    if tool_name == "Read":
        fp = tool_input.get("file_path", "")
        return [fp] if fp else []
    if tool_name != "Bash":
        return []
    out: List[str] = []
    for m in _BASH_READ_RE.finditer(tool_input.get("command", "") or ""):
        tok = m.group(1)
        if tok.startswith("$") or not _is_path_token(tok):
            continue
        if not Path(tok).is_absolute() and cwd:
            tok = str(Path(cwd) / tok)
        out.append(tok)
    return out


def top_dir(path: str, root: Path) -> str:
    """量測用：檔案相對專案根的第一段目錄。"""
    p, r = _norm(path), _norm(str(root)).rstrip("/")
    if p.startswith(r + "/"):
        rel = p[len(r) + 1:]
        return rel.split("/")[0] if "/" in rel else "(root)"
    return "(outside)"

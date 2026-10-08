"""hub_card.py：部位導讀卡（hub 卡）五段表、判定、預算與部位文件路由（單一來源）。

做什麼：導讀卡五段（做什麼／權威在哪／動手前必問／已知病灶／驗法）的同義詞表、段落偵測、
hub 判定（found ≥ 3）、hub 預算（4096 bytes，根層固定）、「超預算該去哪」的部位文件路由。
write-gate（tools/memory-write-gate.py）、落檔端（lib/atom_io_cli）與軌 A 的注入端只許 import 這張表，
不得各自另抄詞表。

段落的認法：每一行先剝 `- `／`[臨]` 前綴，取 `**粗體**` 或 `## 標題` 當段落名；沒有粗體／標題的行
只認「≤12 字的標籤：」。段落名含同義詞即算命中；一段命中多次只算一段。
hub 判定三訊號：kind_hint=hub／標題（或 H1）含「導讀」／found ≥ 4；標題含導讀但一段都沒有的是指標卡（write-gate 判 pointer）。

怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_write_gate_kinds.py
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

# 五段鍵（順序＝導讀卡格式順序）
HUB_SECTIONS = ("what", "authority", "ask", "defects", "verify")

# 段落鍵 → 白話名（擋回訊息用）
HUB_SECTION_LABELS: Dict[str, str] = {
    "what": "做什麼（這部位做什麼、上下游是誰）",
    "authority": "權威在哪（誰是真相、誰只是展演）",
    "ask": "動手前必問",
    "defects": "已知病灶（每條指踩坑卡或病灶清單）",
    "verify": "最近驗證與驗法",
}

# 段落鍵 → 同義詞（抄自 12 張真卡的段落名；子字串比對、先長後短）
HUB_SECTION_SYNONYMS: Dict[str, tuple] = {
    "what": ("這個部位做什麼", "做什麼", "導讀入口", "導航入口", "部位與邊界", "上下游是誰", "職責邊界"),
    "authority": ("上下游與權威", "部位與權威", "權威與入口", "權威在哪", "權威地圖", "權威", "真相來源"),
    "ask": ("動手前必問", "動碼前必讀", "動手前必讀", "動手前", "修改前提問"),
    "defects": ("已知病灶", "病灶", "已知缺陷"),
    "verify": ("最近驗證與驗法", "最近驗證", "驗證方式", "驗證日期", "驗法", "怎麼驗", "測試步驟"),
}

HUB_CARD_BUDGET = 4096   # 根層固定；config 不覆蓋（五段導讀卡約 1300 CJK 字）
HUB_MIN_FOUND = 4        # 只靠段落名認 hub 要 found ≥ 4；三段以下的普通卡（驗法／病灶／權威常見）不當 hub
HUB_TITLE_MARKER = "導讀"  # 標題含此字＝宣告導讀卡（found 不足也算 hub，寫入時仍要求五段齊）
HUB_STANDARD_NAMES = "做什麼／部位與權威／動手前必問／已知病灶／驗法"

# 超預算／現況帳找不到部位文件時的落點（層名，不是路徑）
ROUTE_FALLBACK = "_AIDocs"

_LINE_PREFIX_RE = re.compile(r"^\s*(?:[-*]\s+)?(?:\[(?:固|觀|臨)\]\s*)?")
_BOLD_RE = re.compile(r"^\*\*(.+?)\*\*")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_SHORT_HEAD_RE = re.compile(r"^(.{1,12}?)[：:]")   # 非粗體行只認「短標籤：」（≤12 字），整句不算段落名
_DEPENDS_PATH_RE = re.compile(r"path:\s*([^,\n]+)")


def section_headings(content: str) -> List[str]:
    """每行的段落名（粗體／標題／冒號前短句），保留原順序；空行略過。"""
    out: List[str] = []
    for raw in (content or "").splitlines():
        line = _LINE_PREFIX_RE.sub("", raw, count=1).strip()
        if not line:
            continue
        m = _HEADING_RE.match(line) or _BOLD_RE.match(line)
        if m:
            out.append(m.group(1).strip())
            continue
        m = _SHORT_HEAD_RE.match(line)
        if m:
            out.append(m.group(1).strip())
    return out


def _section_of(heading: str) -> Optional[str]:
    for key in HUB_SECTIONS:
        if any(syn in heading for syn in HUB_SECTION_SYNONYMS[key]):
            return key
    return None


def check_hub_card_sections(content: str) -> Dict[str, List[str]]:
    """回 {found:[鍵], missing:[鍵], headings:[段落名]}；found／missing 依五段順序。"""
    headings = section_headings(content)
    hit = {key for key in (_section_of(h) for h in headings) if key}
    return {
        "found": [k for k in HUB_SECTIONS if k in hit],
        "missing": [k for k in HUB_SECTIONS if k not in hit],
        "headings": headings,
    }


_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def h1_title(content: str) -> str:
    """atom 全文的 H1 標題（沒有回空字串）；落檔端只有全文沒有 title 參數時用。"""
    m = _H1_RE.search(content or "")
    return m.group(1) if m else ""


def is_hub_card(content: str, title: str = "", kind_hint: Optional[str] = None) -> bool:
    """導讀卡判定（三訊號任一）：kind_hint=="hub"／標題（或全文 H1）含「導讀」／五段命中 ≥ HUB_MIN_FOUND。
    found==3 且無其他訊號不是 hub（普通卡常同時有驗法、病灶、權威三段）。"""
    if kind_hint == "hub":
        return True
    if HUB_TITLE_MARKER in (title or "") or HUB_TITLE_MARKER in h1_title(content):
        return True
    return len(check_hub_card_sections(content)["found"]) >= HUB_MIN_FOUND


def budget_limit_for(content: str, default_limit: int, title: str = "", kind_hint: Optional[str] = None) -> int:
    """落檔端選預算：導讀卡用 HUB_CARD_BUDGET，其餘用呼叫端的預設。"""
    return HUB_CARD_BUDGET if is_hub_card(content, title, kind_hint) else int(default_limit)


def missing_labels(missing: Iterable[str]) -> List[str]:
    return [HUB_SECTION_LABELS[k] for k in missing if k in HUB_SECTION_LABELS]


def depends_paths(depends: Optional[Iterable[str]]) -> List[str]:
    """Depends 清單（`path:<絕對路徑>` 或純路徑）→ 路徑字串；空值回 []。"""
    out: List[str] = []
    for d in depends or []:
        s = str(d or "").strip()
        if not s:
            continue
        m = _DEPENDS_PATH_RE.search(s)
        out.append((m.group(1) if m else s).strip())
    return out


def route_doc_for(paths: Iterable[str]) -> str:
    """超預算／現況帳該去的部位文件：沿 paths（Depends 指的檔、既有卡路徑）找最近的部位表，
    取命中列的病灶清單（無則權威地圖），回 `<專案根>/<文件>`；都找不到回 ROUTE_FALLBACK（層名）。"""
    try:
        from .overview_hub import find_map, match_row, parse_map
    except ImportError:
        try:
            from overview_hub import find_map, match_row, parse_map  # type: ignore
        except ImportError:
            return ROUTE_FALLBACK
    for p in paths:
        if not p:
            continue
        found = find_map(str(p))
        if not found:
            continue
        root, map_path = found
        try:
            rows = parse_map(map_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        row = match_row(str(p), root, rows)
        if not row:
            continue
        for key in ("defects_doc", "authority"):
            doc = str(row.get(key) or "").strip()
            if doc and doc != "無":
                return str(Path(root) / doc) if not Path(doc).is_absolute() else doc
    return ROUTE_FALLBACK

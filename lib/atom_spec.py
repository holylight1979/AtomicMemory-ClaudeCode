"""atom_spec.py — 全系統「什麼是合法 atom」的唯一規則來源

純資料 + 純函式，零 IO（除 resolve_scope_dir 需訪問 fs 標記）。
被 memory-audit / atom-health-check / atom_io 共用 import，避免規則漂移。

行為等價對拍 server.js: slugify / buildAtomContent / validateAtomContent / resolveMemDir
（V4 SPEC §4 metadata 順序、§8 scope dir 結構）。
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    from .project_root import claude_data_dir
except ImportError:  # 頂層模組載入（含單獨按檔案載入、lib/ 不在 sys.path）：從本檔所在的 lib/ 找
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    from project_root import claude_data_dir


# ─── Constants（單一規則來源） ───────────────────────────────────────────────

# 子目錄跳過清單（rglob 掃描時用）
# - feedback/: 行為 atom，必掃
# - personal/: V4 user role 宣告檔（role.md），非 atom
# - wisdom/: Wisdom Engine 設計文件（DESIGN.md），非 atom（用設計文件章節）
# - episodic/: auto-generated session 摘要，使用 ## 摘要 章節，與 atom 格式不同
# - _pending_review/: shared 敏感原子待裁決區，非活躍 atom
# - _rejected/: memory-undo 撤銷歸檔區，非活躍 atom
# - _drafts/: auto-capture 草稿隔離區（extract-worker），不入索引不注入
SKIP_DIRS = frozenset({
    "_meta", "_reference", "_staging", "_vectordb", "_distant",
    "episodic", "templates", "personal", "wisdom", "_pending_review",
    "_rejected", "_drafts",
})

# 系統檔前綴（檔名等級跳過）
SKIP_PREFIXES = ("SPEC_", "_")

# 索引檔名稱
MEMORY_INDEX = "MEMORY.md"
ATOM_INDEX = "_ATOM_INDEX.md"

# Last-used / Confirmations / ReadHits 居 <atom>.access.json，
# 故 atom .md 不再 require 這些欄位（OPTIONAL_METADATA 仍接受 legacy 欄位過渡）。
REQUIRED_METADATA = frozenset({"Scope", "Confidence", "Trigger"})
OPTIONAL_METADATA = frozenset({
    "Last-used", "Confirmations", "ReadHits",  # legacy 過渡欄；migration 後清空
    "Privacy", "Source", "Type", "Created", "TTL",
    "Expires-at", "Tags", "Related", "Supersedes", "Quality",
    "Audience", "Author", "Pending-review-by", "Merge-strategy", "Created-at",
    "Decided-by",  # conflict-review 核可 shared atom 時寫入（核可者）
    "Aka",  # 這顆 atom 用過的舊檔名（逗號分隔）；索引把它登錄成指向同一顆的鍵，
            # 改名後舊 Related 仍解析得到，不必去改所有連進來的檔（那些是別人的檔）
    "Depends", "Evidence",  # 壞滅緣（validity conditions）/ 證據等級（了義裁決）
    "Status",  # 選填現況一行（如「案結 2026-07-29」）；cold/skip 一行注入時附帶。
    "Quote",  # 觸發這張卡片的使用者原話引述（單行 ≤200 字）；PostToolUse 自動填、回填腳本補
               # 只寫現況，禁歷史敘事/版本脈絡（feedback-live-檔與記憶不留版本操作脈絡）
})

# 行動 always required; 知識 or 印象（指標型 atom 變體）二選一
REQUIRED_SECTIONS = frozenset({"行動"})
KNOWLEDGE_SECTIONS = frozenset({"知識", "印象"})

VALID_CONFIDENCE = frozenset({"[固]", "[觀]", "[臨]"})
VALID_SCOPES = frozenset({"global", "shared", "role", "personal"})

# ─── Depends（壞滅緣 validity conditions）/ Evidence（證據等級） ────────────────
# 兩欄皆 optional：既有 atom 缺欄位一律靜默通過（向後相容鐵則）。
# Depends 條目兩型：
#   - path 型 `path:<相對或~路徑>` — 機器可驗（存在性）；相對路徑以 ~/.claude 為根
#   - 自由文字型（如 `decision:xxx`、版本描述）— 不可驗，僅展示
DEPENDS_PATH_PREFIX = "path:"

# Evidence：實證（實際跑過/測過）> 引述（文件/網路來源）> 推測（模型推斷）> 未標
VALID_EVIDENCE = frozenset({"實證", "引述", "推測"})
EVIDENCE_RANK = {"實證": 3, "引述": 2, "推測": 1}  # 未標/非法 = 0

TRIGGER_MIN = 3
TRIGGER_MAX = 12
ATOM_MAX_LINES = 200
INDEX_MAX_LINES = 40  # 全域 MEMORY.md 行數上限：Lv1 範疇目錄一行一列 + 表頭 + 指標列。超過代表 always-load 索引又長胖，該瘦身而非再調高
PROJECT_INDEX_MAX_LINES = 150  # 專案層 MEMORY.md 上限：專案層不生成各範疇 _INDEX.md（sync-memory-index 延後），逐顆列表住在 MEMORY.md 本身，容量比全域寬

# ─── Knowledge 區大小預算（寫入端硬拒；audit 的 ATOM_MAX_LINES 為事後 warning）──
# 門檻依據：注入端 per-turn 預算 TURN_BUDGET_LIMIT=500 tok（hooks/wg_core.py）+
# 知識段注入上限 _KNOWLEDGE_CAP_TOKENS_DEFAULT=200 tok（hooks/wg_atoms.py）——
# 知識段超過 ~1KB 時全文注入必被截斷/降級，寫再多也到不了模型眼前。管線查無
# 單顆 byte 硬門檻可直接反推，取 3KB 為硬拒線：低於截斷點的 3 倍餘裕內仍容
# 得下正常結論型 atom；超過即代表在堆個案敘事而非結論。
KNOWLEDGE_BUDGET_BYTES = 3072

# 達預算此比例即預警：撞牆才發現要重整時，選項只剩「刪既有內容」
KNOWLEDGE_BUDGET_WARN_RATIO = 0.8

# 清單型內容的硬拒門檻（待辦標記數）。清單會一直長大，放 atom 必然撞預算，
# 且知識段注入上限 200 tok 會先把它截掉——第一次寫入就擋，不等它長到上限。
TASK_LIST_MIN_ITEMS = 3

# 內容樣式軟警門檻（逐筆表格列數 / 含路徑行數）
STYLE_TABLE_MIN_ROWS = 6
STYLE_PATH_MIN_LINES = 8


# ─── Pure functions ───────────────────────────────────────────────────────────


_SLUG_SPACE_RE = re.compile(r"[\s_]+")
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9一-鿿㐀-䶿-]")
_SLUG_DASH_RE = re.compile(r"-+")


def slugify(title: str) -> str:
    """Atom 檔名 slug。對拍 server.js:655-663 行為等價。

    規則：lowercase → 空白/底線→`-` → 非 ascii/cjk/dash 剝除 → 連續 dash 合併 → trim dash
    """
    s = (title or "").lower()
    s = _SLUG_SPACE_RE.sub("-", s)
    s = _SLUG_STRIP_RE.sub("", s)
    s = _SLUG_DASH_RE.sub("-", s)
    s = s.strip("-")
    return s or "untitled"


def is_atom_file(path: Path, memory_root: Path) -> bool:
    """判斷一個 .md 是否為合法 atom 檔（會被 audit/health/index 計入）。

    排除：MEMORY.md / _ATOM_INDEX.md / SPEC_* / _* 前綴 / SKIP_DIRS 中間目錄。
    """
    if not path.is_file() or path.suffix != ".md":
        return False
    if path.name == MEMORY_INDEX or path.name == ATOM_INDEX:
        return False
    if any(path.name.startswith(p) for p in SKIP_PREFIXES):
        return False
    try:
        rel_parts = path.relative_to(memory_root).parts
    except ValueError:
        return False
    # rel_parts: directory parts + filename. Check intermediate dirs only.
    if is_personal_atom_rel_parts(rel_parts):
        return True  # personal/<user>/<slug>.md 是 atom（role.md / auto 草稿夾除外）
    if any(part in SKIP_DIRS for part in rel_parts[:-1]):
        return False
    return True


def is_personal_atom_rel_parts(rel_parts) -> bool:
    """memory root 下 personal/<user>/…/<slug>.md ⇒ True。
    排除：personal/<user>/role.md（V4 角色宣告）、personal/auto/（自動萃取候選）、`_` 前綴段。
    全域根（本人跨專案偏好）與專案根（本人×專案）同一規則。"""
    parts = list(rel_parts)
    if len(parts) < 3 or parts[0] != "personal":
        return False
    owner = parts[1]
    if owner == "auto" or owner.startswith("_"):
        return False
    if any(p.startswith("_") for p in parts[2:-1]):
        return False
    return parts[-1] != "role.md"


_META_LINE_RE = re.compile(r"^-\s+([\w-]+):[ \t]*(.*)$")


def parse_frontmatter(content: str) -> Dict[str, str]:
    """解析 atom-style metadata block（`- Key: Value` 列表）。

    從 # 標題後的 `- Key: Value` 區塊抽 metadata；空行不結束區塊（conflict-review 核可會在
    標題下插 `- Decided-by:` 再接空行），第一個非空、非 `- Key:` 的行（通常 `## 知識`）才結束。
    值為空的欄位（如 `- Related:`）仍屬區塊、但不放進 dict，呼叫端的 `.get(k, 預設)` 照常生效。
    支援 BOM。回傳 dict（無 `_format` key — atom_spec 不關心 Claude-native YAML）。
    """
    if content.startswith("﻿"):
        content = content[1:]
    fm: Dict[str, str] = {}
    in_meta = False
    for line in content.splitlines():
        if line.strip() == "":
            continue
        m = _META_LINE_RE.match(line) if line.startswith("- ") else None
        if m:
            value = m.group(2).strip()
            if value:
                fm[m.group(1)] = value
            in_meta = True
        elif in_meta:
            break
    return fm


# `- Related:` 行。冒號後只吃同行空白：`\s*` 會跨過換行，值為空時把下一行（通常 `## 知識`）
# 當成值——讀的一方會拿標題當連結名，寫的一方會把連結接到標題後面。
RELATED_LINE_RE = re.compile(r"^- Related:[ \t]*(.*)$", re.MULTILINE)
AKA_LINE_RE = re.compile(r"^- Aka:[ \t]*(.*)$", re.MULTILINE)
_SECTION_START_RE = re.compile(r"^## ", re.MULTILINE)


def _find_meta_line(text: str, pattern: "re.Pattern[str]") -> Optional["re.Match[str]"]:
    """metadata 區塊內第一個符合的行（第一個 `## ` 標題之前）；沒有回 None。"""
    section = _SECTION_START_RE.search(text)
    return pattern.search(text, 0, section.start() if section else len(text))


def find_related_line(text: str) -> Optional["re.Match[str]"]:
    """metadata 區塊的 `- Related:` 行。

    讀寫都以這一行為準。檔內留有版控衝突區段時會同時存在多行 Related，
    只要讀與寫定位到不同行，去重判斷就擋不住重複追加。
    """
    return _find_meta_line(text, RELATED_LINE_RE)


def find_aka_line(text: str) -> Optional["re.Match[str]"]:
    """metadata 區塊的 `- Aka:` 行（改名前用過的檔名）。"""
    return _find_meta_line(text, AKA_LINE_RE)


def split_related(value: str) -> List[str]:
    """逗號分隔的名稱欄（Related / Aka）→ 名稱清單；空值與 `(none)` 都是零項。"""
    if not value or value.strip() == "(none)":
        return []
    return [n.strip().removesuffix(".md") for n in value.split(",") if n.strip()]


_CONFLICT_OPEN_RE = re.compile(r"^<{7}(?: |$)")
_CONFLICT_CLOSE_RE = re.compile(r"^>{7}(?: |$)")


def has_conflict_markers(text: str) -> bool:
    """內容含未解的版控衝突區段：先有 `<<<<<<<` 起頭行、後有 `>>>>>>>` 收尾行。

    git merge-file / diff3 / svn 產生的標記同形。``` 區塊內的不算——談衝突處理的 atom
    會在範例裡放標記，那是內容不是衝突。
    """
    in_fence = False
    opened = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _CONFLICT_OPEN_RE.match(line):
            opened = True
        elif opened and _CONFLICT_CLOSE_RE.match(line):
            return True
    return False


def parse_depends(raw: Optional[str]) -> List[Dict[str, str]]:
    """解析 `- Depends:` 值（逗號分隔）為 typed 條目清單。

    回傳 [{"type": "path"|"free", "value": str}, ...]：
      - path 型：`path:<路徑>` → value 為去前綴後的路徑字串（可為空 → 格式警告）
      - free 型：其他任何條目（decision:xxx、版本描述等）原文保留
    空/None 輸入回傳空清單（欄位 optional，缺欄靜默）。
    """
    entries: List[Dict[str, str]] = []
    for item in re.split(r"[,，]", raw or ""):
        item = item.strip()
        if not item:
            continue
        if item.startswith(DEPENDS_PATH_PREFIX):
            entries.append({"type": "path",
                            "value": item[len(DEPENDS_PATH_PREFIX):].strip()})
        else:
            entries.append({"type": "free", "value": item})
    return entries


def resolve_depends_path(value: str, claude_dir: Optional[Path] = None,
                         base: Optional[Path] = None) -> Path:
    """path 型 Depends 條目 → 絕對路徑。

    - `~` 開頭 → expanduser
    - 絕對路徑 → 原樣
    - 相對路徑 → 以 base 為根（專案卡＝專案根；根層卡＝資料根）；沒給 base 用 claude_dir（預設資料根 claude_data_dir()）
    """
    root = base or claude_dir or claude_data_dir()
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = root / p
    return p


def depends_base_for(mem_dir: Path) -> Path:
    """索引目錄 → 該索引卡片 `path:` 相對路徑的解析根：根層 `<資料根>/memory` → 資料根；
    專案層 `<root>/.claude/memory` → `<root>`；其他佈局退 mem_dir 的上一層。"""
    mem_dir = Path(mem_dir)
    try:
        if mem_dir.resolve() == (claude_data_dir() / "memory").resolve():
            return mem_dir.parent
    except OSError:
        pass
    if mem_dir.parent.name == ".claude":
        return mem_dir.parent.parent
    return mem_dir.parent


def _norm_fs_path(p: Path) -> str:
    """路徑比對鍵：resolve（不要求存在）→ 剝 `\\\\?\\`／`\\\\?\\UNC\\` → 正斜線 → Windows 不分大小寫。"""
    try:
        s = str(Path(p).resolve(strict=False))
    except (OSError, ValueError, RuntimeError):
        s = str(p)
    if s.startswith("\\\\?\\UNC\\"):     # Path.resolve 對 extended-length 前綴的處理隨版本不同，兩邊都剝掉才可比
        s = "\\\\" + s[8:]
    elif s.startswith("\\\\?\\"):
        s = s[4:]
    s = s.replace("\\", "/").rstrip("/")
    return s.lower() if os.name == "nt" else s


def atoms_depending_on(path, mem_dirs) -> List[Dict[str, Any]]:
    """哪些卡的索引 `depends` 有 `path:` 條目指到這個檔（或它所在目錄的前綴）。

    mem_dirs：索引目錄清單；每項是 Path（解析根由 depends_base_for 推）或 (mem_dir, base) 二元組（明給根）。
    命中規則：條目解析成絕對路徑後與 path 相等，或 path 在該條目之下（`src/x` 只命中 `src/x/**`，不命中 `src/xy.cs`）。
    回 [{"name", "path"（索引相對路徑）, "card"（卡絕對路徑）, "dep"（原條目）, "mem_dir"}]，依 mem_dirs 順序、同卡只列一次。
    索引讀不到／條目壞掉一律略過（召回是旁路，不得讓讀檔 hook 炸）。
    """
    try:
        from .atom_index_json import load_atom_index_json
    except ImportError:  # 頂層模組載入（hooks 以 sys.path.insert(lib) 方式）
        from atom_index_json import load_atom_index_json  # type: ignore
    target = _norm_fs_path(Path(path))
    out: List[Dict[str, Any]] = []
    seen = set()
    for item in mem_dirs or []:
        if isinstance(item, (tuple, list)) and len(item) == 2:
            mem_dir, base = Path(item[0]), Path(item[1])
        else:
            mem_dir = Path(item)
            base = depends_base_for(mem_dir)
        try:
            atoms = load_atom_index_json(mem_dir).get("atoms", [])
        except (OSError, ValueError):
            continue
        for a in atoms:
            name = a.get("name") or ""
            deps = a.get("depends")
            if not name or not isinstance(deps, list) or name in seen:
                continue
            for raw in deps:
                if not isinstance(raw, str) or not raw.strip().startswith(DEPENDS_PATH_PREFIX):
                    continue
                value = raw.strip()[len(DEPENDS_PATH_PREFIX):].strip()
                if not value:
                    continue
                dep = _norm_fs_path(resolve_depends_path(value, base=base))
                if target == dep or target.startswith(dep + "/"):
                    seen.add(name)
                    out.append({"name": name, "path": a.get("path") or "",
                                "card": str(mem_dir.parent / (a.get("path") or "")),
                                "dep": raw.strip(), "mem_dir": str(mem_dir)})
                    break
    return out


def depends_warnings(raw: Optional[str]) -> List[str]:
    """Depends 值的格式警告（warning 級，不 fail；缺欄/空值不警告）。"""
    warns: List[str] = []
    for e in parse_depends(raw):
        if e["type"] == "path" and not e["value"]:
            warns.append("Depends 條目 `path:` 缺路徑值")
    return warns


def parse_evidence(raw: Optional[str]) -> Optional[str]:
    """解析 `- Evidence:` 值。合法值原樣回傳；缺欄/空/非法 → None（視同未標）。"""
    v = (raw or "").strip()
    return v if v in VALID_EVIDENCE else None


def evidence_warning(raw: Optional[str]) -> Optional[str]:
    """Evidence 非法值警告（warning 級，不 fail）。缺欄/空值回 None（optional）。"""
    v = (raw or "").strip()
    if v and v not in VALID_EVIDENCE:
        return f"Evidence 值無效: {v}（應為 實證/引述/推測）"
    return None


def evidence_rank(raw: Optional[str]) -> int:
    """Evidence 裁決權重：實證3 > 引述2 > 推測1 > 未標/非法0。"""
    return EVIDENCE_RANK.get((raw or "").strip(), 0)


def validate_atom_content(content: str) -> Optional[str]:
    """驗證 atom 內容結構。回傳 None 表通過；錯誤字串表第一個違規。

    對拍 server.js:724-742 validateAtomContent 行為等價。
    （注意：不檢 REQUIRED_METADATA 完整性，那是 audit 報告層級的檢查；
      此函式只驗 build_atom_content 產出契約。）
    """
    if "---\n" in content and content.index("---\n") < 5:
        return "YAML frontmatter (---) is forbidden in atom files"
    if not re.search(r"^# .+", content, re.MULTILINE):
        return "Missing # title heading"
    # 知識 / 印象 二選一（KNOWLEDGE_SECTIONS；指標型 atom 用 ## 印象 取代 ## 知識，
    # 對齊 memory-audit validate_format 的判定）
    if not any(f"## {sec}" in content for sec in KNOWLEDGE_SECTIONS):
        return "Missing ## 知識 or ## 印象 section"
    if "## 行動" not in content:
        return "Missing ## 行動 section"
    m = re.search(r"^- Confidence:\s*(.+)$", content, re.MULTILINE)
    if not m or m.group(1).strip() not in VALID_CONFIDENCE:
        return "Missing or invalid Confidence metadata"
    return None


def knowledge_sections_bytes(content: str) -> int:
    """atom 全文中 ## 知識 + ## 印象 區 body 的 utf-8 bytes 總和（大小預算量測口徑）。"""
    total = 0
    for sec in KNOWLEDGE_SECTIONS:
        m = re.search(
            r"^##[ \t]+" + re.escape(sec) + r"[ \t]*\n([\s\S]*?)(?=^## |\Z)",
            content, re.MULTILINE,
        )
        if m:
            total += len(m.group(1).encode("utf-8"))
    return total


def knowledge_budget_error(nbytes: int, budget: int = KNOWLEDGE_BUDGET_BYTES) -> Optional[str]:
    """knowledge 區超過大小預算 → 錯誤訊息（寫入端硬拒）；否則 None。budget<=0 停用。"""
    if budget <= 0 or nbytes <= budget:
        return None
    return (
        f"knowledge 區 {nbytes} bytes 超過預算 {budget} bytes——"
        "個案事實移文件；atom 只留結論/判斷/教訓/現況/檔案錨點"
        "（大段逐筆內容改為文件路徑一行）。"
        "注入端知識段上限約 200 tok，放寬本預算也不會讓內容送達"
    )


def knowledge_budget_warning(nbytes: int, budget: int = KNOWLEDGE_BUDGET_BYTES,
                             ratio: float = KNOWLEDGE_BUDGET_WARN_RATIO) -> Optional[str]:
    """已達預算 ratio 但未超額 → 預警訊息；否則 None。budget<=0 停用。"""
    if budget <= 0 or nbytes > budget or nbytes < int(budget * ratio):
        return None
    return (
        f"knowledge 區 {nbytes} bytes 已達預算 {budget} bytes 的 {int(ratio * 100)}%——"
        "接近上限；先分辨這是結論還是清單："
        "清單型改為正本進 memory/_staging/、atom 留指標，別等撞牆才刪既有內容"
    )


# 清單型的訊號＝待辦標記。不能用「條列多」當判準——atom 本來就通篇條列
_TASK_ITEM_RE = re.compile(r"^[ \t]*[-*][ \t]+\[[ xX]\]", re.MULTILINE)


def knowledge_task_list_error(content: str,
                              min_items: int = TASK_LIST_MIN_ITEMS) -> Optional[str]:
    """knowledge 區是待辦清單（待辦標記 >= min_items）→ 錯誤訊息；否則 None。min_items<=0 停用。

    清單會持續長大，而 atom 每次 trigger 整顆注入：越完整越貴，且知識段注入上限約
    200 tok 會先把它截斷——長清單放 atom 根本到不了模型眼前。故於第一次寫入即擋。
    """
    if min_items <= 0:
        return None
    items = 0
    for sec in KNOWLEDGE_SECTIONS:
        m = re.search(
            r"^##[ \t]+" + re.escape(sec) + r"[ \t]*\n([\s\S]*?)(?=^## |\Z)",
            content, re.MULTILINE,
        )
        if m:
            items += len(_TASK_ITEM_RE.findall(m.group(1)))
    if items < min_items:
        return None
    return (
        f"knowledge 區有 {items} 個待辦標記（`- [ ]`／`- [x]`）＝清單型內容——"
        "清單正本請寫 memory/_staging/<主題>.md，atom 只留指標"
        "（正本在哪／怎麼改／什麼不寫這裡）。"
        "理由：atom 隨 trigger 整顆注入、知識段上限約 200 tok，長清單會被截斷"
    )


_STYLE_PATH_RE = re.compile(r"[\w~.\\-]*[/\\][\w.\\-]+\.\w{1,5}")


def knowledge_style_warnings(text: str) -> List[str]:
    """內容樣式軟警（不硬拒）：逐筆表格 / 逐輪檔名·路徑清單 → 應為文件錨點一行。"""
    lines = text.splitlines()
    warns: List[str] = []
    table_rows = sum(1 for ln in lines if ln.lstrip().startswith("|"))
    if table_rows >= STYLE_TABLE_MIN_ROWS:
        warns.append(f"逐筆表格 {table_rows} 列——此類個案清單應收斂為文件錨點一行")
    path_lines = sum(1 for ln in lines if _STYLE_PATH_RE.search(ln))
    if path_lines >= STYLE_PATH_MIN_LINES:
        warns.append(f"含路徑/檔名的行達 {path_lines} 行——逐輪檔名/路徑清單應收斂為文件錨點一行")
    return warns


def _is_block_knowledge(item: str) -> bool:
    """knowledge 元素是否為原樣輸出 block（markdown 表格列，或三反引號 fence）。"""
    s = item.lstrip()
    return s.startswith("|") or s.startswith("```")


def render_knowledge_lines(knowledge: Iterable[str]) -> List[str]:
    """渲染 knowledge 為 ## 知識 區行清單（block-aware）。

    - 一般元素：首行補 `- ` bullet（已 `- ` 開頭不重複），維持多行巢狀 bullet。
    - block 元素（表格/fence）：整段原樣輸出，前後補空行（GFM 渲染需要）。
    對拍 server.js renderKnowledgeLines —— 須 byte-identical。
    """
    out: List[str] = []
    for k in knowledge:
        if _is_block_knowledge(k):
            if out and out[-1] != "":
                out.append("")
            out.extend(k.split("\n"))
            out.append("")
        else:
            out.append(k if k.startswith("- ") else f"- {k}")
    while out and out[-1] == "":
        out.pop()
    return out


def build_atom_content(
    *,
    title: str,
    scope: str,
    confidence: str,
    triggers: Iterable[str],
    knowledge: Iterable[str],
    actions: Optional[Iterable[str]] = None,
    related: Optional[Iterable[str]] = None,
    audience: Optional[Iterable[str]] = None,
    author: Optional[str] = None,
    pending_review_by: Optional[str] = None,
    merge_strategy: Optional[str] = None,
    created_at: Optional[str] = None,
    today: Optional[str] = None,
    status: Optional[str] = None,
    supersedes: Optional[Iterable[str]] = None,
    provenance: Optional[str] = None,
    depends: Optional[Iterable[str]] = None,
    quote: Optional[str] = None,
) -> str:
    """從結構化參數構造 atom 檔內容。

    對拍 tools/workflow-guardian-mcp/lib/atom-render.js buildAtomContent —— byte-identical 等價契約。
    SPEC §4 metadata 順序：Scope → Audience → Author → Source → Quote → Confidence → Trigger →
    Status → Last-used → Confirmations → ReadHits → Pending-review-by →
    Merge-strategy → Created-at → Depends → Related → Supersedes。空值欄位省略（status /
    supersedes / provenance / depends 未給時輸出與既有 parity fixture byte-identical）。
    supersedes：本顆取代的舊 atom（被取代者不再注入、檔案保留）；None 或空 → 不輸出。
    provenance：來源（路徑／URL／commit），渲染為 `- Source:`（write_atom 的 source 是稽核白名單，故另名）。
    depends：壞滅緣條目（`path:<路徑>` 或自由文字），渲染為逗號清單 `- Depends:`。
    quote：觸發寫入的使用者原話（已消毒單行），渲染為 `- Quote:`，緊接 Source 之後。
    """
    today = today or date.today().isoformat()
    triggers_list = list(triggers)
    knowledge_list = list(knowledge)
    actions_list = list(actions) if actions else []
    related_list = list(related) if related else []
    supersedes_list = list(supersedes) if supersedes else []
    audience_list = list(audience) if audience else []
    depends_list = list(depends) if depends else []

    lines: List[str] = [f"# {title}", ""]
    lines.append(f"- Scope: {scope}")
    if audience_list:
        lines.append(f"- Audience: {', '.join(audience_list)}")
    if author:
        lines.append(f"- Author: {author}")
    if provenance:
        lines.append(f"- Source: {provenance}")
    if quote:
        lines.append(f"- Quote: {quote}")
    lines.append(f"- Confidence: {confidence}")
    lines.append(f"- Trigger: {', '.join(triggers_list)}")
    if status:
        lines.append(f"- Status: {status}")
    # Last-used / Confirmations / ReadHits 居 <atom>.access.json，不再寫入 .md 檔頭
    if pending_review_by:
        lines.append(f"- Pending-review-by: {pending_review_by}")
    if merge_strategy and merge_strategy != "ai-assist":
        lines.append(f"- Merge-strategy: {merge_strategy}")
    lines.append(f"- Created-at: {created_at or today}")
    if depends_list:
        lines.append(f"- Depends: {', '.join(depends_list)}")
    if related_list:
        lines.append(f"- Related: {', '.join(related_list)}")
    if supersedes_list:
        lines.append(f"- Supersedes: {', '.join(supersedes_list)}")
    lines.extend(["", "## 知識", ""])
    lines.extend(render_knowledge_lines(knowledge_list))
    lines.extend(["", "## 行動", ""])
    if actions_list:
        for a in actions_list:
            lines.append(a if a.startswith("- ") else f"- {a}")
    else:
        lines.append("- （依知識內容判斷）")
    lines.append("")
    return "\n".join(lines)


def resolve_scope_dir(
    scope: str,
    base_dir: Path,
    role: Optional[str] = None,
    user: Optional[str] = None,
) -> Optional[Path]:
    """V4 scope → 子目錄解析。對拍 server.js:777-824 resolveMemDir 結構部分。

    base_dir 含義：
      - global: ~/.claude/memory/  → 直接回傳 base_dir
      - shared/role/personal: {project_root}/.claude/memory/ → 回傳對應子層

    這支函式只負責結構映射，不做 fs marker 檢查（那是 atom_io 呼叫端職責）。
    無效輸入（unknown scope / 必填欄位缺）回傳 None；caller 自行 raise。
    """
    if scope == "global":
        return base_dir
    if scope == "shared":
        return base_dir / "shared"
    if scope == "role":
        if not role:
            return None
        return base_dir / "roles" / role
    if scope == "personal":
        if not user:
            return None
        return base_dir / "personal" / user
    return None


# ─── Helpers used by audit/health-check ───────────────────────────────────────


def iter_atom_files(memory_root: Path):
    """yield memory_root 下所有合法 atom .md（遞迴）。

    audit/health-check 共用，以 is_atom_file 為唯一判定。
    """
    if not memory_root.is_dir():
        return
    for md in sorted(memory_root.rglob("*.md")):
        if is_atom_file(md, memory_root):
            yield md


# V5+ 多 root atom 搜尋與物理位置規則已搬到 lib/atom_locations.py
# （atom_spec 只負責「什麼是合法 atom」；路徑/路由屬 atom_locations 範疇）

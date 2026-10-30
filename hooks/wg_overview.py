"""wg_overview — 部位表（.claude/overview-map.md）與 OverviewHub 設定（overview-hub.json）的共用工具：留下來的閘都從這裡查表、讀設定、記讀檔。

做什麼：
- 設定四層深合併（_cfg，規則在 lib/hub_config.py）：寫碼守門關時 enabled 一律 False（規則 OVERVIEW_HUB_UNDER_V6）。
- 查表（_lookup／_lookup_quiet）：路徑 → (專案根, 部位表那一列)；量尺閘、PickOne、需求目標共用。
- 讀了什麼（read_targets）與讀檔帳（record_reads）：PostToolUse 每次讀檔記進 state["overview_hub"]，
  提問前先讀過部位檔（規則 ASK_OVERVIEW_BEFORE_DECISION）照這筆判。
- 寫入目標檢查（write_check）：命中這一層 readonly_paths 就擋（規則 OVERVIEW_READONLY_PATHS）；設定有錯照 GATE_SELF_ERROR。
- 提醒帳（remind_*）：工具前判成提醒的那一件記進 state，下一個工具結果送一行；每條規則每個對象一 session 一次。
每個事件各落一行 jsonl 到 workflow/_overview-hub.log。

state["overview_hub"] = {
  "<root>|<part>": {"root", "part", "part_files_read": [...]},
  "<root>|(unmapped)<top_dir>": {"part_files_read": [...]}
}
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import (
    CLAUDE_DIR, CONFIG_PATH, _atom_debug_error, _layer_kind_for_root, org_memory_root, resolve_project_root, v6_enabled,
)
from wg_verify_ledger import vcs_root_of

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))   # 程式碼用本檔位置，CLAUDE_DIR 只定位資料
from hub_config import HUB_REL, INTENT_KEYS, merge_hub_cfg  # noqa: E402
import overview_hub as _oh  # noqa: E402
from overview_hub import (  # noqa: E402
    MAP_REL, card_mem_dir, find_map, match_row, parse_map, read_paths_from_tool, resolve_card, top_dir,
)

import wg_release_rules as _rr  # noqa: E402  判定規則（GREP_CONTENT_IS_READ、BASH_COMMENT_LINES_STRIPPED、TEMP_COPY_NOT_PROJECT…）

LOG_PATH = CLAUDE_DIR / "workflow" / "_overview-hub.log"   # _*.log 不進版控
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_TEMP_ROOTS: List[str] = []


def _long(p: str) -> str:
    """目標側也展成長路徑（與暫存根同一種表示；8.3 短路徑的 TEMP）。"""
    try:
        from handlers._shared import _comparable
        return _comparable(p)
    except Exception:  # noqa: BLE001
        return p


def _temp_roots() -> List[str]:
    """暫存根（規則 TEMP_COPY_NOT_PROJECT 的事實）；WG_TEMP_RULES=off 時每次都回關閉值（案例把假專案建在 tmp 下）。"""
    if str(os.environ.get("WG_TEMP_RULES", "")).lower() == "off":
        return list(_rr.TEMP_DISABLED)
    if not _TEMP_ROOTS:
        try:
            from handlers._shared import _comparable      # 8.3 短路徑展成長路徑，與目標側同一種表示
        except ImportError:
            _comparable = str
        _TEMP_ROOTS.extend(_rr.norm_temp_path(_comparable(r)) for r in _rr.temp_roots(tempdir=tempfile.gettempdir()))
    return _TEMP_ROOTS


_WARNED: set = set()                               # 行程內只警告一次的鍵
_ORG_ROOT_CACHE: List[Optional[Path]] = []         # 行程內快取公司根（[] 未查、[None] 未接上、[Path] 接上）


def _org_root() -> Optional[Path]:
    if not _ORG_ROOT_CACHE:
        _ORG_ROOT_CACHE.append(org_memory_root())
    return _ORG_ROOT_CACHE[0]


def _warn_once(key: str, msg: str) -> None:
    if key in _WARNED:
        return
    _WARNED.add(key)
    sys.stderr.write(f"[Guardian:OverviewHub] {msg}\n")


def _warn_retired(retired: List[str]) -> None:
    for key in retired:
        _warn_once(f"retired:{key}", f"設定鍵「{key}」已退役（沒有程式讀它），請從 overview-hub.json／config.json 移除")


def _cfg(config: Dict[str, Any], root: Optional[Path] = None) -> Dict[str, Any]:
    """四層深合併（hub_config.merge_hub_cfg）：預設 < config.json overview_hub < 公司層 < 專案層 overview-hub.json。

    這裡只補呼叫端的事：公司根（行程內快取）、錯誤與退役鍵各警告一次、驗證器內部錯誤進 atom-debug log、
    `_layer`（root／org／project_mapped／project_unmapped／none）。
    寫碼守門關時 `enabled` 一律 False（規則 OVERVIEW_HUB_UNDER_V6）。回傳必帶 `_errors`（非空時 write_check 報設定錯）。
    """
    org = _org_root()
    c = merge_hub_cfg(config, org, root)
    internal = c.pop("_internal_error", None)
    if internal is not None:
        _atom_debug_error("overview_hub:validate", internal)
    _warn_retired(c.get("_retired") or [])
    for e in c["_errors"]:
        _warn_once(f"error:{root}:{e}", f"設定錯誤（{root or '根層'}）：{e}")
    c["_layer"] = "none" if root is None else _layer_kind_for_root(root, org)
    v6 = v6_enabled(config)
    c["enabled"] = bool(c.get("enabled")) and v6
    return c


def _log(event: str, session_id: str, **kw: Any) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "event": event,
                                "session": session_id[:8], **kw}, ensure_ascii=False) + "\n")
    except OSError as e:
        sys.stderr.write(f"[Guardian:OverviewHub] log 寫入失敗（不影響判定）：{e}\n")


def _lookup(path: str, stop_at: Optional[Path] = None) -> Optional[Tuple[Path, Dict[str, Any]]]:
    """路徑 → (專案根, 命中的表列)；找不到表或沒命中回 None；表存在卻讀不到拋 MapReadError（量尺閘不能把它當成沒有量尺）。
    stop_at：往上找表到這層就停（見 find_map）。"""
    found = find_map(path, stop_at)
    if not found:
        return None
    root, map_path = found
    try:
        rows = parse_map(map_path.read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        raise MapReadError(f"部位表 {map_path} 存在但讀不到（{type(e).__name__}: {e}）") from e
    row = match_row(path, root, rows)
    return (root, row) if row else None


class MapReadError(RuntimeError):
    """部位表找到了（find_map 確認檔案存在）卻讀不到：跟「沒有表／沒命中」是兩回事。量尺閘靠 _lookup 決定改檔屬於哪個部位，
    讀不到表就不知道該部位有沒有尺，不能當成「沒有量尺」靜默跳過；stop._verify_gates 接到這個例外走判定錯誤路徑（一律擋＋stderr
    ＋guard_log）。讀檔帳、PickOne 這些路（_lookup_quiet）照舊當沒命中，但在 stderr 說一聲。"""


def _lookup_quiet(path: str, stop_at: Optional[Path] = None) -> Optional[Tuple[Path, Dict[str, Any]]]:
    """_lookup 給讀檔帳與材料蒐集用的版本：表讀不到 → stderr 一行、回 None（這幾條路不是閘，不為此中斷 hook）。"""
    try:
        return _lookup(path, stop_at)
    except MapReadError as e:
        sys.stderr.write(f"[Guardian:OverviewHub] {e}；這次當成沒命中部位表\n")
        return None


def _project_root_of(path: str) -> Optional[Path]:
    """沒命中任何表列時：檔案落在哪個專案根（宣告認領或四標記）；家目錄／磁碟根／無標記回 None。"""
    if not path or resolve_project_root is None:
        return None
    try:
        p = Path(path)
        if not p.is_absolute():
            return None
        return resolve_project_root(str(p if p.is_dir() else p.parent)).path
    except (OSError, ValueError):
        return None


def _unmapped_root_of(path: str) -> Optional[Path]:
    """無表那條路（改檔閘與讀檔記錄共用，兩邊根要一致）：_project_root_of 找不到、且往上沒有任何部位表時，
    退 VCS 根（.git／.svn，不設層數上限；家目錄與磁碟根不算）。有部位表的專案不走退路，行為不變。"""
    root = _project_root_of(path)
    if root is not None or not path or find_map(path):
        return root
    return vcs_root_of(path)


def write_target_root(path: str) -> Optional[Path]:
    """寫入目標（改檔閘逐目標判）落在哪個專案根，規則 DIR_TARGET_JUDGED_BY_CONTAINER：整個資料夾當目標（rm -rf、
    Remove-Item -Recurse、搬走）看它所在的上一層，不拿資料夾自己的專案標記（.git、_AIDocs、部位表）：刪掉整個專案資料夾
    不是在改那個專案的檔，拿它自己當根只會要求讀「(outside)」的檔，永遠讀不到。檔案照舊（_unmapped_root_of）。
    cwd 這類「我在哪」的目錄不走這裡（_project_root_of／_unmapped_root_of 照舊拿目錄自己）。"""
    try:
        p = Path(path)
        is_dir = p.is_absolute() and p.is_dir()
    except (OSError, ValueError):
        is_dir = False
    return _unmapped_root_of(str(p.parent) if is_dir else path)


def _root_key(root: Path) -> str:
    return str(root).replace(chr(92), "/").lower()


def _key(root: Path, row: Dict[str, Any]) -> str:
    return f"{_root_key(root)}|{row['part_short']}"


def _unmapped_key(root: Path, path: str) -> str:
    return f"{_root_key(root)}|(unmapped){top_dir(path, root)}"


def _rel_to_root(path: str, root: Path) -> Optional[str]:
    p, r = path.replace("\\", "/").lower(), _root_key(root).rstrip("/")
    return p[len(r) + 1:] if p.startswith(r + "/") else None


def _is_readonly(path: str, root: Path, cfg: Dict[str, Any]) -> Optional[str]:
    """readonly_paths（glob）命中 → 回命中的樣式；不命中回 None。`**/` 也配零層。
    基準 root＝這次命中的部位表所在根（無表專案＝resolve_project_root 的根），不是宣告那條 pattern 的設定檔所在層：
    根層 hub.json 的 pattern 經四層合併後，對專案檔也是以專案根相對路徑比對。"""
    rel = _rel_to_root(path, root)
    if rel is None:
        return None
    for pat in cfg.get("readonly_paths") or []:
        p = pat.replace("\\", "/").strip("/").lower()
        if fnmatch.fnmatchcase(rel, p) or ("**/" in p and fnmatch.fnmatchcase(rel, p.replace("**/", ""))):
            return pat
    return None


def _intent_of(state: Dict[str, Any]) -> str:
    v = state.get("turn_intent")
    return v if isinstance(v, str) and v in INTENT_KEYS else "general"


def _cards_for(root: Path, row: Dict[str, Any], cfg: Dict[str, Any]) -> List[Path]:
    """表列的導讀卡檔（找得到的）。卡片目錄由 card_mem_dir 決定：根層與根層 worktree 在 `<根>/memory`，其他專案在 `<根>/.claude/memory`。"""
    if row["status"] not in ("有", "部分", "索引"):
        return []
    mem_dir = card_mem_dir(root, CLAUDE_DIR)
    return [cp for cp in (resolve_card(root, c, mem_dir) for c in row["cards"]) if cp]


def defects_top_n(card_paths: List[Any], n: int) -> List[str]:
    """導讀卡「已知病灶」片的前 n 條 bullet（跨多張卡依序取）；讀不到的卡略過（PickOne 材料用）。"""
    out: List[str] = []
    for cp in card_paths or []:
        try:
            body = Path(cp).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        out.extend(_oh.defect_bullets(body)[:n - len(out)])
        if len(out) >= n:
            break
    return out


_GENERATED_AT_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_SMELLS_STR_FIELDS = ("part", "category", "kind", "reason")


def _smells_rows(path: Path) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[float]]:
    """smells 報告 → (列清單, 解析錯誤, generated_at 時間戳)。json（list 或 {rows|items|smells}，可帶 generated_at）／
    jsonl（一行一筆）／md 表（| 路徑 | 分類 | 理由 | 部位? |）。讀不到、壞 JSON、JSONL 壞行、頂層格式不收 → 錯誤字串（照舊回能解析的列）。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [], f"讀不到：{e}", None
    rows: List[Any] = []
    err: Optional[str] = None
    gen_ts: Optional[float] = None
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        bad = 0
        for i, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                bad += 1
                err = err or f"第 {i} 行不是 JSON"
        if bad:
            err = f"{bad} 行不是 JSON（{err}）"
    elif suffix == ".md":
        for line in text.splitlines():
            if not line.strip().startswith("|") or set(line.replace("|", "").strip()) <= set("-: "):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 3 or cells[0] in ("路徑", "path", "檔案"):
                continue
            rows.append({"path": cells[0].strip("`"), "category": cells[1], "reason": cells[2],
                         **({"part": cells[3]} if len(cells) > 3 else {})})
    else:
        try:
            data = json.loads(text)
        except ValueError as e:
            return [], f"不是合法 JSON：{e}", None
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict) and any(isinstance(data.get(k), list) for k in ("rows", "items", "smells")):
            rows = next(data[k] for k in ("rows", "items", "smells") if isinstance(data.get(k), list))
            raw_gen = data.get("generated_at")
            m = _GENERATED_AT_RE.match(str(raw_gen or ""))
            if m:
                try:   # 0000-01-01、13 月、9999 年這類值 mktime 會拋；退回 mtime 並記一筆
                    gen_ts = time.mktime((int(m.group(1)), int(m.group(2)), int(m.group(3)), 0, 0, 0, 0, 0, -1))
                except (OverflowError, ValueError, OSError):
                    gen_ts = None
                    err = f"generated_at 無法換算：{raw_gen}"
        else:
            err = "頂層要是陣列或含 rows／items／smells 陣列的物件"
    # 報告是外部輸入：path 必須是非空字串；part／category／kind／reason 有值就必須是字串，否則整列丟棄並計數
    good: List[Dict[str, Any]] = []
    bad_type = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        if not isinstance(r.get("path"), str) or not r["path"].strip():
            if r.get("path") not in (None, ""):
                bad_type += 1
            continue
        if any(r.get(k) is not None and not isinstance(r.get(k), str) for k in _SMELLS_STR_FIELDS):
            bad_type += 1
            continue
        good.append(r)
    if bad_type:
        msg = f"{bad_type} 列欄位型別不對（path／part／category／kind／reason 要字串）"
        err = f"{err}；{msg}" if err else msg
    return good, err, gen_ts


def read_scope_keys(path: str, config: Dict[str, Any]) -> Tuple[Optional[Path], Optional[str], Optional[str]]:
    """提問閘對部位用（wg_ask_gate._named_parts）：回（專案根, 部位鍵, 頂層目錄鍵 <根>|<頂層目錄>）。部位只在 OverviewHub 開著、表上有列時才有；
    專案根與頂層目錄不看 OverviewHub 開關（有部位表照表所在的根，沒有就照專案標記或 VCS 根）；不在任何專案裡全回 None。"""
    hit = _lookup_quiet(path) if _cfg(config)["enabled"] else None
    if hit and not _cfg(config, hit[0])["enabled"]:
        hit = None
    found = None if hit else find_map(path)
    root = hit[0] if hit else (found[0] if found else _unmapped_root_of(path))
    if root is None:
        return None, None, None
    return root, (_key(*hit) if hit else None), f"{_root_key(root)}|{top_dir(path, root)}"


_MSYS_DRIVE_RE = re.compile(r"(?<![^\s'\"=(])/([A-Za-z])(?=/)")
_LEAD_CD_RE = re.compile(r"""^\s*cd\s+(?:"([^"]+)"|'([^']+)'|([^\s;&|'"]+))\s*(?:&&|;|\n)""")
_GREP_CMD_RE = re.compile(r"((?:^|[;&|(])\s*grep)(?=\s)([^;&|)\n]*)", re.MULTILINE)
_GREP_NO_CONTENT = ("--count", "--files-with-matches", "--files-without-match", "--quiet", "--silent")


def _grep_prints_lines(args: str) -> bool:
    """SHELL_READ_COUNTS_LIKE_READ：這段 grep 會印出命中的行（不是只印檔名 -l／-L、只印筆數 -c、不印 -q）。"""
    for tok in args.split():
        if tok.startswith("--") and tok.split("=", 1)[0] in _GREP_NO_CONTENT:
            return False
        if tok.startswith("-") and not tok.startswith("--") and set(tok[1:]) & set("lLcq"):
            return False
    return True


_SHORT_FLAGS_RE = re.compile(r"(?<!\S)(-[A-Za-z]+|--line-number)(?!\S)")


def _drop_line_numbers(args: str) -> str:
    """不印內容的 grep 段拿掉 -n（含 -nl 這類合寫裡的 n）：lib 只認帶 -n 的 grep，留著就把只印檔名或筆數的 grep 算成讀過。"""
    def fix(m: "re.Match[str]") -> str:
        tok = m.group(1)
        if tok == "--line-number":
            return ""
        tok = tok.replace("n", "")
        return "" if tok == "-" else tok
    return _SHORT_FLAGS_RE.sub(fix, args)


def _shell_read_text(command: str) -> str:
    """SHELL_READ_COUNTS_LIKE_READ：Bash 讀檔指令交 lib 解析前的兩個改寫——MSYS 寫法 `/c/x` 換成 `C:/x`（跟寫檔判定
    wg_core._write_target_abs 同一個檔）；grep 照會不會印出命中行對齊 lib 只認帶 -n 的判法：會印的補上 -n（-n 不改印出多少內容），
    只印檔名、筆數或不印的（-l、-L、-c、-q）拿掉 -n，就算原本帶 -n 也不算讀過。"""
    command = _MSYS_DRIVE_RE.sub(lambda m: f"{m.group(1).upper()}:", command)
    return _GREP_CMD_RE.sub(lambda m: f"{m.group(1)} -n{m.group(2)}" if _grep_prints_lines(m.group(2))
                            else f"{m.group(1)}{_drop_line_numbers(m.group(2))}", command)


def _lead_cd(command: str, cwd: str) -> str:
    """SHELL_READ_COUNTS_LIKE_READ：指令開頭 `cd <目錄> &&`（或 ; 、換行）→ 後面的相對路徑照這個目錄補；沒有、或目錄含變數 → 原 cwd。
    只認開頭那一個 cd，中間的 cd 不追。"""
    m = _LEAD_CD_RE.match(command)
    d = next((g for g in m.groups() if g), "") if m else ""
    if not d or "$" in d or d.startswith("~"):
        return cwd
    return d if Path(d).is_absolute() or not cwd else str(Path(cwd) / d)


def _writes_files(tool_name: str, tool_input: Dict[str, Any], cwd: str) -> bool:
    """SHELL_WRITE_COMMAND_NOT_A_READ：這條 Bash／PowerShell 指令有寫檔目標（重導向 >、tee、sed -i、Out-File…；判不出目標的也算）。
    判寫檔目標的程式出錯 → 照寫檔算（不算讀過），stderr 說一聲。"""
    try:
        from wg_core import write_paths_from_tool
        return bool(write_paths_from_tool(tool_name, tool_input, cwd or None))
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[Guardian:OverviewHub] 判不出這條指令有沒有寫檔，讀到的檔這次不算讀過：{type(e).__name__}: {e}\n")
        return True


def _read_paths(tool_name: str, tool_input: Dict[str, Any], cwd: str, exit_code: Optional[int] = None) -> List[str]:
    """讀檔辨識的入口：Grep（規則 GREP_CONTENT_IS_READ：output_mode=content 且 path 是檔）、Bash 先剝行首 # 註解行
    （規則 BASH_COMMENT_LINES_STRIPPED）、換 MSYS 路徑、grep 補 -n、相對路徑照開頭的 cd 補（規則 SHELL_READ_COUNTS_LIKE_READ）再交 lib 解析；
    Bash／PowerShell 有寫檔目標整條不算讀（規則 SHELL_WRITE_COMMAND_NOT_A_READ），解析出的路徑照規則 BASH_READONLY_COUNTS_AS_READ
    篩（exit_code＝這次指令的結束碼，未知給 None）；其他工具照 lib 原規則。"""
    if tool_name == "Grep":
        return _rr.grep_read_paths(tool_input)
    if tool_name in ("Bash", "PowerShell") and _writes_files(tool_name, tool_input, cwd):
        return []
    if tool_name == "Bash":
        command = _shell_read_text(_rr.strip_comment_lines(str(tool_input.get("command") or "")))
        tool_input, cwd = {**tool_input, "command": command}, _lead_cd(command, cwd)
    paths = read_paths_from_tool(tool_name, tool_input, cwd)
    return _rr.bash_read_counts(paths, exit_code) if tool_name in ("Bash", "PowerShell") else paths


def read_targets(tool_name: str, tool_input: Dict[str, Any], cwd: str, exit_code: Optional[int] = None) -> List[str]:
    """這次工具呼叫讀到的專案檔：_read_paths 去掉暫存目錄下的檔（規則 TEMP_COPY_NOT_PROJECT）。record_reads 與動資料檔的讀提示
    （wg_data_file）共用這一支，兩邊對「讀了什麼」的認定一致。"""
    return [p for p in _read_paths(tool_name, tool_input, cwd, exit_code) if not _rr.is_temp_path(_long(p), _temp_roots())]


def record_reads(state: Dict[str, Any], tool_name: str, tool_input: Dict[str, Any], cwd: str,
                 config: Dict[str, Any], exit_code: Optional[int] = None) -> None:
    """PostToolUse（Read／Bash／PowerShell／Grep）：這次讀到的專案檔（read_targets）記進 state["overview_hub"]：
    命中部位表的檔記到那個部位（第一次讀到建紀錄；該專案層 OverviewHub 關著不建），表外的檔記到 <根>|(unmapped)<頂層目錄>。
    提問前先讀過部位檔（規則 ASK_OVERVIEW_BEFORE_DECISION）照這筆 part_files_read 判。OverviewHub 關著（含寫碼守門關）不記。
    Bash／PowerShell 指令失敗（exit_code≠0）讀到的不算（規則 BASH_READONLY_COUNTS_AS_READ）。"""
    if not _cfg(config)["enabled"]:
        return
    for p in read_targets(tool_name, tool_input, cwd, exit_code):
        hit = _lookup_quiet(p)
        if hit:
            root, row = hit
            key = _key(root, row)
            if key not in (state.get("overview_hub") or {}) and not _cfg(config, root)["enabled"]:
                continue
            fresh = {"root": str(root), "part": row["part"] or row["part_short"], "part_files_read": []}
        else:
            root = _unmapped_root_of(p)
            if root is None:
                continue
            key, fresh = _unmapped_key(root, p), {"part_files_read": []}
        reads = state.setdefault("overview_hub", {}).setdefault(key, fresh).setdefault("part_files_read", [])
        if p not in reads:
            reads.append(p)


_EXT_UNC_PREFIX = "\\\\?\\UNC\\"
_EXT_PREFIX = "\\\\?\\"


def _strip_extended(path: str) -> str:
    """剝 Windows extended-length 前綴：`\\\\?\\C:\\x` → `C:\\x`、`\\\\?\\UNC\\srv\\share\\x` → `\\\\srv\\share\\x`。"""
    if path.startswith(_EXT_UNC_PREFIX):
        return "\\\\" + path[len(_EXT_UNC_PREFIX):]
    if path.startswith(_EXT_PREFIX):
        return path[len(_EXT_PREFIX):]
    return path


def _path_key(p: Path) -> Optional[str]:
    """路徑相等比對用的鍵：resolve（跟 symlink、還原磁碟實際大小寫）→ 剝 `\\\\?\\` → normpath → normcase（Windows 不分大小寫）。"""
    try:
        s = str(p.resolve())
    except (OSError, ValueError, RuntimeError):
        return None
    return os.path.normcase(os.path.normpath(_strip_extended(s)))


def _own_config_layer(file_path: str) -> Tuple[bool, Optional[Path]]:
    """file_path 是不是 OverviewHub 自己讀的設定檔或部位表；是 → write_check 不查（有錯只回警告）。

    候選（精確比對 _path_key，不比檔名、不預篩）：根層 workflow/config.json；根層／公司根／該檔所屬專案根的
    .claude/overview-hub.json 與 .claude/overview-map.md。專案根＝find_map 從該檔往上找到的那個根：無表專案的
    hub.json 不算（那一層設定本來就不會被載入，沒有它造成的錯誤要修；若根層／公司層另有錯仍照一般檔被擋）。
    回 (是不是, 該檔所屬層的 root；config.json 回 None)。"""
    plain = _strip_extended(file_path)
    fk = _path_key(Path(plain))
    if fk is None:
        return (False, None)
    if fk == _path_key(CONFIG_PATH):
        return (True, None)
    own_rels = (HUB_REL, Path(MAP_REL))
    for layer_root in (CLAUDE_DIR, _org_root()):
        if layer_root is not None and any(fk == _path_key(layer_root / rel) for rel in own_rels):
            return (True, layer_root)
    found = find_map(plain)
    root = found[0] if found else _project_root_of(plain)      # 無表專案的 hub.json 也要能自救（新流程會載入它）
    if root is not None and any(fk == _path_key(root / rel) for rel in own_rels):
        return (True, root)
    return (False, None)


# ─── 提醒帳（規則 REMIND_ON_PRIOR_RESULT、REMIND_PENDING_IN_STATE）：工具前守門判成提醒的那一件先記 state，下一個工具結果取走 ───
REMIND_SENT_KEY = "remind_sent"          # state：這個 session 送過的提醒鍵（wg_release_rules.remind_key）
REMIND_PENDING_KEY = "remind_pending"    # state：工具前記下、等下一個工具結果送出的提醒
REMIND_PENDING_CAP = 20


def remind_hit(rule: str, obj: Any, what: str, fix: str, extra: str = "") -> Dict[str, Any]:
    """一件提醒：規則名、對象（部位／頂層目錄鍵／空＝整個 session）、現象、做法、順帶要送的全文（沒有就空）。"""
    return {"rule": str(rule), "obj": str(obj or ""), "what": str(what or ""), "fix": str(fix or ""), "extra": str(extra or "")}


def remind_sent_list(state: Dict[str, Any]) -> List[str]:
    """state 的提醒帳本：**一份清單**（元素 remind_key；state 一 session 一檔，不再按 session 分桶）。
    舊寫法殘留的 dict（{sid: [鍵]}）攤平成清單、其他形狀重置，寫回 state 後回傳同一個物件（呼叫端 append 直接生效）。"""
    sent = state.get(REMIND_SENT_KEY)
    if isinstance(sent, dict):
        sent = [str(k) for v in sent.values() if isinstance(v, list) for k in v]
    elif not isinstance(sent, list):
        sent = []
    state[REMIND_SENT_KEY] = sent
    return sent


def remind_mark(state: Dict[str, Any], rule: str, obj: Any = "") -> bool:
    """記「這件提醒送過了」；本來沒送過回 True（呼叫端這時才送），送過回 False。"""
    sent = remind_sent_list(state)
    if not _rr.remind_due(sent, rule, obj):
        return False
    sent.append(_rr.remind_key(rule, obj))
    return True


def remind_queue(state: Dict[str, Any], hit: Dict[str, Any]) -> None:
    """工具前守門：這件判成提醒、不擋，先記進 state，等下一個工具結果（PostToolUse）送。"""
    pend = state.setdefault(REMIND_PENDING_KEY, [])
    pend.append(dict(hit))
    del pend[:-REMIND_PENDING_CAP]


def remind_flush(state: Dict[str, Any], session_id: str) -> List[str]:
    """PostToolUse：取走等著的提醒；該送的（同規則同對象本 session 第一次）組一行＋順帶全文，送過的只留帳不重送。回要併進
    additionalContext 的段落。"""
    pend = state.pop(REMIND_PENDING_KEY, None) or []
    out: List[str] = []
    for hit in pend:
        rule, obj = str(hit.get("rule") or ""), hit.get("obj") or ""
        if not remind_mark(state, rule, obj):
            _log("remind_skipped", session_id, rule=rule, obj=obj)
            continue
        out.append(_rr.remind_line(rule, str(hit.get("what") or ""), str(hit.get("fix") or "")))
        if hit.get("extra"):
            out.append(str(hit["extra"]))
        _log("remind_sent", session_id, rule=rule, obj=obj)
    return out


def _cfg_error_deny(cfg: Dict[str, Any], session_id: str, file_path: str,
                    row: Optional[Dict[str, Any]]) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    """`_errors` 非空 → (訊息, deny 理由, 提醒件 GATE_SELF_ERROR)，訊息列全部錯誤；沒錯誤回 None。"""
    if not cfg["_errors"]:
        return None
    where = f"改【{row['part_short']}】部位的檔（{file_path}）" if row else f"改 {file_path}"
    msg = (f"[Guardian:OverviewHub] {where}前，這一層的 OverviewHub 設定有錯（{cfg['_layer']}），閘無法判定，先修設定："
           + "；".join(cfg["_errors"]))
    _log("edit_cfg_error", session_id, part=row["part_short"] if row else None, path=file_path,
         layer=cfg["_layer"], errors=cfg["_errors"])
    return (msg, msg, remind_hit("GATE_SELF_ERROR", "overview_hub", f"OverviewHub 設定有錯（{cfg['_layer']}），閘判不了",
                                        "修這一層的 overview-hub.json：" + "；".join(cfg["_errors"])))


def write_check(session_id: str, file_path: str,
                config: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    """PreToolUse（Write／Edit／NotebookEdit／Bash／PowerShell 的每個寫入目標）：回 (警告文字, deny 理由, 提醒件)。
    命中這一層 readonly_paths（程式產物／索引）→ 擋（規則 OVERVIEW_READONLY_PATHS）；設定有錯（含 enabled 不是 bool）→ 擋訊息列全部錯誤、
    提醒件 GATE_SELF_ERROR，呼叫端拿規則名查 gate_mode 決定照擋還是改提醒（規則 GATE_MODE_TABLE）。
    判不出寫入目標（UNKNOWN:）放行並留帳（規則 UNKNOWN_TARGET_LOGGED）；暫存目錄下的副本不查（規則 TEMP_COPY_NOT_PROJECT）；
    改的是 OverviewHub 自己的設定檔或部位表 → 不查（設定寫錯一個鍵才改得回來），有錯只回警告。"""
    if not file_path:
        return (None, None, None)
    if file_path.startswith("UNKNOWN:"):
        _log("edit_unknown_target", session_id, path=file_path, deny_reason=None, allowed=True)
        return (None, None, None)
    if _rr.is_temp_path(_long(file_path), _temp_roots()):
        _log("edit_temp_copy", session_id, path=file_path, rule="TEMP_COPY_NOT_PROJECT", deny_reason=None)
        return (None, None, None)
    own, own_root = _own_config_layer(file_path)
    if own:
        errors = _cfg(config, own_root)["_errors"]
        if not errors:
            return (None, None, None)
        msg = (f"[Guardian:OverviewHub] 正在改 OverviewHub 自己的設定檔（{file_path}），放行以便修復。目前的設定錯誤："
               + "；".join(errors))
        _log("edit_own_config", session_id, path=file_path, errors=errors)
        return (msg, None, None)
    # 設定錯誤先於 enabled／命中判定：設定壞了（含 enabled 不是 bool）整層都不可信，沒命中部位表的檔也報
    cfg = _cfg(config)
    denied = _cfg_error_deny(cfg, session_id, file_path, None)
    if denied:
        return denied
    if not cfg["enabled"]:
        return (None, None, None)
    hit = _lookup_quiet(file_path)
    root, row = hit if hit else (write_target_root(file_path), None)
    if root is None:
        return (None, None, None)
    cfg = _cfg(config, root)
    denied = _cfg_error_deny(cfg, session_id, file_path, row)
    if denied:
        return denied
    ro = _is_readonly(file_path, root, cfg) if cfg["enabled"] else None
    if not ro:
        return (None, None, None)
    msg = (f"[Guardian:OverviewHub] {file_path} 在這一層的 readonly_paths（樣式「{ro}」）：程式產物／索引不可手改，"
           f"改來源或跑產生器。")
    _log("edit_readonly", session_id, path=file_path, pattern=ro, part=row["part_short"] if row else None,
         deny_reason="readonly", layer=cfg.get("_layer"))
    return (msg, msg, remind_hit("OVERVIEW_READONLY_PATHS", file_path, f"{file_path} 命中 readonly_paths（{ro}）", "改來源或跑產生器"))


def _gitignored_set(root: Path, paths: List[str]) -> set:
    """git check-ignore 一次查一批（規則 RUNTIME_DATA_NO_OVERVIEW 的事實）：回被忽略的那些路徑；不在 git／逾時／出錯回空集合（當不忽略）。"""
    if not paths or not (root / ".git").exists():
        return set()
    try:
        r = subprocess.run(["git", "-C", str(root), "check-ignore", "-z", "--stdin"], input="\0".join(paths) + "\0",
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=2,
                           creationflags=_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return set()
    return {p for p in r.stdout.split("\0") if p}

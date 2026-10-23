"""pack.py：第二意見的材料打包：把要審的東西複製進 job 的 materials/，算可重現的總雜湊。

做什麼：同一份材料不管來源行尾（CRLF／LF）、不管餵進來的順序，打包出來的 manifest.hash 都相同；
manifest 只記相對路徑；材料內文指到沙箱外的絕對路徑（磁碟代號、Git Bash 的 /c/…、UNC）一律遮成「…/<最後一段>」
（replay-guard 的洩題規則：提示詞不得含沙箱外路徑）。

怎麼用（由 run.py prepare 呼叫；單獨跑只為除錯）：
    items = gather_items(request, cfg)                 # 從 cwd／part 蒐材料：卡、病灶前 N、diff、帳本尾 K、需求目標樹、草稿
    manifest = pack_materials(job_dir, items, mode, model)
    why = question_root_missing(question, items)       # 有目標樹而 question 沒含樹根那句 → prepare 回 blocked
雜湊規則：每檔內容統一 LF → sha256；files 依 rel 排序；總雜湊 = sha256("rel\\nsha\\n" 逐檔串接)。
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CODE_DIR = Path(__file__).resolve().parents[2]   # 程式碼根（本檔所在的樹）
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
from lib.project_root import claude_data_dir  # noqa: E402
CLAUDE_DIR = claude_data_dir()   # 根層身分（card_mem_dir 的 claude_dir）：和 wg_overview._cards_for 用的 wg_core.CLAUDE_DIR 同一支算法
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0   # pythonw 父行程下 spawn 不彈 console 窗

# 材料檔名固定（提示詞只引這些相對路徑）
REL_CARD = "card.md"
REL_DEFECTS = "defects.md"
REL_DIFF = "diff.patch"
REL_LEDGER = "ledger.jsonl"
REL_DRAFT = "draft.md"
REL_GOAL = "goal.md"
NO_GOAL = "無目標樹"

_ABS_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/]{1,2})")
_HEADING_RE = re.compile(r"^#{1,3}\s", re.MULTILINE)
# 內文裡指到沙箱外的絕對路徑，每份材料都要遮掉：磁碟代號（MIRROR: tools/replay-guard.py ABS_PATH，沒遮 pre 就擋整份提示詞）、
# Git Bash 的 /c/…（帳本的 cd 指令常見；pre 不擋，但一樣把真工作副本的位置交給審查者；至少兩層才算，JS 正規式 /a/g 不動）、
# UNC（含 JSON 跳脫的四個反斜線）
_ABS_IN_TEXT_RE = re.compile(r"(?<![A-Za-z])[A-Za-z]:[/\\][^\s\"'`)\]]+"
                             r"|(?<![\w/.~-])/[A-Za-z]/[^\s\"'`)\]/\\]+[/\\][^\s\"'`)\]]*"
                             r"|(?<![\w:\\/])(?:\\{2,4}|//)[\w.$-]+[\\/][^\s\"'`)\]]+")
_GOAL_ROOT_RE = re.compile(r"樹根（[^）\n]*）：(.*)")


class PackError(Exception):
    """材料相對路徑不合法或寫檔失敗。"""


def normalize_lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(normalize_lf(text).encode("utf-8")).hexdigest()


def top_n_sections(text: str, n: int) -> str:
    """病灶文件取前 N 節：以「出現最多次的標題層級」當一節（通常是 ##；文件標題 # 留在前言）；不足兩節就整份回。"""
    text = normalize_lf(text)
    heads = list(_HEADING_RE.finditer(text))
    if len(heads) < 2 or n <= 0:
        return text
    by_level: Dict[int, int] = {}
    for m in heads:
        lvl = len(m.group(0).rstrip())
        by_level[lvl] = by_level.get(lvl, 0) + 1
    level = max(by_level, key=lambda k: (by_level[k], -k))
    starts = [m.start() for m in heads if len(m.group(0).rstrip()) == level]
    if len(starts) < 2:
        return text
    preamble = text[:starts[0]]
    cut = starts[n] if n < len(starts) else len(text)
    body = text[starts[0]:cut]
    note = "" if n >= len(starts) else f"\n\n（只取前 {n} 節，共 {len(starts)} 節）\n"
    return preamble + body + note


def tail_lines(text: str, k: int) -> str:
    lines = normalize_lf(text).rstrip("\n").split("\n")
    if k <= 0 or len(lines) <= k:
        return "\n".join(lines) + "\n"
    return "\n".join(lines[-k:]) + "\n"


def check_rel(rel: str) -> str:
    """相對路徑守門：禁絕對路徑、`..`、空段；統一正斜線。"""
    r = (rel or "").strip().replace("\\", "/")
    if not r or _ABS_RE.match(r) or any(seg in ("", "..") for seg in r.split("/")):
        raise PackError(f"材料路徑不合法（只收相對、不得含 ..）：{rel!r}")
    return r


def materials_hash(files: List[Dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for f in sorted(files, key=lambda x: x["rel"]):
        h.update(f"{f['rel']}\n{f['sha256']}\n".encode("utf-8"))
    return h.hexdigest()


def pack_materials(job_dir: Path, items: List[Tuple[str, str]], mode: str, model: str) -> Dict[str, Any]:
    """items=[(rel, text)] → 寫 materials/<rel>（LF）、寫 manifest.json、回 manifest。"""
    job_dir = Path(job_dir)
    mat = job_dir / "materials"
    mat.mkdir(parents=True, exist_ok=True)
    files: List[Dict[str, Any]] = []
    seen = set()
    for rel, text in items:
        r = check_rel(rel)
        if r in seen:
            raise PackError(f"材料重名：{r}")
        seen.add(r)
        body = normalize_lf(text if text is not None else "")
        dst = mat / r
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(body, encoding="utf-8", newline="\n")
        files.append({"rel": r, "sha256": sha256_text(body), "bytes": len(body.encode("utf-8"))})
    files.sort(key=lambda x: x["rel"])
    manifest = {
        "hash": materials_hash(files),
        "files": files,
        "mode": mode,
        "model": model,
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (job_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def manifest_outside_paths(manifest: Dict[str, Any]) -> List[str]:
    """manifest 任何字串值裡出現磁碟絕對路徑就回報（不得含沙箱外路徑）。"""
    bad: List[str] = []

    def walk(v: Any) -> None:
        if isinstance(v, str):
            if re.search(r"[A-Za-z]:[\\/]", v) or v.startswith("//") or v.startswith("\\\\"):
                bad.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(manifest)
    return bad


# ─── 從專案蒐材料 ─────────────────────────────────────────────────────────────


def _read(p: Path) -> str:
    return normalize_lf(p.read_text(encoding="utf-8", errors="replace"))


def _run(cmd: List[str], cwd: str, timeout_s: int) -> str:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout_s, creationflags=_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout if r.returncode == 0 else ""


NEW_FILES_BUDGET = 200_000   # 未追蹤新檔：單檔超過只列檔名；累計不超過它，放不下的只報個數（進提示詞前還會再截 material_max_chars）


def _new_file_patch(root: Path, rel: str) -> str:
    """一個未追蹤新檔 → git 格式的 new file patch 段；二進位、過大、讀不了只留檔頭與原因。"""
    head = f"diff --git a/{rel} b/{rel}\nnew file mode 100644\n--- /dev/null\n+++ b/{rel}\n"
    p = root / rel
    try:
        size = p.stat().st_size
        if size > NEW_FILES_BUDGET:
            return head + f"（未追蹤新檔過大，未附內容：{size} bytes）\n"
        data = p.read_bytes()
    except OSError as e:
        return head + f"（未追蹤新檔讀不了：{type(e).__name__}）\n"
    if b"\0" in data:
        return head + "（二進位新檔，未附內容）\n"
    text = normalize_lf(data.decode("utf-8", errors="replace"))   # 材料一律 LF（CRLF 的檔照 LF 列）
    if not text:
        return head                                                 # 空檔：沒有內容段
    lines = text.split("\n")
    no_eol = lines[-1] != ""
    if not no_eol:
        lines.pop()
    return (head + f"@@ -0,0 +1,{len(lines)} @@\n" + "".join(f"+{ln}\n" for ln in lines)
            + ("\\ No newline at end of file\n" if no_eol else ""))


def _new_files_patch(root: Path, rels: List[str]) -> str:
    """未追蹤新檔逐一接成 patch 段（依路徑排序），累計不超過 NEW_FILES_BUDGET：放不下的那個起只報剩幾個；
    列出來但已不是檔（期間被刪、目錄）的略過。"""
    files = sorted(r for r in rels if (root / r).is_file())
    parts: List[str] = []
    total = 0
    for i, rel in enumerate(files):
        seg = _new_file_patch(root, rel)
        if total + len(seg) > NEW_FILES_BUDGET:
            parts.append(f"（另有 {len(files) - i} 個未追蹤新檔未附：新檔材料累計會超過 {NEW_FILES_BUDGET} 字）\n")
            break
        parts.append(seg)
        total += len(seg)
    return "".join(parts)


def _svn_unversioned(root: Path, status: str) -> Tuple[List[str], List[str]]:
    """`svn status` 的 `?` 行（沒加進版控）→ (檔的相對路徑, 目錄的相對路徑)。目錄不展開：svn 只列目錄本身，
    裡面哪些檔會被 svn:ignore／global-ignores 排除這裡判不了，展開會把被忽略的檔帶進材料。"""
    files: List[str] = []
    dirs: List[str] = []
    for line in status.splitlines():
        if not line.startswith("?") or len(line) < 9:
            continue
        rel = Path(line[8:].strip()).as_posix()
        (dirs if (root / rel).is_dir() else files).append(rel)
    return files, dirs


def collect_diff(cwd: str, timeout_s: int = 20) -> str:
    """工作樹 vs HEAD；空則 main...HEAD；都不是 git 再試 svn diff。回空字串＝沒有差異或無版控。
    git diff／svn diff 都不含沒加進版控的檔：未追蹤新檔（git 的 ls-files --others --exclude-standard、svn 的 `?`）
    接在後面寫成 new file patch 段，新建的檔審查者才看得到。"""
    root = Path(cwd)
    if (root / ".git").exists() or _run(["git", "rev-parse", "--git-dir"], cwd, timeout_s).strip():
        out = _run(["git", "diff", "HEAD"], cwd, timeout_s)
        if not out.strip():
            out = _run(["git", "diff", "main...HEAD"], cwd, timeout_s)
        others = _run(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd, timeout_s)
        return out + _new_files_patch(root, [r for r in others.split("\0") if r])
    if (root / ".svn").exists():
        out = _run(["svn", "diff"], cwd, timeout_s)
        files, dirs = _svn_unversioned(root, _run(["svn", "status"], cwd, timeout_s))
        note = "".join(f"（未加入版控的目錄 {d}/：svn 不列裡面的檔、忽略規則判不了，未附內容）\n" for d in sorted(dirs))
        return out + _new_files_patch(root, files) + note
    return ""


def _hooks_on_path() -> None:
    hooks = str(CODE_DIR / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)


def _mask_one(m: "re.Match[str]") -> str:
    s = m.group(0)
    esc = re.search(r"(?<!\\)\\[nrt]$", s)   # 字串字面值的 \n、\t 跳脫不是路徑的一段（JSON 的 \\n 才是名叫 n 的一段）
    path, tail = (s[:esc.start()], s[esc.start():]) if esc else (s, "")
    core = path.rstrip("\\/")
    last = re.split(r"[\\/]", core)[-1]
    # 尾端的分隔字元照留：JSON 帳本裡 \"C:\\x\" 的那個反斜線是跳脫引號用的，吃掉就不是合法 JSON；只有磁碟代號（C:\）不留代號
    return "…/" + (last if last != core else "") + path[len(core):] + tail


def mask_abs_paths(text: str) -> str:
    """指到沙箱外的絕對路徑（磁碟代號、Git Bash 的 /c/…、UNC）換成「…/<最後一段>」：還看得出指哪個檔，但不把沙箱外路徑送進提示詞。"""
    return _ABS_IN_TEXT_RE.sub(_mask_one, text)


def _one_line(s: Any) -> str:
    return " ".join(str(s or "").split())


def goal_material(session_id: str) -> Tuple[str, Optional[str]]:
    """goal.md 內容＝需求目標樹精簡渲染：第一行「樹根（T<n>）：<樹根全文>」＋ wg_need_goal.review_material（使用者原話、
    同伴轉述、節點與狀態），絕對路徑遮掉。沒帶 session_id、沒有樹、讀不到 → 只有一行「無目標樹」（照樣進 manifest 與 hash），
    第二個回傳值說原因（給 notes，不靜默；開頭固定 wg_release_rules.SO_NO_GOAL_NOTE，Stop 的 SecondOpinion 閘據此在 session
    有樹時不把這次 run 算成跑過）。"""
    _hooks_on_path()
    from wg_release_rules import SO_NO_GOAL_NOTE
    sid = str(session_id or "")
    if not sid:
        return NO_GOAL + "\n", f"{SO_NO_GOAL_NOTE}：沒帶 session_id，找不到這個 session 的樹"
    try:
        import wg_need_goal as ng
        tree = ng.active_tree(ng.load(sid))
        body = ng.review_material(sid) if tree else ""
    except Exception as e:  # noqa: BLE001  目標樹讀不到不擋第二意見，但要說
        return NO_GOAL + "\n", f"{SO_NO_GOAL_NOTE}：讀不到（session_id={sid}）：{type(e).__name__}: {e}"
    if not tree:
        return NO_GOAL + "\n", f"{SO_NO_GOAL_NOTE}：這個 session 沒有樹（session_id={sid}）"
    root = (tree.get("nodes") or {}).get(tree["id"]) or {}
    head = f"樹根（{tree['id']}）：{mask_abs_paths(_one_line(root.get('text')))}"
    return f"{head}\n\n{mask_abs_paths(body)}\n", None


def _norm_q(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(s or "")).split())


def question_root_missing(question: str, items: List[Tuple[str, str]]) -> Optional[str]:
    """材料有目標樹（goal.md 第一行是樹根）而 question 沒含樹根那句（NFKC、空白正規化後子字串比對）→ 回 blocked 原因；
    沒有樹或含了 → None。原因開頭固定 wg_release_rules.SO_QUESTION_ROOT_MISSING：Stop 的 SecondOpinion 閘據此不把這次 blocked
    算成跑過。"""
    m = _GOAL_ROOT_RE.match(dict(items).get(REL_GOAL, ""))
    root = m.group(1).strip() if m else ""
    if not root or _norm_q(root) in _norm_q(question):
        return None
    _hooks_on_path()
    from wg_release_rules import SO_QUESTION_ROOT_MISSING
    return f"{SO_QUESTION_ROOT_MISSING}：「{root}」（整句照抄進 question 再重跑）"


def find_part_row(cwd: str, part: str) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
    """用 lib.overview_hub 找 `<root>/.claude/overview-map.md` 裡該部位的列；沒表或沒命中回 (root|None, None)。"""
    try:
        from lib.overview_hub import find_map, parse_map
    except ImportError:
        return None, None
    found = find_map(cwd)
    if not found:
        return None, None
    root, map_path = found
    want = (part or "").strip().lower()
    for row in parse_map(_read(map_path)):
        names = {str(row.get("part") or "").lower(), str(row.get("part_short") or "").lower()}
        if want and want in names:
            return root, row
    return root, None


def gather_items(request: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[List[Tuple[str, str]], List[str]]:
    """request{cwd, part, mode, session_id?, draft?, materials?{card,defects,diff,ledger,files[]}} → (items, notes)。

    materials 顯式指定的路徑優先（CLI／測試用）；否則從 overview-map 找卡與病灶文件、git/svn 取 diff、
    帳本取 `<CLAUDE_DIR>/workflow/verify-ledger/<session_id>.jsonl`（沒有再找舊位置 `<root>/.claude/verify/_ledger.jsonl`）尾 K；
    需求目標樹照 session_id 找（goal_material，一律放 goal.md）。缺哪樣就在 notes 說，不靜默。
    """
    cwd = str(request.get("cwd") or "")
    part = str(request.get("part") or "")
    mode = str(request.get("mode") or "independent")
    spec = request.get("materials") or {}
    top_n = int(cfg.get("defects_top_n", 5))
    tail_k = int(cfg.get("ledger_tail", 20))
    items: List[Tuple[str, str]] = []
    notes: List[str] = []

    root, row = find_part_row(cwd, part) if cwd else (None, None)
    base = root or (Path(cwd) if cwd else None)

    card_src = spec.get("card")
    if not card_src and row and base is not None:
        try:
            from lib.overview_hub import card_mem_dir, resolve_card
            p = resolve_card(base, row.get("card"), card_mem_dir(base, CLAUDE_DIR))
            card_src = str(p) if p else None
        except ImportError:
            card_src = None
    if card_src and Path(card_src).is_file():
        items.append((REL_CARD, _read(Path(card_src))))
    else:
        notes.append(f"找不到部位卡（part={part!r}）")

    defects_src = spec.get("defects") or (row or {}).get("defects_doc")
    if defects_src and base is not None and not Path(defects_src).is_absolute():
        defects_src = str(base / defects_src)
    if defects_src and Path(defects_src).is_file():
        items.append((REL_DEFECTS, top_n_sections(_read(Path(defects_src)), top_n)))
    else:
        notes.append("沒有病灶文件")

    diff_spec = spec.get("diff")
    if isinstance(diff_spec, dict) and "text" in diff_spec:
        diff_text = normalize_lf(str(diff_spec["text"]))
    elif diff_spec and Path(str(diff_spec)).is_file():
        diff_text = _read(Path(str(diff_spec)))
    else:
        diff_text = collect_diff(cwd, int(cfg.get("vcs_timeout_s", 20))) if cwd else ""
    if diff_text.strip():
        items.append((REL_DIFF, diff_text))
    else:
        notes.append("diff 為空（無改動或無版控）")

    # 帳本來源：materials.ledger 明指（只認它）→ 本 session 的 workflow/verify-ledger/<sid>.jsonl → 舊位置 <根>/.claude/verify/_ledger.jsonl
    sid = str(request.get("session_id") or "")
    if spec.get("ledger"):
        ledger_cands = [str(spec["ledger"])]
    else:
        ledger_cands = [str(CLAUDE_DIR / "workflow" / "verify-ledger" / f"{sid}.jsonl") if sid else "",
                        str(base / ".claude" / "verify" / "_ledger.jsonl") if base else ""]
    ledger_src = next((c for c in ledger_cands if c and Path(c).is_file()), None)
    if ledger_src:
        items.append((REL_LEDGER, tail_lines(_read(Path(ledger_src)), tail_k)))
    else:
        notes.append(f"沒有驗證帳本（session_id={sid or '未給'}）")

    for extra in spec.get("files") or []:
        p = Path(str(extra))
        if p.is_file():
            items.append((f"files/{p.name}", _read(p)))
        else:
            notes.append(f"附加材料不存在：{extra}")

    goal_text, goal_note = goal_material(sid)       # 需求目標樹：沒有也放一行「無目標樹」（進 hash）
    items.append((REL_GOAL, goal_text))
    if goal_note:
        notes.append(goal_note)

    if mode == "review":
        items.append((REL_DRAFT, normalize_lf(str(request.get("draft") or ""))))

    # 提示詞嵌材料全文：每份材料都遮磁碟絕對路徑（帳本一定有本 session 的改檔與指令、卡片的 Depends、diff 裡的字面路徑），
    # 否則 replay-guard pre 擋整份（goal.md 在 goal_material 已遮，再遮一次不變）
    return [(rel, mask_abs_paths(text)) for rel, text in items], notes

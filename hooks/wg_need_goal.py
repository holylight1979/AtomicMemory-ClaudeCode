"""wg_need_goal：需求目標樹（need_goal）的資料層與各關鍵點的判定。

做什麼：每個 session 一個目標檔 workflow/need-goal/<sid>.json，每次修改整段上鎖（取鎖 → 讀 → 改 → 寫暫存檔換名 → 放鎖）。
  五個動作（set／add／update／reconcile／read）的套用與拒收、樹的顯示、新需求開始的提示行（4.1）、改程式前沒樹就擋與
  定位第四行要的樹（4.2）、改檔與收據蓋號、對照義務 (f1) 與交付邊界的完整對照 (f2)、commit 前檢查（4.5）、收尾檢核附樹、
  驗收審查材料、續接單區塊的寫出與匯入、壓縮後重送的目標樹。
  程式只管時機、留存、送回、有沒有做（有沒有寫、掛到存在的節點、引用的東西在不在、先後對不對）；目標內容由 LLM 判斷。
  欄位、狀態轉換、身份與介面的契約：_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/need-goal-契約.md。
怎麼驗：python -X utf8 -m pytest -q hooks/verify/verify_need_goal.py
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import re
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple
from wg_lazy_re import lazy_re  # 模組層樣式第一次用到才編譯（HOOK_IMPORT_ON_USE）

import wg_core
import wg_release_rules as rr
from harness_text import user_typed_text
from wg_verify_ledger import has_cd, is_code_file, reconcile_cfg

# ─── 列舉值（MIRROR: tools/workflow-guardian-mcp/lib/need-goal.js，兩邊同一組）────────────────
ACTIONS = ("set", "add", "update", "reconcile", "read", "verify_scope")
REVIEW_VERDICTS = ("missed", "unrelated")       # verify_scope 的漏判檢討：該驗的沒驗到／與那次改動無關
TREE_STATUS = ("doing", "reconciled", "closed")
NODE_STATUS = ("todo", "doing", "done", "partial", "none", "dropped")
TERMINAL = ("done", "partial", "none", "dropped")
CLARITY = ("clear", "open")
ORIGIN = ("user", "inferred", "grown")
EVIDENCE_KINDS = ("receipt", "case", "file", "atom")
EVIDENCE_LEVELS = ("measured", "read", "inferred")
READ_FORMS = ("full", "compact", "handoff")

LABEL = {
    "tree": {"doing": "進行中", "reconciled": "已對照", "closed": "結束"},
    "status": {"todo": "未開始", "doing": "進行中", "done": "達成", "partial": "部分", "none": "沒有", "dropped": "放棄"},
    "clarity": {"clear": "明確", "open": "待展開"},
    "origin": {"user": "使用者說的", "inferred": "推出來的", "grown": "工作中長出的"},
    "kind": {"code": "寫碼類", "knowledge": "記憶知識類"},
    "level": {"measured": "實測", "read": "讀碼", "inferred": "推論"},
    "ekind": {"receipt": "收據", "case": "驗證案例", "file": "檔案", "atom": "卡片"},
}

ROOT_LABEL = "AI 的解讀"

DEFAULTS: Dict[str, Any] = {"enabled": True, "scope_growth_dirs": 3, "render_chars": 1200}
# 擋下訊息共用的指路句（改檔閘、commit 閘、提問閘）：MCP 是視窗層級共用的 node 程序，改了要 Reload 才載到新工具，
# 叫不到 need_goal 的人照「先用 need_goal」走不下去
NO_TOOL_HINT = "本 session 若叫不到 need_goal 工具（MCP 是舊的），先 Reload Window，或改開一個新的 session 接著做。"

# G11 思考的彎：reconcile 的 turns（這次拐了幾個彎）缺就提醒一句、不擋；≥ TURNS_RETHINK（超過三個）要有「重找最短路：<結果>」才收
# （原話：第二個彎提高注意、第三個警戒極限、第四個幾乎可以確定臭掉；繼續推進只會越跑越偏）。程式只核對有沒有寫，不評結果。
TURNS_RETHINK = 4
_RETHINK_RE = lazy_re(r"重找最短路\s*[：:]\s*\S")
TURNS_HINT = ("這次拐了幾個彎沒填（reconcile 的 turns）：下次附上；第二個彎起提高注意，≥4 要在 note 寫「重找最短路：<結果>」"
              "（只提醒、不擋）")

NODE_ID_RE = lazy_re(r"(?<![A-Za-z0-9_])T\d+(?:\.\d+)*")
NODE_ID_FULL_RE = lazy_re(r"^T\d+(?:\.\d+)*$")
_RECEIPT_REF_RE = lazy_re(r"^[Rr]?(\d+)$")
_LINE_SUFFIX_RE = lazy_re(r":\d+(?:-\d+)?$")
_PEER_RE = lazy_re(r"<\s*cross-session-message\b([^>]*)>(.*?)(?:<\s*/\s*cross-session-message\s*>|\Z)",
                      re.IGNORECASE | re.DOTALL)
_PEER_NAME_RE = lazy_re(r'\bfrom-name\s*=\s*"([^"]*)"')
_PEER_FROM_RE = lazy_re(r'\bfrom\s*=\s*"([^"]*)"')
_BLOCK_RE = lazy_re(r"<!--\s*need-goal:begin[^>]*-->\s*```json\s*(.*?)\s*```\s*<!--\s*need-goal:end\s*-->",
                       re.DOTALL)
HANDOFF_NAME_RE = lazy_re(r"[\\/]_staging[\\/]next-phase[^\\/]*\.md$", re.IGNORECASE)

USER_FIRST_CAP = 4000
USER_CAP = 1000
SAID_MAX = 20
SAID_ALL_MAX = 200           # origin 核對用的原話（said_all）最多幾則；超過丟第二則起最舊的
PEER_CAP = 1000
SAID_LOG_MAX = 5
EDITS_MAX = 300
PART_FILES_MAX = 5           # parts_edited 每個部位最多記幾個改到的檔（擋訊息列給人看，不是清帳依據）
RECEIPTS_MAX = 300
RECEIPTS_SEEN_MAX = 1000
CHECKPOINTS_MAX = 200
LOCK_WAIT_S = 5.0
_RETRY_S = 0.02
_RETRIES = 10
STALE_DAYS = 30

HINT_LINE = ("[NeedGoal] 若這是要動手的需求（改程式、寫或整併文件、整理記憶或設定都算），先用 need_goal(action=set, goal=…, items=[…]) "
             "寫下它真正要達成什麼（一句、用使用者的話、不寫手段；寫整個需求，不只這回合先做的那段），看得出的子目標同一次放 items；"
             "純問答可以不寫。")
# 開新樹收下時附的一句（B5 缺口①：AI 懂了子目標，樹上卻永遠只有樹根）：只送題，有沒有子目標由 AI 判斷
SUBGOAL_LINE = ("樹根寫的是整個需求（使用者這次要的全部，不只這回合先做的那段）；已經看得出的子目標（使用者同一句話裡的其他要求、"
                "要先達成的前提）下次在 set 同一次放 items 一起寫（這次沒帶就用 need_goal(action=add) 補），說不清的 clarity=open；"
                "看不出就不用加。")
# 使用者又說話時樹怎麼長（B5 缺口②：只提換題那條路，AI 被糾正也開新樹、舊樹不收）；每則訊息與糾正提醒共用
TREE_PATHS = ("這則若是補充（多要一件事、新的條件）→ need_goal add 長成子目標；若是糾正 → 改這棵樹（update 改節點、"
              "作廢的標放棄，set 改寫樹根），不開新樹；換成另一件事才 set new_task=true。")
# 批判題的三個具體情況（原設計者補充，來源是判斷入口盤點階段 1 的真實失誤：換成真 git 後舊前置沒真改到檔，「期望不記」的案空轉通過）；
# 定位第五行的提示與「用目標視角重看」的兩問共用；只送題，適不適用由 LLM 判斷
CRITIQUE_CASES = ("遇到這三種情況再多問一句：拿 A 代替 B 判斷（選替身）→ 替身和真正要判的事之間有沒有落差、同類情況會不會被誤判？"
                  "換了測試環境或前提 → 舊的前置步驟在新環境還成立嗎？寫「期望不發生」的案例 → 它通過是因為規則對，"
                  "還是因為什麼都沒發生（先斷言前置狀態成立）？")
# 同一個 session 送過全文之後的那句指回（規則 CRITIQUE_CASES_ONCE_PER_SESSION）
CRITIQUE_CASES_POINTER = "遇到選替身、換前提、寫「期望不發生」的案例這三種情況，照前面那則全文再多問一句。"
# 沒有目標樹時改了記憶知識類的檔（寫入當下，一回合一次）：知識類也要一棵輕樹；不擋寫檔，收尾還沒補由 (f4) 要
KNOWLEDGE_TREE_LINE = ("[NeedGoal] 改了 {name}（記憶知識類），這個 session 還沒有需求目標樹：文件、記憶、設定這類任務也要一棵輕樹——"
                       "用 need_goal(action=set, goal=…) 寫下這次真正要達成什麼（一句、用使用者的話、只寫目標不寫手段；一個節點就夠，"
                       "不要求定位行），沒樹時改的檔會自動掛進樹；做完用 need_goal(action=reconcile) 對照（例如該保留的內容都還在嗎）。"
                       "這一步不擋寫檔；收尾時還沒寫樹或沒對照會被要求補交（記憶知識類，不問使用者）。")
UNTREED_MAX = 200            # 沒樹時改的記憶知識類檔最多記幾個（同一檔只記一筆；超過丟最舊的並記 untreed_dropped）


class NeedGoalLockTimeout(RuntimeError):
    """目標檔的鎖在等待上限內拿不到：不降級成無鎖寫（會掉節點），由呼叫端擋或回報。"""


class NeedGoalCorrupt(ValueError):
    """目標檔不是合法 JSON。"""


# ─── 檔與鎖 ─────────────────────────────────────────────────────────────

def _base_sid(sid: Any) -> str:
    return str(sid or "").split("#agent:", 1)[0]


def _safe_name(sid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", sid) or "_no-sid"


_DEFAULT_WORKFLOW_DIR = Path(wg_core.WORKFLOW_DIR)


def goal_dir() -> Path:
    """目標檔目錄＝資料根的 workflow/need-goal。pytest 裡（PYTEST_CURRENT_TEST）而資料根沒被測試導走時，改寫到系統暫存目錄
    （同 wg_core.logs_dir）：跑真 hook 入口的既有測試不會把假 session 的目標檔寫進資料根。"""
    wf = Path(wg_core.WORKFLOW_DIR)
    if os.environ.get("PYTEST_CURRENT_TEST") and wf == _DEFAULT_WORKFLOW_DIR:
        import tempfile
        return Path(tempfile.gettempdir()) / "wg-test-need-goal"
    return wf / "need-goal"


def goal_path(sid: Any) -> Path:
    return goal_dir() / f"{_safe_name(_base_sid(sid))}.json"


def _skeleton(sid: Any) -> Dict[str, Any]:
    return {"version": 1, "session_id": _base_sid(sid), "seq": 0, "next_tree": 1, "active": None, "cwd": "",
            "user_msgs": 0, "said_log": [], "hint_sent": {"first": False, "after": []}, "trees": {},
            "receipts": [], "imports": []}


def load(sid: Any) -> Dict[str, Any]:
    """不取鎖讀（換檔是原子的）；不存在回空骨架、不建檔；不是合法 JSON 丟 NeedGoalCorrupt。"""
    p = goal_path(sid)
    if not p.exists():
        return _skeleton(sid)
    text = None
    for i in range(_RETRIES):
        try:
            text = p.read_text(encoding="utf-8")
            break
        except FileNotFoundError:
            return _skeleton(sid)
        except PermissionError:
            if i == _RETRIES - 1:
                raise
            time.sleep(_RETRY_S)
    try:
        doc = json.loads(text or "")
    except json.JSONDecodeError as e:
        raise NeedGoalCorrupt(f"{p}: {e}") from e
    if not isinstance(doc, dict):
        raise NeedGoalCorrupt(f"{p}: 頂層不是物件")
    for k, v in _skeleton(sid).items():
        doc.setdefault(k, v)
    return doc


@contextmanager
def _locked(lock_path: Path) -> Iterator[None]:
    deadline = time.monotonic() + LOCK_WAIT_S
    if sys.platform == "win32":
        import msvcrt
        while True:
            fh = open(lock_path, "ab")
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                fh.close()
                if time.monotonic() >= deadline:
                    raise NeedGoalLockTimeout(f"{lock_path.name}：{LOCK_WAIT_S:.0f} 秒內拿不到目標檔的鎖")
                time.sleep(_RETRY_S)
        try:
            yield
        finally:
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            fh.close()
        return
    import fcntl
    fh = open(lock_path, "ab")
    try:
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise NeedGoalLockTimeout(f"{lock_path.name}：{LOCK_WAIT_S:.0f} 秒內拿不到目標檔的鎖")
                time.sleep(_RETRY_S)
        yield
    finally:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        fh.close()


def _write(p: Path, doc: Dict[str, Any]) -> None:
    tmp = p.with_name(f"{p.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        for i in range(_RETRIES):
            try:
                os.replace(tmp, p)
                return
            except PermissionError:
                if i == _RETRIES - 1:
                    raise
                time.sleep(_RETRY_S)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def _prune_stale(d: Path, keep: Path) -> None:
    """刪超過 STALE_DAYS 沒改的目標檔與殘留暫存檔。鎖檔不刪：使用中的鎖檔不會更新時間，刪掉後別的行程重建一個新檔，
    兩邊各鎖各的（非 Windows 的檔案鎖綁在檔案實體上），整段上鎖就失效；空鎖檔留著無害。"""
    cutoff = time.time() - STALE_DAYS * 86400
    for f in list(d.glob("*.json")) + list(d.glob("*.tmp")):
        if f == keep or ".corrupt-" in f.name:
            continue
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            continue


def update_locked(sid: Any, fn: Callable[[Dict[str, Any]], Any]) -> Any:
    """整段上鎖套用 fn(doc)（就地改）；doc 有變才寫回。壞檔改名留證、從空骨架重來（doc 帶 corrupt_backup）。"""
    d = goal_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = goal_path(sid)
    with _locked(p.with_suffix(".lock")):
        fresh = not p.exists()
        try:
            doc = load(sid)
        except NeedGoalCorrupt as e:
            backup = p.with_name(f"{p.stem}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}.json")
            os.replace(p, backup)
            print(f"[NeedGoal] 目標檔損毀，已改名留證：{backup.name}（{e}）", file=sys.stderr)
            _guard("corrupt", sid, backup=str(backup))
            doc = _skeleton(sid)
            doc["corrupt_backup"] = str(backup)
            fresh = True
        before = json.dumps(doc, ensure_ascii=False, sort_keys=True)
        result = fn(doc)
        if json.dumps(doc, ensure_ascii=False, sort_keys=True) != before:
            _write(p, doc)
            if fresh:
                _prune_stale(d, p)
    return result


def next_seq(doc: Dict[str, Any]) -> int:
    doc["seq"] = int(doc.get("seq", 0) or 0) + 1
    return doc["seq"]


def active_tree(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tid = doc.get("active")
    return (doc.get("trees") or {}).get(tid) if tid else None


def tree_of(doc: Dict[str, Any], node_id: Any) -> Optional[Dict[str, Any]]:
    """節點編號所屬的樹（T2.1.3 → T2），不限目前的樹；換題後舊樹欠的對照照樣交得進去。"""
    nid = str(node_id or "")
    return (doc.get("trees") or {}).get(nid.split(".", 1)[0]) if NODE_ID_FULL_RE.match(nid) else None


def _guard(event: str, sid: Any, **kw: Any) -> None:
    try:
        wg_core.append_guard_log("need_goal", {"event": event, "session_id": _base_sid(sid), **kw})
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] 守門紀錄寫不進去：{type(e).__name__}: {e}", file=sys.stderr)


def cfg_of(config: Optional[Dict[str, Any]], root: Optional[Path] = None) -> Dict[str, Any]:
    """OverviewHub 四層合併後的 need_goal 段（根層預設 < config.json overview_hub < 公司層 < 專案層）。合併失敗用預設並浮一行。"""
    out = dict(DEFAULTS)
    try:
        from wg_overview import _cfg as _hub_cfg
        sec = _hub_cfg(config or {}, root).get("need_goal")
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] 讀 need_goal 設定失敗，用預設：{type(e).__name__}: {e}", file=sys.stderr)
        sec = None
    if isinstance(sec, dict):
        out.update({k: sec[k] for k in DEFAULTS if k in sec})
    return out


def _root_of(path: str) -> Optional[Path]:
    try:
        from wg_overview import _project_root_of
        return _project_root_of(path)
    except Exception:  # noqa: BLE001
        return None


def cfg_for_cwd(config: Optional[Dict[str, Any]], cwd: str) -> Dict[str, Any]:
    """cwd 所在專案的 need_goal 設定（專案層覆蓋檔也算）；cwd 空用根層。"""
    return cfg_of(config, _root_of(cwd) if cwd else None)


def slim_reminders(config: Optional[Dict[str, Any]] = None) -> bool:
    """設定 v6.slim_reminders（沒寫＝開）：開＝批判題每個 session 送一次全文、之後一句指回（CRITIQUE_CASES_ONCE_PER_SESSION），
    hook 提示附樹只一行當前節點（TREE_LINE_IN_HINTS）；寫 false 退回每則提示照附批判題全文與樹根一行。
    config＝整份設定，沒給就讀 wg_core.load_config()。只認 JSON 的 false 關。"""
    sec = (wg_core.load_config() if config is None else config).get("v6")
    return not (isinstance(sec, dict) and sec.get("slim_reminders") is False)


def goal_gate_on(config: Optional[Dict[str, Any]]) -> bool:
    """規則 CLOSING_RITUAL_SWITCHES：reconcile_gate.goal_gate=true 才在收尾與 commit 前擋目標對照；沒設或 false＝不擋
    （目標樹照記，交付邊界由程式代填對照）。"""
    return ((config or {}).get("reconcile_gate") or {}).get("goal_gate", False) is True


def hook_cwd(input_data: Optional[Dict[str, Any]], state: Optional[Dict[str, Any]] = None) -> str:
    """hook 入口這次事件的 cwd：hook 輸入的 cwd，沒有就 state 記的 session cwd；都沒有回空（cfg_for_cwd 就用根層）。
    入口取 need_goal 設定一律 cfg_for_cwd(config, hook_cwd(…))，專案層的開關才算數。"""
    return str((input_data or {}).get("cwd") or ((state or {}).get("session") or {}).get("cwd") or "")


# ─── 樹的小工具 ──────────────────────────────────────────────────────────

def _depth(nid: str) -> int:
    return nid.count(".")


def _sort_key(nid: str) -> Tuple[int, ...]:
    return tuple(int(x) for x in nid[1:].split("."))


def _ordered(tree: Dict[str, Any]) -> List[str]:
    return sorted(tree.get("nodes") or {}, key=_sort_key)


def _under(nid: str, anc: str) -> bool:
    """nid 是 anc 本身或在它底下。"""
    return bool(anc) and (nid == anc or nid.startswith(anc + "."))


def _child_id(tree: Dict[str, Any], parent: str) -> str:
    ks = [int(n[len(parent) + 1:]) for n, v in tree["nodes"].items()
          if v.get("parent") == parent and n[len(parent) + 1:].isdigit()]
    return f"{parent}.{max(ks, default=0) + 1}"


def _owed(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [e for e in tree.get("edits") or [] if e.get("owed")]


def add_checkpoint(doc: Dict[str, Any], tree: Dict[str, Any], turn: int, point: str, node: Optional[str]) -> None:
    """關鍵點紀錄 {seq, turn, point, node}（只在 update_locked 的 fn 裡用），最多 CHECKPOINTS_MAX 筆、滿了丟最舊的。"""
    cps = tree.setdefault("checkpoints", [])
    cps.append({"seq": next_seq(doc), "turn": turn, "point": point, "node": node})
    del cps[:-CHECKPOINTS_MAX]


def _add_said(tree: Dict[str, Any], entry: Dict[str, Any]) -> None:
    said = tree.setdefault("user_said", [])
    cap = USER_FIRST_CAP if not said else USER_CAP
    said.append({**entry, "text": str(entry.get("text", ""))[:cap]})
    if len(said) > SAID_MAX:
        del said[1:len(said) - SAID_MAX + 1]
    # 核對 origin=user 用的原話另存一份（顯示用的 user_said 會丟中間、截長，早期或很長的原話就引不到）；不進續接單
    full = tree.setdefault("said_all", [])
    full.append({**entry, "text": str(entry.get("text", ""))[:USER_FIRST_CAP]})
    if len(full) > SAID_ALL_MAX:
        del full[1:len(full) - SAID_ALL_MAX + 1]


def _said_for_check(tree: Dict[str, Any], doc: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """origin 核對的原話來源：本 session 完整的 said_all，加上 user_said（匯入的前一個 session 原話、沒有 said_all 的舊樹），
    再加上還沒掛上任何樹的本 session 原話（規則 ORIGIN_SAID_INCLUDES_UNATTACHED：樹結束時收的，要等重開才掛回去）。"""
    pending = [s for s in (doc or {}).get("said_log") or [] if isinstance(s, dict) and not s.get("attached")]
    return [*(tree.get("said_all") or []), *(tree.get("user_said") or []), *pending]


def _new_tree(doc: Dict[str, Any], goal: str, turn: int, why: str) -> Dict[str, Any]:
    tid = f"T{int(doc.get('next_tree', 1) or 1)}"
    doc["next_tree"] = int(doc.get("next_tree", 1) or 1) + 1
    seq = next_seq(doc)
    tree = {
        "id": tid, "status": "doing", "kind": "knowledge", "goal_rev": 1, "created_turn": turn, "created_seq": seq,
        "user_said": [], "peer_said": [], "links": {"parts": {}}, "edits": [], "node_last_edit": {}, "last_reconcile": None,
        "goal_changed": {"seq": seq, "turn": turn}, "imported_from": None, "checkpoints": [],
        "nodes": {tid: {"parent": None, "text": goal, "origin": "user", "clarity": "clear", "status": "doing",
                        "history": [{"seq": seq, "turn": turn, "what": "create", "why": why}],
                        "evidence": [], "followup": "", "note": ""}},
    }
    _attach_said(doc, tree, turn)
    _adopt_untreed(doc, tree)
    doc["trees"][tid] = tree
    doc["active"] = tid
    return tree


def _attach_said(doc: Dict[str, Any], tree: Dict[str, Any], turn: Optional[int] = None) -> None:
    """還沒進任何樹的使用者原話（沒樹時、或目前的樹已結束時收的），搬進剛開的、剛從續接單接上的、或剛重新打開的樹；
    給 turn 時這一回合的原話也搬（開樹與匯入那一則常是原始需求或開工句）。樹上已有同一則（本 session 的同 seq）不重複；
    匯入的原話（prior）的 seq 是前一個 session 的編號，不拿來比。"""
    have = {s.get("seq") for s in tree.get("user_said") or [] if not s.get("prior")}
    for s in doc.get("said_log") or []:
        if s.get("seq") in have:
            continue
        if not s.get("attached") or (turn is not None and int(s.get("turn", -1)) == int(turn)):
            _add_said(tree, {k: s[k] for k in ("seq", "turn", "text") if k in s})
            s["attached"] = True


def _reopen(doc: Dict[str, Any], tree: Dict[str, Any]) -> None:
    """已對照或結束的樹回到進行中：結束期間收的使用者原話（例如對它的糾正）沒進任何樹，跟著掛回來。"""
    if tree.get("status") in ("reconciled", "closed"):
        tree["status"] = "doing"
        _attach_said(doc, tree)


def _adopt_untreed(doc: Dict[str, Any], tree: Dict[str, Any]) -> None:
    """沒樹時改的記憶知識類檔（doc["untreed"]）掛進剛建立的樹的樹根：改檔照樣記進樹，收尾對照看得到；掛完清掉。"""
    for e in doc.pop("untreed", None) or []:
        tree["edits"].append({"seq": e.get("seq"), "turn": e.get("turn"), "path": e.get("path"), "node": tree["id"],
                              "agent_id": "", "code": False, "owed": False})


def _goal_changed(doc: Dict[str, Any], tree: Dict[str, Any], turn: int) -> None:
    """目標本身改了（改寫樹根、改節點文字）：目標版本 +1，已交的定位要重交。加子節點不算（只開回樹，新節點自己欠結論）。"""
    tree["goal_rev"] = int(tree.get("goal_rev", 1)) + 1
    tree["goal_changed"] = {"seq": next_seq(doc), "turn": turn}
    _reopen(doc, tree)


# ─── 顯示 ────────────────────────────────────────────────────────────────

def _clip(s: Any, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n] + "…"


def _counts(tree: Dict[str, Any]) -> Tuple[int, int, int]:
    nodes = tree.get("nodes") or {}
    sub = sum(1 for n, v in nodes.items() if n != tree["id"] and v.get("status") != "dropped")
    opened = sum(1 for v in nodes.values() if v.get("clarity") == "open" and v.get("status") != "dropped")
    return sub, opened, len(_owed(tree))


def _header(tree: Dict[str, Any]) -> str:
    sub, opened, owed = _counts(tree)
    root = (tree.get("nodes") or {}).get(tree["id"]) or {}
    return (f"{tree['id']}：{_clip(root.get('text'), 80)}（{LABEL['tree'].get(tree.get('status'), '?')}｜"
            f"{LABEL['kind'].get(tree.get('kind'), '?')}｜子目標 {sub}、待展開 {opened}、待對照的改動 {owed}）")


def _evidence_text(ev: Dict[str, Any], doc: Optional[Dict[str, Any]] = None) -> str:
    ref = str(ev.get("ref", ""))
    extra = ""
    if ev.get("kind") == "receipt" and doc is not None and not ev.get("prior"):   # 匯入的收據號是前一個 session 的，對本 session 帳本會對到別條
        r = _receipt_by_ref(doc, ref)
        if r:
            extra = f" `{_clip(r.get('cmd'), 60)}`"
    prior = "（前一個 session）" if ev.get("prior") else ""
    rtg = "（先紅後綠）" if ev.get("red_then_green") else ""
    return f"{LABEL['level'].get(ev.get('level'), '?')} {LABEL['ekind'].get(ev.get('kind'), '?')} {ref}{extra}{rtg}{prior}"


def _node_line(nid: str, node: Dict[str, Any], full: bool, doc: Optional[Dict[str, Any]] = None) -> str:
    st = LABEL["status"].get(node.get("status"), "?")
    if full:
        # 樹根依契約是 AI 對原話的解讀，origin 欄位不動、顯示一律「AI 的解讀」（規則 ORIGIN_USER_NEEDS_QUOTE 樹根版）
        origin = ROOT_LABEL if node.get("parent") is None else LABEL["origin"].get(node.get("origin"), "?")
        tag = f"{st}｜{LABEL['clarity'].get(node.get('clarity'), '?')}｜{origin}"
    else:
        tag = st + ("｜待展開" if node.get("clarity") == "open" else "")
    line = f"{'  ' * _depth(nid)}- {nid} [{tag}] {_clip(node.get('text'), 160 if full else 90)}"
    if not full:
        return line
    hist = [h for h in node.get("history") or [] if h.get("why")]
    if hist:
        line += f"；最近一次為什麼：{_clip(hist[-1]['why'], 120)}"
    if node.get("evidence"):
        line += "；證據：" + "、".join(_evidence_text(e, doc) for e in node["evidence"][:4])
    if node.get("followup"):
        line += f"；未完：{_clip(node['followup'], 120)}"
    if node.get("same_class"):
        line += f"；同類別處：{_clip(node['same_class'], 120)}"
    if node.get("note"):
        line += f"；附註：{_clip(node['note'], 120)}"
    return line


def _group_owed(owed: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    for e in owed:
        name = f"{Path(str(e.get('path', ''))).name}（第 {e.get('turn', '?')} 回合）"
        lst = grouped.setdefault(str(e.get("node")), [])
        if name not in lst:
            lst.append(name)
    return grouped


def _activity(tree: Dict[str, Any], nid: str) -> int:
    node = (tree.get("nodes") or {}).get(nid) or {}
    seqs = [int(h.get("seq") or 0) for h in node.get("history") or [] if isinstance(h, dict)]
    seqs.append(int(((tree.get("node_last_edit") or {}).get(nid) or {}).get("seq") or 0))
    return max(seqs)


def current_node(tree: Optional[Dict[str, Any]], part_key: Optional[str] = None) -> Optional[str]:
    """提示裡那一行「當前節點」：給了部位鍵、而且那個部位的定位掛在活著的節點 → 那個節點（這一塊服務的目標）；
    否則還沒到終點的子節點裡最近有動靜的（節點歷史或改檔掛上的序號最大）；都到終點了就取沒放棄的子節點裡最近的；沒有子節點回 None。"""
    if not tree:
        return None
    nodes = tree.get("nodes") or {}
    link = ((tree.get("links") or {}).get("parts") or {}).get(part_key or "") or {}
    if (nodes.get(link.get("node") or "") or {}).get("status") not in (None, "dropped"):
        return link["node"]
    subs = [n for n, v in nodes.items() if n != tree["id"] and v.get("status") != "dropped"]
    pool = [n for n in subs if nodes[n].get("status") in ("todo", "doing")] or subs
    return max(pool, key=lambda n: (_activity(tree, n), _sort_key(n))) if pool else None


BRIEF_ROOT_CHARS = 60
BRIEF_NODE_CHARS = 60


def _node_brief(tree: Dict[str, Any], nid: str) -> str:
    node = (tree.get("nodes") or {}).get(nid) or {}
    tag = LABEL["status"].get(node.get("status"), "?") + ("｜待展開" if node.get("clarity") == "open" else "")
    return f"當前節點 {nid} [{tag}]：{_clip(node.get('text'), BRIEF_NODE_CHARS)}"


def brief(tree: Optional[Dict[str, Any]], part_key: Optional[str] = None) -> str:
    """樹根一行＋當前節點一行（規則 TREE_ONCE_PER_CALL）：壓縮後重送、舊送法的 hook 提示用；整棵樹只在 need_goal 寫入的回覆送，
    要看用 read（不在每則提示都寫這句：寫了就誘發多叫 read）。"""
    if not tree:
        return ""
    sub, opened, owed = _counts(tree)
    root = (tree.get("nodes") or {}).get(tree["id"]) or {}
    out = [f"{tree['id']}：{_clip(root.get('text'), BRIEF_ROOT_CHARS)}（{LABEL['tree'].get(tree.get('status'), '?')}｜"
           f"子目標 {sub}、待展開 {opened}、待對照 {owed}）"]
    nid = current_node(tree, part_key)
    if nid:
        out.append(_node_brief(tree, nid))
    return "\n".join(out)


def brief_line(tree: Optional[Dict[str, Any]], part_key: Optional[str] = None) -> str:
    """規則 TREE_LINE_IN_HINTS：hook 提示附的一行——當前節點（沒有子節點就是樹根自己）。樹根與整棵樹在 need_goal
    set／add／update／reconcile 的回覆送過了，提示不再重附。"""
    return _node_brief(tree, current_node(tree, part_key) or tree["id"]) if tree else ""


def brief_for(tree: Optional[Dict[str, Any]], part_key: Optional[str] = None,
              config: Optional[Dict[str, Any]] = None) -> str:
    """hook 提示附的目標樹：新送法 brief_line、舊送法 brief（開關 slim_reminders）。"""
    return brief_line(tree, part_key) if slim_reminders(config) else brief(tree, part_key)


def _brief_sig(tree: Dict[str, Any], part_key: Optional[str] = None) -> str:
    """brief 的內容指紋：樹與它的狀態、樹根文字、當前節點與它的文字、狀態、清楚度（不含計數：改一次檔待對照就變，不算內容變了）。"""
    nodes = tree.get("nodes") or {}
    nid = current_node(tree, part_key)
    node = nodes.get(nid or "") or {}
    raw = "\n".join([str(tree.get("id")), str(tree.get("status")), str((nodes.get(tree["id"]) or {}).get("text")), str(nid),
                     str(node.get("text")), str(node.get("status")), str(node.get("clarity"))])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def brief_mark(doc: Dict[str, Any], tree: Optional[Dict[str, Any]], turn: int, part_key: Optional[str] = None) -> str:
    """附樹去重（呼叫端已持有目標檔的鎖）：同一個使用者回合已經附過同一份 brief（導讀卡、讀入範圍提示）就回空字串，
    內容變了或換回合才回 brief_for 並記下。只給純附帶的地方用；每則訊息（不一定送出，不拿來記）、目標視角重看、糾正、
    壓縮重送、交付對照照附。"""
    if not tree:
        return ""
    sig = _brief_sig(tree, part_key)
    last = doc.get("brief_sent") or {}
    if last.get("turn") == int(turn) and last.get("sig") == sig:
        return ""
    doc["brief_sent"] = {"turn": int(turn), "sig": sig}
    return brief_for(tree, part_key)


def brief_once(sid: Any, turn: int, part_key: Optional[str] = None) -> str:
    """brief_mark 的上鎖版（導讀卡用）。鎖拿不到或目標檔壞了照附 brief_for、stderr 一行（寧可多附不靜默少附）。"""
    try:
        return update_locked(sid, lambda d: brief_mark(d, active_tree(d), turn, part_key))
    except (NeedGoalLockTimeout, NeedGoalCorrupt, OSError) as e:
        print(f"[NeedGoal] 附樹去重失敗（照附）：{type(e).__name__}: {e}", file=sys.stderr)
        try:
            return brief_for(active_tree(load(sid)), part_key)
        except (NeedGoalCorrupt, OSError):
            return ""


def critique_mark(doc: Dict[str, Any]) -> bool:
    """規則 CRITIQUE_CASES_ONCE_PER_SESSION（呼叫端已持有目標檔的鎖）：這次送不送 CRITIQUE_CASES 全文。這個 session 還沒送過
    （目標檔沒有 critique_sent）→ 記下、回 True；送過 → False，呼叫端改送 CRITIQUE_CASES_POINTER。舊送法一律 True、不記。
    子代理用主 session 的目標檔，誰先收到全文就算送過（同導讀卡「第一次讀到的那邊收」）。"""
    if not slim_reminders():
        return True
    if doc.get("critique_sent"):
        return False
    doc["critique_sent"] = True
    return True


def critique_once(sid: Any) -> bool:
    """critique_mark 的上鎖版。還沒有目標檔（沒寫過樹）→ True、不為這筆建檔；先不上鎖讀一次：已送過就回 False、不取鎖，
    目標檔壞了 → True、不碰檔（壞檔改名留證留給 need_goal 寫入，提醒不觸發）；鎖拿不到 → True。失敗都 stderr 一行
    （寧可多送一次全文不靜默少送）。"""
    if not goal_path(sid).exists():
        return True
    try:
        if load(sid).get("critique_sent") and slim_reminders():
            return False
        return bool(update_locked(sid, critique_mark))
    except (NeedGoalLockTimeout, NeedGoalCorrupt, OSError) as e:
        print(f"[NeedGoal] 批判題已送紀錄讀寫失敗（照送全文）：{type(e).__name__}: {e}", file=sys.stderr)
        return True


def critique_cases(full: bool) -> str:
    return CRITIQUE_CASES if full else CRITIQUE_CASES_POINTER


def forget_reminders(sid: Any) -> None:
    """壓縮後 context 裡沒有批判題全文了：清掉 critique_sent，下次照送全文（規則 CRITIQUE_CASES_ONCE_PER_SESSION）。
    沒有目標檔不建；沒記過就不取鎖；目標檔壞了不碰（不觸發改名留證）；讀寫失敗 stderr 一行（壓縮後可能只收到指回句）。"""
    if not goal_path(sid).exists():
        return
    try:
        if "critique_sent" not in load(sid):
            return
        update_locked(sid, lambda d: d.pop("critique_sent", None))
    except (NeedGoalLockTimeout, NeedGoalCorrupt, OSError) as e:
        print(f"[NeedGoal] 清不掉批判題已送紀錄（壓縮後可能只送指回句）：{type(e).__name__}: {e}", file=sys.stderr)


def render(tree: Optional[Dict[str, Any]], form: str, chars: Optional[int] = None,
           doc: Optional[Dict[str, Any]] = None) -> str:
    """header（一行）／compact（一行一節點；給 chars 才截，截掉的節點數照實寫）／full（原話、轉述、節點證據、待對照、完整對照、最近收據）。"""
    if not tree:
        return ""
    if form == "header":
        return _header(tree)
    nodes = tree.get("nodes") or {}
    if form == "compact":
        out = [_header(tree)]
        used = len(out[0])
        order = _ordered(tree)
        for i, nid in enumerate(order):
            ln = _node_line(nid, nodes[nid], False)
            if chars is not None and used + len(ln) + 1 > int(chars):
                out.append(f"…（其餘 {len(order) - i} 個節點略）")
                break
            out.append(ln)
            used += len(ln) + 1
        return "\n".join(out)
    out = [f"目標樹 {_header(tree)}（目標版本 {tree.get('goal_rev', 1)}）"]
    said = tree.get("user_said") or []
    if said:
        out.append("使用者原話（權威）：")
        for s in said[:1] + said[1:][-3:]:
            prior = "（前一個 session）" if s.get("prior") else ""
            out.append(f"  - 第 {s.get('turn', '?')} 回合{prior}：「{_clip(s.get('text'), 300)}」")
    peers = tree.get("peer_said") or []
    if peers:
        out.append("同伴轉述（不是使用者說的，不當權威）：")
        for s in peers[-3:]:
            out.append(f"  - {s.get('from') or '?'}（第 {s.get('turn', '?')} 回合）：「{_clip(s.get('text'), 200)}」")
    out.append("節點：")
    for nid in _ordered(tree):
        out.append("  " + _node_line(nid, nodes[nid], True, doc))
    owed = _owed(tree)
    if owed:
        out.append("待對照的改動（收尾時程式照改動與收據自動記進度；要寫自己的判斷用 update）：")
        for node, items in _group_owed(owed).items():
            out.append(f"  - {node} ← {'、'.join(items)}")
    lr = tree.get("last_reconcile")
    if lr:
        stale = "" if lr.get("goal_rev") == tree.get("goal_rev") else \
            f"（之後目標改過，現在版本 {tree.get('goal_rev')}，這次對照作廢）"
        who = "程式代填" if lr.get("by") == "program" else "交過"
        out.append(f"完整對照：第 {lr.get('turn', '?')} 回合{who}，目標版本 {lr.get('goal_rev')}{stale}")
    if doc is not None and doc.get("receipts"):
        out.append("最近收據（證據引用寫 R<號>，或寫 latest 由程式填最近一筆綠的）：")
        for r in doc["receipts"][-8:]:
            out.append(f"  - R{r['seq']} 第 {r.get('turn', '?')} 回合 `{_clip(r.get('cmd'), 80)}` "
                       f"{' '.join(r.get('verdicts') or []) or '無哨兵'} exit {r.get('exit')}")
    return "\n".join(out)


def node_ref(tree: Optional[Dict[str, Any]], text: Any) -> Optional[str]:
    """文字裡第一個是這棵樹節點、狀態不是放棄的 T 編號。"""
    if not tree:
        return None
    nodes = tree.get("nodes") or {}
    for m in NODE_ID_RE.finditer(str(text or "")):
        node = nodes.get(m.group(0))
        if node and node.get("status") != "dropped":
            return m.group(0)
    return None


# ─── 參數驗證（MIRROR: need-goal.js validateArgs）───────────────────────────

def _s(v: Any) -> str:
    return v.strip() if isinstance(v, str) else ""


def _validate_items(action: str, items: List[Any]) -> List[str]:
    errs: List[str] = []
    for i, it in enumerate(items):
        tag = f"items[{i}]"
        if not isinstance(it, dict):
            errs.append(f"{tag} 必須是物件")
            continue
        if action == "add":
            if not _s(it.get("text")):
                errs.append(f"{tag}.text 必填")
            if it.get("clarity") is not None and it.get("clarity") not in CLARITY:
                errs.append(f"{tag}.clarity 無效（{it.get('clarity')}），允許：{'|'.join(CLARITY)}")
            if it.get("origin") is not None and it.get("origin") not in ORIGIN:
                errs.append(f"{tag}.origin 無效（{it.get('origin')}），允許：{'|'.join(ORIGIN)}")
            if it.get("quote") is not None and not isinstance(it.get("quote"), str):
                errs.append(f"{tag}.quote 必須是字串（標 origin=user 時引用使用者原話的字面子句）")
            continue
        if not NODE_ID_FULL_RE.match(_s(it.get("id"))):
            errs.append(f"{tag}.id 必填，格式 T<數字>(.<數字>)*")
        if action == "update":     # why 選填（WHY_OPTIONAL）：有寫就進 history，沒寫不擋
            if not any(it.get(k) is not None for k in ("text", "status", "clarity", "origin")):
                errs.append(f"{tag} 至少要改 text／status／clarity／origin 其中一項")
            if it.get("origin") is not None and it.get("origin") not in ORIGIN:
                errs.append(f"{tag}.origin 無效（{it.get('origin')}），允許：{'|'.join(ORIGIN)}")
            if it.get("quote") is not None and not isinstance(it.get("quote"), str):
                errs.append(f"{tag}.quote 必須是字串（標 origin=user 時引用使用者原話的字面子句）")
            if it.get("text") is not None and not _s(it.get("text")):
                errs.append(f"{tag}.text 不能是空的")
            if it.get("status") is not None and it.get("status") not in NODE_STATUS:
                errs.append(f"{tag}.status 無效（{it.get('status')}），允許：{'|'.join(NODE_STATUS)}")
            if it.get("clarity") is not None and it.get("clarity") not in CLARITY:
                errs.append(f"{tag}.clarity 無效（{it.get('clarity')}），允許：{'|'.join(CLARITY)}")
            continue
        if it.get("status") not in TERMINAL:
            errs.append(f"{tag}.status 必填且只收終點值：{'|'.join(TERMINAL)}")
        if it.get("same_class") is not None and not isinstance(it.get("same_class"), str):
            errs.append(f"{tag}.same_class 必須是字串（同類別處：找到的位置，或為什麼沒有）")
        ev = it.get("evidence")
        if ev is not None and not isinstance(ev, list):
            errs.append(f"{tag}.evidence 必須是陣列")
            continue
        for j, e in enumerate(ev or []):
            etag = f"{tag}.evidence[{j}]"
            if not isinstance(e, dict):
                errs.append(f"{etag} 必須是物件")
                continue
            if e.get("kind") not in EVIDENCE_KINDS:
                errs.append(f"{etag}.kind 無效（{e.get('kind')}），允許：{'|'.join(EVIDENCE_KINDS)}")
            if e.get("level") not in EVIDENCE_LEVELS:
                errs.append(f"{etag}.level 無效（{e.get('level')}），允許：{'|'.join(EVIDENCE_LEVELS)}")
            if not _s(e.get("ref")):
                errs.append(f"{etag}.ref 必填")
            cov = e.get("covers")
            if cov is not None and (not isinstance(cov, list) or not all(NODE_ID_FULL_RE.match(_s(c)) for c in cov)):
                errs.append(f"{etag}.covers 必須是節點編號陣列")
            if e.get("unaffected") is not None and not isinstance(e.get("unaffected"), str):
                errs.append(f"{etag}.unaffected 必須是字串（為什麼第二意見之後改的檔不影響這筆收據）")
    return errs


def _validate_verify_scope(inp: Dict[str, Any]) -> List[str]:
    """verify_scope 的形狀：items 每項 {target, why} 都非空、case_for（選填）是非空字串陣列；reviews（選填）每筆
    {leak, verdict∈missed|unrelated}；no_case（選填）每筆 {path, reason} 都非空。
    內容（檔在不在、是不是案例檔、待檢討的漏判有沒有逐筆檢討、該寫的根因有沒有寫）由 wg_verify_scope 收件時照規則判。"""
    items = inp.get("items")
    if not isinstance(items, list) or not items:
        return ["verify_scope 要給 items（非空陣列，每項 {target, why}）"]
    errs: List[str] = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            errs.append(f"items[{i}] 必須是物件")
            continue
        if not _s(it.get("target")):
            errs.append(f"items[{i}].target 必填（測試檔、測試節點、資料夾或指令）")
        if not _s(it.get("why")):
            errs.append(f"items[{i}].why 必填（為什麼和這次改動有關、會受什麼影響）")
        ins = it.get("inputs")
        if ins is not None and (not isinstance(ins, list) or not all(_s(x) for x in ins)):
            errs.append(f"items[{i}].inputs 必須是非空字串陣列（這一項還讀的檔或資料夾）")
        cf = it.get("case_for")
        if cf is not None and (not isinstance(cf, list) or not cf or not all(_s(x) for x in cf)):
            errs.append(f"items[{i}].case_for 必須是非空字串陣列（這支案例驗的程式檔）")
    nc = inp.get("no_case")
    if nc is not None and not isinstance(nc, list):
        errs.append("no_case 必須是陣列（[{path, reason}]：不需要新案例的程式檔與理由）")
    for j, n in enumerate(nc if isinstance(nc, list) else []):
        if not isinstance(n, dict) or not _s(n.get("path")) or not _s(n.get("reason")):
            errs.append(f"no_case[{j}] 要有 path（改過的程式檔）與 reason（為什麼不需要新案例）")
    rv = inp.get("reviews")
    if rv is not None and not isinstance(rv, list):
        return errs + ["reviews 必須是陣列"]
    for j, r in enumerate(rv or []):
        if not isinstance(r, dict):
            errs.append(f"reviews[{j}] 必須是物件")
            continue
        if not _s(r.get("leak")):
            errs.append(f"reviews[{j}].leak 必填（範圍漏判編號 L…）")
        if r.get("verdict") not in REVIEW_VERDICTS:
            errs.append(f"reviews[{j}].verdict 無效（{r.get('verdict')}），允許：{'|'.join(REVIEW_VERDICTS)}")
    return errs


def validate_input(inp: Dict[str, Any]) -> List[str]:
    """js 那層的同一組規則：動作合法、必填有填、列舉值合法。"""
    action = inp.get("action")
    if action not in ACTIONS:
        return [f"action 無效（{action}），允許：{'|'.join(ACTIONS)}"]
    errs: List[str] = []
    if action == "set":
        if not _s(inp.get("goal")) and not _s(inp.get("import_from")):
            errs.append("set 要給 goal（一句、使用者的語言、只寫目標不寫手段），或給 import_from（續接單路徑）")
        if inp.get("new_task") is not None and not isinstance(inp.get("new_task"), bool):
            errs.append("new_task 必須是 true／false")
        items = inp.get("items")
        if items is not None and not isinstance(items, list):
            errs.append("set 的 items 必須是陣列（子目標 [{text, clarity?, origin?, quote?}]，同 add）")
        elif items:
            errs += _validate_items("add", items)
        return errs
    if action == "read":
        if inp.get("form") is not None and inp.get("form") not in READ_FORMS:
            errs.append(f"form 無效（{inp.get('form')}），允許：{'|'.join(READ_FORMS)}")
        return errs
    if action == "verify_scope":
        return _validate_verify_scope(inp)
    items = inp.get("items")
    if not isinstance(items, list) or not items:
        return [f"{action} 要給 items（非空陣列）"]
    errs += _validate_items(action, items)
    t = inp.get("turns")
    if action == "reconcile" and t is not None and (not isinstance(t, int) or isinstance(t, bool) or t < 0):
        errs.append("turns 必須是 ≥0 的整數")
    elif action == "reconcile" and isinstance(t, int) and t >= TURNS_RETHINK \
            and not any(_RETHINK_RE.search(_s(it.get("note"))) for it in items if isinstance(it, dict)):
        errs.append(f"turns={t} 超過三個彎（G11：第四個彎幾乎可以確定臭掉）：某一項的 note 要寫「重找最短路：<結果>」"
                    "（找到的更短做法，或為什麼沒有更短的）")
    return errs


# ─── 證據與完整對照的七條 ──────────────────────────────────────────────────

LATEST = "latest"   # reconcile 收據寫 latest：程式填最近一筆綠的收據（規則 RECEIPT_LATEST_AUTO，AI 不用先 read 樹查號碼）


def _latest_green(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return next((r for r in reversed(doc.get("receipts") or [])
                 if rr.receipt_green(r.get("verdicts"), r.get("exit"))), None)


def _fill_latest(doc: Dict[str, Any], evidence: List[Dict[str, Any]]) -> None:
    """收據證據寫 latest 的，換成最近一筆綠的收據 R<號>、標 auto（之後改了程式又跑綠，交付邊界由 refresh_auto_evidence 往前推）。"""
    r = _latest_green(doc)
    for e in evidence:
        if e.get("kind") == "receipt" and str(e.get("ref", "")).strip().lower() == LATEST and r:
            e["ref"], e["auto"] = f"R{r['seq']}", True


def _receipt_by_ref(doc: Dict[str, Any], ref: str) -> Optional[Dict[str, Any]]:
    m = _RECEIPT_REF_RE.match(str(ref or "").strip())
    if not m:
        return None
    want = int(m.group(1))
    return next((r for r in doc.get("receipts") or [] if r.get("seq") == want), None)


def _resolve_file(ref: str, cwd: str) -> Path:
    raw = _LINE_SUFFIX_RE.sub("", str(ref).strip().strip("`"))
    p = Path(os.path.expanduser(raw))
    if not p.is_absolute() and cwd:
        p = Path(cwd) / p
    return p


def _def_found(path: Path, owner: Optional[str], name: str) -> bool:
    """檔裡有沒有 def <name>（ast 找函式名，不比字串）。owner 給了（節點 id 寫了類別）就只在那個類別裡找；
    沒給就整檔找，類別裡的也算。解析失敗當找不到並印 stderr。"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError) as e:
        print(f"[NeedGoal] 解析 {path} 找 def 失敗（當找不到）：{type(e).__name__}: {e}", file=sys.stderr)
        return False
    scopes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == owner] if owner else [tree]
    for scope in scopes:
        if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name for n in ast.walk(scope)):
            return True
    return False


def _node_id_missing(kind: str, ref: str, cwd: str) -> Optional[str]:
    """規則 CASE_NODE_ID_NEEDS_DEF：pytest 節點 id（`檔::測試名`、`檔::Class::test[參數]`）以第一個 `::` 切出檔，
    最後一段去掉 `[...]` 當測試名，倒數第二段是類別。檔要在、檔裡要有那個 def 才收；對不上回擋的理由。"""
    path_part, _, rest = ref.strip().strip("`").partition("::")
    segs = rest.split("::")
    name = re.sub(r"\[.*\]$", "", segs[-1])
    owner = segs[-2] if len(segs) > 1 else None
    p = _resolve_file(path_part, cwd)
    has_file = p.is_file()
    found = has_file and _def_found(p, owner, name)
    if found:
        return None
    return (f"{LABEL['ekind'][kind]} {ref} 對不上｜規則 CASE_NODE_ID_NEEDS_DEF｜證據：檔在={'是' if has_file else '否'}"
            f"（{p}）、def {name} 找到={'是' if found else '否'}")


def _atom_exists(name: str, cwd: str) -> bool:
    name = str(name).strip().strip("`")
    if name.endswith(".md"):
        name = name[:-3]
    if not name:
        return False
    try:
        from wg_atoms import resolve_atom_path
        if resolve_atom_path(name):
            return True
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] 全域層找卡失敗（只查專案層）：{type(e).__name__}: {e}", file=sys.stderr)
    if not cwd:
        return False
    try:
        root = wg_core.resolve_project_root(cwd).path
    except Exception:  # noqa: BLE001
        root = None
    mem = Path(root or cwd) / ".claude" / "memory"
    return mem.is_dir() and any(mem.rglob(f"{name}.md"))


def _evidence_missing(doc: Dict[str, Any], ev: Dict[str, Any], cwd: str) -> Optional[str]:
    kind, ref = ev.get("kind"), str(ev.get("ref", ""))
    if kind == "receipt":
        if _receipt_by_ref(doc, ref):
            return None
        if ref.strip().lower() == LATEST:
            return "還沒有綠的收據可填（先跑驗證）"
        return f"收據 {ref} 找不到（寫 latest 由程式填最近一筆綠的收據，或寫 R<號>）"
    if kind in ("case", "file") and "::" in ref:
        return _node_id_missing(kind, ref, cwd)
    if kind in ("case", "file"):
        return None if _resolve_file(ref, cwd).exists() else f"{LABEL['ekind'][kind]} {ref} 不在磁碟上"
    if kind == "atom":
        return None if _atom_exists(ref, cwd) else f"卡片 {ref} 找不到"
    return f"證據種類 {kind} 不認得"


def _last_edit_for(tree: Dict[str, Any], nid: str) -> Optional[Dict[str, Any]]:
    """這個節點要對的程式改動：掛在它本身、它底下，或它的祖先（沒歸屬到更細節點的改動）上的最後一筆。
    讀每個節點的最後改動（node_last_edit），不讀會被截短的 edits 清單。"""
    best = None
    for node, rec in (tree.get("node_last_edit") or {}).items():
        if isinstance(rec, dict) and (_under(node, nid) or _under(nid, node)):
            if best is None or int(rec.get("seq", 0)) > int(best.get("seq", 0)):
                best = rec
    return best


def _ev_fact(doc: Dict[str, Any], e: Dict[str, Any]) -> Tuple[str, str, bool, str]:
    """規則判定要的一筆證據事實：(種類, 證據級, 收據紅不紅, 顯示字)。引用的收據找不到由 _evidence_missing 擋，這裡不算紅。"""
    r = _receipt_by_ref(doc, str(e.get("ref"))) if e.get("kind") == "receipt" else None
    red = bool(r) and rr.receipt_red(r.get("verdicts"), r.get("exit"))
    return str(e.get("kind")), str(e.get("level")), red, _evidence_text(e, doc)


def _hit(v: "rr.Verdict") -> str:
    return f"{v.why}｜規則 {v.rule}｜證據：{'；'.join(v.evidence)}"


def _receipt_rows(doc: Dict[str, Any]) -> List[Tuple[Any, List[str], bool, bool]]:
    """目標檔收據依蓋號先後 → CASE_RED_THEN_GREEN 要的 (收據號, 點名的案例檔, 紅, 綠)。"""
    return [(r.get("seq"), list(r.get("cases") or []),
             rr.receipt_red(r.get("verdicts"), r.get("exit")), rr.receipt_green(r.get("verdicts"), r.get("exit")))
            for r in doc.get("receipts") or []]


def _receipt_cases(r: Dict[str, Any]) -> List[str]:
    """工作暫存收據的完整指令點名哪些案例檔（接它的 cwd 成絕對路徑）；指令裡換目錄（root_uncertain）或沒記 cwd → 執行目錄
    不可信，回空（CASE_RED_THEN_GREEN 不拿它比）。蓋號時就算好：目標檔只存 200 字的指令。"""
    cmd, cwd = str(r.get("cmd") or ""), str(r.get("cwd") or "")
    if not cwd or r.get("root_uncertain") or has_cd(cmd):
        return []
    return rr.case_files_in_cmd(cmd, cwd)


def _evidence_problems(doc: Dict[str, Any], tree: Dict[str, Any], nid: str, e: Dict[str, Any], cwd: str) -> List[str]:
    probs: List[str] = []
    kind, level = e.get("kind"), e.get("level")
    if level == "measured" and kind != "receipt":
        probs.append(f"{nid} 的證據 {e.get('ref')}：實測只能配收據（檔案存在不等於跑過）")
    elif kind == "receipt" and level != "measured":
        probs.append(f"{nid} 的證據 {e.get('ref')}：收據只能標實測")
    miss = _evidence_missing(doc, e, cwd)
    if miss:
        return probs + [f"{nid} 的證據：{miss}"]
    nodes = tree.get("nodes") or {}
    r = _receipt_by_ref(doc, str(e.get("ref"))) if kind == "receipt" else None
    for c in e.get("covers") or [nid]:
        if c not in nodes:
            probs.append(f"{nid} 的證據 {e.get('ref')} covers 指到不存在的節點 {c}")
            continue
        last = _last_edit_for(tree, c) if r else None
        if r and last and int(r["seq"]) <= int(last.get("seq", 0)):
            if _review_fix_unaffected(doc, tree, c, r, last, e):
                continue
            probs.append(f"{nid} 的證據 R{r['seq']} 跑在 {c} 最後一次改動（{Path(str(last.get('path'))).name}）之前：改完沒重跑"
                         + ("（第二意見之後的修補只要重跑碰到它的 verify：這筆不受影響就在證據寫 unaffected＝為什麼）"
                            if doc.get("review") else ""))
    return probs


def _review_done(sid: Any, since: float) -> bool:
    """這個 session 在 since 之後開的第二意見 job 有一個跑完（`workflow/second-opinion/<時間>-<sid 前 8 碼>-<種類>/status.json`
    的 status=done；job 名格式見 tools/second-opinion/run.py new_job_id）。讀不到當沒跑完。"""
    sid8 = re.sub(r"[^0-9a-z]", "", _base_sid(sid).lower())[:8]
    if not sid8:
        return False
    for st in (wg_core.WORKFLOW_DIR / "second-opinion").glob(f"*-{sid8}-*/status.json"):
        try:
            if st.parent.stat().st_mtime + 1 >= since and json.loads(st.read_text(encoding="utf-8")).get("status") == "done":
                return True
        except (OSError, ValueError):
            continue
    return False


def mark_review(sid: Any) -> None:
    """第二意見跑完（second_opinion_result 收到結果）：記下這一刻與當時各節點的最後改動，之後的修補算「審完的修補」
    （規則 REVIEW_FIX_RERUN_TOUCHED_ONLY）。沒有樹不記。"""
    if active_tree(load(sid)) is None:
        return

    def fn(doc: Dict[str, Any]) -> None:
        tree = active_tree(doc)
        doc["review"] = {"seq": next_seq(doc), "tree": tree["id"] if tree else None, "at": time.time(),
                         "node_last_edit": copy.deepcopy((tree or {}).get("node_last_edit") or {})}
    update_locked(sid, fn)


def _review_fix_unaffected(doc: Dict[str, Any], tree: Dict[str, Any], c: str, r: Dict[str, Any],
                           last: Dict[str, Any], e: Dict[str, Any]) -> bool:
    """規則 REVIEW_FIX_RERUN_TOUCHED_ONLY：codex 審完之後的修補只重跑它碰到的檔。收據 r 跑在審查前最後一次改動之後、
    之後的改動全是審完的修補、AI 在這筆證據宣告 unaffected（為什麼後來改的檔不影響它）→ 收據照算，留帳；
    哪筆受影響由 AI 判，程式只核對時間先後與審查真的跑完（_review_done）。沒審過、審查沒跑完、審查前就過期、沒宣告、
    宣告之後又改了（存下來的證據帶對照當時的 seq）→ 照舊算改完沒重跑。"""
    rv = doc.get("review") or {}
    why = _s(e.get("unaffected"))
    if not why or not rv or rv.get("tree") != tree.get("id"):
        return False
    pre = _last_edit_for({"node_last_edit": rv.get("node_last_edit") or {}}, c)
    if int(r["seq"]) <= int((pre or {}).get("seq", 0)) or int(last.get("seq", 0)) <= int(rv.get("seq", 0)):
        return False
    if e.get("seq") is not None and int(last.get("seq", 0)) > int(e["seq"]):
        return False                             # 宣告之後又改了：舊宣告不管新改動
    if not _review_done(doc.get("session_id"), float(rv.get("at") or 0)):
        return False
    _guard("unaffected_declared", doc.get("session_id"), tree=tree["id"], node=c, receipt=r.get("seq"),
           edited=str(last.get("path")), why=why[:200])
    return True


def _problems(doc: Dict[str, Any], tree: Dict[str, Any], view: Dict[str, Dict[str, Any]], cwd: str,
              included: Optional[set]) -> List[str]:
    """完整對照第 3～7 條。view＝節點編號 → {status, evidence, followup, note}（收件時是交上來的）；沒在 view 的用現在的節點。
    included 給了（收件時）就查「每個還活著的節點都在對照裡」；沒給（交付邊界時）只查現在的狀態是終點。"""
    probs: List[str] = []
    nodes = tree.get("nodes") or {}
    for nid in _ordered(tree):
        cur = nodes[nid]
        if included is not None and nid not in included:
            if cur.get("status") != "dropped":
                probs.append(f"{nid} 沒在對照裡（每個還活著的節點都要交終點結論）")
            continue
        v = view.get(nid) or cur
        st = v.get("status")
        if st not in TERMINAL:
            probs.append(f"{nid} 現在是「{LABEL['status'].get(st, st)}」，不是終點（達成／部分／沒有／放棄）")
            continue
        evid = [e for e in v.get("evidence") or [] if not e.get("prior")]
        if st in ("done", "partial") and not evid:
            probs.append(f"{nid} 標「{LABEL['status'][st]}」但沒附證據（前一個 session 的證據不算）")
        for e in evid:
            probs += _evidence_problems(doc, tree, nid, e, cwd)
        if st == "done" and evid:
            facts = [_ev_fact(doc, e) for e in evid]
            probs += [_hit(v) for v in (rr.goal_inferred_verdict(nid, facts),
                                        rr.goal_done_evidence_verdict(nid, tree.get("kind") == "code", facts)) if v.owed]
        if st in ("partial", "none") and not _s(v.get("followup")):
            probs.append(f"{nid} 標「{LABEL['status'][st]}」要寫 followup（接下來要追什麼）")
        if st == "dropped" and included is not None and cur.get("status") != "dropped" and not _s(v.get("note")):
            probs.append(f"{nid} 標「放棄」要在 note 寫為什麼")
    return probs


def _f2_problems(doc: Dict[str, Any], tree: Dict[str, Any]) -> List[str]:
    lr = tree.get("last_reconcile")
    if not lr:
        return ["還沒交完整對照"]
    if lr.get("goal_rev") != tree.get("goal_rev"):
        return [f"完整對照之後目標改過（版本 {lr.get('goal_rev')} → {tree.get('goal_rev')}），舊對照作廢"]
    return _problems(doc, tree, {}, str(doc.get("cwd") or ""), None)


def _needs_f2(tree: Optional[Dict[str, Any]]) -> bool:
    """寫碼類樹交付前要完整對照；從續接單匯入的寫碼類樹也算（前一個 session 的證據不算數，要交新的）。"""
    return bool(tree) and tree.get("kind") == "code"


# ─── 五個動作 ──────────────────────────────────────────────────────────

_NO_TREE = "還沒有目標樹，先用 need_goal(action=set, goal=…) 寫樹根"


KINDS = ("code", "knowledge")
# 規則 CODING_TURN_ONLY 第三層：關鍵字分類判成寫碼、但還沒宣告寫碼樹也還沒改程式時，只送這一行（不啟動守門）
CODE_TREE_HINT = ("[NeedGoal] 這則看起來要改程式：動手前先 need_goal(action=set, kind=code, goal=<整個需求>, items=[看得出的子目標])"
                  " 立寫碼樹；沒立樹直接改程式，守門從第一次改程式檔才起跑。")


def _declare_kind(tree: Dict[str, Any], inp: Dict[str, Any]) -> None:
    """set 帶 kind（code／knowledge）＝LLM 宣告這件事是不是要改程式；寫碼類一旦由改程式檔標上就不退回知識類。"""
    kind = inp.get("kind")
    if kind in KINDS and not (kind == "knowledge" and tree.get("node_last_edit")):
        tree["kind"] = kind


def _op_set(doc: Dict[str, Any], inp: Dict[str, Any], turn: int) -> Dict[str, Any]:
    goal, why = _s(inp.get("goal")), _s(inp.get("why"))
    tree = active_tree(doc)
    if tree is not None and inp.get("new_task") is not True:
        _declare_kind(tree, inp)
    if tree is None or inp.get("new_task") is True:
        # 換題不再要 why（WHY_OPTIONAL）；舊樹還在進行中就在收下時列出沒結束的節點（B5 q3 改成提醒）
        old = tree if tree is not None and tree.get("status") == "doing" else None
        tree = _new_tree(doc, goal, turn, why)
        _declare_kind(tree, inp)
        add_checkpoint(doc, tree, turn, "set", tree["id"])
        events: List[Tuple[str, Dict[str, Any]]] = []
        root_line = _check_root(doc, tree, turn, events)
        note = f"開了新樹 {tree['id']}。{SUBGOAL_LINE}" + (f"\n{root_line}" if root_line else "")
        left = [n for n, v in (old or {}).get("nodes", {}).items() if v.get("status") in ("todo", "doing")]
        if left:
            note += (f"\n舊樹 {old['id']} 還有 {len(left)} 個沒結束的節點（{'、'.join(sorted(left, key=_sort_key)[:6])}）："
                     f"如果這是對 {old['id']} 的糾正或補充，改回 {old['id']}（update／add），不要開新樹；"
                     "被新樹取代的用 update 標放棄，還要做的留著。")
        return {"ok": True, "tree": tree["id"], "goal_changed": True, "note": note, "origin_events": events}
    root = tree["nodes"][tree["id"]]
    if goal == root.get("text"):
        return {"ok": True, "tree": tree["id"], "goal_changed": False, "note": "樹根沒變"}
    root["text"] = goal
    _goal_changed(doc, tree, turn)
    root["history"].append({"seq": tree["goal_changed"]["seq"], "turn": turn, "what": "text", "why": why})
    add_checkpoint(doc, tree, turn, "set", tree["id"])
    events = []
    root_line = _check_root(doc, tree, turn, events)
    return {"ok": True, "tree": tree["id"], "goal_changed": True, "origin_events": events,
            "note": f"{tree['id']} 樹根改寫，目標版本 {tree['goal_rev']}" + (f"\n{root_line}" if root_line else "")}


ORIGIN_DOWNGRADED_MAX = 20


def origin_check_on() -> bool:
    """規則 ORIGIN_USER_NEEDS_QUOTE 的開關 guard.origin_user_check.enabled（workflow/config.json；沒設＝開）。"""
    return ((wg_core.load_config().get("guard") or {}).get("origin_user_check") or {}).get("enabled", True) is not False


def _check_origin(doc: Dict[str, Any], tree: Dict[str, Any], nid: str, node: Dict[str, Any], quote: Any, turn: int,
                  events: List[Tuple[str, Dict[str, Any]]]) -> Optional[str]:
    """子節點要標 origin=user：quote／節點文字對得到樹上的使用者原話 → origin=user、存 quote 與 said_seq、history 記引用；
    對不到 → 強制 inferred、history 記原因、doc.origin_downgraded 記一筆（下一則訊息提醒一次就清）。
    events 收守門紀錄（鎖外由 apply_op 寫）；回要附在回傳 note 的一句，對上回 None。"""
    _, v, match = rr.origin_user_verdict(node.get("text"), quote, _said_for_check(tree, doc), tree.get("peer_said") or [])
    seq, q = next_seq(doc), _s(quote)
    if match is not None:
        said = match["said"]
        prior = "（前一個 session）" if said.get("prior") else ""
        # quote_by：AI 引的（quote）或節點文字本身對上（text）；文字對上的，之後改寫文字不能拿舊文字當引用重核
        node.update({"origin": "user", "quote": match["quote"], "said_seq": said.get("seq"),
                     "quote_by": "quote" if q and match["quote"] == q else "text"})
        node["history"].append({"seq": seq, "turn": turn, "what": "origin",
                                "why": f"引用第 {said.get('turn', '?')} 回合{prior}：{_clip(match['quote'], 200)}"})
        events.append(("origin_quoted", {"node": nid, "text": _clip(node.get("text"), 200), "quote": _clip(match["quote"], 200),
                                         "said_seq": said.get("seq"), "said_turn": said.get("turn")}))
        return None
    node["origin"] = "inferred"
    node["history"].append({"seq": seq, "turn": turn, "what": "origin",
                            "why": f"標使用者說的但對不到原話（{v.why}），改成推出來的"})
    line = (f"{nid}「{_clip(node.get('text'), 60)}」標使用者說的但對不到原話（{v.why}），已改成推出來的；"
            "要標使用者說的請用 quote 引用原句")
    pend = doc.setdefault("origin_downgraded", [])
    pend.append({"node": nid, "turn": turn, "line": line})
    del pend[:-ORIGIN_DOWNGRADED_MAX]
    events.append(("origin_downgraded", {"node": nid, "text": _clip(node.get("text"), 200), "quote": _clip(q, 200), "why": v.why}))
    return line


def _check_root(doc: Dict[str, Any], tree: Dict[str, Any], turn: int,
                events: List[Tuple[str, Dict[str, Any]]]) -> Optional[str]:
    """set 開樹、改寫樹根、匯入時：樹根切句後原話裡沒有的句子列一行提醒（當下回傳與下一則訊息各一次），origin 不動。
    沒有這種句子或開關關掉回 None。"""
    if not origin_check_on():
        return None
    miss = rr.root_unquoted_sentences(tree["nodes"][tree["id"]].get("text"), _said_for_check(tree, doc))
    if not miss:
        return None
    line = ("[NeedGoal] 樹根這幾句原話裡沒有：" + "".join(f"「{_clip(s, 80)}」" for s in miss[:6])
            + "——這些是 AI 的解讀，不是使用者說的")
    pend = doc.setdefault("origin_downgraded", [])
    pend.append({"node": tree["id"], "turn": turn, "line": line, "root": True})
    del pend[:-ORIGIN_DOWNGRADED_MAX]
    events.append(("root_unquoted", {"node": tree["id"], "sentences": [_clip(s, 200) for s in miss[:20]]}))
    return line


def _origin_reminder(doc: Dict[str, Any]) -> List[str]:
    """上次寫入被降級的節點、樹根原話裡沒有的句子：下一則訊息的樹提示帶一次，帶完就清。"""
    return [p["line"] if p.get("root") else f"[NeedGoal] 提醒：{p['line']}" for p in doc.pop("origin_downgraded", None) or []
            if isinstance(p, dict) and p.get("line")]


def _op_add(doc: Dict[str, Any], inp: Dict[str, Any], turn: int) -> Dict[str, Any]:
    parent = _s(inp.get("parent"))
    tree = tree_of(doc, parent) if parent else active_tree(doc)
    if tree is None:
        return {"ok": False, "tree": None, "rejected": [f"parent {parent} 不是任何一棵樹的節點" if parent else _NO_TREE]}
    parent = parent or tree["id"]
    if parent not in tree["nodes"]:
        return {"ok": False, "tree": tree["id"], "rejected": [f"parent {parent} 不是 {tree['id']} 的節點"]}
    _reopen(doc, tree)
    added = []
    check = origin_check_on()
    events: List[Tuple[str, Dict[str, Any]]] = []
    downs: List[str] = []
    for it in inp["items"]:
        nid = _child_id(tree, parent)
        tree["nodes"][nid] = {"parent": parent, "text": _s(it.get("text")), "origin": it.get("origin") or "grown",
                              "clarity": it.get("clarity") or "clear", "status": "todo",
                              "history": [{"seq": next_seq(doc), "turn": turn, "what": "create", "why": ""}],
                              "evidence": [], "followup": "", "note": ""}
        if check and tree["nodes"][nid]["origin"] == "user":
            line = _check_origin(doc, tree, nid, tree["nodes"][nid], it.get("quote"), turn, events)
            downs += [line] if line else []
        added.append(nid)
        add_checkpoint(doc, tree, turn, "add", nid)
    return {"ok": True, "tree": tree["id"], "goal_changed": False, "origin_events": events,
            "note": f"加了 {'、'.join(added)}" + "".join(f"\n  ⚠ {ln}" for ln in downs)}


def _unknown_nodes(doc: Dict[str, Any], ids: List[str]) -> List[str]:
    if not doc.get("trees"):
        return [_NO_TREE]
    return [f"{n} 不是任何一棵樹的節點" for n in ids if n not in ((tree_of(doc, n) or {}).get("nodes") or {})]


def _op_update(doc: Dict[str, Any], inp: Dict[str, Any], turn: int) -> Dict[str, Any]:
    """每一項依節點編號找它所屬的樹（不限目前的樹）：換題後舊樹欠的對照照樣交得進去。"""
    bad = _unknown_nodes(doc, [it["id"] for it in inp["items"]])
    if bad:
        return {"ok": False, "tree": None, "rejected": bad}
    bumped: Dict[str, Dict[str, Any]] = {}
    reopened: Dict[str, Dict[str, Any]] = {}
    cleared = 0
    check = origin_check_on()
    events: List[Tuple[str, Dict[str, Any]]] = []
    downs: List[str] = []
    for it in inp["items"]:
        nid, why = it["id"], _s(it.get("why"))
        tree = tree_of(doc, nid)
        node = tree["nodes"][nid]
        changed = False
        old_text = node.get("text")
        for field in ("text", "clarity", "status"):
            if it.get(field) is None:
                continue
            val = _s(it[field]) if field == "text" else it[field]
            if node.get(field) == val:
                continue
            node[field] = val
            node["history"].append({"seq": next_seq(doc), "turn": turn, "what": field, "why": why})
            changed = True
            if field == "text":
                bumped[tree["id"]] = tree
            elif val not in TERMINAL:
                reopened[tree["id"]] = tree
        want = it.get("origin")
        # 標成使用者說的、或改了使用者說的節點文字（含匯入的）都要重核：新文字是這次寫的，沒新 quote 就拿節點存的 quote 核
        # （存的是舊節點文字對上的就不拿：舊文字核必過）
        recheck = want is None and node.get("origin") == "user" and node.get("text") != old_text
        kept = node.get("quote") if node.get("quote_by") != "text" else None
        if (want == "user" or recheck) and check and node.get("parent") is not None:   # 樹根是 AI 對原話的解讀，不核
            line = _check_origin(doc, tree, nid, node, it.get("quote") or kept, turn, events)
            downs += [line] if line else []
            changed = True
        elif want is not None and node.get("origin") != want:
            node["origin"] = want
            node["history"].append({"seq": next_seq(doc), "turn": turn, "what": "origin", "why": why})
            changed = True
        if not changed:
            node["history"].append({"seq": next_seq(doc), "turn": turn, "what": "status", "why": why})
        seq = next_seq(doc)
        for e in _owed(tree):
            if _under(nid, str(e.get("node") or "")):
                e["owed"] = False
                e["cleared_seq"] = seq
                cleared += 1
        add_checkpoint(doc, tree, turn, "update", nid)
    for tree in bumped.values():
        _goal_changed(doc, tree, turn)
    touched = {tree_of(doc, it["id"])["id"] for it in inp["items"]}
    for tid in touched:
        tree = doc["trees"][tid]
        if tree["nodes"][tid].get("status") == "dropped":
            tree["status"] = "closed"
        elif tid in reopened:
            _reopen(doc, tree)
    first = tree_of(doc, inp["items"][0]["id"])["id"]
    return {"ok": True, "tree": first, "goal_changed": bool(bumped), "origin_events": events,
            "note": f"收下 {len(inp['items'])} 項" + (f"，清掉 {cleared} 筆待對照" if cleared else "")
            + "".join(f"\n  ⚠ {ln}" for ln in downs)}


def _op_reconcile(doc: Dict[str, Any], inp: Dict[str, Any], turn: int, cwd: str) -> Dict[str, Any]:
    """完整對照的對象＝項目節點編號所屬的那一棵樹（不限目前的樹；一次只能對一棵）。"""
    items = {it["id"]: it for it in inp["items"]}
    bad = _unknown_nodes(doc, list(items))
    if bad:
        return {"ok": False, "tree": None, "rejected": bad}
    tids = sorted({tree_of(doc, n)["id"] for n in items})
    if len(tids) > 1:
        return {"ok": False, "tree": None, "rejected": [f"一次完整對照只對一棵樹（這次混了 {'、'.join(tids)}），分開交"]}
    tree = doc["trees"][tids[0]]
    view = {nid: {"status": it["status"], "evidence": [dict(e) for e in it.get("evidence") or []],
                  "followup": _s(it.get("followup")), "note": _s(it.get("note")), "same_class": _s(it.get("same_class"))}
            for nid, it in items.items()}
    for v in view.values():
        _fill_latest(doc, v["evidence"])
    probs = _problems(doc, tree, view, cwd, set(items))
    if probs:
        return {"ok": False, "tree": tree["id"], "rejected": probs}
    seq = next_seq(doc)
    followups = []
    rows = _receipt_rows(doc)
    rtg = []                                     # CASE_RED_THEN_GREEN：只記錄、印在對照摘要，不擋
    for nid, v in view.items():
        node = tree["nodes"][nid]
        prior = [e for e in node.get("evidence") or [] if e.get("prior")]
        node["status"] = v["status"]
        stored = [{"kind": e["kind"], "ref": _s(e.get("ref")), "level": e["level"],
                   "covers": list(e.get("covers") or [nid]), "seq": seq, **({"auto": True} if e.get("auto") else {}),
                   **({"unaffected": _s(e["unaffected"])} if _s(e.get("unaffected")) else {})}
                  for e in v["evidence"]]
        for rec in stored:
            if rec["kind"] != "case":
                continue
            pair = rr.red_then_green(str(_resolve_file(rec["ref"].split("::", 1)[0], cwd)), rows)
            rec["red_then_green"] = pair is not None
            rtg.append(f"{nid} 的案例 {rec['ref']}：" + (f"先紅後綠（red_then_green，R{pair[0]} 紅 → R{pair[1]} 綠）" if pair
                                                          else "案例未見先紅（只記錄、不擋）"))
        node["evidence"] = stored + prior
        node.pop("filled_by", None)              # AI 自己交了對照：之後程式不再代填這個節點
        node["followup"] = v["followup"]
        node["note"] = v["note"]
        node["same_class"] = v["same_class"]
        node["history"].append({"seq": seq, "turn": turn, "what": "reconcile", "why": v["note"] or v["followup"]})
        if v["status"] in ("partial", "none") and v["followup"]:
            followups.append(f"需求目標 {nid}（{LABEL['status'][v['status']]}）：{v['followup']}")
    for e in _owed(tree):
        e["owed"] = False
        e["cleared_seq"] = seq
    tree["last_reconcile"] = {"seq": seq, "turn": turn, "goal_rev": tree.get("goal_rev", 1)}
    if inp.get("turns") is not None:
        tree["last_reconcile"]["turns"] = inp["turns"]
    done = all(n.get("status") in ("done", "dropped") for n in tree["nodes"].values())
    tree["status"] = "closed" if done else "reconciled"
    add_checkpoint(doc, tree, turn, "reconcile", tree["id"])
    bare = [nid for nid, v in view.items() if v["status"] == "done" and not v["same_class"]]
    same = (f"\n  - 達成的 {'、'.join(bare[:6])} 可附 same_class（同類別處還有沒有：找到的位置，或為什麼沒有；只提醒、不擋）"
            if bare else "")
    turns = "" if inp.get("turns") is not None else f"\n  - {TURNS_HINT}"
    return {"ok": True, "tree": tree["id"], "goal_changed": False, "followups": followups,
            "note": f"完整對照收下，{tree['id']} {LABEL['tree'][tree['status']]}" + "".join(f"\n  - {ln}" for ln in rtg)
            + same + turns}


def apply_op(sid: Any, turn: int, tool_input: Dict[str, Any], cwd: str = "") -> Dict[str, Any]:
    """套用一次 need_goal 呼叫。回 {ok, action, tree, rejected, text, goal_changed}；text 是要送回 AI 的整段提示。"""
    inp = dict(tool_input or {})
    action = inp.get("action")
    errs = validate_input(inp)
    if errs:
        return _result(sid, action, {"ok": False, "tree": None, "rejected": errs}, None)
    if action == "verify_scope":                 # 驗證範圍不進目標檔：PostToolUse 轉交 wg_verify_scope.declare
        return {"ok": False, "action": action, "tree": None, "rejected": [], "goal_changed": False,
                "text": "[NeedGoal] verify_scope 由驗證範圍收件（wg_verify_scope），這裡不套用"}
    if action == "read":
        doc = load(sid)
        tree = active_tree(doc)
        form = inp.get("form") or "full"
        if form == "handoff":
            text = handoff_block(sid) or "[NeedGoal] 沒有未結束的樹，續接單不用帶【需求目標樹】區塊"
        elif tree is None:
            text = "[NeedGoal] 還沒有目標樹。若這是要動手的需求，用 need_goal(action=set, goal=…) 寫樹根。"
        else:
            text = "[NeedGoal] " + render(tree, form, doc=doc)
        return {"ok": True, "action": "read", "tree": tree["id"] if tree else None, "rejected": [], "text": text,
                "goal_changed": False}
    if action == "set" and _s(inp.get("import_from")):
        path = _s(inp["import_from"])
        try:
            text = Path(os.path.expanduser(path)).read_text(encoding="utf-8")
        except OSError as e:
            return _result(sid, action, {"ok": False, "tree": None, "rejected": [f"讀不到續接單 {path}：{e}"]}, None)
        res = import_handoff(sid, text, path, turn)
        ok = bool(res["imported"])
        out = {"ok": ok, "tree": (res["imported"] or [None])[-1], "goal_changed": ok,
               "rejected": [] if ok else [res.get("skipped") or "沒有可匯入的樹"],
               "note": "匯入續接單的樹" + "".join(f"\n{ln}" for ln in res.get("root_lines") or [])}
        return _result(sid, action, out, load(sid))

    def fn(doc: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if cwd:
            doc["cwd"] = cwd
        if action == "set":
            r = _op_set(doc, inp, turn)
            if r.get("ok") and inp.get("items"):     # 規則 SET_WITH_SUBGOALS：樹根與看得出的子目標一次寫，不另叫 add
                ra = _op_add(doc, {"items": inp["items"], "parent": r["tree"]}, turn)
                if not ra.get("ok"):
                    r["ok"], r["rejected"] = False, ["樹根收下了，子目標沒收："] + list(ra.get("rejected") or [])
                r["note"] = f"{r.get('note') or ''}\n{ra.get('note') or ''}".strip()
                r["origin_events"] = list(r.get("origin_events") or []) + list(ra.get("origin_events") or [])
        elif action == "add":
            r = _op_add(doc, inp, turn)
        elif action == "update":
            r = _op_update(doc, inp, turn)
        else:
            r = _op_reconcile(doc, inp, turn, cwd or str(doc.get("cwd") or ""))
        if doc.pop("corrupt_backup", None):
            r["note"] = (r.get("note") or "") + "（目標檔損毀，已改名留證；舊樹沒有了，必要時重寫）"
        return r, copy.deepcopy(doc)

    res, snap = update_locked(sid, fn)
    for event, kw in res.pop("origin_events", None) or []:
        _guard(event, sid, **kw)
    if res.get("followups"):
        _append_tracking(sid, turn, res["followups"], cwd or str(snap.get("cwd") or ""))
    return _result(sid, action, res, snap)


def _result(sid: Any, action: Any, res: Dict[str, Any], doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    rejected = list(res.get("rejected") or [])
    tree = ((doc.get("trees") or {}).get(res.get("tree") or "") or active_tree(doc)) if doc else None
    if rejected:
        head = f"[NeedGoal] {action} 拒收，沒有套用：\n" + "\n".join(f"  ✗ {r}" for r in rejected)
    else:
        head = f"[NeedGoal] {action} 收下：{res.get('note') or ''}"
    # 規則 TREE_ONCE_PER_CALL：整棵樹只在 need_goal 寫入的回覆送一次——set（開樹／改樹根）送全樹，原話與 AI 解讀並排是判斷材料；
    # add／update／reconcile 送精簡樹（樹頭＋每個節點一行，不截）；其他 hook 提示只附 brief_for（新送法只一行當前節點，規則 TREE_LINE_IN_HINTS），
    # 原話、收據清單、待對照要看用 read
    form = "full" if action == "set" else "compact"
    body = render(tree, form, doc=doc) if tree else ""
    _guard("op", sid, action=action, tree=res.get("tree"), ok=bool(res.get("ok")), rejected=len(rejected))
    return {"ok": bool(res.get("ok")), "action": action, "tree": res.get("tree"), "rejected": rejected,
            "text": f"{head}\n{body}".rstrip(), "goal_changed": bool(res.get("goal_changed")),
            "kind": (tree or {}).get("kind")}


def _append_tracking(sid: Any, turn: int, lines: List[str], cwd: str) -> None:
    try:
        from wg_harvest import append_tracking, tracking_entries, tracking_slug
        entries = tracking_entries(_base_sid(sid), turn, "\n".join(lines))
        if entries:
            append_tracking(tracking_slug(cwd), entries)
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] 未完事項寫不進追蹤帳本：{type(e).__name__}: {e}", file=sys.stderr)


# ─── 4.1 新需求開始 ──────────────────────────────────────────────────────

def _peer_of(prompt: str) -> Optional[Tuple[str, str]]:
    m = _PEER_RE.search(prompt or "")
    if not m:
        return None
    fm = _PEER_NAME_RE.search(m.group(1) or "") or _PEER_FROM_RE.search(m.group(1) or "")
    sender = fm.group(1) if fm else ""
    body = " ".join(m.group(2).split())
    return (sender, body) if body else None


def on_prompt(sid: Any, prompt: str, turn: int, config: Optional[Dict[str, Any]], cwd: str = "") -> Optional[str]:
    """使用者送出訊息那一刻：使用者本人打的字記進目前的樹、同伴訊息記成轉述、系統通知不記；回要送給 AI 的那一行。
    沒有目前的樹而且是這個 session 第一則使用者訊息、或目前的樹剛對照完／結束 → 送一次「先寫目標」；有樹 → 送 brief_for。"""
    if not sid or not cfg_for_cwd(config, cwd)["enabled"]:
        return None
    typed = user_typed_text(prompt or "", keep_lines=True)
    peer = None if typed else _peer_of(prompt or "")
    if not typed and not peer:
        return None

    def fn(doc: Dict[str, Any]) -> Tuple[Optional[str], bool]:
        seq = next_seq(doc)
        tree = active_tree(doc)
        live = tree if tree and tree.get("status") != "closed" else None
        if peer:
            if live:
                ps = live.setdefault("peer_said", [])
                ps.append({"seq": seq, "turn": turn, "from": peer[0], "text": peer[1][:PEER_CAP]})
                del ps[:-SAID_MAX]
            return ("\n".join([f"[NeedGoal] 目前需求目標 {brief_for(tree, config=config)}", *_origin_reminder(doc)])
                    if tree else None), False
        doc["user_msgs"] = int(doc.get("user_msgs", 0)) + 1
        entry = {"seq": seq, "turn": turn, "text": typed}
        log = doc.setdefault("said_log", [])
        log.append({**entry, "text": typed[:USER_FIRST_CAP], "attached": live is not None})
        del log[:-SAID_LOG_MAX]
        if live:
            _add_said(live, entry)
        sent = doc.setdefault("hint_sent", {"first": False, "after": []})
        if tree is None:
            if doc["user_msgs"] == 1 and not sent.get("first"):
                sent["first"] = True
                return HINT_LINE, True
            return None, False
        lines = [f"[NeedGoal] 目前需求目標 {brief_for(tree, config=config)}", TREE_PATHS, *_origin_reminder(doc)]
        hinted = False
        if tree.get("status") in ("reconciled", "closed") and tree["id"] not in sent.setdefault("after", []):
            sent["after"].append(tree["id"])
            hinted = True
            lines.append(f"[NeedGoal] {tree['id']} {LABEL['tree'][tree['status']]}。若這則是新的要動手的需求，"
                         "用 need_goal(action=set, new_task=true, goal=…) 開新樹（一句、用使用者的話、不寫手段）。")
        return "\n".join(lines), hinted

    text, hinted = update_locked(sid, fn)
    if hinted:
        _guard("prompt_hint", sid, turn_seq=turn)
    return text


# ─── 4.2 動手改程式前 ─────────────────────────────────────────────────────

DIR_SCAN_CAP = 5000     # 搬移／複製的來源是目錄時最多看幾個檔；超過還沒看完就當成有程式檔


def _in_knowledge_part(path: str) -> bool:
    """部位類別是 knowledge（文件、記憶、信件匣）。真源是 overview_hub.path_kind；這支函式不在時當不是。"""
    try:
        from overview_hub import KIND_KNOWLEDGE, path_kind
    except ImportError:
        return False
    return path_kind(str(path)) == KIND_KNOWLEDGE


def is_code_path(path: str, config: Optional[Dict[str, Any]]) -> bool:
    """寫碼類判準：部位類別是 knowledge 的不算；其餘看寫碼查核閘那份副檔名清單（聯集合併，沒副檔名看 `#!`）。"""
    if not path or str(path).startswith("UNKNOWN:") or _in_knowledge_part(path):
        return False
    return is_code_file(str(path), reconcile_cfg(config or {})["code_exts"])


def _has_code(path: str, config: Optional[Dict[str, Any]]) -> bool:
    """搬移或複製的來源有沒有寫碼類檔：檔案照 is_code_path；目錄往下找（略過 .git），看超過 DIR_SCAN_CAP 個檔還沒找到
    也當有（判不了就擋）。"""
    if is_code_path(path, config):
        return True
    if not os.path.isdir(path) or _in_knowledge_part(path):
        return False
    seen = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            seen += 1
            if seen > DIR_SCAN_CAP or is_code_path(os.path.join(root, f), config):
                return True
    return False


def writes_code(path: str, config: Optional[Dict[str, Any]], sources: Any = (), content: Optional[str] = None) -> bool:
    """這次寫入算不算改程式：目標本身是程式檔；或 cp／mv 的來源含程式檔（目的地還不存在，光看路徑分不出來）；
    或要寫進沒副檔名檔案的內容以 `#!` 開頭（新建的腳本磁碟上還沒有，讀不到 shebang）。目標在知識類部位一律不算。"""
    if is_code_path(path, config):
        return True
    if not path or str(path).startswith("UNKNOWN:") or _in_knowledge_part(path):
        return False
    if any(_has_code(str(s), config) for s in sources or ()):
        return True
    return isinstance(content, str) and content.startswith("#!") and not Path(str(path)).suffix


def _ephemeral(path: str) -> bool:
    from handlers import _shared
    return _shared._is_ephemeral_path(path)


def _edit_gate_applies(path: str, config: Optional[Dict[str, Any]], sources: Any = (),
                       content: Optional[str] = None) -> bool:
    """edit_gate 管不管這筆寫入：不是暫存檔、這一層 need_goal 開著、算改程式（writes_code）。讀到程式檔先提示
    （tree_owed_for_edit）用同一支，提示與擋講同一件事。"""
    return not _ephemeral(path) and cfg_of(config, _root_of(path))["enabled"] and writes_code(path, config, sources, content)


def edit_gate(sid: Any, path: str, config: Optional[Dict[str, Any]], sources: Any = (),
              content: Optional[str] = None) -> Optional[str]:
    """4.2 第一層：這次寫入算改程式（writes_code：目標是程式檔、cp／mv 的來源含程式檔、沒副檔名而內容以 #! 開頭）、
    沒有目前的樹 → 回擋的理由。暫存檔、知識類、關掉時不管；判不了（鎖、損毀）一律擋。UNKNOWN 寫入目標不在這裡判（OverviewHub 放行並留帳，規則 UNKNOWN_TARGET_LOGGED）。"""
    if not sid or not path or str(path).startswith("UNKNOWN:"):
        return None
    try:
        if not _edit_gate_applies(path, config, sources, content):
            return None
        if active_tree(load(sid)) is not None:
            return None
    except NeedGoalCorrupt as e:
        _guard("edit_blocked", sid, path=path, why="corrupt")
        return (f"[NeedGoal] 目標檔損毀，無法判定改 {path} 前有沒有需求目標，一律擋：{e}。"
                "用 need_goal(action=set, goal=…) 重寫樹（壞檔會自動改名留證）再改。" + NO_TOOL_HINT)
    except Exception as e:  # noqa: BLE001
        _guard("edit_blocked", sid, path=path, why="error", error=f"{type(e).__name__}: {e}")
        return f"[NeedGoal] 判定改 {path} 前有沒有需求目標時出錯，一律擋：{type(e).__name__}: {e}。先用 Read 查原因。"
    _guard("edit_blocked", sid, path=path, why="no_tree")
    return (f"[NeedGoal] 改程式檔 {path} 前：這個需求還沒有目標樹。先用 need_goal(action=set, goal=…) 寫下"
            "這個需求真正要達成什麼（一句、用使用者的話、只寫目標不寫手段），再改程式。" + NO_TOOL_HINT)


def tree_owed_for_edit(sid: Any, path: str, config: Optional[Dict[str, Any]]) -> bool:
    """讀到程式檔先提示（規則 LOCATE_HINT_ON_FIRST_READ）：現在改這個檔，edit_gate 會不會因為沒有目標樹而擋——同一支
    _edit_gate_applies（讀的時候沒有寫入內容與 cp／mv 來源）加目前的樹；目標檔損毀時改檔照樣擋、修法也是 need_goal set，回 True；
    其他錯誤只 stderr、回 False（不提，改檔時 edit_gate 照判）。"""
    if not sid or not path or str(path).startswith("UNKNOWN:"):
        return False
    try:
        return _edit_gate_applies(path, config) and active_tree(load(sid)) is None
    except NeedGoalCorrupt:
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] 讀檔時判斷有沒有目標樹出錯（這次提示不提立樹，改檔時照判）：{type(e).__name__}: {e}", file=sys.stderr)
        return False


def goal_for_edit(sid: Any, path: str, config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """這次改檔要不要定位第四行：啟用、是程式檔、有目前的樹 → 回那棵樹。目標檔壞了丟 NeedGoalCorrupt（呼叫端擋）。"""
    if not sid or not path or not cfg_of(config, _root_of(path))["enabled"] or not is_code_path(path, config):
        return None
    return active_tree(load(sid))


def link_part(sid: Any, hub_key: str, node_id: str, turn: int) -> None:
    """定位第四行核對通過：記「這個部位 → 這個節點」，之後這個部位的改動掛到這個節點。"""
    def fn(doc: Dict[str, Any]) -> None:
        tree = active_tree(doc)
        if not tree or node_id not in tree["nodes"]:
            return
        cur = tree.setdefault("links", {}).setdefault("parts", {}).get(hub_key)
        if cur and cur.get("node") == node_id:
            return
        tree["links"]["parts"][hub_key] = {"node": node_id, "seq": next_seq(doc)}
        add_checkpoint(doc, tree, turn, "locate", node_id)
    update_locked(sid, fn)


def _hub_key_of(path: str) -> Optional[str]:
    try:
        from wg_overview import _key, _lookup_quiet
        hit = _lookup_quiet(path)
        return _key(*hit) if hit else None
    except Exception:  # noqa: BLE001
        return None


def _hub_part_of(path: str, config: Optional[Dict[str, Any]]) -> Optional[Tuple[str, str]]:
    """改到的檔所屬部位 (key, 部位名)，收尾查它有沒有掛目標（規則 EDITED_PART_NEEDS_GOAL_NODE）；表外、
    OverviewHub 在那一層關掉（不要求定位）回 None。查表失敗只 stderr、當表外。"""
    try:
        from wg_overview import _cfg, _key, _lookup_quiet
        hit = _lookup_quiet(path)
        if not hit or not _cfg(config or {}, hit[0])["enabled"]:
            return None
        return _key(*hit), str(hit[1]["part_short"])
    except Exception as e:  # noqa: BLE001
        print(f"[NeedGoal] 查 {path} 所屬部位失敗，這一筆不記部位：{type(e).__name__}: {e}", file=sys.stderr)
        return None


def stamp_edit(sid: Any, path: str, agent_id: str, turn: int, config: Optional[Dict[str, Any]]) -> Optional[str]:
    """改檔蓋號：掛到部位連到的節點（沒有就樹根）；程式檔記待對照、記改到的部位（parts_edited，收尾 (f3) 查它掛了目標沒）、
    樹升寫碼類、已對照或結束的樹退回進行中（記憶知識類的樹改了知識類檔也退回）。沒有樹：程式檔不記（改之前 edit_gate 已擋）；
    算記憶知識類寫入的（_knowledge_write）記進 untreed（寫樹時掛進新樹），這個回合第一筆回 KNOWLEDGE_TREE_LINE 給呼叫端送回 AI。
    其餘回 None。"""
    if not sid or not path or not cfg_of(config, _root_of(path))["enabled"]:
        return None
    from wg_verify_ledger import git_launcher
    if git_launcher(path):          # 規則 LAUNCHER_NOT_CODE：一次性 git 啟動器的建、改、刪不蓋到樹，不讓節點證據變成「改完沒重跑」
        return None
    code = is_code_path(path, config)
    if active_tree(load(sid)) is None:
        return _note_untreed(sid, path, turn) if not code and _knowledge_write(path, config) else None
    hub_key = _hub_key_of(path)
    part = _hub_part_of(path, config) if code else None

    def fn(doc: Dict[str, Any]) -> None:
        tree = active_tree(doc)
        if not tree:
            return
        if part:
            files = tree.setdefault("parts_edited", {}).setdefault(part[0], {"part": part[1], "files": []})["files"]
            if len(files) < PART_FILES_MAX and not any(rr.same_file(f, path) for f in files):
                files.append(str(path))
        link = (tree.get("links") or {}).get("parts", {}).get(hub_key) if hub_key else None
        node = link["node"] if link and link.get("node") in tree["nodes"] else tree["id"]
        seq = next_seq(doc)
        edits = tree.setdefault("edits", [])
        same = next((e for e in edits if code and e.get("owed") and e.get("path") == str(path) and e.get("node") == node),
                    None)
        if same:                                 # 同一檔還欠著對照：併成一筆、序號更新（欠的義務不因截短而消失）
            same.update(seq=seq, turn=turn, agent_id=str(agent_id or ""))
        else:
            edits.append({"seq": seq, "turn": turn, "path": str(path), "node": node,
                          "agent_id": str(agent_id or ""), "code": code, "owed": code})
        while len(edits) > EDITS_MAX:            # 只丟已清掉義務的舊紀錄；先後判定讀 node_last_edit，不靠這份清單
            drop = next((i for i, e in enumerate(edits) if not e.get("owed")), None)
            if drop is None:
                break
            del edits[drop]
        if code:
            tree.setdefault("node_last_edit", {})[node] = {"seq": seq, "path": str(path)}
            tree["kind"] = "code"
        if code or tree.get("kind") != "code":
            _reopen(doc, tree)                   # 對照之後又改了：回到進行中，交付前要再對照（知識類由 (f4) 要）
    update_locked(sid, fn)
    return None


def _knowledge_write(path: str, config: Optional[Dict[str, Any]]) -> bool:
    """沒樹時這筆寫入算不算記憶知識類（都是查得到的事實）：還在的檔不是程式；還在的目錄裡沒有程式檔（搬過去的目的地，
    往下找的上限同 _has_code）；已經不在的路徑有副檔名、而且副檔名不是程式（刪掉或搬走的文件）。沒副檔名又不在的
    （搬走或刪掉的目錄、無副檔名腳本）分不出，不算；執行期資料（Logs、workflow/state*、快取目錄，規則 RUNTIME_DATA_NO_OVERVIEW，
    這裡不查 .gitignore、不叫 git）不算。"""
    p = str(path)
    root = _root_of(p)
    if not rr.runtime_data_verdict(p, str(root) if root else None, None).owed:
        return False
    if os.path.isdir(p):
        return not _has_code(p, config)
    if os.path.isfile(p):
        return not is_code_path(p, config)
    return bool(Path(p).suffix) and not is_code_path(p, config)


def _note_untreed(sid: Any, path: str, turn: int) -> Optional[str]:
    """沒有目標樹時改了記憶知識類的檔：記進 doc["untreed"]（同一檔一筆、更新回合；收尾 (f4) 與寫樹掛進樹都讀它），
    這個回合第一筆回 KNOWLEDGE_TREE_LINE。上鎖後發現樹已經在了就不記（並行的 set 先到）。"""
    def fn(doc: Dict[str, Any]) -> Optional[str]:
        if active_tree(doc) is not None:
            return None
        log = doc.setdefault("untreed", [])
        seq = next_seq(doc)
        hit = next((e for e in log if rr.same_file(str(e.get("path") or ""), str(path))), None)
        if hit:
            hit.update(seq=seq, turn=turn)
        else:
            log.append({"seq": seq, "turn": turn, "path": str(path)})
        dropped = [str(e.get("path")) for e in log[:-UNTREED_MAX]]
        if dropped:                              # 超過上限丟最舊的，丟的要留訊號（守門紀錄＋計數），不靜默
            del log[:-UNTREED_MAX]
            doc["untreed_dropped"] = int(doc.get("untreed_dropped") or 0) + len(dropped)
            _guard("untreed_dropped", sid, dropped=dropped[:5], total=doc["untreed_dropped"], turn_seq=turn)
        if doc.get("untreed_hint_turn") == turn:
            return None
        doc["untreed_hint_turn"] = turn
        return KNOWLEDGE_TREE_LINE.format(name=Path(str(path)).name)

    line = update_locked(sid, fn)
    if line:
        _guard("knowledge_no_tree", sid, path=str(path), turn_seq=turn)
    return line


def _receipt_ident(key: str, receipt_seq: Any, at: Any) -> str:
    return f"{key}|{receipt_seq}|{at}"


def _referenced_receipts(doc: Dict[str, Any]) -> set:
    refs = set()
    for tree in (doc.get("trees") or {}).values():
        for node in (tree.get("nodes") or {}).values():
            for e in node.get("evidence") or []:
                m = _RECEIPT_REF_RE.match(str(e.get("ref") or "").strip()) if e.get("kind") == "receipt" else None
                if m and not e.get("prior"):
                    refs.add(int(m.group(1)))
    return refs


def _trim_receipts(doc: Dict[str, Any]) -> None:
    """收據超過上限時丟最舊、沒被任何節點證據引用的；丟掉的識別記進 receipts_seen，工作暫存裡還留著的同一筆不會被重新蓋成新號。"""
    rs = doc.get("receipts") or []
    over = len(rs) - RECEIPTS_MAX
    if over <= 0:
        return
    refs = _referenced_receipts(doc)
    seen = doc.setdefault("receipts_seen", [])
    keep = []
    for r in rs:
        if over > 0 and r.get("seq") not in refs:
            seen.append(_receipt_ident(r.get("key", ""), r.get("receipt_seq"), r.get("at")))
            over -= 1
            continue
        keep.append(r)
    doc["receipts"] = keep
    del seen[:-RECEIPTS_SEEN_MAX]


def stamp_receipts(sid: Any, state: Optional[Dict[str, Any]], turn: int) -> int:
    """工作暫存裡還沒蓋號的收據（主 session 與子代理）蓋進目標檔；目標檔還不存在不蓋。回蓋了幾筆。"""
    base = _base_sid(sid)
    if not base or not state or not goal_path(base).exists():
        return 0
    allr = state.get("verify_receipts") or {}
    if not isinstance(allr, dict):
        return 0
    cands: List[Tuple[str, Dict[str, Any]]] = []
    for key, lst in allr.items():
        if key != base and not str(key).startswith(base + "#agent:"):
            continue
        cands += [(str(key), r) for r in lst or [] if isinstance(r, dict)]
    def _seen(doc: Dict[str, Any]) -> set:
        return ({_receipt_ident(r.get("key", ""), r.get("receipt_seq"), r.get("at")) for r in doc.get("receipts") or []}
                | set(doc.get("receipts_seen") or []))

    seen = _seen(load(base))
    fresh = [(k, r) for k, r in cands if _receipt_ident(k, r.get("seq"), r.get("at")) not in seen]
    if not fresh:
        return 0
    fresh.sort(key=lambda kr: (str(kr[1].get("at") or ""), int(kr[1].get("seq") or 0)))

    def fn(doc: Dict[str, Any]) -> int:
        have = _seen(doc)
        n = 0
        for key, r in fresh:
            if _receipt_ident(key, r.get("seq"), r.get("at")) in have:
                continue
            doc.setdefault("receipts", []).append({
                "seq": next_seq(doc), "receipt_seq": r.get("seq"), "key": key, "turn": r.get("turn_seq", turn),
                "at": r.get("at"), "cmd": str(r.get("cmd") or "")[:200], "cases": _receipt_cases(r),
                "verdicts": [f"{s.get('name')}:{s.get('verdict')}" for s in r.get("sentinels") or [] if isinstance(s, dict)],
                "exit": r.get("exit_code"),
            })
            n += 1
        _trim_receipts(doc)
        return n
    return update_locked(base, fn)


# ─── 4.5 改了程式之後、交付之前 ─────────────────────────────────────────────

def _tree_ids(doc: Dict[str, Any]) -> List[str]:
    return sorted(doc.get("trees") or {}, key=lambda t: int(t[1:]) if t[1:].isdigit() else 0)


def auto_progress(sid: Any, turn: int = 0) -> List[Dict[str, Any]]:
    """規則 PROGRESS_LINE_BY_PROGRAM：(f1) 待對照不再叫 AI 另呼叫 update——程式照改到的檔與最近收據替每個欠著的節點記一筆進度
    （history what=progress、by=program），清掉待對照，回記了哪些 [{tree, node, files, receipt}]（給背景本地模型草擬一句進度用）。
    目標有沒有更接近仍由 AI 在完整對照（reconcile）判；它要自己寫進度照樣可以 update。"""
    def fn(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        r = (doc.get("receipts") or [None])[-1]
        rtext = "還沒有收據"
        if r:
            green = rr.receipt_green(r.get("verdicts"), r.get("exit"))
            rtext = f"最近收據 R{r['seq']}（{'綠' if green else '沒綠'}）"
        for tid in _tree_ids(doc):
            tree = doc["trees"][tid]
            for node, names in _group_owed(_owed(tree)).items():
                if node not in tree["nodes"]:
                    continue
                seq = next_seq(doc)
                tree["nodes"][node]["history"].append({"seq": seq, "turn": turn, "what": "progress", "by": "program",
                                                       "why": f"改了 {'、'.join(names[:6])}；{rtext}"})
                out.append({"tree": tid, "node": node, "files": names[:6], "receipt": r.get("seq") if r else None})
            for e in _owed(tree):
                e["owed"] = False
                e["cleared_seq"] = next_seq(doc)
        return out
    try:
        done = update_locked(sid, fn)
    except (NeedGoalLockTimeout, NeedGoalCorrupt, OSError) as e:
        print(f"[NeedGoal] 程式記進度失敗（待對照留著，下次收尾再記）：{type(e).__name__}: {e}", file=sys.stderr)
        return []
    if done:
        _guard("auto_progress", sid, nodes=[d["node"] for d in done])
    return done


AUTO_FOLLOWUP = "程式代填：最後一次改動之後沒有綠收據（要追什麼由 AI 用 reconcile 補 followup）"


def auto_reconcile(sid: Any, turn: int = 0) -> List[str]:
    """規則 RECONCILE_BY_PROGRAM：閘關著（goal_gate=false）時交付邊界由程式照收據代填完整對照——目前的寫碼類樹
    還沒對照（或對照後目標改過、又改了檔）：每個還活著、還沒到終點的節點，最後一次改動之後有綠收據 → 達成、證據掛那筆
    （by=program）；沒有 → 部分、followup 寫 AUTO_FOLLOWUP 等 AI 補。AI 自己交的對照照收、會蓋過這份。回代填了哪些節點。"""
    def fn(doc: Dict[str, Any]) -> List[str]:
        tree = active_tree(doc)
        if not tree or tree.get("kind") != "code":
            return []
        if reconcile_fresh(tree) and not _edited_since_reconcile(tree):
            return []
        greens = [r for r in doc.get("receipts") or [] if rr.receipt_green(r.get("verdicts"), r.get("exit"))]
        seq = next_seq(doc)
        filled: List[str] = []
        for nid in _ordered(tree):
            node = tree["nodes"][nid]
            if node.get("status") in ("dropped", "none") or (node.get("status") in ("done", "partial")
                                                             and node.get("filled_by") != "program"):
                continue                         # AI 自己交的對照不蓋；程式代填過的每次重算
            last = _last_edit_for(tree, nid)
            r = next((g for g in reversed(greens) if int(g["seq"]) > int((last or {}).get("seq", 0))), None)
            if r:
                node["status"] = "done"
                node["evidence"] = [{"kind": "receipt", "ref": f"R{r['seq']}", "level": "measured", "covers": [nid],
                                     "seq": seq, "by": "program"}]
                node["followup"] = ""
            else:
                node["status"] = "partial"
                node["followup"] = node.get("followup") or AUTO_FOLLOWUP
            node["filled_by"] = "program"
            node["history"].append({"seq": seq, "turn": turn, "what": "reconcile", "by": "program",
                                    "why": f"程式代填：{'R' + str(r['seq']) + ' 綠' if r else '沒有改動之後的綠收據'}"})
            filled.append(nid)
        tree["last_reconcile"] = {"seq": seq, "turn": turn, "goal_rev": tree.get("goal_rev", 1), "by": "program"}
        tree["status"] = "closed" if all(n.get("status") in ("done", "dropped") for n in tree["nodes"].values()) else "reconciled"
        return filled
    try:
        filled = update_locked(sid, fn)
    except (NeedGoalLockTimeout, NeedGoalCorrupt, OSError) as e:
        print(f"[NeedGoal] 程式代填完整對照失敗（只記錄，不影響收尾）：{type(e).__name__}: {e}", file=sys.stderr)
        return []
    if filled:
        _guard("auto_reconcile", sid, nodes=filled)
    return filled


def refresh_auto_evidence(sid: Any) -> int:
    """規則 RECEIPT_LATEST_AUTO 的後半：完整對照裡寫 latest 的收據，之後改了程式又跑綠 → 交付邊界時換成最新那筆綠的，
    不叫 AI 為同一件事重交一次對照。只換到「跑了同一組驗證」的新收據：同一條指令，或點名的案例檔涵蓋原本那筆的
    （原本那筆沒點名案例檔就只認同一條指令）——後來跑了別的測試不算重跑了這一項。沒有就不動（照舊算「改完沒重跑」）。回換了幾筆。"""
    def same_run(old: Dict[str, Any], new: Dict[str, Any]) -> bool:
        if str(old.get("cmd") or "") == str(new.get("cmd") or ""):
            return True
        oc = set(old.get("cases") or [])
        return bool(oc) and oc <= set(new.get("cases") or [])

    def fn(doc: Dict[str, Any]) -> int:
        tree = active_tree(doc)
        greens = [r for r in doc.get("receipts") or [] if rr.receipt_green(r.get("verdicts"), r.get("exit"))]
        if not tree or not greens:
            return 0
        n = 0
        for node in tree["nodes"].values():
            for e in node.get("evidence") or []:
                old = _receipt_by_ref(doc, str(e.get("ref"))) if e.get("auto") and e.get("kind") == "receipt" else None
                new = next((r for r in reversed(greens) if old and same_run(old, r)), None)
                if new and int(new["seq"]) > int(old["seq"]):
                    e["ref"] = f"R{new['seq']}"
                    n += 1
        return n
    try:
        doc = load(sid)
        tree = active_tree(doc)
        if not tree or not any(e.get("auto") for v in tree["nodes"].values() for e in v.get("evidence") or []):
            return 0
        n = update_locked(sid, fn)
    except (NeedGoalLockTimeout, NeedGoalCorrupt, OSError) as e:
        print(f"[NeedGoal] 自動換最新收據失敗（照舊要重交對照）：{type(e).__name__}: {e}", file=sys.stderr)
        return 0
    if n:
        _guard("auto_refresh", sid, refs=n)
    return n


def _f2_text(doc: Dict[str, Any]) -> Optional[str]:
    tree = active_tree(doc)
    if not _needs_f2(tree):
        return None
    probs = _f2_problems(doc, tree)
    if not probs:
        return None
    return (f"[Guardian:ReconcileGate] (f2) 交付前的目標對照（{tree['id']}）缺：\n" + "\n".join(f"  - {p}" for p in probs) +
            "\n用 need_goal(action=reconcile, items=[每個還活著的節點：{id, status: done|partial|none|dropped, "
            "evidence: [{kind, ref, level, covers?}], followup?, note?, same_class?}]) 交完整對照：達成要附證據（寫碼類至少一筆沒紅的收據或"
            "讀碼級驗證案例；實測只能配收據，ref 寫 latest 由程式填最近一筆綠的（之後改了又跑綠會自動換新），要在最後一次改動之後跑）、推論最多標部分、部分／沒有寫 followup、"
            "放棄寫 note；達成可附 same_class（同類別處：找到的位置，或為什麼沒有）。\n目前的樹：\n" +
            brief_for(tree))


def _part_link_state(tree: Dict[str, Any], key: str) -> str:
    """定位帳（links.parts）裡這個部位掛的狀態：linked／none／dropped:<節點>／gone:<節點>。"""
    link = ((tree.get("links") or {}).get("parts") or {}).get(key)
    if not link:
        return "none"
    node = (tree.get("nodes") or {}).get(link.get("node"))
    if node is None:
        return f"gone:{link.get('node')}"
    return f"dropped:{link['node']}" if node.get("status") == "dropped" else "linked"


def _unlinked_parts(tree: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {k: v for k, v in ((tree or {}).get("parts_edited") or {}).items() if _part_link_state(tree, k) != "linked"}


def _relinked(sid: Any, doc: Dict[str, Any], config: Optional[Dict[str, Any]], state: Optional[Dict[str, Any]],
              transcript_path: str) -> Dict[str, Any]:
    """(f3) 判之前：寫碼類樹上沒掛目標的部位，先讓 OverviewHub 從 transcript 找補交的定位四行補掛；有掛上就重讀目標檔。"""
    tree = active_tree(doc)
    pending = _unlinked_parts(tree) if _needs_f2(tree) and transcript_path else {}
    if not pending:
        return doc
    from wg_overview import relink_parts
    return load(sid) if relink_parts(state, sid, transcript_path, config or {}, pending) else doc


def _f3_text(doc: Dict[str, Any]) -> Optional[str]:
    """規則 EDITED_PART_NEEDS_GOAL_NODE：目前寫碼類樹上改過程式檔的每個部位都要掛到活著的節點。"""
    tree = active_tree(doc)
    if not _needs_f2(tree):
        return None
    v = rr.edited_part_goal_verdict([(str(info.get("part") or key), list(info.get("files") or []), _part_link_state(tree, key))
                                     for key, info in (tree.get("parts_edited") or {}).items()])
    if not v.owed:
        return None
    return ("[Guardian:ReconcileGate] (f3) 改到的部位沒掛到目標：\n  " + rr.format_hit("f3", v) +
            "\n補交那個部位的定位四行（第四行指到目前樹裡活著的節點、括號寫這一塊的角色；根因層兩個候選＋選擇理由），"
            "收尾時會從對話補掛；這次改動不屬於任何節點 → 先 need_goal(action=add) 長一個子目標再指過去。")


def goal_gate_reason(sid: Any, triggered: bool, config: Optional[Dict[str, Any]],
                     state: Optional[Dict[str, Any]] = None, transcript_path: str = "") -> Optional[str]:
    """回合結束：(f1) 待對照由程式記進度（不擋）；(f2) 完整對照與 (f3) 改到的部位都掛目標只在交付邊界（triggered）判。
    記進度與收據 latest 往前換是記帳、不是閘：reconcile_gate.goal_gate=false 也照做（目標樹與收尾檢核附的樹要是現況）。
    只給主 session 用。開關看目標檔記的 cwd 所在專案（專案層關掉就不擋）。state／transcript_path 給 (f3) 補掛用。"""
    if not sid:
        return None
    doc = load(sid)
    if not cfg_for_cwd(config, str(doc.get("cwd") or ""))["enabled"]:
        return None
    if any(_owed(t) for t in doc["trees"].values()):
        auto_progress(sid, int((state or {}).get("turn_seq") or 0))
    if triggered and refresh_auto_evidence(sid):
        doc = load(sid)
    if not goal_gate_on(config):
        if triggered:
            auto_reconcile(sid, int((state or {}).get("turn_seq") or 0))
        return None
    parts = []
    f2 = _f2_text(doc) if triggered else None
    if f2:
        parts.append(f2)
        _guard("gate_f2", sid, tree=doc.get("active"))
    f3 = _f3_text(_relinked(sid, doc, config, state, transcript_path)) if triggered else None
    if f3:
        parts.append(f3)
        _guard("gate_f3", sid, tree=doc.get("active"))
    return "\n".join(parts) or None


def commit_gate(sid: Any, config: Optional[Dict[str, Any]], state: Optional[Dict[str, Any]] = None,
                transcript_path: str = "") -> Optional[str]:
    """commit 指令執行前：(f1)＋目前的寫碼類樹的 (f2)(f3)。缺了回 deny 理由。開關看目標檔記的 cwd 所在專案。"""
    if not sid or not goal_gate_on(config):
        return None
    try:
        doc = load(sid)
    except NeedGoalCorrupt as e:
        return f"[NeedGoal] commit 前：目標檔損毀，無法核對需求目標，一律擋：{e}\n{NO_TOOL_HINT}"
    if not cfg_for_cwd(config, str(doc.get("cwd") or ""))["enabled"]:
        return None
    if any(_owed(t) for t in doc["trees"].values()):
        auto_progress(sid, int((state or {}).get("turn_seq") or 0))
    if refresh_auto_evidence(sid):
        doc = load(sid)
    parts = [t for t in (_f2_text(doc), _f3_text(_relinked(sid, doc, config, state, transcript_path))) if t]
    if not parts:
        return None
    _guard("commit_blocked", sid, tree=doc.get("active"))
    return "[NeedGoal] commit 前的目標對照沒過，先補再 commit：\n" + "\n".join(parts) + "\n" + NO_TOOL_HINT


def reconcile_fresh(tree: Dict[str, Any]) -> bool:
    """最後一次完整對照還算數：對的是目前的目標版本，而且之後沒有新加（或被打開）還沒到終點的節點。"""
    lr = tree.get("last_reconcile") or {}
    return (bool(lr) and lr.get("goal_rev") == tree.get("goal_rev")
            and not any(v.get("status") in ("todo", "doing") for v in (tree.get("nodes") or {}).values()))


def _edited_since_reconcile(tree: Dict[str, Any]) -> List[str]:
    """最後一次對得上目標版本的完整對照之後改過的檔（沒對照過、或對照後目標改過＝這棵樹全部改檔），去重保序。"""
    lr = tree.get("last_reconcile") or {}
    after = int(lr.get("seq") or 0) if lr and lr.get("goal_rev") == tree.get("goal_rev") else -1
    return list(dict.fromkeys(str(e["path"]) for e in tree.get("edits") or []
                              if isinstance(e, dict) and e.get("path") and int(e.get("seq") or 0) > after))


def knowledge_gate_reason(sid: Any, triggered: bool, config: Optional[Dict[str, Any]], turn_seq: int,
                          since: Optional[int] = None) -> Optional[str]:
    """回合結束的記憶知識類輕樹 (f4)：屬記憶與報告類，呼叫端併進收尾報告那一份（擋滿第 3 次放行並記 reconcile_overflow，
    不問使用者）。KNOWLEDGE_EDIT_NEEDS_LIGHT_TREE 不看措辭：本使用者回合（since～turn_seq）沒樹時改了記憶知識類的檔；
    KNOWLEDGE_TREE_RECONCILE_AT_DELIVERY 只在交付邊界（triggered）：每棵沒結束的知識類樹（換題後的舊樹也算）最後一次完整對照之後
    還有改檔。只給主 session 用。"""
    if not sid or not goal_gate_on(config):
        return None
    doc = load(sid)
    if not cfg_for_cwd(config, str(doc.get("cwd") or ""))["enabled"]:
        return None
    tree = active_tree(doc)
    untreed = [] if tree else [str(e.get("path")) for e in doc.get("untreed") or []
                               if isinstance(e, dict) and rr.in_turn(e.get("turn"), turn_seq, since)]
    hits: List[str] = []
    v = rr.knowledge_light_tree_verdict(untreed)
    if v.owed:
        hits.append(rr.format_hit("f4", v) + "\n    → need_goal(action=set, goal=…) 寫一棵輕樹（一個節點即可，用使用者的話、"
                    "只寫目標），剛改的檔會自動掛進去；交付前再 reconcile。")
    for tid in _tree_ids(doc) if triggered else []:
        t = doc["trees"][tid]
        if t.get("status") == "closed":
            continue
        v = rr.knowledge_reconcile_verdict(t.get("kind"), _edited_since_reconcile(t), tid)
        if v.owed:
            hits.append(rr.format_hit("f4", v) + f"\n    → need_goal(action=reconcile, items=[{tid} 每個還活著的節點：{{id, status, "
                        "evidence?, followup?, note?}])：記憶知識類的「達成」不要求案例或收據，可指到改過的檔（kind=file、"
                        "level=read）；推論最多標部分。這些改動屬另一件新需求，就先 need_goal(action=set, new_task=true) 開新樹。")
    if not hits:
        return None
    _guard("gate_f4", sid, tree=doc.get("active"), turn_seq=turn_seq, hits=len(hits))
    return ("[Guardian:NeedGoal] (f4) 記憶知識類的輕樹（AI 自己補，不問使用者；本回合擋滿第 3 次放行並記帳）：\n"
            + "\n".join("  " + h for h in hits))


# ─── 報告、審查材料、續接單、壓縮重送 ─────────────────────────────────────────

def _said_summary(tree: Dict[str, Any], first_cap: int, cap: int, last: int) -> List[Dict[str, Any]]:
    said = tree.get("user_said") or []
    shown = said[:1] + said[1:][-last:]
    return [{"turn": s.get("turn"), "text": _clip(s.get("text"), first_cap if i == 0 else cap),
             **({"prior": True} if s.get("prior") else {})} for i, s in enumerate(shown)]


def snapshot_for_report(sid: Any, kinds: Tuple[str, ...] = ("code",)) -> Optional[Dict[str, Any]]:
    """收尾檢核報告附的目標樹：原話摘要＋節點＋對照結果；目前的樹類別不在 kinds 回 None。附之前先把 latest 收據往前換
    （RECEIPT_LATEST_AUTO），報告上的對照結果才是現況，AI 不會為了報告上的舊收據重交對照。"""
    refresh_auto_evidence(sid)
    try:
        doc = load(sid)
    except (NeedGoalCorrupt, OSError) as e:
        print(f"[NeedGoal] 收尾檢核附樹失敗：{e}", file=sys.stderr)
        return None
    tree = active_tree(doc)
    if not tree or tree.get("kind") not in kinds:
        return None
    nodes = tree.get("nodes") or {}
    lr = tree.get("last_reconcile") or {}
    probs = _f2_problems(doc, tree)
    return {
        "tree": tree["id"], "status": tree.get("status"), "kind": tree.get("kind"), "goal_rev": tree.get("goal_rev"),
        "root": _clip(nodes.get(tree["id"], {}).get("text"), 300),
        "user_said": _said_summary(tree, 500, 300, 3),
        "peer_said": [{"from": p.get("from"), "text": _clip(p.get("text"), 200)} for p in (tree.get("peer_said") or [])[-2:]],
        "nodes": [{"id": nid, "depth": _depth(nid), "status": nodes[nid].get("status"),
                   "clarity": nodes[nid].get("clarity"), "text": _clip(nodes[nid].get("text"), 200),
                   "evidence": [_evidence_text(e, doc) for e in nodes[nid].get("evidence") or []][:4],
                   "followup": _clip(nodes[nid].get("followup"), 200)} for nid in _ordered(tree)],
        "owed": len(_owed(tree)),
        "reconcile": {"turn": lr.get("turn"), "goal_rev": lr.get("goal_rev"), "ok": not probs, "problems": probs[:10]},
    }


REVIEW_CHARS = 1600   # 驗收審查的需求原話欄會頭尾採樣（codex-companion acceptance.GOAL_HEAD＋GOAL_TAIL）；三段要整段放得下


def review_material(sid: Any) -> str:
    """驗收審查材料：使用者原話（權威）、同伴轉述、目標樹（AI 的解讀）分開標示，總長 ≤ REVIEW_CHARS；沒有樹回空字串。"""
    try:
        doc = load(sid)
    except (NeedGoalCorrupt, OSError):
        return ""
    tree = active_tree(doc)
    if not tree:
        return ""
    out = ["【使用者原話（權威）】"]
    out += [f"- 第 {s.get('turn', '?')} 回合：{s['text']}" for s in _said_summary(tree, 500, 200, 2)] or ["- （沒有記到）"]
    peers = (tree.get("peer_said") or [])[-2:]
    if peers:                                    # 沒有同伴轉述就不印這段（同 render）
        out.append("【同伴轉述（別的 session 送來的話，不是使用者說的，不當權威）】")
        out += [f"- {p.get('from') or '?'}：{_clip(p.get('text'), 120)}" for p in peers]
    out.append("【目標樹（AI 自己的解讀，可能偏離原話；審查時以原話為準）】")
    head = "\n".join(out)
    out.append(render(tree, "compact", chars=max(200, REVIEW_CHARS - len(head) - 1)))
    return "\n".join(out)[:REVIEW_CHARS]


def _export_tree(tree: Dict[str, Any]) -> Dict[str, Any]:
    return {k: copy.deepcopy(v) for k, v in tree.items()
            if k not in ("edits", "links", "checkpoints", "parts_edited", "said_all")}   # said_all 最多 200 則×4000 字，續接單只帶 user_said


def handoff_block(sid: Any) -> str:
    """續接單的【需求目標樹】區塊：人讀段＋機讀 JSON；只帶狀態不是結束的樹，沒有回空字串。"""
    try:
        doc = load(sid)
    except (NeedGoalCorrupt, OSError):
        return ""
    trees = [doc["trees"][t] for t in _tree_ids(doc) if doc["trees"][t].get("status") != "closed"]
    if not trees:
        return ""
    out = ["## 【需求目標樹】", "",
           "（need_goal 產生；接手的 session 讀到這份續接單會自動匯入。使用者原話是權威，樹是上一個 session 的解讀。）", ""]
    for t in trees:
        nodes = t.get("nodes") or {}
        out.append(f"### {_header(t)}")
        said = _said_summary(t, 600, 300, 3)
        if said:
            out.append("- 使用者原話（權威）：")
            out += [f"  - 第 {s.get('turn', '?')} 回合：「{s['text']}」" for s in said]
        if t.get("peer_said"):
            out.append("- 同伴轉述（不是使用者說的）：")
            out += [f"  - {p.get('from') or '?'}：「{_clip(p.get('text'), 200)}」" for p in t["peer_said"][-2:]]
        out.append("- 節點：")
        for nid in _ordered(t):
            line = _node_line(nid, nodes[nid], True, doc)
            out.append("  " + line + ("（未解問題）" if nodes[nid].get("clarity") == "open" else ""))
        follow = [f"{nid}（{LABEL['status'].get(n.get('status'), '?')}）→ {_clip(n.get('followup'), 200)}"
                  for nid, n in nodes.items() if n.get("followup")]
        if follow:
            out.append("- 未完事項：" + "；".join(follow))
        out.append("")
    data = {"version": 1, "session_id": _base_sid(sid), "exported_at": wg_core._now_iso(), "active": doc.get("active"),
            "trees": [_export_tree(t) for t in trees]}
    out += ["<!-- need-goal:begin v1 -->", "```json", json.dumps(data, ensure_ascii=False), "```", "<!-- need-goal:end -->"]
    return "\n".join(out)


def _remap(nid: str, old: str, new: str) -> str:
    return new + nid[len(old):] if _under(nid, old) else nid


def _import_tree(doc: Dict[str, Any], t: Dict[str, Any], src_session: Any, path: str, turn: int) -> Optional[str]:
    old = str(t.get("id") or "")
    if not NODE_ID_FULL_RE.match(old) or "." in old:
        return None
    new = f"T{int(doc.get('next_tree', 1) or 1)}"
    seq = next_seq(doc)
    nodes: Dict[str, Any] = {}
    for nid, n in (t.get("nodes") or {}).items():
        if not isinstance(n, dict) or not _under(str(nid), old):
            continue
        nn = copy.deepcopy(n)
        nn["parent"] = _remap(str(n["parent"]), old, new) if n.get("parent") else None
        nn["evidence"] = [{**e, "prior": True, "covers": [_remap(str(c), old, new) for c in e.get("covers") or []]}
                          for e in n.get("evidence") or [] if isinstance(e, dict)]
        nn["history"] = list(n.get("history") or [])[-1:] + [
            {"seq": seq, "turn": turn, "what": "import", "why": f"從續接單匯入（原 {nid}）"}]
        for k, v in (("status", "todo"), ("clarity", "clear"), ("origin", "inferred"), ("text", ""),
                     ("followup", ""), ("note", "")):
            nn.setdefault(k, v)
        nodes[_remap(str(nid), old, new)] = nn
    if new not in nodes:
        return None
    doc["next_tree"] = int(doc.get("next_tree", 1) or 1) + 1
    doc["trees"][new] = {
        "id": new, "status": t.get("status") if t.get("status") in TREE_STATUS else "doing",
        "kind": t.get("kind") if t.get("kind") in ("code", "knowledge") else "knowledge", "goal_rev": 1,
        "created_turn": turn, "created_seq": seq,
        "user_said": [{**s, "prior": True} for s in t.get("user_said") or [] if isinstance(s, dict)][:SAID_MAX],
        "peer_said": [s for s in t.get("peer_said") or [] if isinstance(s, dict)][-SAID_MAX:],
        "links": {"parts": {}}, "edits": [], "node_last_edit": {}, "last_reconcile": None,
        "goal_changed": {"seq": seq, "turn": turn},
        "imported_from": {"session": src_session, "tree": old, "path": str(path),
                          "map": {k: _remap(k, old, new) for k in (t.get("nodes") or {})}},
        "checkpoints": [], "nodes": nodes,
    }
    return new


def import_handoff(sid: Any, text: str, path: str, turn: int) -> Dict[str, Any]:
    """讀續接單的 need-goal 區塊（取最後一塊）：每棵未結束的樹配新樹號、節點號換前綴，證據與原話標前一個 session。"""
    blocks = _BLOCK_RE.findall(text or "")
    if not blocks:
        return {"imported": [], "map": {}, "text": "", "skipped": "續接單裡沒有 need-goal 區塊"}
    raw = blocks[-1]
    try:
        data = json.loads(raw)
        trees_in = [t for t in data.get("trees") or [] if isinstance(t, dict) and t.get("status") != "closed"]
    except (json.JSONDecodeError, AttributeError) as e:
        return {"imported": [], "map": {}, "text": "", "skipped": f"need-goal 區塊的 JSON 壞了：{e}"}
    if str(data.get("session_id") or "") == _base_sid(sid):
        # 本 session 自己匯出的（壓縮或結束前寫的自動續接單）：樹還在目標檔裡，不重複匯入
        return {"imported": [], "map": {}, "text": "", "skipped": "這是本 session 自己匯出的樹，不重複匯入", "own": True}
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    norm = str(path).replace("\\", "/").lower()

    def fn(doc: Dict[str, Any]) -> Dict[str, Any]:
        done = next((i for i in doc.get("imports") or [] if i.get("path") == norm and i.get("sha") == sha), None)
        if done:
            return {"imported": [], "map": {}, "skipped": f"已匯入過（{'、'.join(done.get('trees') or [])}）"}
        mapping: Dict[str, str] = {}
        for t in trees_in:
            new = _import_tree(doc, t, data.get("session_id"), path, turn)
            if new:
                mapping[str(t["id"])] = new
        if not mapping:
            return {"imported": [], "map": {}, "skipped": "續接單裡沒有未結束的樹"}
        new_ids = list(mapping.values())
        doc["active"] = mapping.get(str(data.get("active") or ""), new_ids[-1])
        _attach_said(doc, doc["trees"][doc["active"]], turn)  # 本 session 匯入前的原話（常是開工句）接在前一個 session 的原話後面
        _adopt_untreed(doc, doc["trees"][doc["active"]])     # 沒樹時改的知識類檔掛進接續的那一棵（不看匯入順序）
        doc.setdefault("imports", []).append({"path": norm, "sha": sha, "at": wg_core._now_iso(), "trees": new_ids})
        events: List[Tuple[str, Dict[str, Any]]] = []
        roots = [ln for ln in (_check_root(doc, doc["trees"][t], turn, events) for t in new_ids) if ln]
        return {"imported": new_ids, "map": mapping, "skipped": None, "origin_events": events, "root_lines": roots,
                "text": render(active_tree(doc), "full", doc=doc)}

    res = update_locked(sid, fn)
    for event, kw in res.pop("origin_events", None) or []:
        _guard(event, sid, **kw)
    if res["imported"]:
        _guard("import", sid, trees=res["imported"], path=str(path))
        head = "、".join(f"{o}→{n}" for o, n in res["map"].items())
        res["text"] = (f"[NeedGoal] 從續接單匯入需求目標樹（{head}；前一個 session 的證據只供閱讀，之後改到的節點要交新證據）。"
                       "先用自己的話覆述目標與現況、確認樹還對，再接著做。\n"
                       + "".join(f"{ln}\n" for ln in res.get("root_lines") or []) + res.get("text", ""))
    else:
        res.setdefault("text", "")
    return res


def handoff_session_of(text: str) -> Optional[str]:
    """續接單最後一塊 need-goal 區塊是哪個 session 匯出的；沒有區塊或讀不出來回 None。"""
    blocks = _BLOCK_RE.findall(text or "")
    try:
        sid = json.loads(blocks[-1]).get("session_id") if blocks else None
    except (json.JSONDecodeError, AttributeError):
        return None
    return str(sid) if sid else None


def recovery_blob(sid: Any, limit: int) -> str:
    """壓縮後獨立重送的目標樹（不依附部位綜觀）：目前的樹 brief（樹根＋當前節點）＋其他未結束的樹是哪幾棵；原話與全樹要看用 read。"""
    try:
        doc = load(sid)
    except (NeedGoalCorrupt, OSError):
        return ""
    live = [doc["trees"][t] for t in _tree_ids(doc) if doc["trees"][t].get("status") != "closed"]
    tree = active_tree(doc)
    if not live and not tree:
        return ""
    out = ["【需求目標樹】（壓縮後重送；使用者原話是權威，樹是 AI 的解讀；原話與全樹用 need_goal(action=read)）"]
    if tree:
        out.append(brief(tree))           # 壓縮後 context 裡沒有寫入回覆送的樹了：照附樹根一行（不套 TREE_LINE_IN_HINTS）
    others = [t["id"] for t in live if not tree or t["id"] != tree["id"]]
    if others:
        out.append(f"其他未結束的樹：{'、'.join(others[:6])}" + ("…" if len(others) > 6 else ""))
    text = "\n".join(out)
    return text if len(text) <= limit else text[:max(0, limit - 1)] + "…"

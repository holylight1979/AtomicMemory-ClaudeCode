"""wg_second_opinion.py：G9 自動第二意見的事實收集（Stop 的 SecondOpinion 段用；判定在 wg_release_rules 的 G9 段）。

做什麼：
  auto_cfg       config `second_opinion.auto` 段＋預設（門檻：4 檔／150 行；高風險部位看部位表類別 gate，risky_prefixes 預設空）。
  turn_events    transcript 尾段裡本回合（最後一則使用者打字之後）的 second_opinion_start／result 呼叫與回傳；result 另記標頭段的
                 mode 與 note 行（start 在前面回合、本回合才取回的 job 照它判：SECOND_OPINION_RESULT_ACROSS_TURNS）。
  changed_lines  本 session 改過的程式檔對 HEAD 的改動行數（git diff --numstat HEAD；未追蹤的新檔算整檔行數；查不到 git 回 None）。
  risky_paths    命中 risky_prefixes（相對版控根，沒有就相對部位表根）或部位表該列類別是 gate 的檔。
  has_goal_tree  這個 session 有沒有需求目標樹（有樹時，材料沒帶到樹的那次 run 不算跑過）。
  not_closing    觸發看事實不看措辭（規則 SECOND_OPINION_FACT_TRIGGER）：每次收尾都判，只有還沒到收尾的 Stop 不判：中途問使用者
                 （最後一行是問句、沒宣告完成）或寫明之後工作還在繼續（仍在等、等待…回報、尚未開始），而且這個使用者回合沒交收尾那批；
                 欠帳不消，下一次收尾照欠。
  fingerprint    出口時的改檔指紋（規則 SECOND_OPINION_EXIT_FINGERPRINT）：交過「不需第二意見｜」或「等第二意見｜」之後，
                 指紋沒變就不再欠；變了（出口之後又改了程式）就再欠一次。mark_exit 記、check 比。
  owed_message   欠的時候那段話：收尾那批先附（wg_closing_round.so_pre_close，SECOND_OPINION_PRE_CLOSE）跟 Stop 擋同一段。
  check          上面的事實交給 wg_release_rules.second_opinion_verdict，回 (Verdict, 事實)；事實的 satisfied＝這次滿足了
                 （跑過或宣告不需），Stop 據此 mark_ok。本回合跑完的第二意見（result 回 done／failed／blocked）不管有沒有
                 宣告完成都記 second_opinion_ran[sid]＝{job, 回合, 那時改過的高風險檔}（check 會改 state，由 Stop 寫回）；
                 之後的回合把它當成上次審過的基準（規則 SECOND_OPINION_RAN_BEFORE）。四行在本回合任一則回覆裡有就算；宣告行與
                 「在等哪個 job」只看收尾這則（SECOND_OPINION_DECLINE_ACCEPTED、SECOND_OPINION_WAITING_NOT_DONE：等待中不算滿足，
                 事實 waiting 給 Stop 留帳）。
  mark_ok        滿足或使用者放行時記 second_opinion_ok[sid]＝回合、second_opinion_cover[sid]＝那時改過的高風險檔；
                 之後的修改（多半是採納意見）只有改到新的高風險檔、或之後新改的程式檔數再過門檻才再要求（規則
                 SECOND_OPINION_ONCE_PER_CLAIM：不准「採納意見再改碼 → 又欠一次」的連鎖）。
怎麼驗：python -X utf8 -m pytest -q hooks/verify/verify_g9_second_opinion.py
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import wg_release_rules as rr
from wg_core import find_vcs_root

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
GIT_TIMEOUT_S = 5.0
NEW_FILE_MAX_BYTES = 2_000_000     # 未追蹤新檔數行數時最多讀這麼多；更大的檔直接當成過門檻

DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "min_code_files": 4,
    "min_changed_lines": 150,
    "risky_prefixes": [],          # 高風險部位由部位表「類別＝gate」決定（_gate_part）；要額外列前綴寫在 config
    "max_blocks_per_turn": 1,
}
GATE_KIND = "gate"                  # 部位表「類別」欄的原字（overview_hub.parse_map 只分 knowledge／code，這裡讀原字）
LETTER = "第二意見"                 # 擋訊息的條目字母（第二意見閘自己的預算照它計次；不在 reconcile_gate.block_letters 裡）
GATE = "second_opinion"             # wg_release 的閘名（last_block／pending_release／user_released）與 guard log 名
START_SUFFIX = "__second_opinion_start"
RESULT_SUFFIX = "__second_opinion_result"
EXIT = "second_opinion_exit"        # state 鍵：{sid: {"fp", "via", "turn"}}（出口時的改檔指紋）
PRE_CLOSE = "second_opinion_pre_close"   # state 鍵：{sid: {"uturn", "owed"}}（這個使用者回合交過收尾那批；wg_closing_round 記）
REDO_VIA = ("declined", "waiting")  # 出口之後又改了程式就再欠的出口；跑過（ran）照 SECOND_OPINION_ONCE_PER_CLAIM
EXIT_COVERS = "SECOND_OPINION_EXIT_FINGERPRINT"   # 出口蓋住這組改動時 Verdict 的規則名


def auto_cfg(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = (((config or {}).get("second_opinion") or {}).get("auto")) or {}
    out = dict(DEFAULTS)
    out.update({k: v for k, v in raw.items() if not str(k).startswith("_")})
    return out


# ─── 本回合的 start／result ─────────────────────────────────────────────

def _blocks(o: Dict[str, Any]) -> List[Dict[str, Any]]:
    msg = o.get("message") if isinstance(o.get("message"), dict) else {}
    content = msg.get("content")
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _result_text(block: Dict[str, Any]) -> str:
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(str(x.get("text") or "") for x in c if isinstance(x, dict))
    return ""


def _field(text: str, key: str) -> str:
    """MCP 回傳的 `key: value` 行（second-opinion.js 的輸出格式）；沒有回空字串。"""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(key + ":"):
            return s[len(key) + 1:].strip()
    return ""


def _notes(text: str) -> List[str]:
    return [ln.strip()[len("note:"):].strip() for ln in text.splitlines() if ln.strip().startswith("note:")]


def _turn_records(transcript_text: str) -> List[Dict[str, Any]]:
    """本回合的 transcript 紀錄（規則 TURN_SINCE_USER_PROMPT：最後一則使用者打字之後；尾段切掉起點就整段算）。"""
    from wg_evasion import is_turn_start
    recs: List[Dict[str, Any]] = []
    for raw in str(transcript_text or "").splitlines():
        try:
            o = json.loads(raw)
        except ValueError:
            continue
        if isinstance(o, dict):
            recs.append(o)
    begin = 0
    for i, o in enumerate(recs):
        if is_turn_start(o):
            begin = i + 1
    return recs[begin:]


# 明說沒完成（「還沒做完」「完成…尚未」）：同 forbidden-phrases.json completion_claim 排除詞的前兩條。
# 「進行中」「等待結果」這類只在最後一則才算數（前面的回覆常是在講別人的檔或某一步，不是在講這次交付）
_COMPLETION_NEG_RE = re.compile(r"(?:還沒|還未|尚未|尚待|未|沒有?)[^，。！？\n]{0,8}(?:完成|做完|解決|收尾|搞定|完工|結案)"
                                r"|(?:完成|做完|解決|收尾|搞定|完工|結案)[^，。！？\n]{0,6}"
                                r"(?:尚未|還沒|還未|未完|沒完|未滿足|沒做完|未達|待補|待修)")


def turn_completion_text(transcript_text: str) -> str:
    """本回合宣告完成的那一則文字；沒宣告回空字串。最後一則有完成詞或狀態詞（排除詞：還沒、進行中、等待…）→ 照它（claims_completion）；
    完全沒提 → 往前看：說過完成、之後沒有明說沒完成，就是最後說完成的那一則。別的閘擋下後的補件回覆常只補那道閘要的行、不再重說完成，
    只看最後一則會被補件那則蓋掉（例：說「做完了」→ ReadingPath 擋 → 補件只寫拐彎判斷 → 第二意見閘一次都沒擋）。
    往前看的每一則跟最後一則同一套判法：這則宣告完成（claims_completion，逐句看）就記它；沒宣告、又明說沒完成才清掉
    （規則 COMPLETION_CLAIM_PER_SENTENCE：「我還沒動git：完成的三件…。全部做完了」是宣告完成，開頭那句的否定不清掉它）。"""
    from wg_evasion import _COMPLETION_CLAIM_RE, _COMPLETION_EXCLUDE_RE, claims_completion
    texts = turn_texts(transcript_text)
    if not texts:
        return ""
    last = texts[-1][-2000:]
    if _COMPLETION_CLAIM_RE.search(last) or _COMPLETION_EXCLUDE_RE.search(last):
        return texts[-1] if claims_completion(texts[-1]) else ""
    claimed = ""
    for t in texts[:-1]:
        if claims_completion(t):
            claimed = t
        elif _COMPLETION_NEG_RE.search(t[-2000:]):
            claimed = ""
    return claimed


def turn_texts(transcript_text: str) -> List[str]:
    """本回合每一則 assistant 文字，依出現順序。"""
    return [str(b.get("text") or "") for o in _turn_records(transcript_text) if o.get("type") == "assistant"
            for b in _blocks(o) if b.get("type") == "text"]


def section_text(text: str, transcript_text: str) -> str:
    """分歧裁決四行要看的那一則：收尾這則四行齊就用它；否則本回合較早、四行齊的最近一則（被別的閘擋下補件的回覆不必重抄）；
    都不齊回收尾這則（擋訊息照它列缺什麼）。"""
    for t in [text, *reversed(turn_texts(transcript_text))]:
        if t and not rr.second_opinion_section_missing(t):
            return t
    return text


def turn_events(transcript_text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """本回合（_turn_records）的 (starts, results)：starts＝[{mode, kind, job_id, status, reason, notes}]、
    results＝[{job_id, status, reason, mode, notes, at}]，依出現順序。result 的 mode、notes 只讀標頭段（第一個空行之前；後面是
    Codex 回覆全文），給 start 在前面回合的 job 判（SECOND_OPINION_RESULT_ACROSS_TURNS）。"""
    calls: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    starts: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []
    for o in _turn_records(transcript_text):
        for b in _blocks(o):
            name = str(b.get("name") or "")
            if b.get("type") == "tool_use" and (name.endswith(START_SUFFIX) or name.endswith(RESULT_SUFFIX)):
                inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                calls[str(b.get("id") or "")] = (name, inp)
                continue
            call = calls.get(str(b.get("tool_use_id") or "")) if b.get("type") == "tool_result" else None
            if call is None:
                continue
            text = _result_text(b)
            ev = {"status": _field(text, "status"), "reason": _field(text, "reason")}
            if call[0].endswith(START_SUFFIX):
                starts.append({"mode": call[1].get("mode"), "kind": call[1].get("kind"),
                               "job_id": _field(text, "job_id") or "-", "notes": _notes(text), **ev})
            else:
                head = text.split("\n\n", 1)[0]
                results.append({"job_id": str(call[1].get("job_id") or "").strip(), "at": str(o.get("timestamp") or ""),
                                "mode": _field(head, "mode"), "notes": _notes(head), **ev})
    return starts, results


# ─── 改動行數 ───────────────────────────────────────────────────────────

def _git(root: Path, args: List[str]) -> Optional[str]:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=GIT_TIMEOUT_S, creationflags=_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _rel(path: str, root: Path) -> Optional[str]:
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def _new_file_lines(path: Path) -> int:
    try:
        if path.stat().st_size > NEW_FILE_MAX_BYTES:
            return 10 ** 6
        return path.read_bytes().count(b"\n") + 1
    except OSError:
        return 0


def _root_lines(root: Path, rels: List[str]) -> Optional[int]:
    """一個 git 根：numstat 對 HEAD 的增刪行＋未追蹤新檔的整檔行數。git 失敗（含沒有 HEAD）回 None。"""
    numstat = _git(root, ["diff", "--numstat", "HEAD", "--", *rels])
    tracked = _git(root, ["ls-files", "-z", "--", *rels])
    if numstat is None or tracked is None:
        return None
    total = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
            total += int(parts[0]) + int(parts[1])
    known = {t for t in tracked.split("\0") if t}
    for rel in rels:
        if rel not in known:
            total += _new_file_lines(root / rel)
    return total


def changed_lines(paths: Sequence[str]) -> Optional[int]:
    """程式檔對 HEAD 的改動行數（各 git 根加總）；沒有任何檔在 git 根、或有一個根查失敗 → None（呼叫端只看檔數）。"""
    by_root: Dict[Path, List[str]] = {}
    for p in paths:
        hit = find_vcs_root(Path(p).parent)
        rel = _rel(p, hit[1]) if hit and hit[0] == "git" else None
        if rel is not None:
            by_root.setdefault(hit[1], []).append(rel)
    if not by_root:
        return None
    total = 0
    for root, rels in by_root.items():
        n = _root_lines(root, rels)
        if n is None:
            print(f"[Guardian:SecondOpinion] {root} 查不到 git 改動行數，只看檔數", file=sys.stderr)
            return None
        total += n
    return total


# ─── 高風險部位 ─────────────────────────────────────────────────────────

def _cells(line: str) -> List[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _raw_kind(map_text: str, row_line: str) -> str:
    """部位表那一列「類別」欄的原字（小寫、去反引號）；表頭沒有類別欄回空字串。欄位對法與 overview_hub.parse_map 相同（表頭格索引）。"""
    for ln in map_text.splitlines():
        if not ln.lstrip().startswith("|") or "類別" not in ln:
            continue
        idx = next((i for i, c in enumerate(_cells(ln)) if "類別" in c), None)
        row = _cells(row_line)
        return row[idx].strip("` ").lower() if idx is not None and idx < len(row) else ""
    return ""


def _map_of(path: str) -> Optional[Tuple[Path, str]]:
    try:
        from overview_hub import find_map
    except ImportError:
        return None
    found = find_map(str(path))
    if not found:
        return None
    try:
        return found[0], found[1].read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"[Guardian:SecondOpinion] 部位表 {found[1]} 讀不到，不判 gate 類別：{type(e).__name__}: {e}", file=sys.stderr)
        return None


def _gate_part(path: str, found: Optional[Tuple[Path, str]]) -> bool:
    if not found:
        return False
    from overview_hub import match_row, parse_map
    row = match_row(str(path), found[0], parse_map(found[1]), anchored=True)
    return bool(row) and _raw_kind(found[1], row["line"]) == GATE_KIND


def _prefix_hit(rel: str, prefix: str) -> bool:
    pre = str(prefix or "").replace("\\", "/").strip().lower()
    if not pre:
        return False
    return rel.startswith(pre) if pre.endswith("/") else (rel == pre or rel.startswith(pre + "/"))


def risky_paths(paths: Sequence[str], prefixes: Sequence[str]) -> List[str]:
    """命中 risky_prefixes（相對版控根；不在版控就相對部位表根）或部位表該列類別是 gate 的檔，照輸入順序。"""
    out: List[str] = []
    for p in paths:
        found = _map_of(p)
        hit = find_vcs_root(Path(p).parent)
        root = hit[1] if hit else (found[0] if found else None)
        rel = (_rel(p, root) or "").lower() if root else ""
        if (rel and any(_prefix_hit(rel, pre) for pre in prefixes)) or _gate_part(p, found):
            out.append(p)
    return out


# ─── 判定 ───────────────────────────────────────────────────────────────

def _mod_turn(m: Dict[str, Any]) -> int:
    return int((m or {}).get("last_turn_seq") or (m or {}).get("turn_seq") or 0)


def _later(a: str, b: str) -> bool:
    """時間字串 a 晚於 b（ISO 8601，轉 UTC 比）；任一邊空或解析不了 → False（當成不晚於，照算審過）。"""
    from datetime import datetime, timezone

    def utc(s: str):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
        return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)
    ua, ub = (utc(a) if a else None), (utc(b) if b else None)
    return bool(ua and ub and ua > ub)


def _job_started_at(job_id: str) -> str:
    """job_id 開頭的開 job 時間（tools/second-opinion/run.py 用本地時間 %Y%m%d-%H%M%S）→ 帶本地時區的 ISO；解析不了回空字串。"""
    from datetime import datetime
    try:
        return datetime.strptime(str(job_id)[:15], "%Y%m%d-%H%M%S").astimezone().isoformat(timespec="seconds")
    except ValueError:
        return ""


def has_goal_tree(session_id: str) -> bool:
    """這個 session 有沒有需求目標樹（有樹時，材料沒帶到樹的 run 不算跑過）。目標檔讀不到或壞了 → 當有（fail-closed）並浮 stderr。"""
    try:
        import wg_need_goal as ng
        return ng.active_tree(ng.load(session_id)) is not None
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:SecondOpinion] 讀不到需求目標樹，當成有樹（材料要帶到樹才算跑過）：{type(e).__name__}: {e}", file=sys.stderr)
        return True


_QUESTION_END_RE = re.compile(r"(?:[?？]|嗎|呢)[\s。.」』）)*]*$")


def not_closing(state: Dict[str, Any], session_id: str, text: str, user_turn: int) -> str:
    """規則 SECOND_OPINION_FACT_TRIGGER 不判的 Stop（還沒到收尾）→ 回哪一類，是收尾回空字串。這個使用者回合交過收尾那批
    （closing_call，wg_closing_round 記在 PRE_CLOSE）就一定是收尾。兩類：
      pending   寫明這則之後工作還在繼續：wg_evasion 判完成的排除詞第一類（仍在等、等待…回報、尚未開始；claims_completion 整則不算的
                那組，同一份詞，看最後 2000 字）；
      question  中途問使用者：收尾這則最後一行（程式碼區塊外）是問句、這則沒宣告完成。
    欠帳不消，下一次收尾照欠。"""
    if int((((state.get(PRE_CLOSE) or {}).get(session_id)) or {}).get("uturn") or -1) == int(user_turn):
        return ""
    from wg_evasion import _COMPLETION_PENDING_RE, claims_completion
    if _COMPLETION_PENDING_RE.search(str(text or "")[-2000:]):
        return "pending"
    lines = [ln.strip() for ln in rr._so_lines(text) if ln.strip()]
    return "question" if lines and _QUESTION_END_RE.search(lines[-1]) and not claims_completion(text) else ""


def _code_entries(own_mod_files: Sequence[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    from wg_code_path import writes_code
    from wg_verify_ledger import git_launcher, session_scratch
    return [m for m in own_mod_files if (m or {}).get("path") and writes_code(str(m["path"]), config)
            and not session_scratch(str(m["path"]))           # 規則 SESSION_SCRATCH_NOT_CODE：暫存區的一次性腳本不數
            and not git_launcher(str(m["path"]))]             # 規則 LAUNCHER_NOT_CODE：worktree 根的一次性 git 啟動器不數


def fingerprint(code: Sequence[Dict[str, Any]]) -> str:
    """規則 SECOND_OPINION_EXIT_FINGERPRINT：本 session 改過的程式檔（路徑、最後改的時間與回合）的指紋；之後再改任何一支就變。"""
    keys = sorted({(rr.canon_path(m["path"]), str(m.get("last_at") or m.get("at") or ""),
                    int(m.get("last_turn_seq") or m.get("turn_seq") or 0)) for m in code})
    return hashlib.sha1(json.dumps(keys, ensure_ascii=False).encode("utf-8")).hexdigest()[:16] if keys else ""


def mark_exit(state: Dict[str, Any], session_id: str, turn: int, facts: Dict[str, Any]) -> bool:
    """交了出口（facts 的 exit_via：declined／waiting／ran）就記出口時的改檔指紋；沒交出口不動 → 回有沒有改 state。"""
    via, fp = str(facts.get("exit_via") or ""), str(facts.get("fingerprint") or "")
    if not via or not fp:
        return False
    rec: Dict[str, Any] = {"fp": fp, "via": via, "turn": int(turn or 0)}
    if via == "waiting":
        rec["jobs"] = [str(j) for j in facts.get("waiting") or []]      # 取回這些 job 的那一回合要四行（不靠背景看守）
    state.setdefault(EXIT, {})[session_id] = rec
    return True


def owed_message(v: rr.Verdict, facts: Dict[str, Any], config: Dict[str, Any]) -> str:
    """欠第二意見時的那段話：收尾那批先附（SECOND_OPINION_PRE_CLOSE）跟 Stop 擋（SECOND_OPINION_REQUIRED）用同一段：先提示後擋，
    講同一件事、同一個格式，照提示做了就不會被擋。"""
    from wg_closing_round import so_background_on
    hint = rr.second_opinion_hint_background() if so_background_on(config) else rr.second_opinion_hint()
    return (f"[Guardian:SecondOpinion] 收尾要處理第二意見（本 session 改了 {facts.get('code_files')} 個程式檔）\n"
            f"{rr.format_hit(LETTER, v)}\n{hint}")


def check(state: Dict[str, Any], session_id: str, own_mod_files: Sequence[Dict[str, Any]], text: str,
          transcript_text: str, config: Dict[str, Any], cfg: Dict[str, Any], closing: bool
          ) -> Tuple[rr.Verdict, Dict[str, Any]]:
    """SecondOpinion Gate 的事實＋判定。git 只在檔數與高風險部位都沒觸發時才查（行數是第三個條件）。
    closing＝這次是收尾（規則 SECOND_OPINION_FACT_TRIGGER：不看有沒有說完成，只有還沒到收尾的 not_closing 不算）；
    收尾那批的提示也用這支判（text 空：收尾還沒寫）。"""
    code = _code_entries(own_mod_files, config)
    uniq: Dict[str, str] = {}      # 同一個檔不同寫法只算一次（SAME_FILE），保留原寫法給 git pathspec（大小寫敏感）
    for m in code:
        uniq.setdefault(rr.canon_path(m["path"]), str(m["path"]))
    paths = list(uniq.values())
    facts: Dict[str, Any] = {"code_files": len(paths), "triggers": [], "satisfied": False, "decline": "",
                             "fingerprint": fingerprint(code), "exit_via": ""}
    claims_done = bool(closing)
    if not paths:
        return rr.second_opinion_verdict(claims_done, [], False, [], text), facts
    starts, results = turn_events(transcript_text)
    runs_now = rr.second_opinion_runs(starts, results, has_tree=has_goal_tree(session_id)) if (starts or results) else []
    # 規則 SECOND_OPINION_RESULT_ACROSS_TURNS：start 不在本回合的 job，不是本 session 開的（foreign）、或開 job 之後又改過程式檔
    # （stale：沒審到後來的改動）都不算
    started_now = {str(s.get("job_id")) for s in starts}
    edits_at = [str(m.get("last_at") or m.get("at") or "") for m in code]
    own8 = re.sub(r"[^0-9a-z]", "", str(session_id or "").lower())[:8]    # 同 tools/second-opinion/run.py 組 job_id 的 sid8

    def carried(j: str, st: str) -> str:
        if j in started_now or not (st in rr.SO_RAN or st == "running"):
            return st
        if (j.split("-") + ["", "", ""])[2] != own8:
            return "foreign"
        return "stale" if any(_later(at, _job_started_at(j)) for at in edits_at) else st
    runs_now = [(j, carried(j, st)) for j, st in runs_now]
    risky_memo: List[List[str]] = []

    def risky_now() -> List[str]:
        if not risky_memo:
            risky_memo.append(risky_paths(paths, list(cfg.get("risky_prefixes") or [])))
        return risky_memo[0]
    ran_now = [j for j, st in runs_now if st in rr.SO_RAN]
    rec = ((state.get("second_opinion_ran") or {}).get(session_id)) or {}
    if ran_now and rec.get("job") != ran_now[-1]:
        # 規則 SECOND_OPINION_RAN_BEFORE：本回合跑完就記下（沒宣告完成也記；start 在前面回合、本回合才取回也算：
        # SECOND_OPINION_RESULT_ACROSS_TURNS），之後的回合以它為審過的基準；
        # 審過的高風險檔只算結果回來那一刻之前改的（結果之後才改的另一支高風險檔不算審過）
        done_at = next((str(r.get("at") or "") for r in reversed(results) if r.get("job_id") == ran_now[-1]), "")
        last_at = {rr.canon_path(m["path"]): str(m.get("last_at") or m.get("at") or "") for m in code}
        seen = [p for p in risky_now() if not (done_at and _later(last_at.get(rr.canon_path(p), ""), done_at))]
        rec = {"job": ran_now[-1], "turn": int(state.get("turn_seq") or 0), "at": done_at,
               "risky": [rr.canon_path(p) for p in seen]}
        state.setdefault("second_opinion_ran", {})[session_id] = rec
    # 規則 SECOND_OPINION_DONE_NOTICE（背景開關開）：收尾寫過「等第二意見｜<job>」的 job，本回合取回跑完了＝接上那一刻，照宣告完成判四行
    # （不再說完成也要；判定、擋次照 SECOND_OPINION_REQUIRED）
    # 在等的 job：出口帳記的（SECOND_OPINION_EXIT_FINGERPRINT，不靠背景開關、前面的閘擋下也記了）＋背景看守記的
    ex = ((state.get(EXIT) or {}).get(session_id)) or {}
    waited_back = False
    if results:
        from wg_closing_round import so_background_on, waited_jobs
        waited = set(ex.get("jobs") or []) if ex.get("via") == "waiting" else set()
        if so_background_on(config):
            waited |= set(waited_jobs(state, session_id))
        waited_back = any(r.get("job_id") in waited and r.get("status") in rr.SO_RAN for r in results)
    claims_done = claims_done or waited_back
    if not claims_done:
        facts["deferred"] = True                     # 改過程式、這次還沒到收尾：不判，欠帳留給下一次收尾
        return rr.second_opinion_verdict(claims_done, [], False, [], text), facts
    # 規則 SECOND_OPINION_EXIT_FINGERPRINT：交過出口、之後沒再改程式（指紋相同）→ 這組改動欠的已經交了，不再欠；
    # 在等的結果本回合取回了不在此列（要接上四行）
    if ex.get("fp") and ex.get("fp") == facts["fingerprint"] and not waited_back:
        facts["covered"] = str(ex.get("via") or "")
        return rr.Verdict(EXIT_COVERS, False, f"上次交了出口（{facts['covered']}）之後沒再改程式"), facts
    ok_turn = int(((state.get("second_opinion_ok") or {}).get(session_id)) or 0)
    risky = risky_now()
    min_files, min_lines = int(cfg.get("min_code_files", 4)), int(cfg.get("min_changed_lines", 150))
    covered = set(((state.get("second_opinion_cover") or {}).get(session_id) or {}).get("risky") or [])
    # 前面回合跑完的才當審過的基準：不是本回合的 job，或是本回合又取一次結果、但記下它的是前面的使用者回合
    prior = bool(rec) and (rec.get("job") not in {j for j, _s in runs_now}
                           or int(rec.get("turn") or 0) < rr.user_turn(state, int(state.get("turn_seq") or 0)))
    if prior:
        ok_turn = max(ok_turn, int(rec.get("turn") or 0))
        covered |= set(rec.get("risky") or [])
    after = {rr.canon_path(m["path"]) for m in code if _mod_turn(m) > ok_turn}
    if prior and rec.get("at"):
        after |= {rr.canon_path(m["path"]) for m in code if _later(str(m.get("last_at") or m.get("at") or ""), rec["at"])}
    new_risky = [p for p in risky if rr.canon_path(p) in after and rr.canon_path(p) not in covered]
    # 規則 SECOND_OPINION_ONCE_PER_CLAIM：審過之後的修改只在改到新的高風險檔、或之後新改的程式檔數再過門檻時才算新一輪
    # 出口是不需／等第二意見、之後又改了程式（指紋變了）→ 新的一組改動，再欠一次（SECOND_OPINION_EXIT_FINGERPRINT）
    fresh = ok_turn == 0 or bool(new_risky) or len(after) >= min_files or (ex.get("via") in REDO_VIA and bool(ex.get("fp")))
    lines = None if (len(paths) >= min_files or risky) else changed_lines(paths)
    triggers = rr.second_opinion_triggers(len(paths), lines, risky, min_files, min_lines)
    runs = runs_now if (triggers and fresh) else []
    # 四行可以在本回合較早那則；宣告行與在等哪個 job 只看收尾這則（SECOND_OPINION_DECLINE_ACCEPTED）
    v = rr.second_opinion_verdict(claims_done, triggers, fresh, runs, section_text(text, transcript_text), closing=text)
    satisfied = bool(triggers and fresh and not v.owed and v.rule != rr.SO_WAITING)
    declined = v.rule == "SECOND_OPINION_DECLINED"
    facts.update(triggers=triggers, fresh=fresh, runs=runs, changed_lines=lines, risky=[rr.canon_path(p) for p in risky],
                 satisfied=satisfied, waiting=list(v.evidence) if v.rule == rr.SO_WAITING else [],
                 decline=(rr.second_opinion_decline(text) or "") if declined else "",
                 exit_via=("waiting" if v.rule == rr.SO_WAITING else "declined" if satisfied and declined
                           else "ran" if satisfied else ""))
    return v, facts


def mark_ok(state: Dict[str, Any], session_id: str, turn: int, facts: Dict[str, Any]) -> None:
    """第二意見這一輪了結（跑過、宣告不需、使用者放行）：記回合與那時改過的高風險檔（之後再改到它們不算新一輪）；
    交了出口就一併記出口時的改檔指紋（mark_exit）。"""
    state.setdefault("second_opinion_ok", {})[session_id] = turn
    cover = state.setdefault("second_opinion_cover", {})
    old = set(((cover.get(session_id) or {}).get("risky")) or [])
    cover[session_id] = {"turn": turn, "risky": sorted(old | set(facts.get("risky") or []))}
    mark_exit(state, session_id, turn, facts)

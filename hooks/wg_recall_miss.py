"""wg_recall_miss.py — 失念偵測（recall-miss）：庫有可防之 atom 但檢索未命中。

現有監控抓「不該注入而注入」（token 稅）；本模組抓對偶面——本 session 踩的坑，
庫中其實已有 atom 可預防，只因 trigger 檢索未命中而沒被注入（五遍行「失念」的
工程化）。SessionEnd 呼叫一次，純本地字串比對（複用 wg_atoms._kw_match 原語），
零 LLM 零 vector，<1s。

訊號源（皆為 state 既有欄位，不重跑任何萃取）：
- failing_tests：測試/lint 失敗（cmd + summary）
- evasion_events / evasion_flag：退避語命中（phrase + context）
- failure_kw：episodic 生成已在用的失敗萃取物——knowledge_queue 的 pitfall/
  failure 項 + 覆轍信號（edit_counts ≥3 檔名、retry_escalation）

精度守則（寧缺勿濫，與 wg_rescue 同哲學）：
- 命中 ≥2 個「不同」trigger 才算候選
- 泛用詞 trigger 不計入門檻：單字元、純數字、泛詞黑名單
  （wg_rescue._GENERIC 共用 + 失敗域 CJK 補充，同格式）
- 每 (session, atom) 一筆；無候選不寫檔

落地：Logs/recall-miss.jsonl
  {"at","session_id","atom","matched_triggers":[...],"evidence"≤200字,"source"}
浮出：memory-effect-report.py D 節（30 天聚合）+ health-weekly.py 黃燈（14 天 ≥3 次）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from wg_core import CLAUDE_DIR, MEMORY_DIR, _atom_debug_error, _now_iso, get_project_memory_dir
from wg_atoms import _kw_match, parse_memory_index
from wg_rescue import _GENERIC as _RESCUE_GENERIC

RECALL_MISS_LOG = CLAUDE_DIR / "Logs" / "recall-miss.jsonl"

_MIN_DISTINCT_TRIGGERS = 2   # 命中 ≥2 個不同（非泛用）trigger 才算候選
_EVIDENCE_CAP = 200          # evidence 片段上限（字）
_MAX_TEXTS = 40              # 問題文本數硬頂（防 state 異常膨脹拖慢 SessionEnd）
_TEXT_CAP = 600              # 單一文本長度上限

# 泛詞黑名單：wg_rescue._GENERIC 共用 + 失敗域高頻詞（單獨命中無鑑別力）。
# 小寫比對；trigger 完全等於這些詞才排除（多詞 trigger 如「測試上傳」不受影響）。
_GENERIC_TRIGGERS = frozenset(_RESCUE_GENERIC) | frozenset({
    "錯誤", "失敗", "問題", "修復", "修正", "測試", "警告", "異常",
    "bug", "error", "fail", "failed", "failure", "fix", "test", "tests",
    "debug", "warning", "issue", "retry",
})

_PURE_DIGIT_RE = re.compile(r"\d+")


def _is_generic_trigger(kw: str) -> bool:
    """單字元 / 純數字 / 泛詞黑名單 → 不計入 ≥2 門檻。"""
    kw = kw.strip().lower()
    if len(kw) <= 1:
        return True
    if _PURE_DIGIT_RE.fullmatch(kw):
        return True
    return kw in _GENERIC_TRIGGERS


def collect_problem_texts(state: Dict[str, Any]) -> List[Tuple[str, str]]:
    """從 state 既有失敗證據組「問題文本集」。回 [(source, text)]，無證據回 []。"""
    texts: List[Tuple[str, str]] = []

    for f in (state.get("failing_tests") or []):
        t = " ".join(x for x in (f.get("cmd", ""), f.get("summary", "")) if x).strip()
        if t:
            texts.append(("failing_tests", t[:_TEXT_CAP]))

    for e in (state.get("evasion_events") or []):
        p = str(e.get("phrase", "")).strip()
        if p:
            texts.append(("evasion", p[:_TEXT_CAP]))
    ev = state.get("evasion_flag")
    if isinstance(ev, dict):
        t = " ".join(x for x in (
            str(ev.get("phrase", "")), str(ev.get("context_excerpt", ""))
        ) if x).strip()
        if t:
            texts.append(("evasion", t[:_TEXT_CAP]))

    # failure_kw：episodic 生成同源的既有萃取物（不重跑 LLM）
    for kq in (state.get("knowledge_queue") or []):
        if kq.get("type") == "pitfall" or kq.get("source") == "failure":
            c = str(kq.get("content", "")).strip()
            if c:
                texts.append(("failure_kw", c[:_TEXT_CAP]))
    rut: List[str] = []
    for fpath, cnt in (state.get("edit_counts") or {}).items():
        try:
            if int(cnt) >= 3:
                rut.append(str(fpath).replace("\\", "/").rsplit("/", 1)[-1])
        except (TypeError, ValueError):
            continue
    if int(state.get("wisdom_retry_count", 0) or 0) >= 2:
        rut.append("retry_escalation")
    if rut:
        texts.append(("failure_kw", " ".join(rut)[:_TEXT_CAP]))

    return texts[:_MAX_TEXTS]


def collect_injected_atoms(state: Dict[str, Any]) -> Set[str]:
    """本 session 已注入過的 atom 名（小寫）——這些不算失念。

    來源聯集（保守寬取：任一管道注入過即排除）：injected_atoms（session 累積）、
    turn_injected（本 turn）、pre_compact_injected_atoms（壓縮前快照）、
    subagent_injections（sub-agent 注入）、rescue_watch owner（注入時建 watch）。
    """
    names: Set[str] = set()
    for n in (state.get("injected_atoms") or []):
        names.add(str(n).lower())
    for e in (state.get("turn_injected") or []):
        n = e.get("name") if isinstance(e, dict) else None
        if n:
            names.add(str(n).lower())
    for n in (state.get("pre_compact_injected_atoms") or []):
        names.add(str(n).lower())
    for rec in (state.get("subagent_injections") or []):
        for a in (rec.get("atoms") or []) if isinstance(rec, dict) else []:
            names.add(str(a).lower())
    for owner in (state.get("rescue_watch") or {}).values():
        atom_name = str(owner).partition("\t")[0]
        if atom_name:
            names.add(atom_name.lower())
    return names


def _load_active_atoms(state: Dict[str, Any]) -> List[Tuple[str, str, List[str]]]:
    """global 索引 + （cwd 對映到專案時）專案索引的 AtomEntry 清單。"""
    atoms = list(parse_memory_index(MEMORY_DIR))
    try:
        cwd = state.get("session", {}).get("cwd", "")
        proj_mem = get_project_memory_dir(cwd) if cwd else None
        if proj_mem and Path(proj_mem).resolve() != MEMORY_DIR.resolve():
            atoms += parse_memory_index(Path(proj_mem))
    except (OSError, ValueError) as e:
        _atom_debug_error("recall_miss:project_index", e)
    return atoms


def detect_recall_misses(
    session_id: str,
    state: Dict[str, Any],
    *,
    atoms: Optional[List[Tuple[str, str, List[str]]]] = None,
    log_path: Optional[Path] = None,
) -> List[dict]:
    """SessionEnd 一次性失念偵測。候選落 jsonl，回寫成功的 record 清單。

    無問題文本 / 無候選 → 不寫檔回 []。單筆寫失敗浮 debug 訊號、不阻斷其餘。
    """
    texts = collect_problem_texts(state)
    if not texts:
        return []
    injected = collect_injected_atoms(state)
    if atoms is None:
        atoms = _load_active_atoms(state)

    lowered = [(src, t, t.lower()) for src, t in texts]
    records: List[dict] = []
    seen: Set[str] = set()  # 每 (session, atom) 一筆（同名跨層索引亦去重）
    lp = log_path or RECALL_MISS_LOG

    for name, _rel, triggers in atoms:
        key = str(name).lower()
        if not name or key in injected or key in seen:
            continue
        matched_all: Set[str] = set()
        best: Optional[Tuple[str, str, int]] = None  # (source, text, hit數)
        for src, t, tl in lowered:
            hits = {
                kw for kw in triggers
                if kw and not _is_generic_trigger(kw) and _kw_match(kw, tl)
            }
            if hits:
                matched_all |= hits
                if best is None or len(hits) > best[2]:
                    best = (src, t, len(hits))
        if len(matched_all) < _MIN_DISTINCT_TRIGGERS or best is None:
            continue
        rec = {
            "at": _now_iso(),
            "session_id": session_id,
            "atom": name,
            "matched_triggers": sorted(matched_all),
            "evidence": best[1][:_EVIDENCE_CAP],
            "source": best[0],
        }
        try:
            lp.parent.mkdir(parents=True, exist_ok=True)
            with open(lp, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            seen.add(key)
            records.append(rec)
        except OSError as e:
            _atom_debug_error("recall_miss:write", e)
    return records

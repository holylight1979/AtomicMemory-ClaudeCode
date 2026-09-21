"""
handlers/ups_inject.py — UserPromptSubmit injection assemble 段

從 user_prompt_submit.py 拆出。
職責：把 search 段排序後的候選組裝成注入內容：
- hot/cold 分類（cold → 1-line 摘要）
- per-turn budget 硬上限（decide_atom_injection：ok/fallback/skip）
- section hints 局部抽取（SECTION_INJECT_THRESHOLD）
- Related-Edge Spreading（max_depth=1）
- ReadHits++ via lib.atom_access + 效用導向晉升提示（Wilson 下界）
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import json as _json_mod
import os
from datetime import datetime

from wg_core import CLAUDE_DIR, log_promotion_audit, _atom_debug_log, _estimate_tokens
from wg_atoms import (
    AtomEntry,
    _strip_atom_for_injection,
    bm25_match,
    spread_related, decide_atom_injection, compute_injection_rank,
    classify_hot_cold, format_cold_inject_line, atom_status_suffix, pointer_path,
    _strip_atom_for_injection_impression_only,
    SECTION_INJECT_THRESHOLD, _extract_sections,
    _TURN_BUDGET_LIMIT,
    read_atom_text, load_access_cached,
)

# budget skip 連續次數上限：首顆超 budget 不再直接 break（後面可能有塞得下的
# 小顆/impression fallback），連 impression fallback 都塞不下連續 N 次才停。
_BUDGET_SKIP_STREAK_MAX = 2

# injection_log state 條目上限（session 累積、超出裁最舊）——供 Stop 取用端
# 稽核閘（AtomAudit）判定「trigger 命中但僅一行路標注入且未 Read」。
_INJECTION_LOG_CAP = 100

# skip 路標只帶標題前 N 字：路標的用途是「知道有這張、去 Read」，不是把長標題整行塞進 context
_POINTER_TITLE_CAP = 80


_INJECTION_TURNS_LOG = CLAUDE_DIR / "Logs" / "injection-turns.jsonl"


def _append_injection_turn_log(
    session_id: str, turn_seq: int, records: List[Dict[str, Any]],
    used_tokens: int, config: Dict[str, Any], **extra: Any,
) -> None:
    """每 turn 一行落 Logs/injection-turns.jsonl：{at, session_id, turn_seq, ok, fallback,
    skip, cold, redundant, dropped, used_tokens, limit, ＋extra（最終裁切統計、輸出字元數）}。
    以「最終送達」為準：form 看 form_final（裁切後），沒有就看 form。state 的 injection_log
    會被 cap 裁掉且 session 結束後不易聚合；這份持久紀錄供 memory-effect-report。fail-open。"""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return  # verify 套件以假 session 跑真 ups_inject，不得污染正式統計
    try:
        counts = {"ok": 0, "fallback": 0, "skip": 0, "cold": 0, "redundant": 0,
                  "dropped": 0, "pointer_trim": 0, "dropped_trim": 0}
        for r in records:
            f = r.get("form_final") or r.get("form")
            if f in counts:
                counts[f] += 1
        row = {
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "session_id": session_id,
            "turn_seq": turn_seq,
            **counts,
            "used_tokens": int(used_tokens),
            "limit": int(_TURN_BUDGET_LIMIT),
            **extra,
        }
        _INJECTION_TURNS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _INJECTION_TURNS_LOG.open("a", encoding="utf-8") as fh:
            fh.write(_json_mod.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001 — 純遙測，不得影響注入
        _atom_debug_log("BUDGET", f"injection-turns log write error: {e}", config)


_REDUNDANCY_MIN_SHARED_DEFAULT = 3  # 與本 turn 已全文注入者 trigger 精確重疊 ≥N → 同題降節錄


def _redundancy_cfg(config: Dict[str, Any]) -> Tuple[bool, int]:
    rg = ((config or {}).get("injection") or {}).get("redundancy_gate") or {}
    return bool(rg.get("enabled", True)), int(rg.get("min_shared_triggers", _REDUNDANCY_MIN_SHARED_DEFAULT) or 0)


def _norm_triggers(triggers) -> set:
    return {str(t).strip().lower() for t in (triggers or []) if str(t).strip()}


def redundant_with(triggers, full_seen: List[Tuple[str, set]], min_shared: int) -> Optional[str]:
    """同題去冗判定：本 atom 的 trigger 與「本 turn 已全文注入」的某顆精確重疊 ≥ min_shared
    → 回該顆名稱（由它代表本題），否則 None。只比 trigger 精確字串（小寫），不比子字串——
    子字串重疊在泛 trigger（workflow-rules 類）上噪音大；全庫實測精確 ≥3 僅 4 對且皆真同題。"""
    if min_shared <= 0:
        return None
    mine = _norm_triggers(triggers)
    if len(mine) < min_shared:
        return None
    for seen_name, seen_set in full_seen:
        if len(mine & seen_set) >= min_shared:
            return seen_name
    return None


def _filter_related_by_relevance(
    related_entries: List[Tuple[AtomEntry, Path]], config: Dict[str, Any],
    access_cache: Optional[Dict[str, Dict]] = None,
    prompt: str = "",
    all_entries: Optional[List[AtomEntry]] = None,
) -> Tuple[List[Tuple[AtomEntry, Path]], List[Tuple[str, str]]]:
    """Phase C：related-spread 最小高訊號集裁切（憲法 Context Confusion 對策）。

    related atom 不命中 prompt（純連結擴散）= 最易成 distractor。本閘**只動 related-spread**，
    主迴圈（trigger/bm25/vector 命中 prompt）完全不碰 → 不誤殺 prompt 相關或新 atom。
    規則：① query gate：鄰居還要跟**這一題**沾得上邊——對全池跑 BM25，分數低於
    `related_gate.query_gate_min`（預設 3.5，正式候選門檻 7.0 的一半）的鄰居不擴散
    （以前只看歷史 activation 不看 query，Related 佔曝光 110/206 卻沒有題目相關性）；
    ② skip_demoted：剔除「已證明低效用」者（demote_candidate, n≥min_n；只動證明過的，
    絕不誤殺新/未證 atom）③ 依注入 rank 降序、保留前 max_related（最小集）。
    關閉 / 無 config / 匯入失敗 → 原樣回傳（fail-open）。回 (kept, skipped:[(name,reason)])。
    """
    ig = ((config or {}).get("injection") or {}).get("related_gate") or {}
    if not ig.get("enabled", True) or not related_entries:
        return related_entries, []
    try:
        from lib.atom_access import usefulness_demote_candidate
    except Exception:
        return related_entries, []  # fail-open
    skip_demoted = ig.get("skip_demoted", True)
    max_related = int(ig.get("max_related", 6))
    u = (config or {}).get("usefulness") or {}
    demote_min_n = int(u.get("demote_min_n", 5))
    z = float(u.get("wilson_z", 1.28))
    demote_lb = float(u.get("demote_lb", 0.35))

    skipped: List[Tuple[str, str]] = []
    # ① query gate（有 prompt 與全池才做；沒有就退回舊行為）
    query_ok: Optional[set] = None
    gate_mode = str(ig.get("query_gate", "bm25"))
    if gate_mode == "bm25" and prompt and all_entries:
        try:
            gate_min = float(ig.get("query_gate_min", 3.5))
            query_ok = {e[0] for e in bm25_match(prompt, all_entries, min_score=gate_min, top_k=200)}
        except Exception:
            query_ok = None  # fail-open：算不出來就不擋

    scored = []
    for entry in related_entries:
        (rname, rel_path, _t), base_dir = entry
        rdir = (base_dir / rel_path).parent if rel_path else (base_dir / "memory")
        if query_ok is not None and rname not in query_ok:
            skipped.append((rname, "no_query_relevance"))
            continue
        if skip_demoted:
            try:
                acc = load_access_cached(rdir / f"{rname}.md", access_cache)
                if usefulness_demote_candidate(acc, demote_lb=demote_lb, min_n=demote_min_n, z=z):
                    skipped.append((rname, "demoted"))
                    continue
            except Exception:
                pass
        scored.append(
            (compute_injection_rank(rname, rdir, config, access_cache), entry, rname)
        )
    scored.sort(key=lambda x: x[0], reverse=True)
    kept = [e for _, e, _ in scored[:max_related]]
    skipped.extend((nm, "min_set_cap") for _, _, nm in scored[max_related:])
    return kept, skipped


def assemble_injection(
    session_id: str,
    state: Dict[str, Any],
    config: Dict[str, Any],
    matched_with_dir: List[Tuple[AtomEntry, Path]],
    all_atoms: List[Tuple[AtomEntry, Path]],
    already_injected: List[str],
    atom_source: Dict[str, str],
    section_hints: Dict[str, List[Dict]],
    lines: List[str],
    caches: Optional[Dict[str, Dict]] = None,
    prompt: str = "",
) -> Tuple[List[str], Dict[str, Path]]:
    """組裝注入內容。mutate state（injected_atoms）/ append lines，
    回傳 (newly_injected, atom_source_dirs)。

    caches：search 段下傳的 {"content", "access"} 讀取快取（None 時自建空 dict，
    函式仍可獨測）——同 atom 本 prompt 只實讀一次。
    prompt：給 Related 擴散的 query gate 用（空字串＝不做 query gate，沿舊行為）。"""
    newly_injected: List[str] = []
    atom_source_dirs: Dict[str, Path] = {}
    if not matched_with_dir:
        return newly_injected, atom_source_dirs

    content_cache = (caches or {}).get("content")
    if content_cache is None:
        content_cache = {}
    access_cache = (caches or {}).get("access")
    if access_cache is None:
        access_cache = {}

    atom_lines: List[str] = []
    used_tokens = 0
    skip_streak = 0  # 連續 budget skip 計數（達 _BUDGET_SKIP_STREAK_MAX 才 break）
    redundancy_on, redundancy_min = _redundancy_cfg(config)
    full_seen: List[Tuple[str, set]] = []  # 本 turn 已全文注入 (name, trigger set)，同題去冗比對用
    rescue_pairs: List[Tuple[str, str]] = []  # (atom, 實注入內容) → 救援日誌 watch
    # 本 turn 注入記錄（name/path/source/form），尾段落 state["injection_log"]。
    # form: ok=全文 / fallback=印象 / skip=budget 一行 / cold=cold 一行
    inject_records: List[Dict[str, Any]] = []

    _atom_scopes: Dict[str, str] = (state.get("atom_index") or {}).get("scopes") or {}

    def _record(name_: str, path_: Path, rel_: str, source_: str, form_: str) -> None:
        inject_records.append({
            "name": name_,
            "path": str(path_),
            "rel": rel_ or f"{name_}.md",
            "source": source_,
            "form": form_,
            "scope": _atom_scopes.get(name_, ""),
        })

    acct = {"used": 0}  # atom 段實際送出的估算 token（含標頭／路標／cold 行，全部計費）

    def _push(block: str, name_: str, path_: Path, rel_: str, source_: str, form_: str,
              rescue_content: Optional[str] = None, final: bool = True) -> bool:
        """把一段 atom 文字放進輸出並記帳。塞不下 1,200 硬頂 → 不送、回 False；`final=True` 才記 dropped
        （中途嘗試全文／節錄失敗不記，避免同一顆留下 dropped＋skip 兩筆互相矛盾的紀錄）。
        以前 cold 行／skip 路標／標頭都不計費，硬頂形同虛設（離線重播 175 例 133 例超）。"""
        tok = _estimate_tokens(block)
        if acct["used"] + tok > _TURN_BUDGET_LIMIT:
            if final:
                _record(name_, path_, rel_, source_, "dropped")
            _atom_debug_log(
                "BUDGET",
                f"atom={name_} source={source_} form={form_} tokens={tok} decision={'dropped' if final else 'no_fit'} "
                f"used={acct['used']}/{_TURN_BUDGET_LIMIT}（硬頂）",
                config,
            )
            return False
        atom_lines.append(block)
        newly_injected.append(name_)
        acct["used"] += tok
        _record(name_, path_, rel_, source_, form_)
        if rescue_content:
            rescue_pairs.append((name_, rescue_content))
        return True

    for (name, rel_path, triggers), base_dir in matched_with_dir:
        atom_path = (base_dir / rel_path) if rel_path else (base_dir / "memory" / f"{name}.md")
        if not atom_path.exists():
            continue
        atom_source_dirs[name] = atom_path.parent
        raw_content = read_atom_text(atom_path, content_cache)
        if raw_content is None:
            continue

        source = atom_source.get(name, "vector")
        classification = classify_hot_cold(atom_path, source, access_cache=access_cache)

        if classification == "cold":
            cold_line = format_cold_inject_line(name, raw_content, rel_path, atom_path)
            if _push(cold_line, name, atom_path, rel_path, source, "cold"):
                _atom_debug_log(
                    "BUDGET",
                    f"atom={name} source={source} classification=cold (1-line) used={acct['used']}/{_TURN_BUDGET_LIMIT}",
                    config,
                )
            continue

        # 同題去冗：與本 turn 已全文注入者 trigger 重疊 ≥N → 只送表頭＋知識前兩句（節錄），
        # 註明由誰代表本題。不整張丟（精確度 > 省 token），但不重複講同一件事。
        if redundancy_on:
            covered_by = redundant_with(triggers, full_seen, redundancy_min)
            if covered_by:
                excerpt = _strip_atom_for_injection_impression_only(raw_content)
                block = f"[Atom:{name}] (same-topic → {covered_by}, 節錄)\n{excerpt}"
                if acct["used"] + _estimate_tokens(block) <= _TURN_BUDGET_LIMIT:
                    _push(block, name, atom_path, rel_path, source, "redundant", rescue_content=excerpt)
                    _atom_debug_log(
                        "REDUNDANCY",
                        f"atom={name} covered_by={covered_by} form=excerpt used={acct['used']}/{_TURN_BUDGET_LIMIT}",
                        config,
                    )
                    continue
                # 連節錄都塞不下 → 落到下方一般 budget 三態（會 skip 成一行路標）

        content = _strip_atom_for_injection(raw_content)
        content_tokens = _estimate_tokens(content)

        if name in section_hints and content_tokens > SECTION_INJECT_THRESHOLD:
            extracted = _extract_sections(content, section_hints[name])
            if extracted is not None:
                content = extracted

        # 三態決策以「含標頭的完整區塊」為準：先試全文，塞不下再試印象式節錄，都不行才路標。
        # decide_atom_injection 只算內文；標頭幾個 token 曾讓 1,199 tok 的內文被判 ok 卻在 _push 破頂，
        # 直接退成路標、丟掉可送的節錄（Codex #8 反例）。
        header_tok = _estimate_tokens(f"[Atom:{name}] (budget fallback)\n")
        decision, inject_content, _consumed = decide_atom_injection(
            raw_content, content, acct["used"] + header_tok
        )
        attempts = []
        if decision == "ok":
            attempts.append(("ok", f"[Atom:{name}]\n{inject_content}", inject_content))
            fb = _strip_atom_for_injection_impression_only(raw_content)
            if fb and _estimate_tokens(fb) < _estimate_tokens(inject_content):
                attempts.append(("fallback", f"[Atom:{name}] (budget fallback)\n{fb}", fb))
        elif decision == "fallback":
            attempts.append(("fallback", f"[Atom:{name}] (budget fallback)\n{inject_content}", inject_content))
        pushed = False
        for form, block, rescue_txt in attempts:
            if _push(block, name, atom_path, rel_path, source, form, rescue_content=rescue_txt, final=False):
                pushed = True
                skip_streak = 0
                if form == "ok":
                    full_seen.append((name, _norm_triggers(triggers)))
                _atom_debug_log(
                    "BUDGET",
                    f"atom={name} source={source} decision={form} used={acct['used']}/{_TURN_BUDGET_LIMIT}",
                    config,
                )
                break
        if pushed:
            continue

        # skip（連 impression fallback 都塞不下、或加上標頭就破頂）→ 1-line 路標後 continue：
        # 排序偏後仍可能有塞得下的小顆；連續 skip/dropped 達上限才視為 budget 真枯竭。
        first_line = content.split("\n", 1)[0].strip("# ").strip()[:_POINTER_TITLE_CAP]
        pointer = (
            f"[Atom:{name}] {first_line}{atom_status_suffix(raw_content)}"
            f" (full: Read {pointer_path(atom_path)})"
        )
        skip_streak += 1
        if _push(pointer, name, atom_path, rel_path, source, "skip"):
            _atom_debug_log(
                "BUDGET",
                f"atom={name} source={source} decision=skip streak={skip_streak} used={acct['used']}/{_TURN_BUDGET_LIMIT}",
                config,
            )
        if skip_streak >= _BUDGET_SKIP_STREAK_MAX:
            break

    # Related-Edge Spreading（+ Phase C 最小高訊號集裁切：剔除已證明低效用、依 rank 保留前 N）
    # 深度由 config injection.related_depth 控制（預設 1；0＝關閉），對齊評估器據此做關閉／現況對照。
    related_depth = int(((config or {}).get("injection") or {}).get("related_depth", 1))
    related_entries = spread_related(
        set(newly_injected), all_atoms, already_injected, max_depth=related_depth,
        content_cache=content_cache,
    ) if related_depth > 0 else []
    related_entries, related_skipped = _filter_related_by_relevance(
        related_entries, config, access_cache=access_cache,
        prompt=prompt, all_entries=[e[0] for e in all_atoms])
    for _sk_name, _sk_reason in related_skipped:
        _atom_debug_log("RELEVANCE", f"atom={_sk_name}(related) skipped={_sk_reason}", config)
    skip_streak = 0
    for (rname, rel_path, _triggers), base_dir in related_entries:
        if rname in newly_injected:
            continue
        rpath = (base_dir / rel_path) if rel_path else (base_dir / "memory" / f"{rname}.md")
        if not rpath.exists():
            continue
        atom_source_dirs[rname] = rpath.parent
        raw_content = read_atom_text(rpath, content_cache)
        if raw_content is None:
            continue
        related_classification = classify_hot_cold(rpath, "related", access_cache=access_cache)
        if related_classification == "cold":
            cold_line = format_cold_inject_line(rname, raw_content, rel_path, rpath)
            cold_line = cold_line.replace(f"[Atom:{rname}] (cold)", f"[Atom:{rname}] (related, cold)", 1)
            if _push(cold_line, rname, rpath, rel_path, "related", "cold"):
                _atom_debug_log(
                    "BUDGET",
                    f"atom={rname}(related) classification=cold (1-line) used={acct['used']}/{_TURN_BUDGET_LIMIT}",
                    config,
                )
            continue

        content = _strip_atom_for_injection(raw_content)
        header_tok = _estimate_tokens(f"[Atom:{rname}] (related, budget fallback)\n")
        decision, inject_content, _consumed = decide_atom_injection(
            raw_content, content, acct["used"] + header_tok
        )
        attempts = []
        if decision == "ok":
            attempts.append(("ok", f"[Atom:{rname}] (related)\n{inject_content}", inject_content))
            fb = _strip_atom_for_injection_impression_only(raw_content)
            if fb and _estimate_tokens(fb) < _estimate_tokens(inject_content):
                attempts.append(("fallback", f"[Atom:{rname}] (related, budget fallback)\n{fb}", fb))
        elif decision == "fallback":
            attempts.append(("fallback", f"[Atom:{rname}] (related, budget fallback)\n{inject_content}", inject_content))
        pushed = False
        for form, block, rescue_txt in attempts:
            if _push(block, rname, rpath, rel_path, "related", form, rescue_content=rescue_txt, final=False):
                pushed = True
                skip_streak = 0
                _atom_debug_log(
                    "BUDGET",
                    f"atom={rname}(related) classification=hot decision={form} used={acct['used']}/{_TURN_BUDGET_LIMIT}",
                    config,
                )
                break
        if pushed:
            continue
        first_line = content.split("\n", 1)[0].strip("# ").strip()[:_POINTER_TITLE_CAP]
        pointer = (
            f"[Atom:{rname}] (related) {first_line}{atom_status_suffix(raw_content)}"
            f" (full: Read {pointer_path(rpath)})"
        )
        skip_streak += 1
        if _push(pointer, rname, rpath, rel_path, "related", "skip"):
            _atom_debug_log(
                "BUDGET",
                f"atom={rname}(related) classification=hot decision=skip streak={skip_streak} used={acct['used']}/{_TURN_BUDGET_LIMIT}",
                config,
            )
        if skip_streak >= _BUDGET_SKIP_STREAK_MAX:
            break

    if atom_lines:
        lines.extend(atom_lines)
        state["injected_atoms"] = already_injected + newly_injected
        # 取用端稽核資料面：session 累積注入記錄（含 source/form），Stop AtomAudit
        # 閘據此判定「trigger 命中但僅一行路標且未 Read」。turn_seq 在 UPS 收尾才
        # +1（user_prompt_submit 尾段），此處先 +1 對齊「本 turn」序號。
        cur_turn = int(state.get("turn_seq", 0)) + 1
        for rec in inject_records:
            rec["turn_seq"] = cur_turn
        inj_log = state.setdefault("injection_log", [])
        inj_log.extend(inject_records)
        if len(inj_log) > _INJECTION_LOG_CAP:
            state["injection_log"] = inj_log[-_INJECTION_LOG_CAP:]
        if rescue_pairs:
            try:
                from wg_rescue import record_rescue_watch
                record_rescue_watch(state, rescue_pairs)
            except Exception as e:
                _atom_debug_log("RESCUE", f"watch record error: {e}", config)
    # 曝光（ReadHits）、回合注入 log、送達名單 → 等最終裁切後由 reconcile_injection_after_trim
    # 以「實際送出」提交；這裡只留待結算資料（記錄物件與 injection_log 共用，結算時就地改 form_final）。
    if inject_records:
        state["_turn_inject_pending"] = {
            "turn": int(state.get("turn_seq", 0)) + 1,
            "records": inject_records,
            "used_tokens": acct["used"],
        }

    return newly_injected, atom_source_dirs


_ATOM_HEAD_RE = re.compile(r"^\[Atom:(\S+)\]")


def reconcile_injection_after_trim(
    session_id: str, state: Dict[str, Any], config: Dict[str, Any], final_lines: List[str],
) -> List[str]:
    """最終送達提交：對照裁切後真正要送出的 lines，修正本 turn 的注入記帳。

    - 被 _truncate_context_by_activation 整塊丟掉的 atom → form_final=dropped_trim，
      從 injected_atoms 移除（下輪還能再注）、rescue watch 撤掉它的 token、不計曝光。
    - 被降成一行指標的 → form_final=pointer_trim（仍算送達，但只是路標）。
    - 其餘 → form_final=form。
    - 曝光（ReadHits）只對實際送出者計；回合 log 帶最終統計與輸出字元數。
    回傳「實際送出」的本 turn atom 名單，供 turn_injected（Stop 效用歸因分母）。
    沒有待結算資料（本 turn 無注入）→ 回 []。fail-open。
    """
    pending = state.pop("_turn_inject_pending", None)
    if not pending:
        return []
    records: List[Dict[str, Any]] = pending.get("records") or []
    if not records:
        return []
    try:
        final_form: Dict[str, str] = {}
        for entry in final_lines or []:
            m = _ATOM_HEAD_RE.match(entry or "")
            if not m:
                continue
            head = entry.split("\n", 1)[0]
            final_form[m.group(1)] = "pointer_trim" if " (truncated) Read " in head else "kept"

        survivors: List[str] = []
        dropped: List[str] = []
        for rec in records:
            name = rec.get("name", "")
            if rec.get("form") == "dropped":
                rec["form_final"] = "dropped"
                continue
            ff = final_form.get(name)
            if ff is None:
                rec["form_final"] = "dropped_trim"
                dropped.append(name)
            elif ff == "pointer_trim":
                rec["form_final"] = "pointer_trim"
                survivors.append(name)
            else:
                rec["form_final"] = rec.get("form", "")
                survivors.append(name)

        pointer_trimmed = [r.get("name", "") for r in records if r.get("form_final") == "pointer_trim"]
        if dropped:
            drop_set = set(dropped)
            state["injected_atoms"] = [n for n in (state.get("injected_atoms") or []) if n not in drop_set]
        # rescue watch 只能留「真的送出過的內容」的 token：整塊丟掉的、降成指標的（全文沒送出）都撤，
        # 否則後續工具碰到沒送出的 token 也會被記成採用證據（Codex #8 反例）。
        unwatch = set(dropped) | set(pointer_trimmed)
        if unwatch:
            watch = state.get("rescue_watch") or {}
            for key in [k for k, v in watch.items() if str(v).split("\t", 1)[0] in unwatch]:
                watch.pop(key, None)
            _atom_debug_log(
                "BUDGET",
                f"final-trim reconciled: dropped={dropped} pointer_trim={pointer_trimmed} → 撤 injected_atoms（dropped）/rescue watch（兩者），dropped 不計曝光",
                config,
            )

        _emit_usefulness_hints(config, [r for r in records if r.get("name") in set(survivors)])
        out_chars = len("\n".join(final_lines or []))
        _append_injection_turn_log(
            session_id, int(pending.get("turn", 0)), records, int(pending.get("used_tokens", 0)),
            config, out_chars=out_chars, delivered=len(survivors),
        )
        return survivors
    except Exception as e:  # noqa: BLE001 — 記帳不得影響注入輸出
        _atom_debug_log("BUDGET", f"reconcile error (fail-open): {e}", config)
        return [r.get("name", "") for r in records if r.get("form") != "dropped"]


def _emit_usefulness_hints(config: Dict[str, Any], delivered_records: List[Dict[str, Any]]) -> None:
    """曝光記帳：每顆「實際送出」的 atom ReadHits++（走 lib.atom_access funnel）。

    ReadHits 是純曝光計數、不進晉升；晉升由 SessionEnd 程式化路徑（Wilson 效用軌）執行。
    以記錄裡的 path 計，所以 Related 專有候選也會記曝光（以前只掃 matched_with_dir 漏掉它們）。
    以前這裡還會對「接近升門」的 atom 寫一列 `hint` 稽核——90 天 1,286/1,372 列全是它、
    沒有任何業務讀者，已停寫；健檢的管線活性改看 log_promotion_heartbeat。
    """
    try:
        from lib.atom_access import increment_read_hits
    except ImportError:
        return
    seen: set = set()
    for rec in delivered_records:
        path_str = rec.get("path", "")
        if not path_str or path_str in seen:
            continue
        seen.add(path_str)
        apath = Path(path_str)
        if apath.exists():
            try:
                increment_read_hits(apath, source="hook:atom-inject")
            except (OSError, ValueError):
                pass

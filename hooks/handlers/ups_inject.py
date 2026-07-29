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

from wg_core import log_promotion_audit, _atom_debug_log, _estimate_tokens
from wg_atoms import (
    AtomEntry,
    _strip_atom_for_injection,
    spread_related, decide_atom_injection, compute_injection_rank,
    classify_hot_cold, format_cold_inject_line, atom_status_suffix,
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


def _filter_related_by_relevance(
    related_entries: List[Tuple[AtomEntry, Path]], config: Dict[str, Any],
    access_cache: Optional[Dict[str, Dict]] = None,
) -> Tuple[List[Tuple[AtomEntry, Path]], List[Tuple[str, str]]]:
    """Phase C：related-spread 最小高訊號集裁切（憲法 Context Confusion 對策）。

    related atom 不命中 prompt（純連結擴散）= 最易成 distractor。本閘**只動 related-spread**，
    主迴圈（trigger/bm25/vector 命中 prompt）完全不碰 → 不誤殺 prompt 相關或新 atom。
    規則：① skip_demoted：剔除「已證明低效用」者（demote_candidate, n≥min_n；只動證明過的，
    絕不誤殺新/未證 atom）② 依注入 rank 降序、保留前 max_related（最小集）。
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
    scored = []
    for entry in related_entries:
        (rname, rel_path, _t), base_dir = entry
        rdir = (base_dir / rel_path).parent if rel_path else (base_dir / "memory")
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
) -> Tuple[List[str], Dict[str, Path]]:
    """組裝注入內容。mutate state（injected_atoms）/ append lines，
    回傳 (newly_injected, atom_source_dirs)。

    caches：search 段下傳的 {"content", "access"} 讀取快取（None 時自建空 dict，
    函式仍可獨測）——同 atom 本 prompt 只實讀一次。"""
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
    rescue_pairs: List[Tuple[str, str]] = []  # (atom, 實注入內容) → 救援日誌 watch
    # 本 turn 注入記錄（name/path/source/form），尾段落 state["injection_log"]。
    # form: ok=全文 / fallback=印象 / skip=budget 一行 / cold=cold 一行
    inject_records: List[Dict[str, Any]] = []

    def _record(name_: str, path_: Path, rel_: str, source_: str, form_: str) -> None:
        inject_records.append({
            "name": name_,
            "path": str(path_),
            "rel": rel_ or f"{name_}.md",
            "source": source_,
            "form": form_,
        })

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
            cold_line = format_cold_inject_line(name, raw_content, rel_path)
            atom_lines.append(cold_line)
            newly_injected.append(name)
            _record(name, atom_path, rel_path, source, "cold")
            _atom_debug_log(
                "BUDGET",
                f"atom={name} source={source} classification=cold (1-line)",
                config,
            )
            continue

        content = _strip_atom_for_injection(raw_content)
        content_tokens = _estimate_tokens(content)

        if name in section_hints and content_tokens > SECTION_INJECT_THRESHOLD:
            extracted = _extract_sections(content, section_hints[name])
            if extracted is not None:
                content = extracted

        decision, inject_content, consumed = decide_atom_injection(
            raw_content, content, used_tokens
        )
        if decision == "ok":
            atom_lines.append(f"[Atom:{name}]\n{inject_content}")
            newly_injected.append(name)
            rescue_pairs.append((name, inject_content))
            used_tokens += consumed
            skip_streak = 0
            _record(name, atom_path, rel_path, source, "ok")
            _atom_debug_log(
                "BUDGET",
                f"atom={name} source={source} tokens={consumed} decision=ok used={used_tokens}/{_TURN_BUDGET_LIMIT}",
                config,
            )
        elif decision == "fallback":
            atom_lines.append(f"[Atom:{name}] (budget fallback)\n{inject_content}")
            newly_injected.append(name)
            rescue_pairs.append((name, inject_content))
            used_tokens += consumed
            skip_streak = 0
            _record(name, atom_path, rel_path, source, "fallback")
            _atom_debug_log(
                "BUDGET",
                f"atom={name} source={source} tokens={consumed} decision=fallback used={used_tokens}/{_TURN_BUDGET_LIMIT}",
                config,
            )
        else:
            # skip（連 impression fallback 都塞不下）→ 1-line 指標後 continue：
            # 排序偏後仍可能有塞得下的小顆；連續 skip 達上限才視為 budget 真枯竭。
            first_line = content.split("\n", 1)[0].strip("# ").strip()
            display_path = rel_path or f"{name}.md"
            atom_lines.append(
                f"[Atom:{name}] {first_line}{atom_status_suffix(raw_content)}"
                f" (full: Read {display_path})"
            )
            newly_injected.append(name)
            _record(name, atom_path, rel_path, source, "skip")
            skip_streak += 1
            _atom_debug_log(
                "BUDGET",
                f"atom={name} source={source} decision=skip streak={skip_streak} used={used_tokens}/{_TURN_BUDGET_LIMIT}",
                config,
            )
            if skip_streak >= _BUDGET_SKIP_STREAK_MAX:
                break

    # Related-Edge Spreading（+ Phase C 最小高訊號集裁切：剔除已證明低效用、依 rank 保留前 N）
    related_entries = spread_related(
        set(newly_injected), all_atoms, already_injected, max_depth=1,
        content_cache=content_cache,
    )
    related_entries, related_skipped = _filter_related_by_relevance(
        related_entries, config, access_cache=access_cache)
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
            cold_line = format_cold_inject_line(rname, raw_content, rel_path)
            cold_line = cold_line.replace(f"[Atom:{rname}] (cold)", f"[Atom:{rname}] (related, cold)", 1)
            atom_lines.append(cold_line)
            newly_injected.append(rname)
            _record(rname, rpath, rel_path, "related", "cold")
            _atom_debug_log(
                "BUDGET",
                f"atom={rname}(related) classification=cold (1-line)",
                config,
            )
            continue

        content = _strip_atom_for_injection(raw_content)
        decision, inject_content, consumed = decide_atom_injection(
            raw_content, content, used_tokens
        )
        if decision == "ok":
            atom_lines.append(f"[Atom:{rname}] (related)\n{inject_content}")
            newly_injected.append(rname)
            rescue_pairs.append((rname, inject_content))
            used_tokens += consumed
            skip_streak = 0
            _record(rname, rpath, rel_path, "related", "ok")
            _atom_debug_log(
                "BUDGET",
                f"atom={rname}(related) classification=hot tokens={consumed} decision=ok used={used_tokens}/{_TURN_BUDGET_LIMIT}",
                config,
            )
        elif decision == "fallback":
            atom_lines.append(f"[Atom:{rname}] (related, budget fallback)\n{inject_content}")
            newly_injected.append(rname)
            rescue_pairs.append((rname, inject_content))
            used_tokens += consumed
            skip_streak = 0
            _record(rname, rpath, rel_path, "related", "fallback")
            _atom_debug_log(
                "BUDGET",
                f"atom={rname}(related) classification=hot tokens={consumed} decision=fallback used={used_tokens}/{_TURN_BUDGET_LIMIT}",
                config,
            )
        else:
            first_line = content.split("\n", 1)[0].strip("# ").strip()
            atom_lines.append(
                f"[Atom:{rname}] (related) {first_line}{atom_status_suffix(raw_content)}"
                f" (full: Read {rel_path or rname + '.md'})"
            )
            newly_injected.append(rname)
            _record(rname, rpath, rel_path, "related", "skip")
            skip_streak += 1
            _atom_debug_log(
                "BUDGET",
                f"atom={rname}(related) classification=hot decision=skip streak={skip_streak} used={used_tokens}/{_TURN_BUDGET_LIMIT}",
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
        _emit_usefulness_hints(
            session_id, config, newly_injected, matched_with_dir,
            caches={"content": content_cache, "access": access_cache},
        )

    return newly_injected, atom_source_dirs


def _emit_usefulness_hints(
    session_id: str,
    config: Dict[str, Any],
    newly_injected: List[str],
    matched_with_dir: List[Tuple[AtomEntry, Path]],
    caches: Optional[Dict[str, Dict]] = None,
) -> None:
    """ReadHits++ via lib.atom_access (funnel discipline)。

    ReadHits 降為純曝光計數、退出晉升路徑；晉升提示改由
    效用 Wilson 下界接近/已達升門時觸發（純曝光不再提示，杜絕雜訊）。
    SYNC: lib/atom_access.usefulness_hint_tier、server.js usefulnessStats、
          wg_atoms._self_iterate_atoms 晉升閘。
    """
    try:
        from lib.atom_access import (
            increment_read_hits, usefulness_stats,
            usefulness_hint_tier,
        )
    except ImportError:
        increment_read_hits = None
        usefulness_stats = None
        usefulness_hint_tier = None
    content_cache = (caches or {}).get("content")
    access_cache = (caches or {}).get("access")
    confidence_re = re.compile(r"^- Confidence:\s*(\[(?:臨|觀|固)\])", re.MULTILINE)
    PROMOTION_TARGETS = {"[臨]": "[觀]", "[觀]": "[固]"}
    u_cfg = config.get("usefulness", {})
    promote_lb = float(u_cfg.get("promote_lb", 0.6))
    min_n = int(u_cfg.get("min_n", 3))
    wilson_z = float(u_cfg.get("wilson_z", 1.96))
    for inj_name in newly_injected:
        for (name, rel_path, triggers), base_dir in matched_with_dir:
            if name != inj_name:
                continue
            apath = (base_dir / rel_path) if rel_path else (base_dir / "memory" / f"{name}.md")
            if not apath.exists():
                break
            if increment_read_hits is not None:
                try:
                    increment_read_hits(apath, source="hook:atom-inject")
                except (OSError, ValueError):
                    pass
            # 效用導向晉升提示：Wilson 下界接近/已達升門才提示。
            # 快取為 increment 前快照——hint tier 只看 α/β（increment 不動），一致。
            if usefulness_hint_tier is None:
                break
            text = read_atom_text(apath, content_cache)
            if text is None:
                break
            try:
                acc = load_access_cached(apath, access_cache)
            except (OSError, ValueError):
                break
            conf_m = confidence_re.search(text)
            if not conf_m:
                break
            cur = conf_m.group(1)
            target = PROMOTION_TARGETS.get(cur)
            if target is None:  # [固] 已達頂，無可晉升
                break
            tier = usefulness_hint_tier(
                acc, promote_lb=promote_lb, min_n=min_n, z=wilson_z
            )
            if tier is None:
                break
            st = usefulness_stats(acc, z=wilson_z)
            lb, n = st["lower_bound"], int(st["n"])
            # chat 不出提示行（跟進率極低）；晉升由 SessionEnd 程式化路徑執行，
            # 此處只留 audit 記錄供稽核。
            log_promotion_audit(
                "hint", inj_name,
                **{"from": cur, "to": target,
                   "method": "usefulness", "tier": tier,
                   "lower_bound": round(lb, 3), "n": n,
                   "session_id": session_id}
            )
            break

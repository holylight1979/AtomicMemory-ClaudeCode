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
from typing import Any, Dict, List, Tuple

from wg_core import log_promotion_audit, _atom_debug_log
from wg_atoms import (
    AtomEntry,
    _strip_atom_for_injection,
    spread_related, decide_atom_injection, compute_injection_rank,
    classify_hot_cold, format_cold_inject_line,
    SECTION_INJECT_THRESHOLD, _extract_sections,
    _TURN_BUDGET_LIMIT,
)
from wg_extraction import log_injection


def _filter_related_by_relevance(
    related_entries: List[Tuple[AtomEntry, Path]], config: Dict[str, Any],
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
        from lib.atom_access import read_access, usefulness_demote_candidate
    except Exception:
        return related_entries, []  # fail-open
    skip_demoted = ig.get("skip_demoted", True)
    max_related = int(ig.get("max_related", 6))
    u = (config or {}).get("usefulness") or {}
    min_n = int(u.get("min_n", 3))
    z = float(u.get("wilson_z", 1.96))
    demote_lb = float(u.get("demote_lb", 0.35))

    skipped: List[Tuple[str, str]] = []
    scored = []
    for entry in related_entries:
        (rname, rel_path, _t), base_dir = entry
        rdir = (base_dir / rel_path).parent if rel_path else (base_dir / "memory")
        if skip_demoted:
            try:
                acc = read_access(rdir / f"{rname}.md")
                if usefulness_demote_candidate(acc, demote_lb=demote_lb, min_n=min_n, z=z):
                    skipped.append((rname, "demoted"))
                    continue
            except Exception:
                pass
        scored.append((compute_injection_rank(rname, rdir, config), entry, rname))
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
) -> Tuple[List[str], Dict[str, Path]]:
    """組裝注入內容。mutate state（injected_atoms）/ append lines，
    回傳 (newly_injected, atom_source_dirs)。"""
    newly_injected: List[str] = []
    atom_source_dirs: Dict[str, Path] = {}
    if not matched_with_dir:
        return newly_injected, atom_source_dirs

    atom_lines: List[str] = []
    used_tokens = 0

    for (name, rel_path, triggers), base_dir in matched_with_dir:
        atom_path = (base_dir / rel_path) if rel_path else (base_dir / "memory" / f"{name}.md")
        if not atom_path.exists():
            continue
        atom_source_dirs[name] = atom_path.parent
        try:
            raw_content = atom_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue

        source = atom_source.get(name, "vector")
        classification = classify_hot_cold(atom_path, source)

        if classification == "cold":
            cold_line = format_cold_inject_line(name, raw_content, rel_path)
            atom_lines.append(cold_line)
            newly_injected.append(name)
            _atom_debug_log(
                "BUDGET",
                f"atom={name} source={source} classification=cold (1-line)",
                config,
            )
            log_injection(session_id or "", name, "cold", source)
            continue

        content = _strip_atom_for_injection(raw_content)
        content_tokens = len(content) // 4

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
            used_tokens += consumed
            _atom_debug_log(
                "BUDGET",
                f"atom={name} source={source} tokens={consumed} decision=ok used={used_tokens}/{_TURN_BUDGET_LIMIT}",
                config,
            )
            log_injection(session_id or "", name, "hot", source)
        elif decision == "fallback":
            atom_lines.append(f"[Atom:{name}] (budget fallback)\n{inject_content}")
            newly_injected.append(name)
            used_tokens += consumed
            _atom_debug_log(
                "BUDGET",
                f"atom={name} source={source} tokens={consumed} decision=fallback used={used_tokens}/{_TURN_BUDGET_LIMIT}",
                config,
            )
            log_injection(session_id or "", name, "hot", source)
        else:
            first_line = content.split("\n", 1)[0].strip("# ").strip()
            display_path = rel_path or f"{name}.md"
            atom_lines.append(f"[Atom:{name}] {first_line} (full: Read {display_path})")
            newly_injected.append(name)
            _atom_debug_log(
                "BUDGET",
                f"atom={name} source={source} decision=skip used={used_tokens}/{_TURN_BUDGET_LIMIT}",
                config,
            )
            log_injection(session_id or "", name, "hot", source)
            break

    # Related-Edge Spreading（+ Phase C 最小高訊號集裁切：剔除已證明低效用、依 rank 保留前 N）
    related_entries = spread_related(
        set(newly_injected), all_atoms, already_injected, max_depth=1,
    )
    related_entries, related_skipped = _filter_related_by_relevance(related_entries, config)
    for _sk_name, _sk_reason in related_skipped:
        _atom_debug_log("RELEVANCE", f"atom={_sk_name}(related) skipped={_sk_reason}", config)
    for (rname, rel_path, _triggers), base_dir in related_entries:
        if rname in newly_injected:
            continue
        rpath = (base_dir / rel_path) if rel_path else (base_dir / "memory" / f"{rname}.md")
        if not rpath.exists():
            continue
        atom_source_dirs[rname] = rpath.parent
        try:
            raw_content = rpath.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        related_classification = classify_hot_cold(rpath, "related")
        if related_classification == "cold":
            cold_line = format_cold_inject_line(rname, raw_content, rel_path)
            cold_line = cold_line.replace(f"[Atom:{rname}] (cold)", f"[Atom:{rname}] (related, cold)", 1)
            atom_lines.append(cold_line)
            newly_injected.append(rname)
            _atom_debug_log(
                "BUDGET",
                f"atom={rname}(related) classification=cold (1-line)",
                config,
            )
            log_injection(session_id or "", rname, "cold", "related")
            continue

        content = _strip_atom_for_injection(raw_content)
        decision, inject_content, consumed = decide_atom_injection(
            raw_content, content, used_tokens
        )
        if decision == "ok":
            atom_lines.append(f"[Atom:{rname}] (related)\n{inject_content}")
            newly_injected.append(rname)
            used_tokens += consumed
            _atom_debug_log(
                "BUDGET",
                f"atom={rname}(related) classification=hot tokens={consumed} decision=ok used={used_tokens}/{_TURN_BUDGET_LIMIT}",
                config,
            )
            log_injection(session_id or "", rname, "hot", "related")
        elif decision == "fallback":
            atom_lines.append(f"[Atom:{rname}] (related, budget fallback)\n{inject_content}")
            newly_injected.append(rname)
            used_tokens += consumed
            _atom_debug_log(
                "BUDGET",
                f"atom={rname}(related) classification=hot tokens={consumed} decision=fallback used={used_tokens}/{_TURN_BUDGET_LIMIT}",
                config,
            )
            log_injection(session_id or "", rname, "hot", "related")
        else:
            first_line = content.split("\n", 1)[0].strip("# ").strip()
            atom_lines.append(f"[Atom:{rname}] (related) {first_line} (full: Read {rel_path or rname + '.md'})")
            newly_injected.append(rname)
            _atom_debug_log(
                "BUDGET",
                f"atom={rname}(related) classification=hot decision=skip used={used_tokens}/{_TURN_BUDGET_LIMIT}",
                config,
            )
            log_injection(session_id or "", rname, "hot", "related")
            break

    if atom_lines:
        lines.extend(atom_lines)
        state["injected_atoms"] = already_injected + newly_injected
        _emit_usefulness_hints(
            session_id, config, newly_injected, matched_with_dir, lines
        )

    return newly_injected, atom_source_dirs


def _emit_usefulness_hints(
    session_id: str,
    config: Dict[str, Any],
    newly_injected: List[str],
    matched_with_dir: List[Tuple[AtomEntry, Path]],
    lines: List[str],
) -> None:
    """ReadHits++ via lib.atom_access (funnel discipline)。

    ReadHits 降為純曝光計數、退出晉升路徑；晉升提示改由
    效用 Wilson 下界接近/已達升門時觸發（純曝光不再提示，杜絕雜訊）。
    SYNC: lib/atom_access.usefulness_hint_tier、server.js usefulnessStats、
          wg_atoms._self_iterate_atoms 晉升閘。
    """
    try:
        from lib.atom_access import (
            increment_read_hits, read_access, usefulness_stats,
            usefulness_hint_tier,
        )
    except ImportError:
        increment_read_hits = None
        read_access = None
        usefulness_stats = None
        usefulness_hint_tier = None
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
            # 效用導向晉升提示：Wilson 下界接近/已達升門才提示
            if usefulness_hint_tier is None or read_access is None:
                break
            try:
                text = apath.read_text(encoding="utf-8-sig")
                acc = read_access(apath)
            except (OSError, ValueError, UnicodeDecodeError):
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
            status = "已達效用升門" if tier == "eligible" else "效用接近升門"
            lines.append(
                f"⚡ [{inj_name}] 效用 lb={lb:.2f} (n={n})，目前{cur}→{target}："
                f"{status}（need lb≥{promote_lb} & n≥{min_n}），"
                f"觸及相關行為時請主動確認是否晉升"
            )
            log_promotion_audit(
                "hint", inj_name,
                **{"from": cur, "to": target,
                   "method": "usefulness", "tier": tier,
                   "lower_bound": round(lb, 3), "n": n,
                   "session_id": session_id}
            )
            break

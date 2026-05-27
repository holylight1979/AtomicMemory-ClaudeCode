"""
handlers/user_prompt_submit.py — UserPromptSubmit hook handler

最大的 handler（~680 行）。負責每輪 prompt 的：
- evasion guard 旁路（清 failing_tests）
- V4.1 user decision detector gate
- confirmed extractions / veto
- long_die response（停用/保持 backend）
- Hot Cache 注入
- atom-write guard reminder（建議階段不該宣告 [固]/[觀]）
- session context（first prompt only）+ proactive classification
- wisdom engine situation classification
- _AIDocs keyword matching
- JIT internal pipeline reference for memory system dev
- atom auto-injection（trigger + vector + related spread + hot/cold + budget）
- supersedes filtering
- ACT-R activation sorting
- per-turn budget hard cap
- ReadHits++ via lib.atom_access
- Fix Escalation Protocol
- Evasion 上輪命中 → 注入舉證要求
- Handoff Protocol
- failure-triggered extraction
- topic tracking
- sync reminders
- atom-debug log
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from wg_core import (
    MEMORY_DIR, _ensure_state, _estimate_tokens, _now_iso, write_state,
    output_json, output_nothing, log_promotion_audit,
    discover_all_project_memory_dirs,
    MEMORY_INDEX,
    _atom_debug_log, _atom_debug_error,
)
from wg_atoms import (
    AtomEntry,
    parse_memory_index, parse_project_aliases,
    _kw_match, _strip_atom_for_injection,
    compute_token_budget, compute_activation,
    spread_related, decide_atom_injection, _truncate_context_by_activation,
    classify_intent, _update_topic_tracker,
    classify_hot_cold, format_cold_inject_line,
    SECTION_INJECT_THRESHOLD, _extract_sections,
    _TURN_BUDGET_LIMIT,
    _search_episodic_context, _build_session_context,
    _proactive_classify, _semantic_search,
    bm25_match,
)
from wg_extraction import (
    detect_signal,
    _maybe_spawn_failure_extraction,
    log_injection,
)
from wg_evasion import is_dismiss_prompt
from handlers._shared import (
    _SUPERSEDES_RE,
    WISDOM_AVAILABLE, classify_situation,
    read_hot_cache, mark_injected, format_injection_line,
)

# Ollama client（dispatcher 已加 tools/ 到 sys.path）
sys.path.insert(0, str(Path.home() / ".claude" / "tools"))
try:
    from ollama_client import check_long_die_status, disable_backend, OllamaClient
except ImportError:
    check_long_die_status = lambda: None  # noqa: E731
    disable_backend = lambda *a, **k: False  # noqa: E731
    OllamaClient = None


def _is_memory_system_dev(prompt_lower: str, cwd: str) -> bool:
    """嚴格判斷是否為記憶系統開發場景。需 2+ 命中或 CWD 匹配。"""
    cwd_norm = cwd.replace("\\", "/")
    if "/.claude/hooks" in cwd_norm or "/.claude/tools" in cwd_norm:
        return True
    MEM_KEYWORDS = [
        "workflow-guardian", "wg_", "atom memory", "原子記憶",
        "wisdom_engine", "記憶系統", "memory system",
        "hot_cache", "extract-worker", "vector service",
        "hook pipeline", "萃取管線", "注入管線",
    ]
    hits = sum(1 for kw in MEM_KEYWORDS if kw in prompt_lower)
    return hits >= 2


def handle_user_prompt_submit(
    input_data: Dict[str, Any], config: Dict[str, Any]
) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
        return

    prompt = input_data.get("prompt", "")
    clean_prompt = re.sub(r'<ide_\w+>.*?</ide_\w+>', '', prompt, flags=re.DOTALL).strip()
    prompt_lower = clean_prompt.lower()
    lines: List[str] = []

    # ── Evasion Guard: 追蹤近 5 則 user prompt ─────
    rup = state.setdefault("recent_user_prompts", [])
    rup.append(clean_prompt[:500])
    if len(rup) > 5:
        state["recent_user_prompts"] = rup[-5:]

    if state.get("failing_tests") and is_dismiss_prompt(clean_prompt):
        state["failing_tests"] = []

    # ─── V4.1: User Decision Detector gate ────────────────────────────
    ue_config = config.get("userExtraction", {})
    if ue_config.get("enabled", False):
        try:
            det = detect_signal(clean_prompt)
            if det.get("signal"):
                turn_n = state.get("topic_tracker", {}).get("prompt_count", 0)
                pending = state.setdefault("pending_user_extract", [])
                pending.append({
                    "turn_id": f"{session_id}-{turn_n}",
                    "prompt": clean_prompt,
                    "score": det["score"],
                    "matched": det["matched"],
                    "ts": _now_iso(),
                })
                if len(pending) > 10:
                    state["pending_user_extract"] = pending[-10:]
        except Exception as e:
            _atom_debug_error("V4.1:user_extract_gate", e)

    # ─── V4.1 [F5]: Confirmed extractions ──
    confirmed = state.get("confirmed_extractions", [])
    if confirmed:
        veto = any(kw in prompt_lower for kw in ("否", "不要記", "別記", "取消記憶"))
        if veto:
            for ext in confirmed:
                _atom_debug_log(
                    "user-extract:rejected",
                    f"User vetoed: {ext.get('statement', '')[:80]}",
                    config,
                )
            state["confirmed_extractions"] = []
        else:
            for ext in confirmed:
                stmt = ext.get("statement", "")
                lines.append(
                    f"[V4.1] 偵測到決策語句：「{stmt}」— 將記為 atom。回覆「否」可攔截。"
                )
            state["confirmed_extractions"] = []

    # ─── Dual-Backend: long_die user response ─────
    try:
        long_die = check_long_die_status()
        if long_die:
            backend_name = long_die.get("backend", "")
            if any(kw in prompt_lower for kw in ("停用", "disable")):
                if disable_backend(backend_name):
                    if OllamaClient is not None:
                        OllamaClient._clear_long_die_marker()
                    lines.append(
                        f"[Dual-Backend] 已永久停用 '{backend_name}'。"
                        f"如需重新啟用，修改 config.json 中 enabled: true。"
                    )
                else:
                    lines.append(f"[Dual-Backend] 停用 '{backend_name}' 失敗，請手動修改 config.json。")
            elif any(kw in prompt_lower for kw in ("保持", "keep", "忽略")):
                if OllamaClient is not None:
                    OllamaClient._clear_long_die_marker()
                lines.append(f"[Dual-Backend] 保持 '{backend_name}'，long_die 將在時間段到期後自動恢復。")
    except Exception as e:
        print(f"[dual-backend] Long DIE response error: {e}", file=sys.stderr)

    # ─── Hot Cache Fast Path ───────────────────────────────
    hot_cache_tokens = 0
    if read_hot_cache:
        try:
            hot_data = read_hot_cache(session_id)
            if hot_data:
                lines.append(format_injection_line(hot_data))
                hot_cache_tokens = hot_data.get("token_estimate", 50)
                mark_injected(session_id)
        except Exception:
            pass

    # ─── Atom-Write Guard: confidence gate reminder ─────────────────────
    atom_write_triggers = (
        "記住", "記下來", "存起來", "存下來", "值得存", "值得記",
        "寫成 atom", "寫 atom", "存成 atom", "存atom", "存成[固]", "存成 [固]",
        "存成[觀]", "存成 [觀]", "記為[固]", "記為 [固]",
    )
    if any(kw in clean_prompt for kw in atom_write_triggers):
        lines.append(
            "[Atom-Write Guard] 偵測到記憶寫入意圖。硬規則："
            "(1) 新 atom 一律 [臨]，MCP atom_write 會 reject [固]/[觀]；"
            "(2) 單次成功 ≠ 穩定模式，需 4+ session 命中才建議晉升；"
            "(3) 晉升走 atom_promote（雙軌：Primary Confirmations ≥4→[觀]/≥10→[固] 或 Auxiliary ReadHits ≥20→[觀]/≥50→[固]），不手動改 frontmatter；"
            "(4) 若是更新既有 atom，用 mode=append 並保留原 confidence。"
        )

    # ─── Phase 0: Session Context Injection ────────
    budget = compute_token_budget(prompt)
    budget = max(budget - hot_cache_tokens, 500)
    if not state.get("session_context_injected", False):
        state["session_context_injected"] = True
        episodic_results = _search_episodic_context(prompt, config, session_id=session_id)
        if episodic_results:
            ctx_lines = _build_session_context(episodic_results)
            if ctx_lines:
                lines.extend(ctx_lines)
                sc_config = config.get("session_context", {})
                reserved = sc_config.get("reserved_tokens", 200)
                budget = max(budget - reserved, 500)
            proactive_lines = _proactive_classify(state, episodic_results, prompt, config)
            lines.extend(proactive_lines)

    # ─── Wisdom Engine — situation classification ──────────
    if WISDOM_AVAILABLE and classify_situation is not None:
        try:
            mod_paths = [m["path"] for m in state.get("modified_files", [])]
            tracker = state.get("topic_tracker", {})
            prompt_analysis = {
                "intent": tracker.get("intent_distribution", {}).get("top", ""),
                "keywords": tracker.get("keyword_signals", []),
                "estimated_files": max(len(mod_paths), 1),
            }
            result = classify_situation(prompt_analysis)
            if result.get("inject"):
                lines.append(result["inject"])
            cur = result.get("approach", "direct")
            prev = state.get("wisdom_approach", "direct")
            rank = {"direct": 0, "confirm": 1, "plan": 2}
            if rank.get(cur, 0) > rank.get(prev, 0):
                state["wisdom_approach"] = cur
        except Exception as e:
            print(f"[v2.8] Wisdom prompt error: {e}", file=sys.stderr)

    # ─── _AIDocs keyword matching ──────────────────
    aidocs_state = state.get("aidocs", {})
    aidocs_kw_map = aidocs_state.get("keywords", {})
    max_matches = config.get("aidocs", {}).get("max_prompt_matches", 3)
    if aidocs_kw_map and prompt.strip():
        matched_docs: List[str] = []
        for fname, keywords in aidocs_kw_map.items():
            if any(_kw_match(kw, prompt_lower) for kw in keywords):
                matched_docs.append(fname)
        if matched_docs and len(matched_docs) <= 5:
            aidocs_root = aidocs_state.get("project_root", "")
            pointer_lines = ["[Guardian:AIDocs] Relevant project docs:"]
            for doc in matched_docs[:max_matches]:
                desc = ""
                for f, d in aidocs_state.get("entries", []):
                    if f == doc:
                        desc = d
                        break
                doc_path = f"_AIDocs/{doc}" if aidocs_root else doc
                pointer_lines.append(f"  → Read `{doc_path}` — {desc[:80]}")
            lines.extend(pointer_lines)

    # ── JIT load internal pipeline reference for memory system dev ──
    if _is_memory_system_dev(prompt_lower, state.get("session", {}).get("cwd", "")):
        ref_path = MEMORY_DIR / "_reference" / "internal-pipeline.md"
        if ref_path.exists():
            try:
                ref_text = ref_path.read_text(encoding="utf-8")
                ref_tokens = len(ref_text) // 4
                jit_budget = min(ref_tokens, 250)
                if jit_budget <= budget:
                    lines.append(f"[JIT:InternalPipeline]\n{ref_text[:jit_budget * 4]}")
                    budget -= jit_budget
            except (OSError, UnicodeDecodeError):
                pass

    # ─── Phase 1: Atom auto-injection ─────────────
    atom_index = state.get("atom_index", {})
    already_injected = state.get("injected_atoms", [])

    all_atoms: List[Tuple[AtomEntry, Path]] = []
    for entry in atom_index.get("global", []):
        name, rel_path, triggers = entry
        all_atoms.append(((name, rel_path, triggers), MEMORY_DIR.parent))
    proj_dir_str = atom_index.get("project_memory_dir", "")
    proj_root_str = atom_index.get("project_root", "")
    if proj_dir_str:
        proj_parent = Path(proj_dir_str).parent
        proj_root = Path(proj_root_str) if proj_root_str else None
        for entry in atom_index.get("project", []):
            name, rel_path, triggers = entry
            if rel_path.startswith("_AIAtoms/") and proj_root:
                base = proj_root
            else:
                base = proj_parent
            all_atoms.append(((name, rel_path, triggers), base))

    matched_with_dir: List[Tuple[AtomEntry, Path]] = []
    atom_source: Dict[str, str] = {}
    alias_injected_projects: set = set()

    _MAX_CROSS_PROJECT_SCAN = 20

    loaded_proj_names = set()
    if proj_dir_str:
        loaded_proj_names.add(Path(proj_dir_str).parent.name)
    _all_cross = [
        (s, m) for s, m in discover_all_project_memory_dirs()
        if s not in loaded_proj_names
    ]
    if len(_all_cross) > _MAX_CROSS_PROJECT_SCAN:
        def _mem_mtime(item: Tuple[str, Path]) -> float:
            try:
                return item[1].stat().st_mtime
            except OSError:
                return 0.0
        _all_cross = sorted(_all_cross, key=_mem_mtime, reverse=True)[:_MAX_CROSS_PROJECT_SCAN]
    for _cross_slug, cross_mem in _all_cross:
        if _cross_slug in loaded_proj_names:
            continue
        aliases = parse_project_aliases(cross_mem)
        if aliases and any(alias in prompt_lower for alias in aliases):
            try:
                mem_text = (cross_mem / MEMORY_INDEX).read_text(encoding="utf-8-sig")
                mem_lines = mem_text.split("\n")
                mem_lines = [l for l in mem_lines if not (l.startswith("|") and "|" in l[1:])]
                mem_text = "\n".join(l for l in mem_lines if l.strip()).strip()
                lines.append(f"[Guardian:AliasMatch] {_cross_slug} matched via alias")
                if mem_text:
                    lines.append(f"[ProjectMemory:{_cross_slug}]\n{mem_text}")
                alias_injected_projects.add(_cross_slug)
            except (OSError, UnicodeDecodeError):
                pass
        cross_atoms = parse_memory_index(cross_mem)
        if not cross_atoms:
            continue
        cross_parent = cross_mem.parent
        for name, rel_path, triggers in cross_atoms:
            if name not in already_injected and sum(_kw_match(kw, prompt_lower) for kw in triggers) >= 2:
                all_atoms.append(((name, rel_path, triggers), cross_parent))
                _atom_debug_log("CrossProject", f"{_cross_slug}/{name} matched", config)
    for (name, rel_path, triggers), base_dir in all_atoms:
        if name not in already_injected and any(_kw_match(kw, prompt_lower) for kw in triggers):
            matched_with_dir.append(((name, rel_path, triggers), base_dir))
            atom_source[name] = "trigger"

    intent = classify_intent(prompt)

    kw_matched_names = {e[0][0] for e in matched_with_dir}

    # V5 P5a: BM25 over global layer (replaces vector round-trip for global atoms).
    # Only run if no/few trigger hits (≤2). Project layer still uses vector below.
    vs_cfg = config.get("vector_search", {})
    if vs_cfg.get("global_layer", "bm25") == "bm25" and len(matched_with_dir) <= 2:
        global_atoms = [e for e in all_atoms if e[1] == MEMORY_DIR.parent]
        if global_atoms:
            global_entries = [e[0] for e in global_atoms]
            bm25_hits = bm25_match(
                prompt, global_entries,
                min_score=vs_cfg.get("bm25_min_score", 1.0),
                top_k=vs_cfg.get("bm25_top_k", 3),
            )
            for entry in bm25_hits:
                name = entry[0]
                if name in kw_matched_names or name in already_injected:
                    continue
                for tup in global_atoms:
                    if tup[0][0] == name:
                        matched_with_dir.append(tup)
                        atom_source.setdefault(name, "bm25")
                        kw_matched_names.add(name)
                        break

    _v4_id = state.get("user_identity", {})
    _v4_user = _v4_id.get("user") or None
    _v4_roles = _v4_id.get("roles") or None
    if _v4_id.get("management"):
        _v4_user = None
        _v4_roles = None
    # Vector fallback: only when BM25/trigger gave 0 hits, OR for project layer enrichment.
    sem_atoms = _semantic_search(
        prompt, config, intent=intent,
        user=_v4_user, roles=_v4_roles,
        session_id=session_id,
    ) if (len(matched_with_dir) == 0 or vs_cfg.get("global_layer") != "bm25") else []
    section_hints: Dict[str, List[Dict]] = {}
    for sem_entry in sem_atoms:
        sem_name, sem_path = sem_entry[0], sem_entry[1]
        sem_sections = sem_entry[3] if len(sem_entry) > 3 else []
        if sem_sections:
            section_hints[sem_name] = sem_sections
        if sem_name in kw_matched_names or sem_name in already_injected:
            continue
        for (name, rel_path, triggers), base_dir in all_atoms:
            if name == sem_name:
                matched_with_dir.append(((name, rel_path, triggers), base_dir))
                atom_source.setdefault(name, "vector")
                kw_matched_names.add(name)
                break

    # Supersedes filtering
    superseded_names: set = set()
    for (name, rel_path, triggers), base_dir in matched_with_dir:
        atom_path = (base_dir / rel_path) if rel_path else (base_dir / "memory" / f"{name}.md")
        if not atom_path.exists():
            continue
        try:
            text = atom_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        sm = _SUPERSEDES_RE.search(text)
        if sm:
            for old in sm.group(1).split(","):
                old = old.strip()
                if old:
                    superseded_names.add(old)
    if superseded_names:
        matched_with_dir = [
            entry for entry in matched_with_dir
            if entry[0][0] not in superseded_names
        ]

    # ACT-R activation sort
    def _activation_key(entry):
        (name, rel_path, _triggers), base_dir = entry
        atom_dir = (base_dir / rel_path).parent if rel_path else (base_dir / "memory")
        return compute_activation(name, atom_dir)

    matched_with_dir.sort(key=_activation_key, reverse=True)

    newly_injected: List[str] = []
    atom_source_dirs: Dict[str, Path] = {}
    if matched_with_dir:
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

        # Related-Edge Spreading
        related_entries = spread_related(
            set(newly_injected), all_atoms, already_injected, max_depth=1,
        )
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

            # ReadHits++ via lib.atom_access (Wave 2 funnel discipline)
            try:
                from lib.atom_access import increment_read_hits, read_access
            except ImportError:
                increment_read_hits = None
                read_access = None
            confidence_re = re.compile(r"^- Confidence:\s*(\[(?:臨|觀|固)\])", re.MULTILINE)
            READHIT_THRESHOLDS = {"[臨]": 20, "[觀]": 50}
            PROMOTION_TARGETS = {"[臨]": "[觀]", "[觀]": "[固]"}
            for inj_name in newly_injected:
                for (name, rel_path, triggers), base_dir in matched_with_dir:
                    if name != inj_name:
                        continue
                    apath = (base_dir / rel_path) if rel_path else (base_dir / "memory" / f"{name}.md")
                    if not apath.exists():
                        break
                    new_count = None
                    if increment_read_hits is not None:
                        try:
                            new_count = increment_read_hits(apath, source="hook:atom-inject")
                        except (OSError, ValueError):
                            new_count = None
                    if new_count is not None:
                        try:
                            text = apath.read_text(encoding="utf-8-sig")
                        except (OSError, UnicodeDecodeError):
                            text = ""
                        conf_m = confidence_re.search(text)
                        if conf_m:
                            cur = conf_m.group(1)
                            rh_threshold = READHIT_THRESHOLDS.get(cur)
                            if rh_threshold and new_count >= rh_threshold:
                                target = PROMOTION_TARGETS[cur]
                                lines.append(
                                    f"⚡ [{inj_name}] ReadHits={new_count}, "
                                    f"目前{cur}, ReadHits 已達{target}輔助門檻，"
                                    f"觸及相關行為時請主動確認是否晉升"
                                )
                                log_promotion_audit(
                                    "hint", inj_name,
                                    **{"from": cur, "to": target,
                                       "readhits": new_count,
                                       "session_id": session_id}
                                )
                    break

    # Blind-Spot Reporter
    if (not matched_with_dir and not newly_injected and not alias_injected_projects
            and len(clean_prompt) >= 10):
        sem_count = len(sem_atoms) if sem_atoms else 0
        _atom_debug_log(
            "BlindSpot",
            f"未匹配: {clean_prompt[:80]} | intent={intent}, sem_results={sem_count}, already_injected={len(already_injected)}",
            config,
        )

    # Fix Escalation Protocol
    retry_count = state.get("wisdom_retry_count", 0)
    fix_esc_warned = state.get("fix_escalation_warned", False)
    if retry_count >= 2 and not fix_esc_warned:
        state["fix_escalation_warned"] = True
        state["fix_escalation_triggered"] = True
        lines.append(
            f"[Guardian:FixEscalation] 偵測到重複修正 "
            f"(retry={retry_count})。"
            "依據「精確修正升級」規則，必須暫停直接修復，"
            "執行 /fix-escalation 精確修正會議。"
        )

    # Evasion 上輪命中 → 注入舉證要求
    ev = state.get("evasion_flag")
    if ev:
        lines.append(
            f"[Guardian:Evasion] 你上輪用了退避語『{ev.get('phrase', '')}』。\n"
            f"  context: …{ev.get('context_excerpt', '')[:200]}…\n"
            "feedback-rigor-standards 規則：1-3 行能修就當場修。請說明：\n"
            "  (a) 實際修補成本（列出要改的檔/行數）\n"
            "  (b) 若仍選擇不修，為何這不是 feedback atom 所禁的退避說法？"
        )
        state["evasion_flag"] = None

    # Handoff Protocol
    if intent == "handoff":
        lines.append(
            "[Guardian:Handoff] 偵測到 handoff 意圖。"
            "下 session 的 Claude 不會看到本次對話脈絡。"
            "請執行 /handoff 走 6 區塊強制模板，不要徒手寫 prompt。"
        )

    # Failure-triggered extraction
    _maybe_spawn_failure_extraction(
        session_id, state, config, clean_prompt, lines
    )

    # Topic tracking
    _update_topic_tracker(state, prompt, intent, newly_injected)

    # Phase 2: Sync reminders
    mod_count = len(state.get("modified_files", []))
    kq_count = len(state.get("knowledge_queue", []))
    sync_kw = config.get("sync_keywords", [])
    prompt_has_sync = any(kw in prompt for kw in sync_kw)

    if prompt_has_sync and (mod_count > 0 or kq_count > 0):
        lines.append(f"[Guardian] Sync context: {mod_count} files modified, {kq_count} knowledge items pending.")
        if mod_count > 0:
            files = list({m["path"] for m in state["modified_files"]})
            lines.append(f"Files: {', '.join(f.rsplit('/', 1)[-1] for f in files[:10])}")
        if kq_count > 0:
            for q in state["knowledge_queue"]:
                lines.append(f"  - {q.get('classification', '[臨]')} {q['content'][:60]}")
    elif mod_count > 0 or kq_count > 0:
        remind_after = config.get("remind_after_turns", 3)
        remind_count = state.get("remind_count", 0)
        if remind_count < remind_after:
            state["remind_count"] = remind_count + 1
        else:
            max_reminders = config.get("max_reminders", 3)
            total_reminds = state.get("total_reminds", 0)
            if total_reminds < max_reminders:
                lines.append(
                    f"[Guardian] Reminder: {mod_count} files modified, {kq_count} knowledge items pending. "
                    "Consider syncing when current task completes."
                )
                state["remind_count"] = 0
                state["total_reminds"] = total_reminds + 1

    write_state(session_id, state)

    # atom-debug summary
    if (config or {}).get("atom_debug", False):
        prompt_preview = re.sub(r"<[^>]+>", "", prompt[:300]).strip()[:120] if prompt else ""
        total_tok = 0
        summary_parts = []
        _ATOM_BLOCK_RE = re.compile(r"^\[Atom:(\S+)\](?:\s*\(related\))?\n")
        for line_item in lines:
            tok = _estimate_tokens(line_item)
            total_tok += tok
            am = _ATOM_BLOCK_RE.match(line_item)
            if am:
                aname = am.group(1)
                is_related = "(related) " if "(related)" in line_item[:60] else ""
                src = f"memory/{aname}.md"
                for (n, rp, _), bd in matched_with_dir:
                    if n == aname and rp:
                        src = rp
                        break
                summary_parts.append(f"  [注入了 {src}] {is_related}(~{tok} tok)")
            else:
                first = line_item.split("\n", 1)[0][:120]
                if line_item.count("\n") > 1:
                    n_lines = line_item.count("\n") + 1
                    summary_parts.append(f"  {first} ...({n_lines}行, ~{tok} tok)")
                else:
                    summary_parts.append(f"  {first} (~{tok} tok)")
        injection_body = (
            f"[PROMPT] {prompt_preview}\n"
            f"[注入摘要] {len(lines)}項, 合計 ~{total_tok} tok\n"
            + ("\n".join(summary_parts) if summary_parts else "NONE")
        )
        _atom_debug_log("注入", injection_body, config)

    if lines:
        lines = _truncate_context_by_activation(lines, budget, atom_source_dirs)
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "\n".join(lines),
            }
        })
    else:
        output_nothing()

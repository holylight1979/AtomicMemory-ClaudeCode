"""
handlers/ups_search.py — UserPromptSubmit search pipeline 段

從 user_prompt_submit.py 拆出。
職責：本輪 prompt 的 atom 候選收集與排序：
- atom index 組裝（global + project 層，_AIAtoms/ 基底解析）
- 跨專案 alias 掃描（mtime 排序上限 20 專案）+ ProjectMemory 注入
- trigger keyword match
- BM25 over global layer（trigger 命中 ≤2 才跑）
- vector fallback（_semantic_search，含 V4 identity 過濾）+ section hints
- supersedes filtering
- ACT-R activation sort

公開函式 collect_matched_atoms() 回傳排序後的候選與來源歸因。
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

from wg_core import (
    MEMORY_DIR, MEMORY_INDEX,
    discover_all_project_memory_dirs,
    _atom_debug_log,
)
from wg_atoms import (
    AtomEntry,
    parse_memory_index, parse_project_aliases,
    any_trigger_hit, count_trigger_hits, compute_activation, compute_injection_rank,
    classify_intent,
    _semantic_search,
    bm25_match,
)
from handlers._shared import _SUPERSEDES_RE

_MAX_CROSS_PROJECT_SCAN = 20


def _merge_hit(
    name: str,
    pool: List[Tuple[AtomEntry, Path]],
    source_tag: str,
    matched_with_dir: List[Tuple[AtomEntry, Path]],
    atom_source: Dict[str, str],
    kw_matched_names: set,
    already_injected: List[str],
) -> None:
    """把 BM25/vector 命中的 atom 名依 pool 解析後合併進候選（去重 + 來源歸因）。"""
    if name in kw_matched_names or name in already_injected:
        return
    for tup in pool:
        if tup[0][0] == name:
            matched_with_dir.append(tup)
            atom_source.setdefault(name, source_tag)
            kw_matched_names.add(name)
            break


def collect_matched_atoms(
    session_id: str,
    state: Dict[str, Any],
    config: Dict[str, Any],
    prompt: str,
    prompt_lower: str,
    lines: List[str],
) -> Tuple[
    List[Tuple[AtomEntry, Path]],  # matched_with_dir（已 ACT-R 排序）
    Dict[str, str],                # atom_source（name → trigger/bm25/vector）
    List[Tuple[AtomEntry, Path]],  # all_atoms（含跨專案補入）
    list,                          # sem_atoms（vector 原始結果，供 blind-spot 統計）
    Dict[str, List[Dict]],         # section_hints（vector section 提示）
    set,                           # alias_injected_projects
    str,                           # intent
]:
    """收集並排序本輪可注入的 atom 候選。append lines（alias 注入）。"""
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
            if name not in already_injected and count_trigger_hits(triggers, prompt_lower) >= 2:
                all_atoms.append(((name, rel_path, triggers), cross_parent))
                _atom_debug_log("CrossProject", f"{_cross_slug}/{name} matched", config)
    for (name, rel_path, triggers), base_dir in all_atoms:
        if name in atom_source:
            continue  # 同名去重：all_atoms 多層（global/project/cross）混入同名時只取首見
        if name not in already_injected and any_trigger_hit(triggers, prompt_lower):
            matched_with_dir.append(((name, rel_path, triggers), base_dir))
            atom_source[name] = "trigger"

    intent = classify_intent(prompt)

    kw_matched_names = {e[0][0] for e in matched_with_dir}

    # BM25 over global layer (replaces vector round-trip for global atoms).
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
                _merge_hit(
                    entry[0], global_atoms, "bm25",
                    matched_with_dir, atom_source, kw_matched_names, already_injected,
                )

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
        sem_name = sem_entry[0]
        sem_sections = sem_entry[3] if len(sem_entry) > 3 else []
        if sem_sections:
            section_hints[sem_name] = sem_sections
        _merge_hit(
            sem_name, all_atoms, "vector",
            matched_with_dir, atom_source, kw_matched_names, already_injected,
        )

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

    # ACT-R activation sort（扣分心懲罰：高曝光低效用者降權，憲法 Distraction 對策）
    def _activation_key(entry):
        (name, rel_path, _triggers), base_dir = entry
        atom_dir = (base_dir / rel_path).parent if rel_path else (base_dir / "memory")
        return compute_injection_rank(name, atom_dir, config)

    matched_with_dir.sort(key=_activation_key, reverse=True)

    return (
        matched_with_dir, atom_source, all_atoms,
        sem_atoms, section_hints, alias_injected_projects, intent,
    )

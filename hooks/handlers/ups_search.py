"""
handlers/ups_search.py — UserPromptSubmit search pipeline 段

從 user_prompt_submit.py 拆出。
職責：本輪 prompt 的 atom 候選收集與排序：
- atom index 組裝（global + project 層，_AIAtoms/ 基底解析）；候選池在 SessionStart
  已依 scope 可見性收窄（SPEC §8.1），他專案 atom 從不進池
- 跨專案 alias 掃描（mtime 排序上限 20 專案）：prompt 命中他專案別名 → 只帶入該專案
  MEMORY.md 目錄（去 personal/roles 行），不撈 atom
- trigger keyword match
- BM25 over global layer（trigger 命中 ≤2 才跑）
- vector fallback（_semantic_search，layers 白名單＝候選池同一套可見性）+ section hints
- supersedes filtering
- ACT-R activation sort

公開函式 collect_matched_atoms() 回傳排序後的候選與來源歸因。
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

from wg_core import (
    MEMORY_DIR, MEMORY_INDEX,
    discover_all_project_memory_dirs, _is_under_claude_dir,
    _atom_debug_log,
)
import math

from wg_atoms import (
    AtomEntry,
    parse_project_aliases, visible_vector_layers,
    any_trigger_hit, count_trigger_hits, compute_activation, compute_injection_rank,
    classify_intent,
    _semantic_search,
    bm25_match, BM25_MIN_SCORE_DEFAULT,
    read_atom_text, rrf_fuse, RRF_ACTIVATION_GAIN,
)
from handlers._shared import _SUPERSEDES_RE

# 跨專案 alias 快取：每 prompt 都是新進程，免每次重讀最多 20 個專案的 MEMORY.md
# alias 行。以該檔 mtime_ns 為鍵；變動即重讀。fail-open：快取壞掉就照舊逐檔讀。
# 只快取 alias——他專案的 atom 索引不再讀（他專案 atom 不進候選池）。
_CROSS_CACHE_NAME = "cross-project-index-cache.json"


def _cross_cache_key(mem: Path) -> str:
    try:
        return str((mem / MEMORY_INDEX).stat().st_mtime_ns)
    except OSError:
        return "0"


def _load_cross_project_cache(cross: List[Tuple[str, Path]]) -> Dict[str, Dict[str, Any]]:
    """回 {str(mem_dir): {"aliases": [...]}}，只含鍵仍有效者；失效／缺席者逐檔重讀後回寫。"""
    import json as _json
    from wg_core import WORKFLOW_DIR
    path = WORKFLOW_DIR / _CROSS_CACHE_NAME
    try:
        data = _json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        data = {}
    out: Dict[str, Dict[str, Any]] = {}
    stale: List[Tuple[str, Path]] = []
    for _slug, mem in cross:
        ent = data.get(str(mem))
        if ent and ent.get("key") == _cross_cache_key(mem):
            out[str(mem)] = ent
        else:
            stale.append((_slug, mem))
    if stale:
        for _slug, mem in stale:
            try:
                ent = {
                    "key": _cross_cache_key(mem),
                    "aliases": parse_project_aliases(mem),
                }
            except Exception:  # noqa: BLE001 — 單一專案讀壞不影響其餘
                continue
            data[str(mem)] = ent
            out[str(mem)] = ent
        try:
            keep = {str(m) for _s, m in cross}
            data = {k: v for k, v in data.items() if k in keep}
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            pass
    return out

_MAX_CROSS_PROJECT_SCAN = 20

_ALIAS_HIDDEN_SEGMENTS = ("personal/", "roles/", "_pending_review")


def _alias_memory_text(mem_text: str) -> str:
    """alias 帶入他專案 MEMORY.md 時只留目錄性文字：去表格列、去空行、
    去提到 personal/ roles/ 待審區的行（他人與個人層連名字都不外露）。"""
    out: List[str] = []
    for line in mem_text.split("\n"):
        if not line.strip():
            continue
        if line.startswith("|") and "|" in line[1:]:
            continue
        low = line.lower()
        if any(seg in low for seg in _ALIAS_HIDDEN_SEGMENTS):
            continue
        out.append(line)
    return "\n".join(out).strip()


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
    List[Tuple[AtomEntry, Path]],  # matched_with_dir（已排序：RRF×activation 或 legacy ACT-R）
    Dict[str, str],                # atom_source（name → trigger/bm25/vector）
    List[Tuple[AtomEntry, Path]],  # all_atoms（含跨專案補入）
    list,                          # sem_atoms（vector 原始結果，供 blind-spot 統計）
    Dict[str, List[Dict]],         # section_hints（vector section 提示）
    set,                           # alias_injected_projects
    str,                           # intent
    Dict[str, Dict],               # caches：{"content": path→text, "access": md path→access dict}
]:
    """收集並排序本輪可注入的 atom 候選。append lines（alias 注入）。

    caches 隨管線下傳（assemble_injection 續用）——同 atom 本 prompt 只實讀一次。
    """
    atom_index = state.get("atom_index", {})
    already_injected = state.get("injected_atoms", [])
    content_cache: Dict[str, str] = {}
    access_cache: Dict[str, Dict] = {}
    caches: Dict[str, Dict] = {"content": content_cache, "access": access_cache}

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
    _cross_cache = _load_cross_project_cache(_all_cross)
    for _cross_slug, cross_mem in _all_cross:
        _cached = _cross_cache.get(str(cross_mem))
        aliases = _cached["aliases"] if _cached else parse_project_aliases(cross_mem)
        if aliases and any(alias in prompt_lower for alias in aliases):
            try:
                mem_text = (cross_mem / MEMORY_INDEX).read_text(encoding="utf-8-sig")
                mem_text = _alias_memory_text(mem_text)
                lines.append(f"[Guardian:AliasMatch] {_cross_slug} matched via alias")
                if mem_text:
                    lines.append(f"[ProjectMemory:{_cross_slug}]\n{mem_text}")
                alias_injected_projects.add(_cross_slug)
                _atom_debug_log("CrossProject", f"{_cross_slug} alias → MEMORY.md 目錄", config)
            except (OSError, UnicodeDecodeError):
                pass
    trigger_hits: Dict[str, int] = {}  # RRF trigger 路排序依據（命中數降冪）
    for (name, rel_path, triggers), base_dir in all_atoms:
        if name in atom_source:
            continue  # 同名去重：all_atoms 多層（global/project/cross）混入同名時只取首見
        if name not in already_injected and any_trigger_hit(triggers, prompt_lower):
            matched_with_dir.append(((name, rel_path, triggers), base_dir))
            atom_source[name] = "trigger"
            trigger_hits[name] = count_trigger_hits(triggers, prompt_lower)

    intent = classify_intent(prompt)

    kw_matched_names = {e[0][0] for e in matched_with_dir}
    trigger_hit_count = len(matched_with_dir)  # 純 trigger 命中數（BM25 合併前快照）

    # BM25 over global layer (replaces vector round-trip for global atoms).
    # Only run if no/few trigger hits (≤2). Project layer still uses vector below.
    vs_cfg = config.get("vector_search", {})
    bm25_route: List[str] = []  # RRF bm25 路（bm25_match 已依分數排序、min_score 已過濾）
    if vs_cfg.get("global_layer", "bm25") == "bm25" and len(matched_with_dir) <= 2:
        global_atoms = [e for e in all_atoms if e[1] == MEMORY_DIR.parent]
        if global_atoms:
            global_entries = [e[0] for e in global_atoms]
            bm25_hits = bm25_match(
                prompt, global_entries,
                min_score=vs_cfg.get("bm25_min_score", BM25_MIN_SCORE_DEFAULT),
                top_k=vs_cfg.get("bm25_top_k", 3),
            )
            bm25_route = [entry[0] for entry in bm25_hits]
            for entry in bm25_hits:
                _merge_hit(
                    entry[0], global_atoms, "bm25",
                    matched_with_dir, atom_source, kw_matched_names, already_injected,
                )

    # 向量路可見性：layers 白名單＝候選池同一套（global + 本專案 shared + 本人 role/personal）。
    # 管理職不豁免——管理職多的是待審清單，不是別人的 personal（SPEC §8.2）。
    _v4_id = state.get("user_identity", {})
    _v4_user = _v4_id.get("user") or None
    _v4_roles = _v4_id.get("roles") or None
    _sess_cwd = str((state.get("session") or {}).get("cwd") or "")
    _vis_layers = visible_vector_layers(
        atom_index.get("project_slug", ""), _v4_user, _v4_roles,
        include_local=bool(_sess_cwd) and _is_under_claude_dir(_sess_cwd),
    )
    # Vector 兩用途：hits=0 → 全層 fallback；hits>0 → 專案層 enrichment
    #（trigger/BM25 只擅長全域層關鍵詞，專案層語意近似仍值得補充；
    #  結果仍受 assemble 端 TURN_BUDGET_LIMIT 硬頂與服務端 min_score 約束）。
    # enrichment 前置條件：trigger 已命中 ≥3（keyword 訊號充足）就不再為專案層
    # 每 prompt 打 vector round-trip（省 200-500ms；召回缺口由 trigger 命中兜底）。
    project_atoms = [e for e in all_atoms if e[1] != MEMORY_DIR.parent]
    full_fallback = (
        len(matched_with_dir) == 0 or vs_cfg.get("global_layer") != "bm25"
    )
    if full_fallback or (project_atoms and trigger_hit_count < 3):
        sem_atoms = _semantic_search(
            prompt, config, intent=intent,
            user=_v4_user, roles=_v4_roles,
            session_id=session_id, layers=_vis_layers,
        )
    else:
        sem_atoms = []
    if not full_fallback and sem_atoms:
        # enrichment 模式：只取專案層命中，全域層交給 trigger/BM25
        project_names = {e[0][0] for e in project_atoms}
        sem_atoms = [s for s in sem_atoms if s[0] in project_names]
        if sem_atoms:
            _atom_debug_log(
                "ENRICH",
                f"project-layer vector enrichment: +{len(sem_atoms)} "
                f"({', '.join(s[0] for s in sem_atoms)})",
                config,
            )
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

    # Supersedes filtering（讀過的內文入 content_cache，assemble 段免重讀）
    superseded_names: set = set()
    for (name, rel_path, triggers), base_dir in matched_with_dir:
        atom_path = (base_dir / rel_path) if rel_path else (base_dir / "memory" / f"{name}.md")
        if not atom_path.exists():
            continue
        text = read_atom_text(atom_path, content_cache)
        if text is None:
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

    def _rank_of(entry) -> float:
        """ACT-R 注入 rank（activation − 分心懲罰，憲法 Distraction 對策）。"""
        (name, rel_path, _triggers), base_dir = entry
        atom_dir = (base_dir / rel_path).parent if rel_path else (base_dir / "memory")
        return compute_injection_rank(name, atom_dir, config, access_cache)

    # 排序：RRF 融合（相關性路 rank 融合 × activation 乘性調節）；
    # fusion="legacy" 回退純 ACT-R rank 排序。入場過濾（各路 min_score）不變。
    fusion = vs_cfg.get("fusion", "rrf")
    if fusion == "rrf" and matched_with_dir:
        trigger_route = sorted(trigger_hits, key=trigger_hits.get, reverse=True)
        vector_route = [s[0] for s in sem_atoms]
        rrf_scores = rrf_fuse({
            "trigger": trigger_route,
            "bm25": bm25_route,
            "vector": vector_route,
        })

        def _fused_key(entry) -> float:
            name = entry[0][0]
            return rrf_scores.get(name, 0.0) * math.exp(
                RRF_ACTIVATION_GAIN * _rank_of(entry)
            )

        matched_with_dir.sort(key=_fused_key, reverse=True)
    else:
        matched_with_dir.sort(key=_rank_of, reverse=True)

    return (
        matched_with_dir, atom_source, all_atoms,
        sem_atoms, section_hints, alias_injected_projects, intent,
        caches,
    )

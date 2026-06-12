"""
handlers/session_start.py — SessionStart hook handler

最大的 handler（~400 行）。負責：
- V5 P0 log rotation
- Session 去重 / merged_into 處理
- atom_index 解析 + V4 role-aware atoms 收集
- MEMORY.md 動態重生（V4 layout）
- _AIDocs bridge / project delegate hook
- Periodic review / oscillation / rut / wisdom reflection / long_die / MCP health / REG-005 等多項 SessionStart 提醒
- Vector service fire-and-forget bg subprocess
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import (
    CLAUDE_DIR, WORKFLOW_DIR, MEMORY_DIR, EPISODIC_DIR,
    MEMORY_INDEX,
    _now_iso, _atom_debug_error,
    cwd_to_project_slug, get_project_memory_dir, find_project_root,
    register_project,
    read_state, write_state, new_state, _find_active_sibling_state,
    _check_mcp_servers,
    _is_under_claude_dir, is_local_realm_path, REALM_AUTOMOVE_MARKER,
)
from wg_atoms import (
    parse_memory_index, parse_aidocs_index, extract_aidocs_keywords,
)
from wg_evasion import (
    _load_oscillation_warnings, _detect_rut_patterns, _check_periodic_review_due,
)
from wg_roles import (
    get_current_user, load_user_role, is_management, bootstrap_personal_dir,
)
from handlers._shared import (
    _MEMORY_MD_AUTO_HEADER, _V4_TRIGGER_LINE_RE,
    _call_project_hook, _cleanup_old_states,
    WISDOM_AVAILABLE, get_reflection_summary,
)

# Ollama client 在 tools/ 下（dispatcher 已加 sys.path）
sys.path.insert(0, str(Path.home() / ".claude" / "tools"))
try:
    from ollama_client import check_long_die_status
except ImportError:
    check_long_die_status = lambda: None  # noqa: E731


def _collect_v4_role_atoms(
    project_mem_dir: Optional[Path], user: str, roles: List[str],
) -> List[Tuple[str, str, List[str]]]:
    """列出使用者可見的 V4 sub-layer atoms（SPEC §8.1）。"""
    if not project_mem_dir or not project_mem_dir.is_dir():
        return []

    out: List[Tuple[str, str, List[str]]] = []
    mem_dir_name = project_mem_dir.name

    scan_targets: List[Path] = []
    shared = project_mem_dir / "shared"
    if shared.is_dir():
        scan_targets.append(shared)
    roles_root = project_mem_dir / "roles"
    for r in roles:
        rd = roles_root / r
        if rd.is_dir():
            scan_targets.append(rd)
    personal_dir = project_mem_dir / "personal" / user
    if personal_dir.is_dir():
        scan_targets.append(personal_dir)

    for base in scan_targets:
        for md in sorted(base.glob("**/*.md")):
            rel_parts = md.relative_to(base).parts
            if any(p.startswith("_") for p in rel_parts[:-1]):
                continue
            if md.name in (MEMORY_INDEX, "_ATOM_INDEX.md"):
                continue
            if md.name.startswith("_") or md.name.startswith("SPEC_"):
                continue
            try:
                text = md.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            tm = _V4_TRIGGER_LINE_RE.search(text)
            triggers: List[str] = []
            if tm:
                triggers = [t.strip().lower() for t in tm.group(1).split(",") if t.strip()]
            layer_rel = md.relative_to(project_mem_dir)
            rel_path = f"{mem_dir_name}/{layer_rel.as_posix()}"
            out.append((md.stem, rel_path, triggers))
    return out


def _regenerate_role_filtered_memory_index(
    project_mem_dir: Path, user: str, roles: List[str], management: bool,
    v4_entries: List[Tuple[str, str, List[str]]],
) -> None:
    """V4：依角色動態寫 {proj}/.claude/memory/MEMORY.md（SPEC §3）。"""
    target = project_mem_dir / MEMORY_INDEX
    if target.exists():
        try:
            first = target.read_text(encoding="utf-8-sig").split("\n", 1)[0].strip()
        except (OSError, UnicodeDecodeError):
            first = ""
        if first != _MEMORY_MD_AUTO_HEADER:
            return

    lines = [
        _MEMORY_MD_AUTO_HEADER,
        f"# MEMORY Index — {user} ({', '.join(roles) or 'programmer'})",
        "",
        f"> 由 workflow-guardian SessionStart 生成。依角色 filter。",
        f"> User: {user} | Roles: {', '.join(roles) or 'programmer'} | Management: {management}",
        "",
        "| Atom | Path | Trigger | Scope |",
        "|------|------|---------|-------|",
    ]
    for name, rel, triggers in sorted(v4_entries, key=lambda e: e[0]):
        parts = Path(rel).parts
        scope = ""
        try:
            subscope = parts[1]
            if subscope == "shared":
                scope = "shared"
            elif subscope == "roles" and len(parts) >= 4:
                scope = f"role:{parts[2]}"
            elif subscope == "personal" and len(parts) >= 4:
                scope = f"personal:{parts[2]}"
        except IndexError:
            pass
        trig_str = ", ".join(triggers) if triggers else ""
        lines.append(f"| {name} | {rel} | {trig_str} | {scope} |")
    try:
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as e:
        _atom_debug_error("V4:regenerate_memory_md", e)


def _count_pending_review(project_mem_dir: Optional[Path]) -> int:
    if not project_mem_dir:
        return 0
    pr = project_mem_dir / "shared" / "_pending_review"
    if not pr.is_dir():
        return 0
    try:
        return sum(1 for p in pr.glob("*.md"))
    except OSError:
        return 0


def _count_recent_auto_atoms(user: str, cwd: str, hours: int = 24) -> int:
    """[F18] Count auto-extracted-v4.1 atoms created within last N hours."""
    import re as _re
    count = 0
    cutoff = datetime.now() - timedelta(hours=hours)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    dirs_to_scan: List[Path] = []
    project_root = find_project_root(cwd)
    if project_root:
        d = Path(project_root) / ".claude" / "memory" / "personal" / "auto" / user
        if d.is_dir():
            dirs_to_scan.append(d)
    d = CLAUDE_DIR / "memory" / "personal" / "auto" / user
    if d.is_dir() and d not in dirs_to_scan:
        dirs_to_scan.append(d)

    for auto_dir in dirs_to_scan:
        for md_file in auto_dir.glob("*.md"):
            if md_file.name.startswith("_"):
                continue
            try:
                text = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if "auto-extracted-v4.1" not in text:
                continue
            m = _re.search(r'^-\s*Created:\s*(\S+)', text, _re.MULTILINE)
            if m:
                if m.group(1) >= cutoff_str:
                    count += 1
            else:
                try:
                    mtime = md_file.stat().st_mtime
                    if mtime >= cutoff.timestamp():
                        count += 1
                except OSError:
                    pass
    return count


def handle_session_start(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "unknown")
    cwd = input_data.get("cwd", "")
    source = input_data.get("source", "startup")

    # V5 P0: log rotation — prevent runaway log bloat
    try:
        from wg_core import rotate_log_if_oversized
        rotate_log_if_oversized(WORKFLOW_DIR / "guardian-crash.log", max_mb=10)
        rotate_log_if_oversized(WORKFLOW_DIR / "extract-worker.log", max_mb=10)
        rotate_log_if_oversized(CLAUDE_DIR / "Logs" / "codex-companion.log", max_mb=10)
    except Exception as e:
        _atom_debug_error("session_start:log_rotation", e)

    # ── V3/1.5A: SessionStart 去重 ──
    sibling = None
    if source != "compact":
        sibling = _find_active_sibling_state(cwd, session_id)
        if sibling and source == "resume":
            redirect_state = new_state(session_id, cwd, source)
            redirect_state["merged_into"] = sibling["session"]["id"]
            redirect_state["phase"] = "merged"
            write_state(session_id, redirect_state)
            lines = [f"[Workflow Guardian] Session merged ({source})."]
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": "\n".join(lines),
                }
            }, ensure_ascii=False))
            sys.exit(0)

    existing = read_state(session_id)
    if existing and source in ("compact", "resume"):
        # V5+ realm 閘門已知限制：compact/resume 複用舊 state 的 atom_index 快取，
        # 不重建候選。故若 session 於 ~/.claude 啟動（local 在快取）後跨環境 resume
        # 到外部專案 cwd，殘留的 local 候選不會被重濾（極低頻：同一 session id 跨
        # 機器/跨根 resume）。重啟（source=startup/新 session）即走上方重建分支正確過濾。
        state = existing
        prev_atoms = state.get("injected_atoms", [])
        state["injected_atoms"] = []
        mod_count = len(state.get("modified_files", []))
        kq_count = len(state.get("knowledge_queue", []))
        phase = state.get("phase", "working")
        lines = [
            f"[Workflow Guardian] Session resumed ({source}). Phase: {phase}.",
            f"Modified files: {mod_count}. Knowledge queue: {kq_count}.",
        ]
        if mod_count > 0:
            files = [m["path"].rsplit("/", 1)[-1] for m in state["modified_files"][-5:]]
            lines.append(f"Recent: {', '.join(files)}")
        if kq_count > 0:
            items = [q["content"][:40] for q in state["knowledge_queue"][:3]]
            lines.append(f"Pending knowledge: {'; '.join(items)}")
        # 注（2026-06-01 Phase-0 probe）：full `/compact` 實測會觸發 SessionStart(source=compact)
        # （序：PreCompact → SessionStart(compact) → PostCompact），故本分支非死碼、保留。
        # 但此處僅「列出壓縮前 atom 名稱」（資訊性 ~30 tok）；完整內文的壓縮後復原由
        # PostCompact(snapshot stash)→PostToolBatch(一次性注入) 負責（選配 #4），兩者互補不重複。
        # 且 SessionStart(compact) 不保證觸發（no-op / auto-compact 僅 PreCompact+PostCompact），
        # 故內文復原不可依賴本分支。詳見 _AIDocs/ClaudeCodeInternals/cc-hook-system.md。
        if prev_atoms:
            atom_names = ", ".join(prev_atoms)
            lines.append(f"[Atom Recovery] 壓縮前已載入: {atom_names}")
    else:
        state = new_state(session_id, cwd, source)
        if sibling and source == "startup":
            state["_skip_vector_init"] = True

        global_atoms = parse_memory_index(MEMORY_DIR)
        # ── V5+ realm 注入閘門（範疇限定）──────────────────────────────────────
        # 此處為「新 session 候選快取建立處」——user_prompt_submit 只讀此快取做
        # trigger 比對注入，故閘門落點在此、非注入迴圈。外部專案（cwd∉~/.claude）
        # 濾掉 local-realm atom（index path 前綴 _AIDocs/_atoms/）；core（含 feedback-*
        # 所在的 _AIDocs/Failures/）不受影響。直接用既有 3-tuple 的 path 過濾，不查
        # realm map、不改 tuple 形狀。is_local_realm_path 為 None（lib import 失敗）→
        # 不過濾（fail-open 回退至 pre-S2 全注入，安全）。
        if is_local_realm_path is not None and not _is_under_claude_dir(cwd):
            global_atoms = [
                (n, p, t) for (n, p, t) in global_atoms if not is_local_realm_path(p)
            ]
        project_mem_dir = get_project_memory_dir(cwd)
        project_atoms = parse_memory_index(project_mem_dir) if project_mem_dir else []
        project_root = find_project_root(cwd)

        register_project(cwd)

        v4_user = ""
        v4_roles: List[str] = []
        v4_mgmt = False
        v4_entries: List[Tuple[str, str, List[str]]] = []
        try:
            v4_user = get_current_user()
            bootstrap_personal_dir(cwd, v4_user)
            role_info = load_user_role(cwd, v4_user)
            v4_roles = role_info.get("roles") or ["programmer"]
            v4_mgmt = is_management(cwd, v4_user)
            if project_mem_dir:
                v4_entries = _collect_v4_role_atoms(project_mem_dir, v4_user, v4_roles)
        except Exception as e:
            _atom_debug_error("V4:role_bootstrap", e)

        state["user_identity"] = {
            "user": v4_user,
            "roles": v4_roles,
            "management": v4_mgmt,
        }

        v4_layout_active = bool(project_mem_dir) and any(
            (project_mem_dir / d).is_dir() for d in ("shared", "roles", "personal")
        )

        if v4_layout_active:
            project_atoms_merged = list(v4_entries)
        else:
            project_atoms_merged = list(project_atoms)
            existing_names = {n for n, _p, _t in project_atoms_merged}
            for name, rel_path, triggers in v4_entries:
                if name in existing_names:
                    continue
                project_atoms_merged.append((name, rel_path, triggers))
                existing_names.add(name)

        state["atom_index"] = {
            "global": [(n, p, t) for n, p, t in global_atoms],
            "project": [(n, p, t) for n, p, t in project_atoms_merged],
            "project_memory_dir": str(project_mem_dir) if project_mem_dir else "",
            "project_root": str(project_root) if project_root else "",
        }
        state["injected_atoms"] = []
        state["phase"] = "working"

        if v4_layout_active and v4_user:
            _regenerate_role_filtered_memory_index(
                project_mem_dir, v4_user, v4_roles, v4_mgmt, v4_entries,
            )

        aidocs_entries = parse_aidocs_index(project_root) if project_root else []
        aidocs_keywords = extract_aidocs_keywords(aidocs_entries) if aidocs_entries else {}
        state["aidocs"] = {
            "project_root": str(project_root) if project_root else "",
            "entries": [(f, d) for f, d, _kw in aidocs_entries],
            "keywords": aidocs_keywords,
        }

        g_names = [n for n, _, _ in global_atoms]
        p_names = [n for n, _, _ in project_atoms_merged]
        lines = [
            "[Workflow Guardian] Active.",
            f"Global: {len(g_names)} atoms. Project: {len(p_names)}.",
        ]

        # ── 索引載入後校驗（2026-06-12 總檢視 E1）─────────────────────────
        # 防 _atom_index.json 被 funnel 外改壞 → 注入鏈靜默降效（2026-05 前科
        # 同型）。廉價雙向：index→disk 存在性 + memory/ 頂層→index 漏登。
        # 失配＝log（always-on）+ 可見 advisory，不自動重建（避免與 funnel 互搶）。
        try:
            _idx_missing = [
                n for n, p, _t in global_atoms
                if p and not (CLAUDE_DIR / p).exists()
            ]
            _idx_paths = {
                str((CLAUDE_DIR / p).resolve()).lower()
                for _n, p, _t in global_atoms if p
            }
            _disk_orphans = [
                f.stem for f in MEMORY_DIR.glob("*.md")
                if not f.name.startswith("_") and f.name != MEMORY_INDEX
                and str(f.resolve()).lower() not in _idx_paths
            ]
            if _idx_missing or _disk_orphans:
                _atom_debug_error(
                    "session_start:index_validate",
                    RuntimeError(
                        f"index 失配 missing_on_disk={_idx_missing[:5]} "
                        f"unindexed_on_disk={_disk_orphans[:5]}"
                    ),
                )
                lines.append(
                    "[Guardian:IndexValidate] ⚠ _atom_index.json 與磁碟失配"
                    f"（索引指向不存在 {len(_idx_missing)} 筆 / 磁碟未登記 "
                    f"{len(_disk_orphans)} 筆）。請跑 "
                    "python tools/sync-atom-index.py 重建；詳 Logs/atom-debug。"
                )
        except Exception as e:
            _atom_debug_error("session_start:index_validate", e)
        if v4_user:
            lines.append(
                f"[Role] user={v4_user} roles={','.join(v4_roles) or 'programmer'} mgmt={v4_mgmt}"
            )
            if v4_mgmt:
                pending = _count_pending_review(project_mem_dir)
                if pending > 0:
                    lines.append(f"[Pending Review] {pending} 件待裁決（shared/_pending_review/）")

        if v4_user and config.get("userExtraction", {}).get("enabled", False):
            try:
                v41_count = _count_recent_auto_atoms(v4_user, cwd, hours=24)
                if v41_count > 0:
                    lines.append(
                        f"[V4.1] 昨日新增 {v41_count} 條自動萃取 atom，/memory-peek 檢視"
                    )
            except Exception as e:
                _atom_debug_error("V4.1:daily_push", e)

        max_entries = config.get("aidocs", {}).get("max_session_start_entries", 15)
        if aidocs_entries:
            fnames = [f for f, _d, _kw in aidocs_entries[:max_entries]]
            lines.append(f"[AIDocs] {len(aidocs_entries)} docs: {', '.join(fnames)}")
            lines.append("[查閱知識庫] Read _AIDocs/_INDEX.md")
        elif project_root and not (Path(project_root) / "_AIDocs").is_dir():
            lines.append("[Guardian] No _AIDocs found. Run /init-project to create.")

        if project_root:
            try:
                ph_result = _call_project_hook(
                    project_root, "session_start",
                    {"cwd": cwd, "session_id": session_id},
                )
                if ph_result:
                    for extra_line in ph_result.get("lines", []):
                        if extra_line:
                            lines.append(extra_line)
            except Exception as e:
                _atom_debug_error("project_hook:session_start", e)

    # ── V5+ realm：本地範疇 catalog 注入（補完 index 層 realm 一致性）────────────
    # core catalog 走 CLAUDE.md @import memory/MEMORY.md（全專案，fail-safe 退路）；
    # 本地範疇明細抽到側檔 memory/_local_catalog.md，僅核心環境（cwd∈~/.claude）此處注入，
    # 外部專案不注入 → always-load 省本地段。對 startup/resume/compact 兩分支皆生效。
    # fail-safe：缺檔/讀錯/非核心 → 靜默略過（catalog 本屬 readability，local atom 仍 trigger 注入）。
    try:
        if _is_under_claude_dir(cwd):
            _lc = MEMORY_DIR / "_local_catalog.md"
            if _lc.exists():
                _lc_txt = _lc.read_text(encoding="utf-8-sig").strip()
                if _lc_txt:
                    lines.append(_lc_txt)
    except Exception as e:
        _atom_debug_error("realm:local_catalog_inject", e)

    # V5+ Realm 維度：上個 session 自動歸類搬移的不靜默提示（永不靜默；讀後清 marker）
    try:
        if REALM_AUTOMOVE_MARKER.exists():
            try:
                _rm = json.loads(REALM_AUTOMOVE_MARKER.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                _rm = []
            if isinstance(_rm, list) and _rm:
                _names = ", ".join(
                    (f"{m.get('slug','?')}（{m.get('via')}）"
                     if m.get("via") in ("LLM", "Else") else m.get("slug", "?"))
                    for m in _rm[:6]
                )
                _more = f" 等 {len(_rm)} 顆" if len(_rm) > 6 else f"（{len(_rm)} 顆）"
                lines.append(
                    f"[Realm] 已自動歸 local：{_names}{_more}。"
                    f"外部專案不再注入；如需還原：python tools/atom-set-realm.py set <slug> --to-core"
                )
                # 移檔後 doc-sync（user 補充）：舊 path/檔名引用提示需同步的說明文件
                _drefs: Dict[str, List[str]] = {}
                for _m in _rm:
                    for _k, _v in (_m.get("doc_refs") or {}).items():
                        _drefs.setdefault(_k, []).extend(_v or [])
                if _drefs:
                    _parts = "；".join(
                        f"{_k}→{', '.join(sorted(set(_v)))}" for _k, _v in list(_drefs.items())[:4]
                    )
                    lines.append(f"[Realm] ⚠ 說明文件含被搬 atom 的舊引用，請查是否需同步：{_parts}")
            try:
                REALM_AUTOMOVE_MARKER.unlink()
            except OSError:
                pass
    except Exception as e:
        print(f"[realm] automove notice error: {e}", file=sys.stderr)

    try:
        review_reminder = _check_periodic_review_due(config)
        if review_reminder:
            lines.append(review_reminder)
            state["review_due"] = True
    except Exception as e:
        print(f"[v2.6] Review check error: {e}", file=sys.stderr)

    try:
        osc_warning = _load_oscillation_warnings()
        if osc_warning:
            lines.append(osc_warning)
    except Exception as e:
        print(f"[v2.16] Oscillation load error: {e}", file=sys.stderr)

    try:
        rut_warning = _detect_rut_patterns(state, config)
        if rut_warning:
            lines.append(rut_warning)
    except Exception as e:
        print(f"[v2.17] Rut detection error: {e}", file=sys.stderr)

    if WISDOM_AVAILABLE:
        try:
            wisdom_lines = get_reflection_summary()
            lines.extend(wisdom_lines)
        except Exception as e:
            print(f"[v2.8] Wisdom reflection error: {e}", file=sys.stderr)

    try:
        long_die = check_long_die_status()
        if long_die:
            backend_name = long_die.get("backend", "remote")
            until = long_die.get("until", "?")
            lines.append(
                f"[⚠ Long DIE] 遠端 Ollama backend '{backend_name}' 多次連線失敗，"
                f"已暫停至 {until}。請確認是否要永久停用此 backend？"
                f"（回覆「停用 {backend_name}」或「保持」）"
            )
    except Exception as e:
        print(f"[dual-backend] Long DIE check error: {e}", file=sys.stderr)

    try:
        mcp_issues = _check_mcp_servers()
        if mcp_issues:
            lines.append("[MCP] " + "; ".join(mcp_issues))
    except Exception as e:
        print(f"[mcp-health] Check error: {e}", file=sys.stderr)

    write_state(session_id, state)

    try:
        _cleanup_old_states()
    except Exception as e:
        print(f"[v3] SessionStart cleanup error: {e}", file=sys.stderr)

    try:
        (WORKFLOW_DIR / "vector_ready.flag").unlink(missing_ok=True)
    except OSError:
        pass

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }, ensure_ascii=False))

    # ── V3/1.5C: Vector service — fire-and-forget bg subprocess ────────────
    if (config.get("vector_search", {}).get("auto_start_service", True)
            and not state.get("_skip_vector_init")):
        try:
            vs_port = config.get("vector_search", {}).get("service_port", 3849)
            vs_script = str(CLAUDE_DIR / "tools" / "memory-vector-service" / "service.py")
            flag_path = str(WORKFLOW_DIR / "vector_ready.flag")
            probe_log_path = str(CLAUDE_DIR / "Logs" / "vector-observation-probe.log")
            _bg_code = f"""
import urllib.request, urllib.error, urllib.parse, subprocess, sys, time, os, json, re
from pathlib import Path

port = {vs_port}
base = f"http://127.0.0.1:{{port}}"

try:
    urllib.request.urlopen(f"{{base}}/health", timeout=2)
except Exception:
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        sock.close()
        kw = {{"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}}
        if sys.platform == "win32":
            kw["creationflags"] = 0x08000000
        else:
            kw["start_new_session"] = True
        subprocess.Popen([sys.executable, {repr(vs_script)}], **kw)
    except OSError:
        sock.close()

ready = False
for _ in range(30):
    try:
        urllib.request.urlopen(f"{{base}}/health", timeout=2)
        ready = True
        break
    except Exception:
        time.sleep(0.5)

if ready:
    try:
        Path({repr(flag_path)}).write_text("ready", encoding="utf-8")
    except Exception:
        pass

if ready:
    try:
        urllib.request.urlopen(f"{{base}}/search?q=warmup&top_k=1&min_score=0.99", timeout=15)
    except Exception:
        pass

probe_q = "workflow guardian SessionStart 機制"
vec_count = -1
fallback_used = not ready
if ready:
    try:
        params = urllib.parse.urlencode({{"q": probe_q, "top_k": 5, "min_score": 0.5}})
        with urllib.request.urlopen(f"{{base}}/search/ranked?{{params}}", timeout=10) as r:
            data = json.loads(r.read())
            vec_count = len(data) if isinstance(data, list) else 0
    except Exception:
        vec_count = -1
        fallback_used = True

kw_count = 0
mem_dir = Path({repr(str(CLAUDE_DIR / "memory"))})
try:
    pattern = re.compile("workflow|guardian|SessionStart", re.IGNORECASE)
    for md in mem_dir.rglob("*.md"):
        try:
            if pattern.search(md.read_text(encoding="utf-8", errors="ignore")):
                kw_count += 1
        except Exception:
            pass
except Exception:
    pass

try:
    log_p = Path({repr(probe_log_path)})
    log_p.parent.mkdir(parents=True, exist_ok=True)
    rec = {{
        "ts": time.time(),
        "session_id": {repr(session_id)},
        "fn": "session_start_probe",
        "flag_state": "ready" if ready else "no_flag",
        "result_count": vec_count,
        "fallback_used": fallback_used,
        "kw_count": kw_count,
        "probe_q": probe_q,
    }}
    with open(str(log_p), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\\n")
except Exception:
    pass
"""
            _bg_kwargs: dict = {
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if sys.platform == "win32":
                _bg_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            else:
                _bg_kwargs["start_new_session"] = True
            subprocess.Popen(
                [sys.executable, "-c", _bg_code],
                **_bg_kwargs,
            )
        except Exception as e:
            _atom_debug_error("注入:vector_service_bg", e)

    sys.exit(0)

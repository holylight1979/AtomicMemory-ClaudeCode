"""
handlers/session_start.py — SessionStart hook handler

最大的 handler（~400 行）。負責：
- Log rotation
- Session 去重 / merged_into 處理
- atom_index 解析 + V4 role-aware atoms 收集
- MEMORY.md 動態重生（V4 layout）
- _AIDocs bridge / project delegate hook
- Periodic review / oscillation / rut / wisdom reflection / long_die / MCP health / REG-005 等多項 SessionStart 提醒
- Vector service fire-and-forget bg subprocess
"""

import json
import os
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
    _is_under_claude_dir, is_local_realm_path, is_cross_project_local,
    iter_realm_category_dirs,
    REALM_AUTOMOVE_MARKER,
)
from wg_atoms import (
    parse_memory_index, parse_aidocs_index, extract_aidocs_keywords,
    filter_visible, scope_from_rel_path,
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


def _check_se_sentinel_residual(lines: List[str], min_age_s: float = 60.0) -> None:
    """SessionEnd 哨兵殘留（session_end._se_sentinel_arm 留下、未被正常收尾拆除）
    → 告警一行 + 清除。只認 mtime 超過 min_age_s 者：並行 session 的 SessionEnd
    可能正在跑（<30s 窗），剛 arm 的哨兵不是殘留，不得誤清誤報。"""
    import time as _time
    se_dir = wg_core_workflow_dir() / "se-sentinel"
    if not se_dir.is_dir():
        return
    now = _time.time()
    residual = []
    for p in sorted(se_dir.glob("*.json")):
        try:
            if now - p.stat().st_mtime > min_age_s:
                residual.append(p)
        except OSError:
            continue
    if not residual:
        return
    sids = ", ".join(p.stem[:12] + "…" for p in residual[:3])
    lines.append(
        f"[Guardian:SE-Sentinel] 偵測到 {len(residual)} 個 SessionEnd "
        f"未跑完的殘留哨兵（{sids}）——上次收尾（episodic 生成/晉升掃描/"
        "realm sweep 等）可能中斷未完成。"
    )
    for p in residual:
        try:
            p.unlink()
        except OSError:
            pass


def wg_core_workflow_dir() -> Path:
    """取 wg_core.WORKFLOW_DIR 的即時值（測試 monkeypatch wg_core 後仍生效）。"""
    import wg_core
    return wg_core.WORKFLOW_DIR


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
        _atom_debug_error("regenerate_memory_md", e)


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
    """Count auto-extracted-v4.1 atoms created within last N hours."""
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


def _refresh_vector_flag(
    config: Dict[str, Any], *, flag_path: Optional[Path] = None
) -> str:
    """SessionStart 冷啟動關窗：服務已暖（health 200）則寫/保留 `vector_ready.flag`，
    首個 prompt 即可用 vector；ping 失敗才拆 flag（fail-closed，防信任指向死服務的舊
    flag——27d 靜默失效的教訓）。回 'kept'（服務活）/ 'cleared'（無回應→拆）。

    下方 fire-and-forget bg subprocess 仍會重啟服務 + 重驗/重建 flag + probe log；
    此僅在服務本就常駐時提前把 flag 立好，消掉「拆→async 重建」之間的 no_flag 空窗
    （該空窗內早期搜尋 fallback 到 keyword）。ping timeout 短：服務活 ~ms、死則
    connection-refused 立即失敗，故對 SessionStart 延遲影響可忽略。
    """
    flag = flag_path or (WORKFLOW_DIR / "vector_ready.flag")
    port = config.get("vector_search", {}).get("service_port", 3849)
    try:
        import urllib.request
        urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.0)
    except Exception:
        try:
            flag.unlink(missing_ok=True)
        except OSError:
            pass
        return "cleared"
    try:
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text("ready", encoding="utf-8")
    except OSError:
        pass
    return "kept"


def _prune_aec_files(max_age_days: int = 7) -> int:
    """清 workflow/ 下 per-turn 執行期狀態檔的 TTL GC（mtime 超過 max_age_days）。

    對象：aec-report/ 與 aec-decision/（*.json，Python 寫報告 / Node 寫決策）、
    pan-pass/ 與 pan-deny/（*.flag / *.json，PAN 預告閘門 armed marker 與 deny 計數）。
    寫了不清會無限累積。在 SessionStart 順手掃一次（比照上方 log rotation 的開機
    打掃時機）。glob 副檔名白名單自然略過 atomic write 的 .tmp 過渡檔。
    fail-open：目錄不存在 / 單檔被別進程刪或鎖 → 略過不炸。回傳刪除檔數（供測試 / 觀測）。"""
    cutoff = (datetime.now() - timedelta(days=max_age_days)).timestamp()
    pruned = 0
    for sub, patterns in (
        ("aec-report", ("*.json",)),
        ("aec-decision", ("*.json",)),
        ("pan-pass", ("*.flag",)),
        ("pan-deny", ("*.json",)),
    ):
        for pattern in patterns:
            try:
                entries = list((WORKFLOW_DIR / sub).glob(pattern))
            except Exception:
                continue
            for p in entries:
                try:
                    if p.stat().st_mtime < cutoff:
                        p.unlink()
                        pruned += 1
                except Exception:
                    continue
    # 殘檔帳本 aec-tempfiles/<sid>.jsonl：過期且「帳上路徑全都已不在磁碟」才清——
    # 只要還有一個殘檔在，帳本就得留著讓 HUD 繼續列（帳本存在的意義就是追到處置為止）。
    try:
        ledgers = list((WORKFLOW_DIR / "aec-tempfiles").glob("*.jsonl"))
    except Exception:
        ledgers = []
    for p in ledgers:
        try:
            if p.stat().st_mtime >= cutoff:
                continue
            alive = False
            for line in p.read_text(encoding="utf-8").splitlines():
                try:
                    path = json.loads(line).get("path", "")
                except Exception:
                    continue
                if path and os.path.exists(path):
                    alive = True
                    break
            if not alive:
                p.unlink()
                pruned += 1
        except Exception:
            continue
    return pruned


HEALTH_RUN_STALE_DAYS = 10  # 週排程 + 3 天寬限；超過 = 排程器本身死了


def _health_advisory(last_run_path) -> list:
    """週健檢死人開關 → advisory 行（無異常回 []，不佔 context）。

    三種浮出：last-run 缺檔（從未跑/被清）、at 逾 HEALTH_RUN_STALE_DAYS 天
    （Task Scheduler 停擺）、上次健檢 red>0（有待處理項未看）。自身壞掉走
    _atom_debug_error，不阻斷 SessionStart。
    """
    try:
        if not last_run_path.exists():
            return [
                "[Guardian:HealthCheck] ⚠ 週健檢 last-run 不存在——排程未註冊或"
                "檔案被清。手動跑 python tools/health-weekly.py 並確認 schtasks"
                " Claude-Memory-WeeklyHealth 存在。"
            ]
        d = json.loads(last_run_path.read_text(encoding="utf-8"))
        at = datetime.fromisoformat(d.get("at", ""))
        age = (datetime.now() - at).days
        out = []
        if age > HEALTH_RUN_STALE_DAYS:
            out.append(
                f"[Guardian:HealthCheck] ⚠ 週健檢已 {age} 天未跑（上次 "
                f"{at:%Y-%m-%d}）——Task Scheduler 疑停擺，檢查 schtasks "
                "Claude-Memory-WeeklyHealth。"
            )
        if int(d.get("red", 0)) > 0:
            out.append(
                f"[Guardian:HealthCheck] 🔴 上次健檢有 {d['red']} 項需處理 → "
                f"Read {d.get('report', 'workflow/health-reports/')}"
            )
        return out
    except Exception as e:
        _atom_debug_error("session_start:health_advisory", e)
        return [
            "[Guardian:HealthCheck] ⚠ health-last-run.json 不可解析——健檢狀態"
            "未知，手動跑 python tools/health-weekly.py。"
        ]


def _scope_layout_advisory(project_mem_dir) -> list:
    """專案記憶尚未依 scope 分層整理 → 開場一行說明改動＋整理入口。

    記憶系統升級後（personal 只本人、專案規則進 shared 記提出者、他專案不注入），其他機器上
    的既有專案不會自己整理；「已整理」＝ _atom_index.json.layout 標記或 shared/_taxonomy.json
    （lib.atom_locations.scope_layout_classified）。純判定、fail-open。
    """
    try:
        if not project_mem_dir or not Path(project_mem_dir).is_dir():
            return []
        from atom_locations import scope_layout_classified
        if scope_layout_classified(Path(project_mem_dir)):
            return []
        return [
            "[Guardian:ScopeLayout] 記憶系統已改為 scope 分層：personal 只給本人、針對專案的規則進 shared "
            "並記提出者、他專案 atom 不再注入。本專案的記憶尚未依此整理（無 layout 標記／shared/_taxonomy.json）。"
            "使用者說「整理記憶分類」→ 走 /memory classify：plan 出建議表 → 使用者確認 personal 去向 → "
            "apply（搬檔、索引 scope 回寫、標記）→ 提醒把 .claude/memory 上傳版控。"
        ]
    except Exception as e:  # noqa: BLE001
        _atom_debug_error("session_start:scope_layout_advisory", e)
        return []


def _followup_advisory() -> list:
    """回訪到期 → 開場自動跑 tools/followup-check.py，把檢查結果＋自足交接推進 context。

    存在理由：「一週後再看數據」在 session 關掉後必然被遺忘；登記表 workflow/followups.json
    以「接手者零記憶」寫交接，到期後使用者任何一次開 CC 都會看到並能直接行動。
    每日提醒一次（--mark-shown），PASS 自動結案（--auto-close），首次整份、之後精簡（--brief）。
    純子程序、fail-open：失敗只 debug log，不阻斷 SessionStart。無到期項回 []。
    """
    try:
        import subprocess
        reg = WORKFLOW_DIR / "followups.json"
        if not reg.exists():
            return []
        r = subprocess.run(
            [sys.executable, str(CLAUDE_DIR / "tools" / "followup-check.py"),
             "--run", "--auto-close", "--brief", "--mark-shown"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=25)
        out = (r.stdout or "").strip()
        return [out] if out else []
    except Exception as e:
        _atom_debug_error("session_start:followup_advisory", e)
        return ["[Guardian:Followup] ⚠ 回訪檢查器執行失敗（見 atom-debug log）——手動跑 python tools/followup-check.py --run"]


def _unpushed_advisory() -> list:
    """本地有已 commit 未 push 的東西 → advisory 行（無則回 []，不佔 context）。

    存在理由：SessionEnd 的晉升自動提交把 push 丟到背景（30s 預算內不等網路），
    push 掛掉時 commit 只留在本地、當下沒人看得到。這裡在下個 session 開頭補上
    可見性，讓「背景 fail-open」不變成「永遠沒人發現」（可觀測性鐵律）。

    只讀 git 不寫，任何失敗回 []——沒有 upstream / 不是 repo / git 不在都算正常。
    """
    try:
        import subprocess
        if not (CLAUDE_DIR / ".git").exists():
            return []
        r = subprocess.run(
            ["git", "-C", str(CLAUDE_DIR), "rev-list", "--count", "@{u}..HEAD"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=5)
        if r.returncode != 0:  # 無 upstream / detached HEAD → 不是異常，不吵
            return []
        ahead = int((r.stdout or "0").strip() or 0)
        if ahead <= 0:
            return []
        return [
            f"[Guardian:Sync] ⚠ ~/.claude 本地有 {ahead} 筆 commit 未 push"
            f"（背景 push 可能失敗，見 Logs/auto-commit.log）→ 跑 git push 補推。"
        ]
    except Exception as e:
        _atom_debug_error("session_start:unpushed_advisory", e)
        return []


def handle_session_start(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "unknown")
    cwd = input_data.get("cwd", "")
    source = input_data.get("source", "startup")

    # log rotation — prevent runaway log bloat
    try:
        from wg_core import rotate_log_if_oversized
        rotate_log_if_oversized(WORKFLOW_DIR / "guardian-crash.log", max_mb=10)
        rotate_log_if_oversized(WORKFLOW_DIR / "extract-worker.log", max_mb=10)
        rotate_log_if_oversized(CLAUDE_DIR / "Logs" / "codex-companion.log", max_mb=10)
        _prune_aec_files(max_age_days=7)  # AEC 報告/決策檔 7 天 TTL（防執行期狀態檔無限累積）
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
        # 注：full `/compact` 會觸發 SessionStart(source=compact)
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
        # 所在的 _AIDocs/Failures/）不受影響。**例外**：is_cross_project_local 為真者
        # （storage 在 _atoms 但屬 CROSS_PROJECT_LOCAL_DOMAINS；清單目前為空、機制保留）保留——
        # 解開「儲存位置綁死注入範圍」，對偶 feedback-*。直接用既有 3-tuple 的 path 過濾，
        # 不查 realm map、不改 tuple 形狀。is_local_realm_path 為 None（lib import 失敗）→
        # 不過濾（fail-open 回退至 pre-S2 全注入，安全）。
        if is_local_realm_path is not None and not _is_under_claude_dir(cwd):
            global_atoms = [
                (n, p, t) for (n, p, t) in global_atoms
                if not is_local_realm_path(p) or is_cross_project_local(p)
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
            _atom_debug_error("role_bootstrap", e)

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

        # scope 可見性（SPEC §8.1）：候選池只留本人看得到的——personal 只給本人、
        # role 只給持有者；V3 / V4 佈局一視同仁。UPS 六條檢索路全從此池取，不再各自過濾。
        global_atoms = filter_visible(global_atoms, v4_user, v4_roles)
        project_atoms_merged = filter_visible(project_atoms_merged, v4_user, v4_roles)
        atom_scopes = {n: scope_from_rel_path(p, "global") for n, p, _t in global_atoms}
        atom_scopes.update({n: scope_from_rel_path(p, "shared") for n, p, _t in project_atoms_merged})
        project_slug = ""
        if project_root:
            try:
                project_slug = cwd_to_project_slug(str(project_root.resolve()))
            except OSError:
                project_slug = cwd_to_project_slug(str(project_root))

        state["atom_index"] = {
            "global": [(n, p, t) for n, p, t in global_atoms],
            "project": [(n, p, t) for n, p, t in project_atoms_merged],
            "project_memory_dir": str(project_mem_dir) if project_mem_dir else "",
            "project_root": str(project_root) if project_root else "",
            "project_slug": project_slug,
            "scopes": atom_scopes,
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

        # ── 全域 index 解析 fail-loud ──
        # 全域 index 檔存在但解析出 0 atom = 解析失敗（_ATOM_INDEX.md 表內空行/檔
        # 截斷等），非合法空層（全域恆有 atom）。不再 silent——log + 顯著 advisory。
        # 專案層可合法為空，故僅檢全域。
        try:
            if not g_names and (
                (MEMORY_DIR / "_atom_index.json").exists()
                or (MEMORY_DIR / "_ATOM_INDEX.md").exists()
                or (MEMORY_DIR / MEMORY_INDEX).exists()
            ):
                _atom_debug_error(
                    "session_start:global_index_zero",
                    RuntimeError("全域 index 檔存在但 parse_memory_index 回傳 0 atom"),
                )
                lines.append(
                    "[Guardian:IndexZero] ⚠ 全域 atom index 解析出 0 筆——index 檔存在但"
                    " parse 失敗（疑 _ATOM_INDEX.md 表內空行/格式損壞），trigger 注入將"
                    "全失效。跑 python tools/sync-atom-index.py 重建；詳 Logs/atom-debug。"
                )
        except Exception as e:
            _atom_debug_error("session_start:global_index_zero", e)

        # ── 索引載入後校驗 ─────────────────────────
        # 防 _atom_index.json 被 funnel 外改壞 → 注入鏈靜默降效。
        # 廉價雙向：index→disk 存在性 + memory/ 頂層→index 漏登。
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
            # 磁碟側：memory/ 根層 *.md ＋ 各範疇資料夾（memory/<範疇>/**、含 Failures）
            # 遞迴；`_` 前綴目錄（_reference/_INDEX 等）與 skip 名單由 iter_realm_category_dirs 剪掉。
            _disk_candidates = list(MEMORY_DIR.glob("*.md"))
            if iter_realm_category_dirs is not None:
                for _cat_dir in iter_realm_category_dirs(MEMORY_DIR):
                    _disk_candidates += [
                        f for f in _cat_dir.rglob("*.md")
                        if not any(part.startswith("_") for part in f.relative_to(_cat_dir).parts)
                    ]
            _disk_orphans = [
                f.stem for f in _disk_candidates
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

        # ── skill 計數 SoT 防呆 ──────────────────────────────
        # 補 PostToolUse 自動同步漏接者（如 Bash 刪 skill 目錄）：實檔
        # skills/*/SKILL.md 數 ≠ _skill_index.json count → advisory 提示跑
        # tools/skill-index.py --write。不自動改檔（與 PostToolUse 自動同步分工）。
        try:
            if (config or {}).get("skill_index", {}).get("enabled", True):
                import json as _json
                _sk_dir = CLAUDE_DIR / "skills"
                _true_sk = sum(1 for _ in _sk_dir.glob("*/SKILL.md"))
                _idx = _sk_dir / "_skill_index.json"
                _idx_n = None
                if _idx.exists():
                    try:
                        _idx_n = _json.loads(
                            _idx.read_text(encoding="utf-8-sig")).get("count")
                    except (ValueError, OSError):
                        _idx_n = None
                if _idx_n != _true_sk:
                    lines.append(
                        f"[Guardian:SkillIndex] ⚠ skills/ 實檔 {_true_sk} 個 ≠ "
                        f"_skill_index.json count={_idx_n}。請跑 "
                        "python tools/skill-index.py --write 同步計數與文件 marker。"
                    )
        except Exception as e:
            _atom_debug_error("session_start:skill_index_validate", e)

        # ── 週健檢死人開關 ──────────────────────────────────
        # tools/health-weekly.py（Task Scheduler 每週跑）落 health-last-run.json。
        # 缺檔/逾期 = 排程器本身死了；red>0 = 上次健檢有待處理項。兩者都必須
        # 在 session 內浮出（fail-open 必告知）——「靜默死 27 天」的最後防線。
        lines.extend(_health_advisory(WORKFLOW_DIR / "health-last-run.json"))

        # ── 未推送 commit ─────────────────────────────────────
        # SessionEnd 晉升自動提交的 push 走背景、失敗當下無人知 → 這裡補可見性。
        lines.extend(_unpushed_advisory())
        lines.extend(_followup_advisory())
        lines.extend(_scope_layout_advisory(project_mem_dir))

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
                        f"昨日新增 {v41_count} 條自動萃取 atom，/memory-peek 檢視"
                    )
            except Exception as e:
                _atom_debug_error("daily_push", e)

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

    # config.json 解析失敗 → 一行告警（load_config 標旗；fail-open 必浮出）
    if config.get("_config_parse_failed"):
        lines.append(
            "[Guardian:Config⚠] workflow/config.json 解析失敗，已退回內建 DEFAULTS"
            "——請修復 JSON（詳 Logs/atom-debug）。"
        )

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

    # SessionEnd 哨兵殘留檢查：殘留＝上個 session 的收尾流程未跑完即中斷
    # （harness timeout / 例外）→ 浮一行告警後清（收尾擁擠不得靜默失敗）。
    try:
        _check_se_sentinel_residual(lines)
    except Exception as e:
        print(f"SE-sentinel check error: {e}", file=sys.stderr)

    # 效用歸因遙測 advisory：上個 session 判定 unknown 比率連續偏高（讀後清 marker）
    try:
        _ow_marker = WORKFLOW_DIR / "outcome-unknown-advisory.json"
        if _ow_marker.exists():
            try:
                _ow = json.loads(_ow_marker.read_text(encoding="utf-8"))
                if _ow.get("msg"):
                    lines.append(_ow["msg"])
            except (OSError, json.JSONDecodeError):
                pass
            try:
                _ow_marker.unlink()
            except OSError:
                pass
    except Exception as e:
        print(f"Outcome-watch notice error: {e}", file=sys.stderr)

    try:
        review_reminder = _check_periodic_review_due(config)
        if review_reminder:
            lines.append(review_reminder)
            state["review_due"] = True
    except Exception as e:
        print(f"Review check error: {e}", file=sys.stderr)

    try:
        osc_warning = _load_oscillation_warnings()
        if osc_warning:
            lines.append(osc_warning)
    except Exception as e:
        print(f"Oscillation load error: {e}", file=sys.stderr)

    try:
        rut_warning = _detect_rut_patterns(state, config)
        if rut_warning:
            lines.append(rut_warning)
    except Exception as e:
        print(f"Rut detection error: {e}", file=sys.stderr)

    if WISDOM_AVAILABLE:
        try:
            wisdom_lines = get_reflection_summary()
            lines.extend(wisdom_lines)
        except Exception as e:
            print(f"Wisdom reflection error: {e}", file=sys.stderr)

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

    # 可觀測性：Vector 連續 3 session no_flag → 浮出告警（fail-open 的『不阻斷』
    # 必須『告知』——避免服務再度靜默死沒人知）
    try:
        _probe_log = CLAUDE_DIR / "Logs" / "vector-observation-probe.log"
        if _probe_log.exists():
            _tail = _probe_log.read_text(encoding="utf-8", errors="ignore").splitlines()[-3:]
            _recs = []
            for _ln in _tail:
                try:
                    _recs.append(json.loads(_ln))
                except Exception:
                    pass
            if len(_recs) >= 3 and all(r.get("flag_state") == "no_flag" for r in _recs):
                lines.append(
                    "[Guardian:Vector⚠] Vector 服務連續 3 session 未就緒（no_flag）——"
                    "語意召回/episodic/衝突偵測可能靜默失效，請查 tools/memory-vector-service 或跑 /vector。"
                )
    except Exception:
        pass

    # 可觀測性：IDENTITY.md 完整性哨兵——被覆寫成 stub / 缺核心契約段時浮出告警
    # （完整版備份在 templates/IDENTITY.template.md；檢查本身出錯不阻斷）
    try:
        _identity = CLAUDE_DIR / "IDENTITY.md"
        _id_ok = False
        _id_size = 0
        if _identity.exists():
            _id_size = _identity.stat().st_size
            _id_text = _identity.read_text(encoding="utf-8", errors="ignore")
            _id_ok = "自主行為契約" in _id_text and _id_size >= 2000
        if not _id_ok:
            lines.append(
                f"[Guardian:Identity⚠] IDENTITY.md 疑似損毀/被覆寫（現 {_id_size} bytes），"
                "完整版在 templates/IDENTITY.template.md，請比對回復。"
            )
    except Exception:
        pass

    write_state(session_id, state)

    try:
        _cleanup_old_states()
    except Exception as e:
        print(f"SessionStart cleanup error: {e}", file=sys.stderr)

    # 服務已暖則保留 flag（省冷啟動 no_flag 空窗），只有 health ping 失敗才拆（fail-closed）。
    try:
        _refresh_vector_flag(config)
    except Exception as e:
        _atom_debug_error("SessionStart:vector_flag_refresh", e)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }, ensure_ascii=False))

    # ── Vector service：fire-and-forget 啟動器（自癒/觀測邏輯在 starter.py）──
    if (config.get("vector_search", {}).get("auto_start_service", True)
            and not state.get("_skip_vector_init")):
        try:
            starter = CLAUDE_DIR / "tools" / "memory-vector-service" / "starter.py"
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
                [sys.executable, str(starter),
                 "--phase", "sessionstart", "--session-id", session_id or ""],
                **_bg_kwargs,
            )
        except Exception as e:
            _atom_debug_error("注入:vector_service_bg", e)

    sys.exit(0)

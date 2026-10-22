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
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import (
    CLAUDE_DIR, CODE_DIR, WORKFLOW_DIR, MEMORY_DIR, EPISODIC_DIR,
    MEMORY_INDEX,
    _now_iso, _atom_debug_error,
    get_project_memory_dir, find_project_root,
    register_project,
    read_state, write_state, new_state, _find_active_sibling_state,
    _check_mcp_servers,
    _is_under_claude_dir,
    iter_realm_category_dirs,
    REALM_AUTOMOVE_MARKER,
    find_vcs_root, find_svn_root, memory_dir_candidates,
    resolve_project_root, org_memory_root, load_config, load_org_local,
)
from wg_atoms import (
    parse_memory_index, parse_aidocs_index, extract_aidocs_keywords,
    build_candidate_pool,
)
from project_root import claude_config_dir   # lib/（wg_core 已放進 sys.path）：Claude Code 設定目錄，啟動檔在這裡
from wg_evasion import (
    _load_oscillation_warnings, _detect_rut_patterns, _check_periodic_review_due,
)
from wg_roles import (
    get_current_user, load_user_role, is_management, bootstrap_personal_dir,
)
from handlers._shared import (
    _MEMORY_MD_AUTO_HEADER,
    _call_project_hook, _cleanup_old_states, prune_workflow_records,
    WISDOM_AVAILABLE, get_reflection_summary,
)
import wg_hook_timing as _hook_timing
from wg_hook_timing import lap as _hook_lap

# Ollama client 在 tools/ 下（dispatcher 已加 sys.path）；用本檔位置推樹根，不用 Path.home()
_TOOLS_DIR = str(Path(__file__).resolve().parents[2] / "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

try:
    from vcs_ignore import (  # lib/：衍生檔退出版控（wg_core 已把 CODE_DIR/lib 放上 sys.path）
        DERIVED_DIRS as _DERIVED_DIR_NAMES,
        DERIVED_FILES as _DERIVED_INDEX_NAMES,
        REBUILD_HINT as _REBUILD_MANUAL,
        advisory_lines as _vcs_ignore_lines,
        derived_exit_hint as _derived_exit_hint,
        under_claude_dir as _under_claude_dir,
    )
except ImportError as _e:  # lib 不在（hooks 升了、lib 沒升）：缺檔重建與衝突提示照舊，只少「退出版控」那段；留痕不無聲
    _atom_debug_error("session_start:vcs_ignore_import", _e)
    _DERIVED_INDEX_NAMES = ("_atom_index.json", "_ATOM_INDEX.md")
    _DERIVED_DIR_NAMES = ("_staging", "episodic", "vector-db")
    _REBUILD_MANUAL = 'python ~/.claude/tools/sync-atom-index.py --rebuild --memory-dir "{mem}"'
    _vcs_ignore_lines = None
    _derived_exit_hint = None
    _under_claude_dir = lambda _p: True  # noqa: E731  分不出是不是根層記憶 → 不做過期檢查，只保留缺檔重建
try:
    from ollama_client import check_long_die_status
except ImportError:
    check_long_die_status = lambda: None  # noqa: E731


def check_identity_integrity(live_dir: Path, data_dir: Path) -> List[str]:
    """IDENTITY.md 完整性哨兵：Claude Code 實際載入的那份（設定目錄 live_dir 的 CLAUDE.md @IDENTITY.md）被覆寫成 stub、
    缺核心契約段 → 告警行。資料根（WG_CLAUDE_DIR）不放啟動檔，不看它；兩者不同時訊息註明查的是哪一份。"""
    identity = live_dir / "IDENTITY.md"
    size, text = 0, ""
    if identity.exists():
        size = identity.stat().st_size
        text = identity.read_text(encoding="utf-8", errors="ignore")
    if "自主行為契約" in text and size >= 2000:
        return []
    note = "" if os.path.normcase(str(live_dir)) == os.path.normcase(str(data_dir)) else \
        f"（查的是 Claude Code 設定目錄這份；資料根 {data_dir} 不放啟動檔）"
    return [f"[Guardian:Identity⚠] {identity} 疑似損毀/被覆寫（現 {size} bytes）{note}，"
            "完整版在 templates/IDENTITY.template.md，請比對回復。"]


def check_always_load_contracts(claude_dir: Path) -> List[str]:
    """必載檔硬契約哨兵：memory/_meta/always-load-contracts.json 登記的句子在 live 檔缺席 → 告警行。

    契約句被修剪／覆寫時，模型當 session 就失去事前依據（事後閘只看狀態不懂語意）。
    claude_dir 給 Claude Code 設定目錄（live 檔是 Claude Code 載入的那幾份），不是資料根。
    登記表缺或壞 → 回一行告警（不阻斷）。
    """
    reg_path = claude_dir / "memory" / "_meta" / "always-load-contracts.json"
    try:
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"[Guardian:Contract⚠] 硬契約登記表讀取失敗（{reg_path.name}：{e}）"]
    out: List[str] = []
    for c in reg.get("contracts") or []:
        live = claude_dir / str(c.get("live", ""))
        try:
            text = live.read_text(encoding="utf-8", errors="ignore") if live.exists() else ""
        except OSError:
            text = ""
        missing = [m for m in (c.get("must_contain") or []) if m not in text]
        if missing:
            out.append(
                f"[Guardian:Contract⚠] {c.get('live')} 缺硬契約「{c.get('id')}」"
                f"（缺：{'、'.join(missing)}）→ {c.get('fix', '比對 template 回復')}"
            )
    return out


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


def _index_stale_reason(memory_dir: Path, json_path: Path) -> str:
    """索引在，但磁碟上的記憶卡已經變了 → 回一句原因；沒變回空字串。

    索引不入版控之後，隊友的卡經 svn／git 更新進來，本機那份舊索引不會跟著動，
    新卡就不會被注入。這裡只看兩件事：有沒有記憶卡比索引新、索引登記的檔還在不在。
    索引讀不到就當沒變——判斷失敗不該變成每次都重建。
    """
    try:
        index_mtime = json_path.stat().st_mtime
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    for p in memory_dir.rglob("*.md"):
        rel = p.relative_to(memory_dir)
        if rel.parts[0] in _DERIVED_DIR_NAMES or p.name.startswith("_") or p.name == "MEMORY.md":
            continue
        try:
            if p.stat().st_mtime > index_mtime:
                return f"{rel.as_posix()} 比索引新"
        except OSError:
            continue
    for a in data.get("atoms") or []:
        path = a.get("path") or ""
        if path and not (memory_dir.parent / path).exists():
            return f"索引登記的 {path} 已不在"
    return ""


def _rebuild_index_if_missing(memory_dir: Optional[Path]) -> str:
    """索引檔不在（沒入版控／被清掉／新 clone）、或專案記憶卡比索引新 → 就地從磁碟重建。

    索引是衍生檔，本來就該能從 atom 重生；能重生才敢不入版控，
    不入版控才不會「兩個人各加一顆 atom ＝ 同一區塊各插一列 ＝ 衝突」。
    專案記憶的索引不入版控，所以隊友更新進來的卡要靠這裡的過期檢查才進得了索引；
    ~/.claude 自己的記憶索引在版控裡、隨 pull 更新，不做過期檢查。
    _ATOM_INDEX.md（mirror）缺檔同理：JSON 在就直接重生、不起子行程。
    回傳要顯示的一行（沒事做回空字串）。重建失敗要大聲並附手動指令——
    否則 trigger 注入靜默變空，沒人知道。
    """
    if not memory_dir or not memory_dir.is_dir():
        return ""
    json_path = memory_dir / "_atom_index.json"
    md_path = memory_dir / "_ATOM_INDEX.md"
    manual = _REBUILD_MANUAL.format(mem=memory_dir)
    stale = ""
    if json_path.exists() and md_path.exists():
        if _under_claude_dir(memory_dir):
            return ""
        stale = _index_stale_reason(memory_dir, json_path)
        if not stale:
            return ""
    elif json_path.exists():
        try:
            from atom_index_json import regenerate_atom_index_md
            regenerate_atom_index_md(memory_dir)
        except Exception as e:  # noqa: BLE001
            _atom_debug_error("session_start:regenerate_mirror", e)
            return f"[Guardian:Index] ⚠ _ATOM_INDEX.md 不在且重生失敗（{e}）→ 手動 {manual}"
        if not md_path.exists():
            return f"[Guardian:Index] ⚠ _ATOM_INDEX.md 不在且重生沒產出檔案 → 手動 {manual}"
        return f"[Guardian:Index] _ATOM_INDEX.md 不在 → 已從 _atom_index.json 重生（{memory_dir}）。"
    elif not any(memory_dir.rglob("*.md")):
        return ""
    what = f"索引過期（{stale}）" if stale else "索引不在"
    harm = "新進的記憶卡這輪不會被注入" if stale else "trigger 注入這輪會是空的"
    import subprocess as _sp
    cmd = [sys.executable, str(CODE_DIR / "tools" / "sync-atom-index.py"),
           "--memory-dir", str(memory_dir), "--rebuild"]
    try:
        r = _sp.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                    creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
    except (OSError, _sp.SubprocessError) as e:
        return f"[Guardian:Index] ⚠ {what}且重建失敗（{e}）——{harm} → 手動 {manual}"
    if not json_path.exists():
        return (f"[Guardian:Index] ⚠ 索引不在且重建沒產出檔案：{(r.stderr or '').strip()[:200]}"
                f"——trigger 注入這輪會是空的 → 手動 {manual}")
    if stale:
        if r.returncode != 0:
            return (f"[Guardian:Index] ⚠ {what}且重建失敗：{(r.stderr or '').strip()[:200]}"
                    f"——{harm} → 手動 {manual}")
        # 內容沒變時重建工具可能不改寫檔案：碰一下時間，否則同一張卡每次開 session 都判過期
        try:
            os.utime(json_path)
        except OSError:
            pass
    # 帶上條目數：從零重建只收「磁碟掃得到的 atom」，舊索引若登記過非 atom 檔
    #（_reference/ 下的參考文、沒有元資料的敘事文），重建後條目會變少。
    # 不報數字的話那個落差是隱形的。
    try:
        import json as _json
        n = len(_json.loads(json_path.read_text(encoding="utf-8")).get("atoms") or [])
        count = f"，共 {n} 筆"
    except (OSError, ValueError):
        count = ""
    mirror = "" if md_path.exists() else f"；⚠ _ATOM_INDEX.md 仍不在 → 手動 {manual}"
    return f"[Guardian:Index] {what} → 已從磁碟重建（{memory_dir}）{count}{mirror}。"


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
        target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
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
        flag.write_text("ready", encoding="utf-8", newline="\n")
    except OSError:
        pass
    return "kept"


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


def _tracking_advisory(cwd: str, state: Dict[str, Any]) -> list:
    """本專案追蹤帳本（AEC (k) 與交付時「順手看到最該修」寫的）：一個 session 只列一次（state["tracking_advisory_sent"]，
    重建 state 時照搬）。先列附了建議、還沒解的項目（不分部位，最新 3 筆＋要 AI 第一則回覆告訴使用者）；再列沒標部位、
    沒附建議的未結項筆數＋最舊 3 筆（標了部位的改在第一次碰到該部位時隨導讀卡注入）。
    同專案疑似由舊算法（子目錄 cwd）分裂出的帳本只在 stderr 列，不自動合併。讀不到只 stderr，回 []。"""
    if not cwd or state.get("tracking_advisory_sent"):
        return []
    state["tracking_advisory_sent"] = True
    try:
        from wg_harvest import open_tracking_items, proposal_lines, read_tracking, tracking_slug
        slug = tracking_slug(cwd)
        tdir = WORKFLOW_DIR / "tracking"
        split = sorted(p.name for p in tdir.glob(f"{slug}-*.jsonl")) if tdir.is_dir() else []
        if split:
            print(f"[Guardian:Tracking] 疑似同專案分裂的追蹤帳本（舊版用子目錄 cwd 命名，不自動合併）：{', '.join(split)}；"
                  f"本專案帳本＝{slug}.jsonl", file=sys.stderr)
        open_items = open_tracking_items(read_tracking(slug))
        proposals = proposal_lines(open_items)
        items = [e for e in open_items
                 if not str(e.get("part") or "").strip() and not str(e.get("proposal") or "").strip()]
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:Tracking] 讀追蹤項失敗：{type(e).__name__}: {e}", file=sys.stderr)
        return []
    out = ["\n".join(proposals)] if proposals else []
    if not items:
        return out
    oldest = sorted(items, key=lambda e: str(e.get("at") or ""))[:3]
    lines = [f"[Guardian:Tracking] 本專案未結追蹤項 {len(items)} 筆（未標部位，不會隨部位導讀卡注入）；最舊 3 筆："]
    lines += [f"- {str(e.get('text') or '')[:200]}（{str(e.get('at') or '')[:10]}）" for e in oldest]
    lines.append("處理完在 AEC (k) 寫「結案：<原文開頭至少 8 字；原文不足 8 字就寫全文>」（未標部位的項目，結案行也不帶部位）；"
                 "新記的追蹤項可在行尾加「｜建議：<怎麼解>｜該誰解：<誰>」；跟帳上某一筆是同一件就加「｜同追蹤項：<那筆裡連續至少 8 字>」，"
                 "系統換成新說法、不另記一筆。")
    return out + ["\n".join(lines)]


def _verify_scope_advisory(cwd: str) -> list:
    """驗證範圍：背景全量的自寫收據先入帳（紅掉的測試名拿去找範圍漏判），再列這個 repo 待檢討的漏判與累計數字。
    送回給 LLM 檢討；讀不到只 stderr，回 []。"""
    try:
        import wg_verify_scope as vs
        from wg_verify_ledger import load_self_runs
        vs.sync_runs(load_self_runs())
        return vs.advisory(cwd)
    except Exception as e:  # noqa: BLE001
        print(f"[Guardian:VerifyScope] 開場列範圍漏判失敗：{type(e).__name__}: {e}", file=sys.stderr)
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
            [sys.executable, str(CODE_DIR / "tools" / "followup-check.py"),
             "--run", "--auto-close", "--brief", "--mark-shown"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = (r.stdout or "").strip()
        return [out] if out else []
    except Exception as e:
        _atom_debug_error("session_start:followup_advisory", e)
        return ["[Guardian:Followup] ⚠ 回訪檢查器執行失敗（見 atom-debug log）——手動跑 python tools/followup-check.py --run"]


def _spawn_pull_sync(session_id: str, cwd: str, config: Dict[str, Any]) -> int:
    """SessionStart 的拉取觸發：`vcs_sync.enabled` 且 `vcs_sync.pull.enabled` 才 spawn（reason="pull"）。
    fail-open：任何失敗只進 atom-debug log（spawn 自己會留 `.unpushed`／last_error 給 advisory）。回 pid（0＝未起）。"""
    try:
        import wg_vcs_sync as _vs
        vs = _vs.vcs_sync_config(config or {})
        if not vs.get("enabled", True) or not (vs.get("pull") or {}).get("enabled", True):
            return 0
        return _vs.spawn_vcs_sync(session_id, cwd, reason="pull", config=config)
    except Exception as e:
        _atom_debug_error("session_start:spawn_pull_sync", e)
        return 0


def _maybe_spawn_provenance_backfill(config: Dict[str, Any]) -> int:
    """舊 atom 來源回填：有比上次更新的 transcript 才 detached 跑 `tools/atom-provenance-backfill.py --apply --quiet`。
    判定只比 mtime（<50ms）；config `provenance.backfill.enabled=false` 關。fail-open：失敗只進 atom-debug log。回 pid（0＝未起）。"""
    try:
        prov = (config or {}).get("provenance") or {}
        if not prov.get("enabled", True) or not (prov.get("backfill") or {}).get("enabled", True):
            return 0
        import importlib.util
        tool = CODE_DIR / "tools" / "atom-provenance-backfill.py"
        if not tool.exists():
            return 0
        spec = importlib.util.spec_from_file_location("atom_provenance_backfill", tool)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules["atom_provenance_backfill"] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        if not mod.needs_run():
            return 0
        import subprocess as _sp
        import wg_vcs_sync as _vs
        kwargs: Dict[str, Any] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = _sp.CREATE_NO_WINDOW | _sp.DETACHED_PROCESS
        else:
            kwargs["start_new_session"] = True
        mod.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(mod.LOG_PATH, "a", encoding="utf-8", newline="\n") as log_fh:
            proc = _sp.Popen([_vs._gui_python(), str(tool), "--apply", "--quiet"],
                             stdin=_sp.DEVNULL, stdout=_sp.DEVNULL, stderr=log_fh,
                             env=_vs.worker_env(), **kwargs)
        return int(proc.pid or 0)
    except Exception as e:
        _atom_debug_error("session_start:provenance_backfill", e)
        return 0


def _unpushed_advisory() -> list:
    """本地有已 commit 未 push／worker 留下 `.unpushed` 標記的 root → advisory 行（無則回 []）。
    拉側（roots.json 的 last_pull／pulled_commits／pull_error 與 `.behind` 標記）也在這裡報：拉入 N 筆 → 一行提醒
    候選池以本次載入快照為準；`.behind` → 一行理由。pull 欄位與 push 的 last_error 分欄，解除 `.unpushed` 的邏輯不碰它們。

    存在理由：vcs-sync worker 在背景 commit+push 記憶庫，push 守門擋下（本地有未發布程式碼
    commit）或 push／svn commit 失敗時只留標記與 log、當下沒人看得到。這裡在下個 session 開頭補上
    可見性，讓「背景 fail-open」不變成「永遠沒人發現」（可觀測性鐵律）。

    範圍：workflow/vcs-sync/roots.json 列出的每個 root（根層 + 專案）；roots.json 尚無根層時退回
    只查 ~/.claude。每 root 依序看：git `rev-list --count @{u}..HEAD`、`.unpushed` 標記（查詢成功且
    ahead=0 → 已沒有東西待推，不論使用者是補推原 HEAD 還是另開 commit，都算已解決：刪標記並清 roots.json
    的 last_error；查詢失敗 rc≠0 不得當 ahead=0——那是「不知道」，標記照報、不刪）、roots.json 的
    last_error（skip／索引失敗／spawn 失敗）、`.req/` 內無人消費的請求（含 inflight 殘留：worker 沒起或中途死）。
    除了清已解決的標記／last_error 外只讀不寫；單一 root 失敗不影響其他 root——沒有 upstream / 不是 repo /
    git 不在都算正常（查不到 ahead 就不報 ahead）。
    """
    try:
        import subprocess
        from pathlib import Path as _P
        try:
            import wg_vcs_sync as _vs
            roots = _vs.load_roots()
        except Exception as e:
            _atom_debug_error("session_start:unpushed_advisory:roots", e)
            _vs, roots = None, {}
        entries = [(_P(k), v or {}) for k, v in roots.items()]
        if not any(r.resolve() == CLAUDE_DIR.resolve() for r, _ in entries) and (CLAUDE_DIR / ".git").exists():
            entries.insert(0, (CLAUDE_DIR, {}))

        def _git(root: _P, *args: str):
            """回 (成功?, stdout)。失敗（無 upstream／不是 repo／git 不在）與「0」必須分得開。"""
            r = subprocess.run(
                ["git", "-C", str(root), *args],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return r.returncode == 0, (r.stdout or "").strip()

        lines = []
        for root, info in entries:
            vcs = info.get("vcs", "git")
            last_error = info.get("last_error")
            label = "~/.claude" if root.resolve() == CLAUDE_DIR.resolve() else root.as_posix()
            try:
                rec = _vs.read_unpushed_record(root) if _vs else None
                is_git = vcs == "git" and (root / ".git").exists()
                ahead, ahead_known = 0, False
                if is_git:
                    ok, out = _git(root, "rev-list", "--count", "@{u}..HEAD")
                    if ok and out.isdigit():
                        ahead, ahead_known = int(out), True
                if rec and ahead_known and ahead == 0:
                    # 查詢成功且沒有東西待推 → 已解決（使用者補推原 HEAD 也算）。先清 roots.json 的
                    # last_error（可能因 roots.lock 逾時失敗），成功才刪標記；失敗就留著下次再清，
                    # 否則標記沒了、last_error 卻永遠清不掉。
                    cleared = True
                    if last_error:
                        cleared = bool(_vs.update_root_record(
                            _vs.SyncTarget(vcs, root, list(info.get("pathspecs") or [])), last_error=None))
                        if cleared:
                            last_error = None
                    if cleared:
                        _vs.clear_unpushed(root)
                        rec = None
                pending = _vs.pending_requests(root, include_inflight=True) if _vs else 0
                orphan = pending > 0 and _vs is not None and not _vs.lock_is_live(root)
            except Exception as e:
                _atom_debug_error("session_start:unpushed_advisory:root", e)
                lines.append(f"[Guardian:Sync] ⚠ {label} 未 push 檢查失敗（{type(e).__name__}）——見 atom-debug log。")
                continue
            reason = (rec or {}).get("reason")
            if ahead > 0:
                lines.append(
                    f"[Guardian:Sync] ⚠ {label} 本地有 {ahead} 筆 commit 未 push"
                    f"（背景 vcs-sync 守門或 push 失敗，見 Logs/vcs-sync.log）→ 確認後 git push 補推。")
            elif reason:
                lines.append(
                    f"[Guardian:Sync] ⚠ {label} 記憶庫未上版控：{reason[:80]}（見 Logs/vcs-sync.log）")
            elif last_error:
                lines.append(
                    f"[Guardian:Sync] ⚠ {label} 上次背景同步未完成：{str(last_error)[:80]}（見 Logs/vcs-sync.log）")
            if orphan:
                lines.append(
                    f"[Guardian:Sync] ⚠ {label} 有 {pending} 筆同步請求無人處理（worker 未起或中斷）"
                    "→ 下次收割／SessionEnd 會自動補跑；急的話手動 python hooks/vcs-sync-worker.py。")
            lines.extend(_pull_advisory_lines(_vs, root, label, info))
        return lines
    except Exception as e:
        _atom_debug_error("session_start:unpushed_advisory", e)
        # fail-open 但要告知：這個檢查曾靜默 crash 三週沒人知道
        return [f"[Guardian:Sync] ⚠ 未 push 檢查失敗（{type(e).__name__}）——見 atom-debug log；手動 git status 確認。"]


def _pull_advisory_lines(_vs, root, label: str, info: Dict[str, Any]) -> list:
    """拉側兩行（各自可缺）：上次拉入 N>0 筆 → 提醒候選池是本次載入快照；`.behind` 標記（或只剩 pull_error）→ 理由。
    「拉入 N 筆」一次性：報過就把 last_pull 記進 roots.json pull_reported_at，同一次 last_pull 不再報（cooldown 內
    的 reason=pull 請求不會覆寫 last_pull，沒有這個欄位會每個 session 重複報）。"""
    try:
        lines = []
        pulled = info.get("pulled_commits") or 0
        last_pull = info.get("last_pull")
        if last_pull and pulled > 0 and info.get("pull_reported_at") != last_pull:
            lines.append(
                f"[Guardian:Sync] {label} 記憶層上次同步拉入 {pulled} 筆 commit（{str(last_pull)[:19]}）；"
                "候選池以本次載入快照為準。")
            # 「只報一次」盡力而為：寫 pull_reported_at 失敗（roots.lock 逾時，回 False、已進 atom-debug log）就不算
            # 已報，下個 session 會再報同一次拉入；兩個 session 同時讀到同一份快照也會各報一次。重報一行提醒無害，
            # 不為此在讀→判→寫之間加鎖。
            if _vs:
                _vs.update_root_record(_vs.SyncTarget(info.get("vcs", "git"), root, list(info.get("pathspecs") or [])),
                                       pull_reported_at=last_pull)
        rec = _vs.read_behind_record(root) if _vs else None
        reason = (rec or {}).get("reason") or info.get("pull_error")
        if reason:
            lines.append(f"[Guardian:Sync] ⚠ {label} 記憶層落後未併入：{str(reason)[:100]}（見 Logs/vcs-sync.log）")
        return lines
    except Exception as e:
        _atom_debug_error("session_start:pull_advisory", e)
        return [f"[Guardian:Sync] ⚠ {label} 拉取狀態檢查失敗（{type(e).__name__}）——見 atom-debug log。"]


def _index_conflict_advisory(cwd: str) -> list:
    """開場 advisory：上個 session 的 pull/rebase 卡在索引三檔衝突、還沒解就關掉 → 這裡浮出一行。

    exists()-first 省錢：先一次 `git rev-parse --git-dir`（worktree 相容），只有 MERGE_HEAD／
    CHERRY_PICK_HEAD／rebase-merge／rebase-apply 任一存在（真的卡在合併中）才跑 `git ls-files -u`。
    唯讀 git；非 repo／git 不在／任何失敗 → []。PreToolUse 的 check_merge_driver 會在下一個
    `rebase --continue`／`commit` 前自動 --resolve，這行只是讓人先知道現況。
    """
    lines: list = []
    try:
        if not cwd or not Path(cwd).is_dir():
            return []
        # svn 側獨立找：git 疊在 svn 上（同層兩個都有）時 find_vcs_root 回 git，svn 衝突會被略過
        svn_root = find_svn_root(Path(cwd))
        if svn_root is not None:
            lines += _svn_index_conflict_advisory(cwd, svn_root)
        vcs = find_vcs_root(Path(cwd))  # 零子行程：非工作區直接零行
        if vcs is None or vcs[0] != "git":
            return lines
        r = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=2, cwd=cwd, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            return lines
        gitdir = Path((r.stdout or "").strip())
        if not gitdir.is_absolute():
            gitdir = Path(cwd) / gitdir
        if not any((gitdir / n).exists()
                   for n in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "rebase-merge", "rebase-apply")):
            return lines
        r = subprocess.run(
            ["git", "ls-files", "-u", "-z"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=2, cwd=cwd, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            return lines
        index_names = {"MEMORY.md", "_ATOM_INDEX.md", "_atom_index.json", "_INDEX.md", "_local_catalog.md"}
        names = sorted({
            entry.split("\t", 1)[1].rsplit("/", 1)[-1]
            for entry in (r.stdout or "").split("\0") if "\t" in entry
        } & index_names)
        if names:
            lines.append(
                f"[Guardian:IndexConflict] ⚠ 索引三檔尚未合併（{', '.join(names)}）"
                "→ python ~/.claude/tools/merge-atom-index.py --resolve 後 git rebase --continue")
        return lines
    except Exception as e:
        _atom_debug_error("session_start:index_conflict_advisory", e)
        return lines


_SVN_INDEX_NAMES = ("MEMORY.md", "_ATOM_INDEX.md", "_atom_index.json")


def _svn_index_conflict_advisory(cwd: str, root: Path) -> list:
    """SVN 工作副本：update 衝突會在原檔旁留下 <檔>.mine。memory dir 候選裡有就提示（零子行程）。

    索引三檔與 atom 分開講。索引裡的 _atom_index.json／_ATOM_INDEX.md 是衍生檔，衝突的正解是退出版控
    （指令與 [Guardian:VcsIgnore] 同源），hook 的自動合併只是暫時處置；atom 衝突要人判斷，
    而且在解完之前 SessionEnd 的反向連結修補會跳過它們——放著不解，連結就一直補不上。
    """
    index_names: set = set()
    derived_paths: list = []
    atoms: list = []
    for d in memory_dir_candidates(Path(cwd), root):
        for mine in d.rglob("*.mine"):
            original = mine.name[:-len(".mine")]
            if original in _SVN_INDEX_NAMES:
                index_names.add(original)
                if original in _DERIVED_INDEX_NAMES:
                    derived_paths.append(mine.with_name(original))
            elif original.endswith(".md"):
                atoms.append(original[:-3])
    out = []
    if index_names:
        msg = f"[Guardian:IndexConflict] ⚠ SVN 索引三檔尚未解（{', '.join(sorted(index_names))}）"
        if derived_paths and _derived_exit_hint is not None:
            msg += f"。{_derived_exit_hint('svn', derived_paths)}；暫時處置："
        else:
            msg += "→ "
        msg += "在 CC 下 svn commit 前 hook 會自動解，或手動 python ~/.claude/tools/merge-atom-index.py --resolve"
        out.append(msg)
    if atoms:
        shown = "、".join(sorted(atoms)[:3]) + ("…" if len(atoms) > 3 else "")
        out.append(
            f"[Guardian:IndexConflict] ⚠ SVN 有 {len(atoms)} 顆 atom 衝突未解（{shown}）"
            "→ 先解衝突再收工；未解期間自動修補會跳過這些檔")
    return out


def _org_advisory(org_root, pool: Dict[str, Any]) -> List[str]:
    """公司層一行：`[Org] 公司層 N 顆（<root>）`。
    這台沒接上、使用者也還沒回答過（本機狀態檔沒有 enabled／declined）且共用 config 有 repo_url →
    要 AI 用 AskUserQuestion 問使用者放哪裡；**每個 session 都出，直到有答案**（接上或 --decline）。
    這幾行是給模型看的指示，不是給人看的通知：SessionStart 的輸出使用者看不到，只寫「對我說…」等於沒人會做。
    沒 repo_url 零 context。根未 checkout／索引缺 → 警告一行（fail-open 必浮訊號）。cwd 就是 org 根時池不另列 org 組，不報。"""
    if org_root is None:
        shared = load_config().get("org_memory")
        local = load_org_local()
        if not isinstance(shared, dict) or not shared.get("repo_url") or local.get("enabled") or local.get("declined"):
            return []
        cmd = "python ~/.claude/tools/org-memory.py"
        default_root = str(shared.get("default_root") or "")
        if default_root.startswith("~"):
            default_root = str(Path(default_root).expanduser())  # config 寫家目錄相對路徑，問人時給展開後的真路徑
        opt_default = (f"(1) 接上，放在預設路徑 {default_root} (Recommended) → 執行 `{cmd} --join`；" if default_root else "")
        return [
            f"❓ [Org] 公司有一層所有專案共用的記憶（{shared.get('repo_url')}），這台機器還沒接上，使用者也還沒被問過。"
            f"第一則回覆前先用 AskUserQuestion 問使用者：{opt_default}"
            f"(2) 接上，放在使用者指定的資料夾（請他給完整路徑）→ `{cmd} --join \"<路徑>\"`；"
            f"(3) 先不接 → `{cmd} --decline`（之後不再問；想接時說「接上公司記憶」）。"
            f"選定後由你執行指令：資料夾不存在會自動從公司 repo 下載建立，路徑只記在這台機器的 "
            f"workflow/org-memory.local.json（不進版控）；接上後告知「重開 session 生效」。"
        ]
    root = Path(org_root)
    if not (root / ".claude" / "memory").is_dir():
        return [f"[Org] 公司層記憶尚未接上（{root} 下無 .claude/memory）→ 對我說「接上公司記憶」或 /org join"]
    if not pool.get("org_base"):
        return []
    if not (Path(pool["org_base"]) / "memory" / "_atom_index.json").is_file():
        return [f"[Org] 公司層索引缺檔：{root}/.claude/memory/_atom_index.json（請在該 repo 跑 sync-atom-index）"]
    return [f"[Org] 公司層 {len(pool.get('org') or [])} 顆（{root}）"]
def _vcs_ignore_advisory(project_mem_dir) -> list:
    """專案記憶庫的衍生檔退出版控：設 svn:ignore／.gitignore＋「已被版控」告警一次（lib/vcs_ignore）。

    每個記憶庫每種 VCS 只處理一次（marker：workflow/vcs-ignore.json），之後零子行程；
    記憶庫目錄尚未版控時不記、下次再試。無 VCS／~/.claude 自己的記憶 → []。
    """
    try:
        if not project_mem_dir or _vcs_ignore_lines is None:
            return []
        return _vcs_ignore_lines(Path(project_mem_dir), WORKFLOW_DIR / "vcs-ignore.json", timeout=4.0)
    except Exception as e:  # noqa: BLE001
        _atom_debug_error("session_start:vcs_ignore_advisory", e)
        return ["[Guardian:VcsIgnore] ⚠ 衍生檔版控檢查失敗（見 atom-debug log）"
                "——手動 python -m lib.vcs_ignore <memory-dir> 檢視"]


def _personal_sync_advisory(project_mem_dir, user: str) -> list:
    """本人 personal atom 的版控同步狀態 → 開場最多三行（無事零 context）。

    存在理由：personal 層的設計是「可上版控、僅本人可搜」（可見性由索引 scope=personal:<user>
    控管）。但索引三檔跟著 repo 走、personal 檔卻可能留在本機（沒 commit、或被 .gitignore 擋掉）
    → 他機索引懸空、兩機 hook 重建索引互相加回/拿掉。以前靠人傳話「請把 personal 上傳」；
    這裡讓每個人的 CC 在自己機器上看到自己的缺口，自己補。

    三種訊號（各自獨立、可同時出）：
      1. personal/<user>/ 被 .gitignore 擋住 → 提示移除該行
      2. 本人 personal 檔未 commit（untracked / modified）→ 提示收尾一起 commit
      3. 索引列了本人 personal atom 但本機無檔 → 多半留在本人另一台機器未 push

    唯讀 git；非 repo／無 user／git 不在 → []。自身出錯不阻斷 SessionStart。
    """
    try:
        if not project_mem_dir or not user:
            return []
        mem = Path(project_mem_dir)
        if not mem.is_dir():
            return []
        try:
            if mem.resolve() == Path(MEMORY_DIR).resolve():
                return []  # 全域核心 repo 對外公開發布，personal 依 .gitignore 留本機是刻意設計；只管專案層
        except OSError:
            pass
        personal_dir = mem / "personal" / user

        def _git(*args, timeout=5):
            return subprocess.run(
                ["git", "-C", str(mem), *args],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

        top = _git("rev-parse", "--show-toplevel")
        if top.returncode != 0:  # 不是 repo → 不吵
            return []
        try:
            rel = personal_dir.resolve().relative_to(Path(top.stdout.strip()).resolve()).as_posix()
        except Exception:
            rel = personal_dir.as_posix()

        # ── 3. 索引懸空（先算：決定本機無目錄時要不要繼續）──
        dangling: list = []
        idx = mem / "_atom_index.json"
        if idx.exists():
            try:
                atoms = json.loads(idx.read_text(encoding="utf-8")).get("atoms", [])
                prefix = f"memory/personal/{user}/"
                for a in atoms:
                    ap = str(a.get("path", ""))
                    if ap.startswith(prefix) and not (mem.parent / ap).exists():
                        dangling.append(a.get("name") or Path(ap).stem)
            except Exception as e:  # noqa: BLE001
                _atom_debug_error("session_start:personal_sync_index", e)

        if not personal_dir.is_dir() and not dangling:
            return []

        out: list = []

        # ── 1. 被 .gitignore 擋住 ──
        # --no-index：不受目錄內已追蹤檔干擾；探測目錄內虛擬檔名（對目錄本身判定不穩）
        ign = _git("check-ignore", "-q", "--no-index", "--", str(personal_dir / "_probe.md"))
        if ign.returncode == 0:
            out.append(
                f"[Guardian:PersonalSync] ⚠ {rel}/ 被 .gitignore 擋住——personal 層現行設計是"
                "「可上版控、僅本人可搜」；擋掉會讓索引在他機懸空、兩機互相加回/拿掉。"
                "移除 .gitignore 中對應行，把該目錄一起 commit。"
            )

        # ── 2. 未 commit ──
        if personal_dir.is_dir() and ign.returncode != 0:
            st = _git("status", "--porcelain=v1", "--untracked-files=all", "--", str(personal_dir))
            pending = []
            for line in (st.stdout or "").splitlines():
                if len(line) < 4:
                    continue
                path = line[3:].strip().strip('"')
                if " -> " in path:
                    path = path.split(" -> ", 1)[1]
                if path.endswith(".access.json"):
                    continue
                pending.append(Path(path).stem)
            if pending:
                shown = ", ".join(pending[:3]) + ("…" if len(pending) > 3 else "")
                out.append(
                    f"[Guardian:PersonalSync] 你有 {len(pending)} 個 personal atom 尚未上版控（{shown}）"
                    "——只有本人搜得到，但要 commit + push 才會跟到你的其他機器；索引已列它們，"
                    f"他機會懸空。收尾時 `git add {rel}/` 一起 commit。"
                )

        if dangling:
            shown = ", ".join(dangling[:3]) + ("…" if len(dangling) > 3 else "")
            out.append(
                f"[Guardian:PersonalSync] 索引列了你 {len(dangling)} 顆 personal atom 但本機無檔（{shown}）"
                f"——多半留在你另一台機器未 push；到那台跑 `git add {rel}/` + commit + push。"
            )
        return out
    except Exception as e:  # noqa: BLE001
        _atom_debug_error("session_start:personal_sync_advisory", e)
        return [f"[Guardian:PersonalSync] ⚠ personal 同步檢查失敗（{type(e).__name__}）——見 atom-debug log。"]


_ROOT_ASK_CMD = "python ~/.claude/tools/project-tree.py"


def _project_root_notice(res, cwd: str) -> List[str]:
    """專案根宣告行（📍 認領／info、⚠️ 警告、❓ 引導）。沒宣告也沒候選 → 空清單，外部專案零 token。"""
    if res is None:
        return []
    lines: List[str] = []
    if res.declared and res.path is not None:
        from project_root import CLAIM_LABEL
        label = CLAIM_LABEL.get(res.claimed_by, res.claimed_by)
        if res.claimed_by != "self":
            lines.append(
                f"📍 [Guardian:ProjectRoot] {cwd} 屬 {res.path} 的子專案（宣告：{label} @ {res.via}）"
                f"→ 記憶歸 {res.path / '.claude' / 'memory'}")
    for info in res.infos:
        lines.append(f"📍 [Guardian:ProjectRoot] {info}")
    for warn in res.warnings:
        lines.append(f"⚠️ [Guardian:ProjectRoot] {warn}")
    if res.claimed_by in ("nearest", "none") and res.candidates and not res.standalone:
        cands = "、".join(str(c) for c in res.candidates)
        best = res.candidates[0]
        lines.append(
            f"❓ [Guardian:ProjectRoot] 上層 {cands} 有記憶層但未宣告與本層（{cwd}）的關係。"
            f"第一則回覆前先用 AskUserQuestion 問使用者，四選一："
            f"(1) 認領 {best} (Recommended) → 執行 `{_ROOT_ASK_CMD} claim --root \"{best}\" --cwd \"{cwd}\"`；"
            f"(2) 本層獨立 → `{_ROOT_ASK_CMD} standalone on --cwd \"{cwd}\"`；"
            f"(3) 瀏覽選別的資料夾 → `{_ROOT_ASK_CMD} pick --cwd \"{cwd}\"`；"
            f"(4) 這次先不決定（不寫檔，下次再問）。選定後由你執行指令，並告知「重開 session 生效」。")
    return lines


def _root_fingerprint_matches(existing: Dict[str, Any], res) -> bool:
    """resume/compact 能沿用舊 state 的前提：專案根指紋沒變（舊 state 沒指紋＝不符 → 重建）。"""
    if res is None:
        return True
    return (existing.get("atom_index") or {}).get("project_root_fingerprint") == res.fingerprint


_CARRY_ON_REBUILD = (
    "modified_files", "accessed_files", "vcs_queries", "knowledge_queue", "sync_pending",
    "stop_blocked_count", "topic_tracker", "session_context_injected",
    # A2.4：專案根指紋變了重建 atom_index 時，OverviewHub 的注入紀錄／意圖／Depends 已提示的卡／已送過候選的部位照搬，不重注不重送
    "overview_hub", "turn_intent", "depends_hints", "candidates_sent",
    # 一 session 一次的旗標也要照搬，否則重建後 idle 一行、權威地圖、未結追蹤項提示會重送
    "idle_scan_sent", "authority_map_injected", "tracking_advisory_sent",
)


def _first_session_hint_lines(root_res, cwd: str) -> list:
    """T1-7（track-d2 的 first_session_hint）掛 SessionStart：無部位表的專案給 scaffold 指令；表有「骨架」列就列每張卡的空段；
    表齊或不在任何專案 → 空。根層 cwd 以 ~/.claude 當根（它的表在 ~/.claude/.claude/overview-map.md）。fail-open。"""
    try:
        root = None
        if cwd:
            c = Path(cwd)
            if c == CLAUDE_DIR or CLAUDE_DIR in c.parents:
                root = CLAUDE_DIR
        if root is None and root_res is not None and getattr(root_res, "path", None):
            root = Path(root_res.path)
        if root is None:
            return []
        lib_dir = str(Path(__file__).resolve().parents[2] / "lib")   # 程式碼用本檔位置；CLAUDE_DIR 只拿來判根層與定位卡
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        from overview_scaffold import first_session_hint
        hint = first_session_hint(root, CLAUDE_DIR / "memory" if root == CLAUDE_DIR else None)
        return [hint] if hint else []
    except Exception as e:  # noqa: BLE001
        _atom_debug_error("session_start:first_session_hint", e)
        return []


def _need_goal_note(session_id: str, path: Path) -> str:
    """續接單帶【需求目標樹】時補一句：自己匯出的不用匯入，別的 session 的 Read 時走 wg_need_goal 的匯入。判不了 → 空字串。"""
    try:
        from wg_need_goal_points import handoff_note
        return handoff_note(session_id, path.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:  # noqa: BLE001
        _atom_debug_error("session_start:need_goal_note", e)
        return ""


def _next_phase_pointer(cwd: str, source: str, session_id: str = "") -> list:
    """壓縮／恢復後的接續指標：找最新的 `_staging/next-phase-*.md`（專案層優先，其次根層），
    一行叫模型先 Read 它並覆述現狀＋下一步。壓縮會丟掉對話裡的計畫脈絡；這個檔是單一權威狀態，
    不靠模型記得「該去讀」。檔裡有【需求目標樹】區塊時多補一句匯入與否。找不到就不吵。fail-open。"""
    try:
        from wg_core import resolve_staging_dir
        cands = []
        dirs = []
        try:
            dirs.append(resolve_staging_dir(cwd))
        except Exception:
            pass
        dirs.append(MEMORY_DIR / "_staging")
        seen = set()
        for d in dirs:
            if not d or str(d) in seen or not Path(d).is_dir():
                continue
            seen.add(str(d))
            cands += [p for p in Path(d).glob("next-phase-*.md") if p.is_file()]
        if not cands:
            return []
        newest = max(cands, key=lambda p: p.stat().st_mtime)
        why = "context 剛壓縮" if source == "compact" else "session 恢復"
        return [
            f"[Guardian:Resume] {why}：對話裡的計畫脈絡可能已失真 → 先 `Read {newest.as_posix()}`"
            "（最新交接檔），用一句話覆述現狀＋下一步再動工。" + _need_goal_note(session_id, newest)
        ]
    except Exception as e:  # noqa: BLE001
        _atom_debug_error("session_start:next_phase_pointer", e)
        return []


def _take_git_snapshot(state: Dict[str, Any], cwd: str) -> None:
    """開場快照：記下 cwd 所在 repo 的工作樹與本地分支（Stop 拿來比對，補抓 python 腳本裡開的工作樹這類指令解析看不到的
    建立，見 handlers/aec_ledger.snapshot_entries）。compact／resume 沿用開場那份；不是 repo 就不記。"""
    if (state.get("git_snapshot") or {}).get("repo") or not cwd:
        return
    try:
        from handlers import aec_ledger
        snap = aec_ledger.git_snapshot(cwd)
    except Exception as e:  # noqa: BLE001
        _atom_debug_error("session_start:git_snapshot", e)
        return
    if snap:
        state["git_snapshot"] = snap


def _ss_output(lines: List[str]) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n".join(lines)}},
                      ensure_ascii=False)


def _fallback_output(lines: List[str]) -> str:
    """背景鬧鐘代送（到上限 95% 還沒送出）：當下已備好的開場提示（追蹤提示在前段）＋一行說明；state 這次沒寫回。"""
    return _ss_output([*lines, "[Guardian:HookTiming] 開場 hook 快到上限被取消，先送出已備好的開場提示，其餘這次沒跑、"
                               "session 狀態這次沒寫回（下一則提問會重建）；各段耗時記在 Logs/guard-hook_timing.jsonl。"])


def _degraded_exit(session_id: str, state: Dict[str, Any], lines: List[str]) -> None:
    """開場超時降級（累計過上限 80%）：state 寫回、已備好的提示照送（追蹤提示在最前段），後面的選配提示與檢查
    這次跳過（含開場 git 快照、清舊 state、向量服務旗標與啟動）。"""
    lines.append(_hook_timing.degrade_note())
    write_state(session_id, state)
    _hook_timing.claim_output()
    print(_ss_output(lines))
    sys.exit(0)


def handle_session_start(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "unknown")
    cwd = input_data.get("cwd", "")
    source = input_data.get("source", "startup")
    root_res = None
    root_lines: List[str] = []
    try:
        root_res = resolve_project_root(cwd) if (resolve_project_root and cwd) else None
        root_lines = _project_root_notice(root_res, cwd)
    except Exception as e:
        _atom_debug_error("session_start:project_root", e)
    root_lines = [*root_lines, *_first_session_hint_lines(root_res, cwd)]

    # log rotation — prevent runaway log bloat
    try:
        from wg_core import rotate_log_if_oversized
        rotate_log_if_oversized(WORKFLOW_DIR / "guardian-crash.log", max_mb=10)
        rotate_log_if_oversized(WORKFLOW_DIR / "extract-worker.log", max_mb=10)
        rotate_log_if_oversized(CLAUDE_DIR / "Logs" / "codex-companion.log", max_mb=10)
        prune_workflow_records(current_sid=session_id)  # workflow/ 執行紀錄照 _shared.WORKFLOW_RETENTION 清
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
            if root_res is not None:
                redirect_state["atom_index"] = {
                    "project_root": str(root_res.path) if root_res.path else "",
                    "project_root_fingerprint": root_res.fingerprint,
                }
            write_state(session_id, redirect_state)
            lines = [f"[Workflow Guardian] Session merged ({source}).", *root_lines]
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": "\n".join(lines),
                }
            }, ensure_ascii=False))
            sys.exit(0)

    existing = read_state(session_id)
    _hook_lap("前置")
    _index_rebuild_notes: List[str] = []   # resume 分支不重建，仍要有值供收尾組訊息
    root_rebuilt = False
    if existing and source in ("compact", "resume") and not _root_fingerprint_matches(existing, root_res):
        # 專案根指紋變了（cwd 換了、宣告檔改了、或舊 state 還沒有指紋）→ 走下方重建分支重算
        # atom_index / aidocs，session 脈絡（修改檔、知識佇列…）照搬
        root_rebuilt = True
    if existing and source in ("compact", "resume") and not root_rebuilt:
        # compact/resume 複用舊 state 的 atom_index 快取（指紋相同才走到這裡）
        state = existing
        prev_atoms = state.get("injected_atoms", [])
        state["injected_atoms"] = []
        mod_count = len(state.get("modified_files", []))
        kq_count = len(state.get("knowledge_queue", []))
        phase = state.get("phase", "working")
        lines = [
            f"[Workflow Guardian] Session resumed ({source}). Phase: {phase}.",
            f"Modified files: {mod_count}. Knowledge queue: {kq_count}.",
            *root_lines,
            *_next_phase_pointer(cwd, source, session_id),
        ]
        if source == "compact":
            # 需求目標樹當場重送（不等下一批工具）；記時間讓緊接著的 PostCompact 不再存一份
            try:
                from wg_need_goal_points import recovery_text
                goal = recovery_text(session_id, config, cwd)
            except Exception as e:  # noqa: BLE001
                _atom_debug_error("session_start:need_goal_recovery", e)
                goal = ""
            if goal:
                lines.append(goal)
                state["need_goal_recovery_sent"] = time.time()
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
        if root_rebuilt and existing:
            for key in _CARRY_ON_REBUILD:
                if key in existing:
                    state[key] = existing[key]
            state["phase"] = existing.get("phase", "working")
        if sibling and source == "startup":
            state["_skip_vector_init"] = True

        # 追蹤提示最先算（只要 cwd 與 state）：開場超時降級、或背景鬧鐘代送時，最該到眼前的這段已經備好
        tracking_lines = _tracking_advisory(cwd, state)
        lines = ["[Workflow Guardian] Active.", *root_lines, *tracking_lines]
        _hook_timing.set_fallback(lambda: _fallback_output(lines))
        _hook_lap("追蹤提示")

        # ── 記憶層背景「拉」：在首次讀索引之前 detached 起 vcs-sync worker（秒回、不等）。
        # 趕不趕得上本次候選池隨緣——拉入的 atom 下一個 session 才一定進候選池，advisory 只報同步事實。
        _spawn_pull_sync(session_id, cwd, config)

        _index_rebuild_notes.append(_rebuild_index_if_missing(MEMORY_DIR))
        global_atoms = parse_memory_index(MEMORY_DIR)
        project_mem_dir = get_project_memory_dir(cwd)
        _index_rebuild_notes.append(_rebuild_index_if_missing(project_mem_dir))
        project_root = find_project_root(cwd)

        register_project(cwd)

        v4_user = ""
        v4_roles: List[str] = []
        v4_mgmt = False
        try:
            v4_user = get_current_user()
            bootstrap_personal_dir(cwd, v4_user)
            role_info = load_user_role(cwd, v4_user)
            v4_roles = list(role_info.get("roles") or [])  # 查不到職能＝[]，不預設 programmer
            v4_mgmt = is_management(cwd, v4_user)
        except Exception as e:
            _atom_debug_error("role_bootstrap", e)
        _hook_lap("索引與職能")

        state["user_identity"] = {
            "user": v4_user,
            "roles": v4_roles,
            "management": v4_mgmt,
        }

        # 候選池單源（wg_atoms.build_candidate_pool，memory_search 同用）：local-realm 閘門、
        # scope 可見性（SPEC §8.1：personal 只給本人、role 只給持有者）、Supersedes 名單都在裡面收窄一次；
        # UPS 六條檢索路全從此池取，不再各自過濾。副作用（註冊、bootstrap、MEMORY.md 重生）留在本檔。
        org_root = org_memory_root()
        pool = build_candidate_pool(
            cwd, v4_user, v4_roles,
            org_root=str(org_root) if org_root else None, global_atoms=global_atoms,
        )
        global_atoms = pool["global"]
        project_atoms_merged = pool["project"]

        v4_layout_active = bool(project_mem_dir) and any(
            (project_mem_dir / d).is_dir() for d in ("shared", "roles", "personal")
        )

        state["atom_index"] = {
            "global": pool["global"],
            "project": pool["project"],
            "org": pool["org"],
            "org_base": pool["org_base"],
            "project_memory_dir": pool["project_memory_dir"],
            "project_root": pool["project_root"],
            "project_root_fingerprint": root_res.fingerprint if root_res else "",
            "project_slug": pool["project_slug"],
            "scopes": pool["scopes"],
            "superseded": pool["superseded"],
        }
        state["injected_atoms"] = []
        if not root_rebuilt:
            state["phase"] = "working"

        if v4_layout_active and v4_user:
            _regenerate_role_filtered_memory_index(
                project_mem_dir, v4_user, v4_roles, v4_mgmt, project_atoms_merged,
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
            "[Workflow Guardian] Active." if not root_rebuilt
            else f"[Workflow Guardian] Session resumed ({source}); 專案根變更，atom index 已重建.",
            f"Global: {len(g_names)} atoms. Project: {len(p_names)}.",
            *[n for n in _index_rebuild_notes if n],
            *root_lines,
            *tracking_lines,
        ]
        if _hook_lap("候選池"):
            _degraded_exit(session_id, state, lines)

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
                _sk_dir = CODE_DIR / "skills"   # skills 屬程式碼樹（與 tools／hooks／lib 並列）
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
        if _hook_lap("索引校驗"):
            _degraded_exit(session_id, state, lines)

        # 選配提示：每段跑完打一點，累計過上限 80% 就送出收掉，後面的這次不跑。

        # ── 週健檢死人開關 ──────────────────────────────────
        # tools/health-weekly.py（Task Scheduler 每週跑）落 health-last-run.json。
        # 缺檔/逾期 = 排程器本身死了；red>0 = 上次健檢有待處理項。兩者都必須
        # 在 session 內浮出（fail-open 必告知）——「靜默死 27 天」的最後防線。
        lines.extend(_health_advisory(WORKFLOW_DIR / "health-last-run.json"))
        if _hook_lap("健檢"):
            _degraded_exit(session_id, state, lines)

        # ── 未推送 commit ─────────────────────────────────────
        # SessionEnd 晉升自動提交的 push 走背景、失敗當下無人知 → 這裡補可見性。
        lines.extend(_unpushed_advisory())
        lines.extend(_index_conflict_advisory(cwd))
        if _hook_lap("未推送與索引衝突"):
            _degraded_exit(session_id, state, lines)
        lines.extend(_followup_advisory())
        if _hook_lap("回訪"):
            _degraded_exit(session_id, state, lines)
        lines.extend(_verify_scope_advisory(cwd))
        lines.extend(_scope_layout_advisory(project_mem_dir))
        lines.extend(_vcs_ignore_advisory(project_mem_dir))
        lines.extend(_personal_sync_advisory(project_mem_dir, v4_user))
        if _hook_lap("範圍、分層與同步"):
            _degraded_exit(session_id, state, lines)
        lines.extend(_org_advisory(org_root, pool))
        _maybe_spawn_provenance_backfill(config)
        if _hook_lap("公司層"):
            _degraded_exit(session_id, state, lines)

        if v4_user:
            lines.append(
                f"[Role] user={v4_user} roles={','.join(v4_roles) or '-'} mgmt={v4_mgmt}"
            )
            # 待審草稿對所有人顯示（裁決資格另由 config review.deciders 決定）
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

    _hook_timing.set_fallback(lambda: _fallback_output(lines))   # compact／resume 那支也有代送（startup 前面已登記）
    if _hook_lap("開場主段"):
        _degraded_exit(session_id, state, lines)

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
    if _hook_lap("標記檔提示"):
        _degraded_exit(session_id, state, lines)

    try:
        review_reminder = _check_periodic_review_due(config)
        if review_reminder:
            lines.append(review_reminder)
            state["review_due"] = True
    except Exception as e:
        print(f"Review check error: {e}", file=sys.stderr)

    try:
        osc_warning = _load_oscillation_warnings(state)
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
    if _hook_lap("回顧提示"):
        _degraded_exit(session_id, state, lines)

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
    if _hook_lap("服務檢查"):
        _degraded_exit(session_id, state, lines)

    # 可觀測性：IDENTITY.md 完整性哨兵與必載檔硬契約哨兵（登記表驅動；USER.md 已由 user-init.sh 從 USER-{user}.md 拷好）。
    # 兩者都看 Claude Code 設定目錄（實際載入的那幾份），不看資料根：WG_CLAUDE_DIR 指到別處時那裡沒有啟動檔
    try:
        lines.extend(check_identity_integrity(claude_config_dir(), CLAUDE_DIR))
    except Exception as e:
        print(f"identity integrity check error: {e}", file=sys.stderr)
    try:
        lines.extend(check_always_load_contracts(claude_config_dir()))
    except Exception as e:
        print(f"always-load contract check error: {e}", file=sys.stderr)
    if _hook_lap("必載檔哨兵"):
        _degraded_exit(session_id, state, lines)

    _take_git_snapshot(state, cwd)
    if _hook_lap("git 快照"):
        _degraded_exit(session_id, state, lines)
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
    _hook_lap("清舊 state 與向量旗標")

    _hook_timing.claim_output()
    print(_ss_output(lines))

    # ── Vector service：fire-and-forget 啟動器（自癒/觀測邏輯在 starter.py）──
    # 已降級就不起：輸出送出後行程還得在上限內結束（Claude Code 取消時不保證採用已印的輸出）
    if (config.get("vector_search", {}).get("auto_start_service", True)
            and not state.get("_skip_vector_init") and not _hook_timing.degraded()):
        try:
            starter = CODE_DIR / "tools" / "memory-vector-service" / "starter.py"
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

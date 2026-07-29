"""atom_io.py — 全系統 atom 寫入唯一 funnel

設計目標：
  - 所有 atom 寫入入口（MCP server.js / hooks / tools）統一走 write_atom()
  - 行為對拍 server.js:1065 toolAtomWrite （byte-identical 內容契約）
  - 反向證明：每筆寫入記入 _meta/atom_io_audit.jsonl，可對拍 mtime 找出繞過

Skip flags：
  - skip_gate=True: 不呼叫 memory-write-gate.py（migration / 測試用）
  - skip_conflict_check=True: 不呼叫 memory-conflict-detector.py（同上）
  - dry_run=True: 算路徑、構造內容、validate，但不落檔（測試用）
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .atom_spec import (
    SKIP_DIRS, MEMORY_INDEX, VALID_CONFIDENCE, VALID_SCOPES,
    build_atom_content, slugify, validate_atom_content, render_knowledge_lines,
    knowledge_sections_bytes, knowledge_budget_error,
)
from .atom_locations import (
    CLAUDE_DIR, GLOBAL_MEMORY_DIR, FAILURES_DIR,
    is_failures_routed_title, failures_write_target, local_write_target,
    atom_search_roots, locate_existing_atom,
)


# ─── Constants ────────────────────────────────────────────────────────────────

AUDIT_LOG = GLOBAL_MEMORY_DIR / "_meta" / "atom_io_audit.jsonl"

# 接受的 source（供 audit 反查；未列舉值 → write_raw 回 WriteResult(ok=False, error="invalid source")、不 raise，呼叫端必檢查 .ok）
VALID_SOURCES = frozenset({
    "mcp",
    "hook:atom-inject",  # workflow-guardian.py 注入 atom 時走 atom_access
    "hook:episodic",
    "hook:episodic-confirm",  # wg_episodic L367 cross-session 加計
    "hook:user-extract",
    "hook:extract-worker",
    "tool:atom-move",
    "tool:atom-set-realm",  # V5+ Realm 維度：core⇄local 範疇搬移（_AIDocs/_atoms/ path 唯一寫者）
    "tool:atom-health-check",  # atom 健康診斷 / 反向參照修補
    "tool:atom-heal",  # 記憶自癒（腦內世界 P3）：機械修反向連結 / LLM 提案修死連結
    "tool:changelog-roll",
    "tool:memory-audit",  # memory-audit demote/compact/log_evolution 修補
    "tool:memory-cleanup",  # 一次性根目錄整理（merge-orphan-access）
    "tool:migrate",
    "tool:sync-atom-index",
    "tool:sync-memory-index",
    "tool:undo",
    "test",  # 測試用，等價測試 fixture 使用
})

# SPEC §7.4 sensitive audience triggers auto-pending
SENSITIVE_AUDIENCE = frozenset({"architecture", "decision"})

# edit_metadata 參數欄名 → frontmatter 標籤（參數複數、frontmatter 單數）。
# 行比對 regex 就地建於 edit_metadata 內（per-label），嚴禁 import tools/
# （sync-atom-index.py 含 '-' 無法 import，且 lib 反依賴 tools 為架構倒掛）。
_META_FIELD_LABEL = {"triggers": "Trigger", "related": "Related", "tags": "Tags"}


# ─── Result type ──────────────────────────────────────────────────────────────


@dataclass
class WriteResult:
    ok: bool
    path: Optional[Path] = None
    error: Optional[str] = None
    audit_id: str = ""
    routed_to_pending: bool = False
    skip_gate: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["path"] = str(self.path) if self.path else None
        return d


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _gen_audit_id() -> str:
    """ULID-ish: 13-char timestamp(ms) + 10-char random hex (足夠 audit 唯一性)。"""
    ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return f"{ts_ms:013d}-{secrets.token_hex(5)}"


def _audit_log(entry: Dict[str, Any]) -> None:
    """Append JSONL entry to atom_io_audit.jsonl（best-effort），>10MB 輪替。"""
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if AUDIT_LOG.stat().st_size > 10 * 1024 * 1024:
            _rotate_audit_log()
    except OSError:
        pass


def _rotate_audit_log() -> None:
    """輪替 atom_io_audit.jsonl（保留 3 份），對拍 memory-write-gate._rotate_log。"""
    for i in range(2, 0, -1):
        src = Path(f"{AUDIT_LOG}.{i}")
        dst = Path(f"{AUDIT_LOG}.{i + 1}")
        if src.exists():
            if i == 2:
                try:
                    src.unlink()
                except OSError:
                    pass
            else:
                try:
                    src.rename(dst)
                except OSError:
                    pass
    try:
        AUDIT_LOG.rename(Path(f"{AUDIT_LOG}.1"))
    except OSError:
        pass


def _detect_eol(path: Path) -> str:
    """偵測既有檔的主要行尾，供 byte-stable 覆寫。

    讀不到 / 新檔 → os.linesep（維持現行 Windows=CRLF 慣例，避免新 atom 行尾翻轉）。
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return os.linesep
    if b"\r\n" in raw:
        return "\r\n"
    if b"\n" in raw:
        return "\n"
    return os.linesep


def _atomic_write(path: Path, content: str) -> None:
    """tmp + rename 落檔，與 server.js 行為等價。

    EOL byte-stable（reformat blast radius 根治）：先把 content 正規化成純 LF，
    再套用「既有檔的行尾慣例」，並以 newline="" 寫入關閉平台轉譯。
    否則 Windows 預設 newline=None 會把每個 \\n 翻成 os.linesep——caller 混寫的
    既有 CRLF（如 server.js append 用 Node 原樣讀 \\r\\n 再拼 \\n）會被二次翻成
    CR CR LF，整檔行尾全變 → git 視為全行更動（append 2 行卻 48 行 diff 的根因）。
    既有 CRLF 檔偵測為 CRLF→原樣保留，僅真正新增的行進 diff。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    eol = _detect_eol(path)
    body = content.replace("\r\n", "\n").replace("\r", "\n")
    if eol != "\n":
        body = body.replace("\n", eol)
    # tmp 後綴帶 PID+TID 唯一化（仿 atom_access._write_raw）：固定 ".tmp" 會讓
    # 併發 session 寫同一 atom 時共用 tmp 檔互踩（truncate 競態 → 半空檔）。
    import threading as _threading
    tmp = path.with_suffix(
        f"{path.suffix}.tmp.{os.getpid()}.{_threading.get_ident()}"
    )
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(body)
        os.replace(str(tmp), str(path))
    except OSError:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def _find_project_root(cwd: Optional[str]) -> Optional[Path]:
    """對拍 wg_paths.find_project_root / server.js findProjectRoot。"""
    if not cwd:
        return None
    p = Path(cwd).resolve()
    for _ in range(4):
        if (p / ".claude" / "memory" / MEMORY_INDEX).exists():
            return p
        if (p / "_AIDocs").is_dir():
            return p
        if (p / ".git").exists() or (p / ".svn").exists():
            return p
        parent = p.parent
        if parent == p:
            break
        p = parent
    return None


def _resolve_target(
    scope: str,
    project_cwd: Optional[str],
    role: Optional[str],
    user: Optional[str],
    audience: Optional[List[str]],
    force_global: bool,
    title: Optional[str] = None,
    realm: Optional[str] = None,
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    """回傳 {dir, base, index_dir, index_root, search_roots, scope_label, routed_to_*, error}。

    `dir` = **新 atom 的落點**（扁平；主題分層由事後 classifier sweep 歸位，見
    [[scope-shared-無主題子夾路由-專案靠-project_hooks-sweep-分層]]）。
    `search_roots` = **既有 atom 的定位範圍**（append/replace 用，含子夾）——兩者
    刻意分離：create 不猜子夾、append/replace 不因子夾而找不到檔。

    對拍 server.js:777 resolveMemDir + 1095-1101 sensitive audience routing。
    V5+ 擴展（皆 global scope 內疊加，與 scope 正交）：
      - title 前綴 feedback- → 物理路由 _AIDocs/Failures/（routed_to_failures）
      - realm=local → 物理路由 _AIDocs/_atoms/<domain>/（routed_to_local；realm 由 path 推導，不存欄位）
    兩者索引皆仍在 memory/_atom_index.json（index_root=CLAUDE_DIR，單一來源）。
    realm 只在 scope=global 生效（local atom 維持 scope=global，realm 與 scope 正交）。
    """
    if force_global:
        scope = "global"

    if scope == "global":
        # global 的三個物理居所（memory/ + _AIDocs/Failures/ + _AIDocs/_atoms/）一律
        # 全納入定位範圍，不隨 create 落點縮窄——否則 realm/domain 給錯（或沒給）的
        # append/replace 會在錯的子樹找檔。對拍 server.js append/replace 的 find-fallback。
        global_roots = atom_search_roots()
        if is_failures_routed_title(title):
            return {
                **failures_write_target(),
                "search_roots": global_roots,
                "scope_label": "global",
                "routed_to_failures": True, "routed_to_pending": False,
                "routed_to_local": False,
                "error": None,
            }
        if realm == "local":
            return {
                **local_write_target(domain),
                "search_roots": global_roots,
                "scope_label": "global",
                "routed_to_failures": False, "routed_to_pending": False,
                "routed_to_local": True,
                "error": None,
            }
        GLOBAL_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        return {
            "dir": GLOBAL_MEMORY_DIR, "base": GLOBAL_MEMORY_DIR,
            "index_dir": GLOBAL_MEMORY_DIR, "index_root": CLAUDE_DIR,
            "search_roots": global_roots,
            "scope_label": "global",
            "routed_to_failures": False, "routed_to_pending": False,
            "routed_to_local": False,
            "error": None,
        }

    if scope not in ("shared", "role", "personal"):
        return {"error": f"Unknown scope: {scope}"}

    if scope == "role" and not role:
        return {"error": "scope=role requires 'role' parameter"}
    if scope == "personal" and not user:
        return {"error": "scope=personal requires 'user' parameter"}

    root = _find_project_root(project_cwd)
    if not root:
        return {"error": f"No project root found for scope={scope} cwd={project_cwd!r}"}
    # ~/.claude itself is global; reject V4 sub-scopes (P1 雙層防護)
    try:
        if root.resolve() == CLAUDE_DIR.resolve():
            return {"error": "cwd is ~/.claude itself; use scope=global for cross-project knowledge"}
    except OSError:
        pass

    base = root / ".claude" / "memory"
    if scope == "shared":
        target_dir = base / "shared"
        scope_label = "shared"
    elif scope == "role":
        target_dir = base / "roles" / role
        scope_label = f"role:{role}"
    else:  # personal
        target_dir = base / "personal" / user
        scope_label = f"personal:{user}"
    # 定位範圍 = 該 scope 自己的子樹（含主題子夾）。**不**放寬到 base/：
    # scope=shared 不得改到 personal/ 的檔，personal 不得跨使用者。
    # personal/auto/<user>/（extract-worker 自動草稿）落在 target_dir 之外 → 自然排除。
    search_roots = [target_dir]

    routed_to_pending = False
    if scope == "shared" and audience and any(
        a.strip().lower() in SENSITIVE_AUDIENCE for a in audience
    ):
        target_dir = base / "shared" / "_pending_review"
        routed_to_pending = True

    target_dir.mkdir(parents=True, exist_ok=True)
    return {
        "dir": target_dir, "base": base,
        "index_dir": base, "index_root": base.parent,
        "search_roots": search_roots,
        "scope_label": scope_label,
        "routed_to_failures": False, "routed_to_pending": routed_to_pending,
        "routed_to_local": False,
        "error": None,
    }


# ─── Index update（對拍 server.js:953 appendToIndex） ─────────────────────────


def write_index(
    base_dir: Path,
    slug: str,
    rel_path: str,
    triggers: Iterable[str],
    source: str,
) -> WriteResult:
    """更新或追加 atom 條目到 _atom_index.json (SoT)，並回寫 _ATOM_INDEX.md mirror。

    對拍 server.js:953 appendToIndex；JSON 為唯一機器源
    （atom_index_json 同 package，import 恆成功；MD 由其自動 regen）。
    """
    if source not in VALID_SOURCES:
        return WriteResult(ok=False, error=f"invalid source: {source}",
                           audit_id=_gen_audit_id())

    audit_id = _gen_audit_id()
    triggers_list = list(triggers)

    # write JSON via lib/atom_index_json (auto-regen MD mirror)
    from .atom_index_json import upsert_atom
    upsert_atom(
        mem_dir=base_dir,
        name=slug,
        path=rel_path,
        triggers=triggers_list,
        scope="global",
    )
    index_path = base_dir / "_atom_index.json"
    _audit_log({
        "audit_id": audit_id,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "op": "index", "source": source,
        "path": str(index_path), "slug": slug,
    })
    return WriteResult(ok=True, path=index_path, audit_id=audit_id)


def write_index_full(
    index_path: Path,
    content: str,
    *,
    source: str,
) -> WriteResult:
    """整檔覆寫 MEMORY.md / _ATOM_INDEX.md（給 sync-memory-index / sync-atom-index 整表重組用）。

    與 write_index 的差異：
      - write_index: row-by-row append/update（單 atom 寫入後同步索引）
      - write_index_full: 整檔覆寫（batch tool 重組整個 atom 索引表，例如 feedback-* 群組合併）

    所有寫入仍走 _atomic_write + _audit_log，行為對拍 funnel 其他入口。
    """
    if source not in VALID_SOURCES:
        return WriteResult(ok=False, error=f"invalid source: {source}",
                           audit_id=_gen_audit_id())
    audit_id = _gen_audit_id()
    try:
        _atomic_write(index_path, content)
    except OSError as e:
        return WriteResult(ok=False, error=f"write failed: {e}", audit_id=audit_id)
    _audit_log({
        "audit_id": audit_id, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "op": "index_full", "source": source, "path": str(index_path),
    })
    return WriteResult(ok=True, path=index_path, audit_id=audit_id)


# ─── Raw write escape hatch（給 V4 spec 不適用的 atom 子族用） ───────────────


def write_raw(
    file_path: Path,
    content: str,
    *,
    source: str,
    op: str = "raw",
) -> WriteResult:
    """Raw atom 寫入入口 — caller 提供完整 content + 絕對 path。

    用途：failures/ episodic/ cross-session 等子族不符 V4 build_atom_content 規範
    （沒 Trigger / Last-used / 用 Type:procedural 等），無法走 write_atom，但
    仍需走 audit log + PreToolUse 放行清單。

    funnel 只負責 _atomic_write + _audit_log；不做 validate / scope resolve / build。
    """
    audit_id = _gen_audit_id()
    if source not in VALID_SOURCES:
        return WriteResult(ok=False, audit_id=audit_id,
                           error=f"invalid source: {source}")
    try:
        _atomic_write(file_path, content)
    except OSError as e:
        return WriteResult(ok=False, audit_id=audit_id, error=f"write failed: {e}")
    _audit_log({
        "audit_id": audit_id, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "op": op, "source": source, "path": str(file_path),
    })
    return WriteResult(ok=True, audit_id=audit_id, path=file_path)


def _build_append_content(existing: str, knowledge: List[str]) -> str:
    """把 knowledge 渲染後插入 ## 行動 之前（block-aware）。

    write_atom(mode=append) 與 append_atom_file 共用的唯一拼接實作
    （server.js append 改 spawn CLI 走此處，
    消滅 js 自拼 readFileSync+`\\n` 的 CRLF 混寫面）。
    caller 須先確認 "## 行動" 存在。
    """
    action_idx = existing.find("## 行動")
    rendered = "\n".join(render_knowledge_lines(knowledge))
    before = existing[:action_idx].rstrip()
    after = existing[action_idx:]
    # 表格/fence 開頭需與既有知識間隔一空行才正確渲染（block-aware append）
    gap = "\n\n" if rendered.lstrip().startswith(("|", "```")) else "\n"
    return before + gap + rendered + "\n\n" + after


def append_atom_file(
    file_path: Path,
    knowledge: List[str],
    *,
    source: str,
    op: str = "atom_append",
) -> WriteResult:
    """對「已定位」的 atom .md 追加知識行（path 由 caller 解析，不重跑 scope 路由）。

    供 server.js toolAtomWrite(mode=append) spawn 用：js 端已處理 legacy fallback /
    Failures / local-realm 路由得到 file_path，內容拼接與落檔統一走 py（單一實作，
    EOL 由 _atomic_write byte-stable）。對拍 write_atom(mode=append) 拼接行為。
    不更新 access.json / index（caller 沿既有 spawnAtomAccess / appendToIndex 流程）。
    """
    audit_id = _gen_audit_id()
    if source not in VALID_SOURCES:
        return WriteResult(ok=False, audit_id=audit_id,
                           error=f"invalid source: {source}")
    fp = Path(file_path)
    try:
        existing = fp.read_text(encoding="utf-8-sig")
    except OSError as e:
        return WriteResult(ok=False, audit_id=audit_id, error=f"read failed: {e}")
    if "## 行動" not in existing:
        return WriteResult(ok=False, audit_id=audit_id,
                           error=f"Atom {fp.name} has no ## 行動 section")
    content = _build_append_content(existing, knowledge)
    err = validate_atom_content(content)
    if err:
        return WriteResult(ok=False, audit_id=audit_id,
                           error=f"Validation failed after append: {err}")
    # 大小預算硬拒（append 是 atom 肥大化的實際路徑：一次一點、累積成山）。
    # 以「拼接後」的 knowledge 區總量計——existing 已超額者任何 append 都會被拒，
    # 逼迫先瘦身（結論留 atom、個案敘事外移文件）再追加。
    budget_err = knowledge_budget_error(knowledge_sections_bytes(content))
    if budget_err:
        return WriteResult(ok=False, audit_id=audit_id,
                           error=f"Budget rejected after append: {budget_err}")
    return write_raw(fp, content, source=source, op=op)


def edit_metadata(
    file_path: Path,
    *,
    triggers: Optional[List[str]] = None,
    related: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    source: str = "mcp",
) -> WriteResult:
    """atom 元資料外科編輯 — 只替換 frontmatter 的 Trigger/Related/Tags 行。

    取代直接 Write/Edit atom .md（會被 Guardian guard 擋）與整檔 atom_write replace
    （重建知識區、風險高）。byte-stable：**只改目標那幾行**，其餘行原樣保留。

    SoT 順序（triggers 變更時）：先寫 _atom_index.json（機器唯一源），成功才續寫
    frontmatter（衍生），避免 frontmatter 領先 index 造成不可復原 drift。部分失敗
    可由 `tools/sync-atom-index.py --fix` 冪等復原，故不建交易層。

    Args:
        file_path: atom .md 絕對路徑（global memory 或 _AIDocs/Failures/ 皆可）
        triggers/related/tags: list[str]，None 表不動該欄位
        source: audit source（須在 VALID_SOURCES；預設 "mcp"）
    """
    audit_id = _gen_audit_id()
    if source not in VALID_SOURCES:
        return WriteResult(ok=False, audit_id=audit_id,
                           error=f"invalid source: {source}")

    # ── Read（utf-8-sig 容 BOM；但若原檔有 BOM 須原樣保留，避免非目標 byte 變更） ──
    try:
        raw = Path(file_path).read_bytes()
    except OSError as e:
        return WriteResult(ok=False, audit_id=audit_id, error=f"read failed: {e}")
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")

    # ── Surgical replace（每個非 None 欄位，只改那一行，count=1；找不到不靜默） ──
    fields = {"triggers": triggers, "related": related, "tags": tags}
    new_text = text
    for field_name, values in fields.items():
        if values is None:
            continue
        label = _META_FIELD_LABEL[field_name]
        value_str = ", ".join(values)
        replacement = f"- {label}: {value_str}"
        # per-label regex 收斂到「該欄位那一行」（就地定義，不依賴 tools/）
        line_re = re.compile(rf"^-\s*{label}:\s*.*$", re.MULTILINE)
        new_text, n = line_re.subn(replacement, new_text, count=1)
        if n == 0:
            # 找不到該欄位行 → 不靜默 no-op（且 frontmatter 尚未寫，index 也未寫）
            return WriteResult(
                ok=False, audit_id=audit_id,
                error=f"frontmatter field not found: {label}",
            )

    # ── SoT 先行：triggers 變更時先寫 _atom_index.json ──
    if triggers is not None:
        base_dir = GLOBAL_MEMORY_DIR  # global memory 與 Failures atoms 索引同居此
        slug = Path(file_path).stem
        try:
            rel_path = Path(file_path).resolve().relative_to(
                CLAUDE_DIR.resolve()).as_posix()
        except ValueError:
            return WriteResult(
                ok=False, audit_id=audit_id,
                error=f"file not under {CLAUDE_DIR}: {file_path}",
            )
        idx_res = write_index(base_dir, slug, rel_path, triggers, source)
        if not idx_res.ok:
            # index 領先失敗 → 不續寫 frontmatter（避免不可復原 drift）
            return idx_res

    # ── 寫 frontmatter（衍生，index 之後）；原檔有 BOM 則原樣補回 ──
    if had_bom:
        new_text = "﻿" + new_text
    return write_raw(Path(file_path), new_text, source=source, op="meta-edit")


# update_atom_field 已移除
# ----------------------------
# 計數類欄位（ReadHits / Confirmations / Last-used）已移到 <atom>.access.json
# 旁路檔，由 lib/atom_access.py 統一管理。任何過去呼叫 update_atom_field 的位置：
#   - hooks/wg_episodic.py:370 cross-session confirm → atom_access.increment_confirmation
#   - 其餘無實際 caller（grep 確認）
# 詳見 _AIDocs/Architecture.md「Atomic Memory Single Funnel」章節。


# ─── Main entry ───────────────────────────────────────────────────────────────


def write_atom(
    *,
    title: str,
    scope: str,
    confidence: str,
    triggers: List[str],
    knowledge: List[str],
    actions: Optional[List[str]] = None,
    related: Optional[List[str]] = None,
    audience: Optional[List[str]] = None,
    role: Optional[str] = None,
    user: Optional[str] = None,
    project_cwd: Optional[str] = None,
    mode: str = "create",
    source: str,
    skip_gate: bool = False,
    skip_conflict_check: bool = False,
    dry_run: bool = False,
    force_global: bool = False,
    pending_review_by: Optional[str] = None,
    merge_strategy: Optional[str] = None,
    author: Optional[str] = None,
    today: Optional[str] = None,
    realm: Optional[str] = None,
    domain: Optional[str] = None,
) -> WriteResult:
    """寫入 atom 的唯一入口。對拍 server.js:1065 toolAtomWrite byte-identical。

    Required: title, scope, confidence, triggers, knowledge, mode, source
    V5+ realm/domain（選填，僅 scope=global 生效）：realm="local" → 物理落
    _AIDocs/_atoms/<domain>/，realm 由 path 推導不存欄位。預設 core（現狀）。
    """
    audit_id = _gen_audit_id()

    # ── Validate ──
    if source not in VALID_SOURCES:
        return WriteResult(ok=False, audit_id=audit_id,
                           error=f"invalid source: {source} (must be in VALID_SOURCES)")
    if not title or not confidence or not triggers or not knowledge or not mode:
        return WriteResult(ok=False, audit_id=audit_id,
                           error="Missing required parameters")
    if confidence not in VALID_CONFIDENCE:
        return WriteResult(ok=False, audit_id=audit_id,
                           error=f"invalid confidence: {confidence}")
    if mode == "create" and confidence != "[臨]":
        return WriteResult(ok=False, audit_id=audit_id,
                           error=f"New atom must start at [臨] (got {confidence})")

    # V4: scope=project legacy mapping → shared
    if scope == "project":
        scope = "shared"
    if scope not in VALID_SCOPES:
        return WriteResult(ok=False, audit_id=audit_id,
                           error=f"Unknown scope: {scope}")

    # ── Resolve target dir ──
    resolved = _resolve_target(scope, project_cwd, role, user, audience, force_global,
                               title=title, realm=realm, domain=domain)
    if resolved.get("error"):
        return WriteResult(ok=False, audit_id=audit_id, error=resolved["error"])
    mem_dir = resolved["dir"]
    scope_label = resolved["scope_label"]
    routed_to_pending = resolved["routed_to_pending"]

    pending_by = pending_review_by or ("management" if routed_to_pending else None)

    slug = slugify(title)
    file_path = mem_dir / f"{slug}.md"
    index_root = resolved["index_root"]

    # append/replace 的實體檔可能不在扁平落點（專案 shared/<Domain>/、local realm
    # _AIDocs/_atoms/<domain>/）→ 索引優先、rglob 為輔定位。create 不做：新 atom
    # 一律落扁平點，主題分層交事後 classifier sweep（見 _resolve_target docstring）。
    if mode in ("append", "replace") and not file_path.exists():
        found, loc_err = locate_existing_atom(
            slug,
            index_dir=resolved["index_dir"],
            index_root=index_root,
            search_roots=resolved.get("search_roots") or [],
        )
        if loc_err:
            return WriteResult(ok=False, audit_id=audit_id, error=loc_err)
        if found:
            file_path = found

    try:
        rel_path = file_path.relative_to(index_root).as_posix()
    except ValueError:
        return WriteResult(ok=False, audit_id=audit_id,
                           error=f"located atom outside index root: {file_path}")

    # ── Build content ──
    if mode == "create":
        if file_path.exists():
            return WriteResult(ok=False, audit_id=audit_id,
                               error=f"Atom already exists: {slug}.md (use mode=append/replace)")
        content = build_atom_content(
            title=title, scope=scope_label, confidence=confidence, triggers=triggers,
            knowledge=knowledge, actions=actions, related=related, audience=audience,
            author=author, pending_review_by=pending_by, merge_strategy=merge_strategy,
            today=today,
        )
    elif mode == "append":
        if not file_path.exists():
            return WriteResult(ok=False, audit_id=audit_id,
                               error=f"Atom not found: {slug}.md (use mode=create first)")
        existing = file_path.read_text(encoding="utf-8-sig")
        action_idx = existing.find("## 行動")
        if action_idx < 0:
            return WriteResult(ok=False, audit_id=audit_id,
                               error=f"Atom {slug}.md has no ## 行動 section")
        # Last-used 不再寫 .md；append 後由下方 atom_access.write_access_field 刷
        content = _build_append_content(existing, knowledge)
    elif mode == "replace":
        # Confirmations/ReadHits 在 access.json，replace 不需保留（檔本就分離）
        # Author/Created-at 仍從舊 atom .md 抽（屬知識性 metadata）
        prev_author = author
        prev_created = today or datetime.now(timezone.utc).date().isoformat()
        if file_path.exists():
            old = file_path.read_text(encoding="utf-8-sig")
            am = re.search(r"^- Author:\s*(.+)$", old, re.MULTILINE)
            if am:
                prev_author = am.group(1).strip()
            cmm = re.search(r"^- Created-at:\s*(.+)$", old, re.MULTILINE)
            if cmm:
                prev_created = cmm.group(1).strip()
        content = build_atom_content(
            title=title, scope=scope_label, confidence=confidence, triggers=triggers,
            knowledge=knowledge, actions=actions, related=related, audience=audience,
            author=prev_author, pending_review_by=pending_by, merge_strategy=merge_strategy,
            created_at=prev_created, today=today,
        )
    else:
        return WriteResult(ok=False, audit_id=audit_id,
                           error=f"Unknown mode: {mode}")

    # ── Validate content ──
    err = validate_atom_content(content)
    if err:
        return WriteResult(ok=False, audit_id=audit_id, error=f"Validation failed: {err}")

    # ── Dry-run short-circuit ──
    if dry_run:
        return WriteResult(ok=True, audit_id=audit_id, path=file_path,
                           routed_to_pending=routed_to_pending, skip_gate=skip_gate,
                           extra={"content": content, "rel_path": rel_path,
                                  "scope_label": scope_label, "dry_run": True})

    # ── Write file ──
    _atomic_write(file_path, content)

    # ── 同步維護 <atom>.access.json 旁路檔 ──
    # 延遲 import 避免 atom_io ↔ atom_access 環依（atom_access import atom_io 的 audit infra）
    today_str = today or datetime.now(timezone.utc).date().isoformat()
    try:
        from . import atom_access
        if mode == "create":
            # init 一次帶齊 first_seen + last_used（單寫；create 時 sidecar 必為新檔）
            atom_access.init_access(
                file_path, first_seen=today_str, last_used=today_str, source=source,
            )
        else:  # append / replace
            atom_access.write_access_field(
                file_path, field="last_used", value=today_str, source=source,
            )
    except (ImportError, ValueError, OSError):
        # access 旁路檔失敗不致命；atom .md 已落檔
        pass

    # ── Update index ──
    if mode in ("create", "replace"):
        write_index(resolved["index_dir"], slug, rel_path, triggers, source)

    # ── Audit log ──
    _audit_log({
        "audit_id": audit_id, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "op": "write", "source": source, "mode": mode, "scope": scope_label,
        "slug": slug, "path": str(file_path),
        "routed_to_pending": routed_to_pending, "skip_gate": skip_gate,
    })

    return WriteResult(ok=True, audit_id=audit_id, path=file_path,
                       routed_to_pending=routed_to_pending, skip_gate=skip_gate)


def locate_atom(
    title: str,
    scope: str = "shared",
    *,
    project_cwd: Optional[str] = None,
    role: Optional[str] = None,
    user: Optional[str] = None,
    audience: Optional[List[str]] = None,
    force_global: bool = False,
    realm: Optional[str] = None,
    domain: Optional[str] = None,
) -> WriteResult:
    """定位既有 atom 實體檔（唯讀，無副作用之外的落檔）。給 MCP js 端 append/replace 用。

    js 不自建第二套定位邏輯（既有 findAtomFileRecursive 只覆蓋 scope=global，
    專案 scope 全漏）——統一 spawn 本函式，py/js 定位規則單一來源、不會漂移。
    回 WriteResult：ok=True 且 path=None ⇒ 找不到（caller 給 not-found 訊息）；
    ok=False ⇒ 撞名或 scope 解析錯，error 已含說明。extra.rel_path 供索引回寫。
    """
    audit_id = _gen_audit_id()
    if scope == "project":
        scope = "shared"
    resolved = _resolve_target(scope, project_cwd, role, user, audience, force_global,
                               title=title, realm=realm, domain=domain)
    if resolved.get("error"):
        return WriteResult(ok=False, audit_id=audit_id, error=resolved["error"])

    slug = slugify(title)
    index_root = resolved["index_root"]
    file_path = resolved["dir"] / f"{slug}.md"
    if not file_path.exists():
        found, loc_err = locate_existing_atom(
            slug,
            index_dir=resolved["index_dir"],
            index_root=index_root,
            search_roots=resolved.get("search_roots") or [],
        )
        if loc_err:
            return WriteResult(ok=False, audit_id=audit_id, error=loc_err)
        if not found:
            return WriteResult(ok=True, audit_id=audit_id, path=None,
                               extra={"found": False})
        file_path = found
    try:
        rel_path = file_path.relative_to(index_root).as_posix()
    except ValueError:
        return WriteResult(ok=False, audit_id=audit_id,
                           error=f"located atom outside index root: {file_path}")
    return WriteResult(ok=True, audit_id=audit_id, path=file_path,
                       extra={"found": True, "rel_path": rel_path,
                              "scope_label": resolved["scope_label"]})

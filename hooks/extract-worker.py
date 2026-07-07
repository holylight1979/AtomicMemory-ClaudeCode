#!/usr/bin/env python3
"""Extraction worker for response capture.

Spawned by workflow-guardian.py as a detached subprocess.
Three modes:
  - SessionEnd (default): full transcript extraction
  - per_turn: incremental extraction from byte_offset, lighter, writes back to state
  - failure: failure-pattern extraction triggered by user complaints, writes to failure atoms

Reads context from stdin (JSON), outputs results to stdout (JSON).
Survives hook timeout — runs ~60s on GTX 1050 Ti.
"""

import json
import re
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# ─── Import centralized paths from wg_core (V5: wg_paths merged into wg_core) ─
_HOOKS_DIR = str(Path.home() / ".claude" / "hooks")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from wg_core import (
    cwd_to_project_slug,
    get_transcript_path,
    resolve_failures_dir,
    find_project_root,
    CLAUDE_DIR,
    MEMORY_DIR,
)
from wg_extraction import classify_extracted_item

# route failure atom writes through atom_io funnel
_LIB_PARENT = str(Path.home() / ".claude")
if _LIB_PARENT not in sys.path:
    sys.path.insert(0, _LIB_PARENT)
from lib.atom_io import build_atom_content, write_raw  # noqa: E402
from lib.atom_spec import slugify  # noqa: E402

WORKFLOW_DIR = CLAUDE_DIR / "workflow"

# Windows cp950 → UTF-8 (detached subprocess doesn't inherit guardian's encoding)
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

# ─── Import shared core from lib/ ───────────────────────────────────────────
_CLAUDE_ROOT = str(CLAUDE_DIR)
if _CLAUDE_ROOT not in sys.path:
    sys.path.insert(0, _CLAUDE_ROOT)

from lib.ollama_extract_core import (
    _call_ollama,
    _parse_llm_response,
    _dedup_items,
    _word_overlap_score,
    _atom_debug_log,
    _atom_debug_error,
    _estimate_tokens,
    ack_then_clear,
    VALID_TYPES,
)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _empty_result() -> Dict[str, Any]:
    return {
        "extracted_items": [],
        "cross_session_observations": [],
        "aggregation_suggestions": [],
    }


# ─── Transcript helpers ──────────────────────────────────────────────────────


def _extract_all_assistant_texts(
    transcript_path: Path, max_chars: int = 20000, byte_offset: int = 0
) -> tuple:
    """Read assistant text blocks from JSONL transcript.

    Returns (texts: list[str], final_byte_offset: int).
    When byte_offset > 0, seeks to that position first (incremental read).
    """
    texts = []
    total = 0
    final_offset = byte_offset
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            if byte_offset > 0:
                f.seek(byte_offset)
            for raw_line in f:
                try:
                    obj = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "assistant":
                    continue
                content = obj.get("message", {}).get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        t = block.get("text", "")
                        if t and len(t) > 30:
                            texts.append(t)
                            total += len(t)
                if total >= max_chars:
                    break
            final_offset = f.tell()
    except (OSError, UnicodeDecodeError) as e:
        _atom_debug_error("extract_worker:transcript_read", e)
        pass
    return texts, final_offset


# ─── Prompt templates ─────────────────────────────────────────────────────────

_SYSTEM_CONTEXT = (
    "你是「原子記憶系統」的知識萃取器。萃取出的知識會存入長期記憶，供未來 session 引用。\n"
    "只萃取「這個專案/環境特有的」、「下次會用到的」事實。通用程式知識不要。\n\n"
)

_FORMAT_SPEC = (
    "輸出 JSON array: [{\"content\": \"精簡事實，最多150字\", "
    "\"type\": \"factual|procedural|architectural|pitfall|decision\"}]\n\n"
    "範例（值得萃取）:\n"
    '  {"content": "rdchat Open WebUI LDAP 端點是 /api/v1/auths/ldap，用 user 欄位（非 email）", "type": "factual"}\n'
    '  {"content": "GTX 1050 Ti 跑 qwen3:1.7b generate 約 30s，qwen3-embedding embed 約 5s", "type": "factual"}\n'
    '  {"content": "LanceDB search 用 cosine metric，min_score 0.65 以下多為噪音", "type": "architectural"}\n\n'
    "範例（不要萃取）:\n"
    '  ✗ "Python 的 dict 是 hash table" → 通用知識\n'
    '  ✗ "修改了 config.py 第 43 行" → session 進度，不是知識\n'
    '  ✗ "使用 git commit 提交變更" → 常識\n\n'
)

_RULES_COMMON = (
    "規則:\n"
    "- 只萃取此專案/環境特有的具體事實（含數值、路徑、版本、錯誤碼）\n"
    "- 跳過：程式碼片段、session 進度、隨便 Google 就能查到的知識\n"
    "- 跳過：規劃/計畫/待辦/下一步/草稿/TODO/Phase 排程等未來意圖（只取已確定的事實）\n"
    "- 沒有值得萃取的內容就輸出 []\n"
    "- 直接輸出 JSON，不要解釋\n"
    "/no_think\n\n"
)

_PROMPT_TEMPLATES = {
    "build": (
        _SYSTEM_CONTEXT
        + "本次 session 類型：開發建構。重點關注：架構決策、工具配置、框架行為、API 特性。\n\n"
        + _FORMAT_SPEC + _RULES_COMMON
        + "Session 文字:\n{text}\n\nJSON:"
    ),
    "debug": (
        _SYSTEM_CONTEXT
        + "本次 session 類型：除錯。重點關注：根因分析、錯誤模式、誤導性症狀、環境相關的坑。\n\n"
        + _FORMAT_SPEC + _RULES_COMMON
        + "Session 文字:\n{text}\n\nJSON:"
    ),
    "design": (
        _SYSTEM_CONTEXT
        + "本次 session 類型：設計。重點關注：設計決策的理由、權衡分析、被否決的方案及原因。\n\n"
        + _FORMAT_SPEC + _RULES_COMMON
        + "Session 文字:\n{text}\n\nJSON:"
    ),
}

_FAILURE_PROMPT = (
    "你是「原子記憶系統」的失敗模式分析器。使用者回報了重複或未修好的問題。\n"
    "分析對話內容，萃取出失敗模式記錄。\n\n"
    "四種失敗類型:\n"
    "- env: 環境踩坑（工具/平台/版本/port/路徑/config 造成的非預期行為）\n"
    "- assumption: 假設錯誤（直覺判斷錯誤、沒調查就下結論、調查方向偏差）\n"
    "- silent: 靜默失敗（看似正常但結果不對、錯誤被吞掉、資料沒寫入）\n"
    "- cognitive: 認知偏差（代理指標、過度工程、反覆犯同一模式、選錯抽象層級）\n\n"
    "輸出格式 — JSON array:\n"
    '[{"content": "{觸發場景} → {錯誤行為} → {正確做法}（根因: ...）", '
    '"failure_type": "env|assumption|silent|cognitive", '
    '"domain_tags": ["tag1"]}]\n\n'
    "規則:\n"
    "- 如果對話中不是真正的失敗（使用者只是描述需求），輸出 []\n"
    "- content 遵循「觸發 → 錯誤 → 正確（根因）」格式，最多 150 字\n"
    "- 最多萃取 2 條\n"
    "- domain_tags: 1-3 個領域標籤（如 gameplay, memory-system, git, unity, ollama）\n"
    "- 直接輸出 JSON\n\n"
    "使用者的回報:\n{failure_prompt}\n\n"
    "最近對話:\n{text}\n\nJSON:"
)

VALID_FAILURE_TYPES = ("env", "assumption", "silent", "cognitive")


def _build_prompt(intent: str, text: str, existing_items: List[dict] = None) -> str:
    template = _PROMPT_TEMPLATES.get(intent, _PROMPT_TEMPLATES["build"])
    prompt = template.replace("{text}", text[:4000])
    # Removed pre-filter dedup injection (was ~200 tok/call).
    # Post-filter _dedup_items() at threshold=0.65 is sufficient to catch duplicates.
    return prompt


# ─── Pattern aggregation ──────────────────────────────────────────────────────


def _check_trigger_overlap(items: List[dict]) -> List[dict]:
    """Check for overlapping topics among extracted items (n<=5, O(n^2) ok)."""
    suggestions = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            ca = items[i].get("content", "")
            cb = items[j].get("content", "")
            score = _word_overlap_score(ca, cb)
            if score > 0.40:
                suggestions.append({
                    "item_a": ca,
                    "item_b": cb,
                    "overlap_score": round(score, 2),
                })
    return suggestions


# ─── Cross-session observation ────────────────────────────────────────────────


def _cross_session_search(
    items: List[dict], session_id: str, config: Dict[str, Any]
) -> List[dict]:
    """Vector search each item for cross-session patterns."""
    vs_config = config.get("vector_search", {})
    if not vs_config.get("enabled", True):
        return []

    port = vs_config.get("service_port", 3849)
    cs_config = config.get("cross_session", {})
    min_score = cs_config.get("min_score", 0.75)
    timeout_s = cs_config.get("timeout_seconds", 15)
    current_prefix = session_id[:8] if session_id else ""

    observations = []

    for item in items:
        content = item.get("content", "")
        if not content or len(content) < 20:
            continue

        try:
            params = urllib.parse.urlencode({
                "q": content[:200],
                "top_k": 5,
                "min_score": min_score,
            })
            url = f"http://127.0.0.1:{port}/search/ranked?{params}"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    results = json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    url = f"http://127.0.0.1:{port}/search?{params}"
                    req = urllib.request.Request(url, headers={"Accept": "application/json"})
                    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                        results = json.loads(resp.read())
                else:
                    continue

            # Count distinct sessions from episodic atoms
            session_atoms = set()
            for r in results:
                atom_name = r.get("atom_name", "")
                if "episodic" in atom_name.lower():
                    if current_prefix and current_prefix in atom_name:
                        continue
                    session_atoms.add(atom_name)
                elif atom_name:
                    session_atoms.add(f"atom:{atom_name}")

            hit_count = len(session_atoms)
            if hit_count < 2:
                continue

            # Increment confirmations (no classification change)
            item["confirmations"] = item.get("confirmations", 1) + hit_count

            obs = {
                "content": content[:80],
                "sessions_hit": hit_count,
                "matched_atoms": sorted(session_atoms),
                "suggest_promotion": hit_count >= 4,
            }

            if hit_count >= 4:
                item["promotion_hint"] = (
                    f"建議晉升 → [觀]（{hit_count} sessions 命中，需使用者確認）"
                )

            observations.append(obs)

        except Exception as e:
            _atom_debug_error("萃取:_cross_session_search", e)
            continue  # Skip this item, try next

    return observations


# ─── Main orchestrator ────────────────────────────────────────────────────────


def run_extraction(ctx: Dict[str, Any]) -> Dict[str, Any]:
    session_id = ctx.get("session_id", "")
    cwd = ctx.get("cwd", "")
    config = ctx.get("config", {})
    knowledge_queue = ctx.get("knowledge_queue", [])
    intent = ctx.get("session_intent", "build")
    mode = ctx.get("mode", "session_end")
    is_per_turn = mode == "per_turn"
    is_failure = mode == "failure"

    # recall sessions rarely produce new knowledge
    if intent == "recall" and not is_failure:
        return _empty_result()

    # Find and read transcript
    transcript = get_transcript_path(session_id, cwd)
    if not transcript:
        return _empty_result()

    rc = config.get("response_capture", {})
    pt = rc.get("per_turn", {})
    fc = rc.get("failure_extraction", {})

    if is_failure:
        byte_offset = ctx.get("byte_offset", 0)
        max_chars = 3000
        max_items = fc.get("max_items", 2)
    elif is_per_turn:
        byte_offset = ctx.get("byte_offset", 0)
        max_chars = 4000
        max_items = pt.get("max_items", 3)
    else:
        # SessionEnd skips already-extracted bytes with overlap for context
        prev_offset = ctx.get("byte_offset", 0)
        overlap = 1000  # chars of overlap to maintain context continuity
        byte_offset = max(0, prev_offset - overlap)
        max_chars = rc.get("session_end_max_chars", 20000)
        max_items = rc.get("session_end_max_items", 5)

    texts, final_offset = _extract_all_assistant_texts(
        transcript, max_chars=max_chars, byte_offset=byte_offset
    )
    if not texts:
        return _empty_result()

    combined = "\n---\n".join(texts)
    if len(combined) < 50:
        return _empty_result()

    # Build prompt based on mode
    if is_failure:
        failure_prompt = ctx.get("failure_prompt", "")[:500]
        prompt = _FAILURE_PROMPT.replace("{failure_prompt}", failure_prompt)
        prompt = prompt.replace("{text}", combined[:3000])
    else:
        # LLM extraction with intent-aware prompt
        # Pass existing items so LLM avoids duplicates in generation
        prompt = _build_prompt(intent, combined,
                               existing_items=knowledge_queue if knowledge_queue else None)

    raw = _call_ollama(prompt)
    parsed = _parse_llm_response(raw)
    if not parsed:
        return _empty_result()

    # Dedup against existing knowledge_queue (0.65 for both modes)
    items = _dedup_items(parsed, knowledge_queue, threshold=0.65)
    # Cap items
    items = items[:max_items]
    if not items:
        return _empty_result()

    # Content-type gate — filter out plan/draft items (route to _staging)
    plan_items = [it for it in items if classify_extracted_item(it) == "plan"]
    items = [it for it in items if classify_extracted_item(it) != "plan"]
    if plan_items:
        print(f"Filtered {len(plan_items)} plan-type items from extraction", file=sys.stderr)
    if not items and not is_failure:
        return _empty_result()

    # Tag source
    source_tag = "failure" if is_failure else ("per-turn" if is_per_turn else "session-end")
    for item in items:
        item["source"] = source_tag

    # Pattern aggregation
    aggregation = _check_trigger_overlap(items)

    # Cross-session vector search (skip in per_turn and failure if configured)
    # lazy mode — only search items that overlap with existing knowledge_queue,
    # since brand-new items (confirmations=1) are unlikely to have cross-session hits.
    observations = []
    if not (is_per_turn and pt.get("skip_cross_session", True)) and not is_failure:
        # Pre-filter: only items with word overlap against existing queue worth searching
        searchable = []
        for item in items:
            ic = item.get("content", "")
            for eq in knowledge_queue:
                if _word_overlap_score(ic, eq.get("content", "")) >= 0.30:
                    searchable.append(item)
                    break
        if searchable:
            observations = _cross_session_search(searchable, session_id, config)

    result = {
        "extracted_items": items,
        "cross_session_observations": observations,
        "aggregation_suggestions": aggregation,
    }
    if is_per_turn:
        result["final_offset"] = final_offset
    return result


# ─── State writeback (for per-turn mode) ─────────────────────────────────


def _write_state_atomic(state_path: Path, state: dict) -> bool:
    """Atomic write: temp file → rename. Returns True on success."""
    tmp = state_path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        tmp.replace(state_path)
        return True
    except OSError as e:
        _atom_debug_error("extract_worker:state_write", e)
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        return False


def _per_turn_writeback(ctx: dict, result: dict) -> None:
    """Write per-turn extraction results back to session state."""
    session_id = ctx.get("session_id", "")
    if not session_id:
        return
    state_path = WORKFLOW_DIR / f"state-{session_id}.json"
    if not state_path.exists():
        return
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    items = result.get("extracted_items", [])
    if items:
        kq = state.get("knowledge_queue", [])
        kq.extend(items)
        state["knowledge_queue"] = kq

    if result.get("final_offset"):
        state["extraction_offset"] = result["final_offset"]

    state["extract_worker_pid"] = 0  # clear lease (worker done)
    state["last_updated"] = _now_iso()
    _write_state_atomic(state_path, state)
    # Note: ack_then_clear (imported from lib/) is available for
    # user-extract-worker.py to pop from pending_user_extract after
    # successful atom_write. Not called here — per_turn appends to
    # knowledge_queue for later session_end processing.

# ─── Session-end writeback: flush knowledge → [臨] atoms ──────────────────────
#
# 補長期缺口：session_end 深度萃取算完即丟、knowledge_queue 從未落地成 atom
# （見上方 _per_turn_writeback 註解「per_turn appends to knowledge_queue for later
# session_end processing」——那個 processing 從沒實作）。此處補完：把本 session
# 累積的 queue + session_end 全文萃取，過品質閘後寫成 global personal [臨] atom，
# 全自動、不問使用者。只清「寫成功」的 queue 項，失敗者留待下次重試。

_FLUSH_MIN_LEN = 12  # 過短碎句不值得建 atom（內聯常數，非旋鈕）


def _flush_route(cwd, _find_root=None):
    """決定自動萃取 atom 草稿的落點。

    專案 session（cwd 有 project root 且非 ~/.claude）→ scope=shared（只在該專案
    注入），~/.claude / 無 root / 空 cwd → scope=global。避免專案專屬知識污染 global core。
    auto-capture [臨] 草稿一律隔離到 `_drafts/auto-capture/` 子層（dedup_dir）——
    `sync-atom-index` EXCLUDED_DIR_PARTS 排除 `_drafts` → 不入索引、不注入、不計數，根治
    content-as-filename 碎片污染 memory/ 根。scope 仍決定 _drafts 掛在
    global（memory/）或專案 shared 樹下。_find_root 供測試注入。
    回 (scope, project_cwd, draft_dir)。"""
    finder = _find_root or find_project_root
    root = finder(cwd) if cwd else None
    rootp = Path(root) if root else None
    try:
        is_project = bool(rootp) and rootp.resolve() != CLAUDE_DIR.resolve()
    except OSError:
        is_project = False
    draft = Path("_drafts") / "auto-capture"
    if is_project:
        return "shared", cwd, rootp / ".claude" / "memory" / "shared" / draft
    return "global", None, MEMORY_DIR / draft


def _flush_item_to_atom(content: str, triggers: list, *,
                        scope: str = "global", project_cwd=None,
                        dedup_dir=MEMORY_DIR) -> str:
    """把一條萃取知識寫成 [臨] auto-capture 草稿，隔離落 dedup_dir（`_drafts/auto-capture/`，
    見 _flush_route）。

    auto-capture 草稿**不再走 write_atom 入索引/注入**（避免大量
    content-as-filename 碎片污染 memory/ 根層）。改 build_atom_content + write_raw 直寫
    dedup_dir（`_drafts/` 被 sync-atom-index 排除 → 不入索引、不注入、不計數）。草稿待人工
    檢視/手動晉升；真有值的知識在工作中已正規記錄（changelog / atom_write）。
    content 推 slug、路徑去重 + -N 防撞。Returns 'wrote' | 'deduped' | 'failed'。
    """
    content = content.strip()
    triggers = [t.strip() for t in (triggers or []) if t and str(t).strip()] or ["auto-capture"]
    slug = slugify(content[:60]) or "auto-capture"

    try:
        dedup_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        _atom_debug_error("session_end_writeback:draft_mkdir", e)
        return "failed"

    if (dedup_dir / f"{slug}.md").exists():
        try:
            if content[:80] in (dedup_dir / f"{slug}.md").read_text(encoding="utf-8-sig"):
                return "deduped"
        except (OSError, UnicodeDecodeError):
            pass
        for i in range(2, 10):
            if not (dedup_dir / f"{slug}-{i}.md").exists():
                slug = f"{slug}-{i}"
                break

    try:
        atom_text = build_atom_content(
            title=slug,
            scope=scope,
            confidence="[臨]",
            triggers=triggers,
            knowledge=[f"- [臨] {content}"],
            author="auto-captured",
        )
        res = write_raw(dedup_dir / f"{slug}.md", atom_text,
                        source="hook:extract-worker", op="auto_capture_draft")
    except Exception as e:
        _atom_debug_error("session_end_writeback:write_draft", e)
        return "failed"
    if res.ok:
        return "wrote"
    _atom_debug_error("session_end_writeback:write_draft", Exception(res.error or ""))
    return "failed"


def _session_end_writeback(ctx: dict, result: dict) -> None:
    """Flush session_end 萃取 + 累積 knowledge_queue → [臨] atoms（全自動）。

    順序：先 fresh（session_end 全文萃取的精選 top-N，品質較高）再 queue（per_turn
    累積）。達 max_atoms 上限即停，未處理的 queue 項留在 queue 下次再 flush（不丟）。
    """
    config = ctx.get("config", {})
    sef = config.get("response_capture", {}).get("session_end_flush", {})
    if not sef.get("enabled", True):
        return

    session_id = ctx.get("session_id", "")
    queue = ctx.get("knowledge_queue", []) or []
    fresh = result.get("extracted_items", []) or []
    max_atoms = sef.get("max_atoms", 8)
    # 依 session cwd 決定落點——專案 session → 專案層 shared、不污染 global core。
    flush_scope, flush_pcwd, dedup_dir = _flush_route(ctx.get("cwd", ""))

    # fresh 先（origin='fresh'，不在 queue 不需清）；queue 後（記原 index 供 ack-clear）
    tagged = [("fresh", -1, it) for it in fresh] + \
             [("queue", i, it) for i, it in enumerate(queue)]

    written_q_indices = []
    n_written = 0
    seen: List[str] = []
    for origin, qidx, it in tagged:
        if n_written >= max_atoms:
            break
        content = (it.get("content") or "").strip()
        if len(content) < _FLUSH_MIN_LEN or classify_extracted_item(it) == "plan":
            continue
        if any(_word_overlap_score(content, s) >= 0.65 for s in seen):
            if origin == "queue":
                written_q_indices.append(qidx)  # 已被本批其他項涵蓋 → 視為已捕捉、可清
            continue
        status = _flush_item_to_atom(
            content, it.get("domain_tags", []),
            scope=flush_scope, project_cwd=flush_pcwd, dedup_dir=dedup_dir)
        if status in ("wrote", "deduped"):
            seen.append(content)
            if status == "wrote":
                n_written += 1
            if origin == "queue":
                written_q_indices.append(qidx)
        # failed → 不清，留 queue 下次重試

    if written_q_indices and session_id:
        ack_then_clear(WORKFLOW_DIR / f"state-{session_id}.json",
                       "knowledge_queue", written_q_indices)

    _atom_debug_log(
        "session_end_writeback",
        f"flushed {n_written} atoms → {flush_scope}, cleared {len(written_q_indices)} queue items",
        config,
    )


# ─── Failure writeback ────────────────────────────────────────────────────────

_FAILURE_TYPE_FILE = {
    "env": "env-traps.md",
    "assumption": "wrong-assumptions.md",
    "silent": "silent-failures.md",
    "cognitive": "cognitive-patterns.md",
}

_FAILURE_TITLES = {
    "env": "環境踩坑（Environment Traps）",
    "assumption": "假設錯誤（Wrong Assumptions）",
    "silent": "靜默失敗（Silent Failures）",
    "cognitive": "認知模式偏差（Cognitive Patterns）",
}

# ── 失敗深記：多區塊骨架 ──────────────────────────────────────────────
#
# 舊版失敗只寫一行「- [臨] {content}」——根因/設計脈絡全丟。改成五區塊骨架：
# 始末/根因/設計原理/運作邏輯/防再犯。腳本（小模型）一律自動寫能填的部分（始末＝
# LLM 敘事、根因＝從「（根因: …）」拆出），其餘空段留「待補」標記給 Claude 在
# 高 effort 時用 atom_write 深寫補完（見 handlers/stop.py Deep Post-Mortem Gate）。

_FAILURE_SKELETON_SECTIONS = ("始末", "根因", "設計原理", "運作邏輯", "防再犯")
_FAILURE_TODO_MARK = "_(待補：深寫時由 Claude 補完)_"
_ROOT_CAUSE_RE = re.compile(r"[（(]\s*根因\s*[:：]\s*(.+?)\s*[）)]\s*$")


def _split_root_cause(content: str) -> tuple:
    """從 LLM content「{敘事}…（根因: X）」尾端拆出根因。無「（根因: …）」則
    回 (原文, "")。Returns (narrative, root_cause)。"""
    content = (content or "").strip()
    m = _ROOT_CAUSE_RE.search(content)
    if m:
        narrative = content[:m.start()].strip()
        return (narrative or content), m.group(1).strip()
    return content, ""


def _build_failure_skeleton(content: str, tags: list, now: str) -> str:
    """組多區塊失敗骨架。始末填 LLM 敘事；能拆出根因就填，其餘留待補。"""
    narrative, root = _split_root_cause(content)
    tag_str = "  " + " ".join(f"#{t}" for t in tags) if tags else ""
    # 標題取觸發場景（→ 前段）首 40 字，純供人眼掃讀
    title = (narrative.split("→")[0].strip() or narrative)[:40]
    return "\n".join([
        f"### [臨] {title}{tag_str}  ({now})",
        "",
        f"- **始末**：{narrative}",
        f"- **根因**：{root or _FAILURE_TODO_MARK}",
        f"- **設計原理**：{_FAILURE_TODO_MARK}",
        f"- **運作邏輯**：{_FAILURE_TODO_MARK}",
        f"- **防再犯**：{_FAILURE_TODO_MARK}",
    ])


def _failure_dedup_hit(existing_text: str, content: str) -> bool:
    """與既有失敗檔比對是否已記過同一條（新骨架的始末行 + 舊單行格式皆涵蓋）。"""
    for line in existing_text.split("\n"):
        ls = line.strip()
        if "**始末**" in ls:
            cmp_line = ls.split("：", 1)[-1] if "：" in ls else ls
        elif ls.startswith("- ["):  # 舊版 - [臨] 單行格式 backward-compat
            cmp_line = ls
        else:
            continue
        if _word_overlap_score(content, cmp_line) >= 0.65:
            return True
    return False


def _failure_writeback(ctx: dict, items: list) -> None:
    """將萃取的失敗記錄寫入對應 failure atom 檔。"""
    cwd = ctx.get("cwd", "")
    config = ctx.get("config", {})

    # 路由：有專案 memory dir → 專案層；否則 → 全域層
    failures_dir = resolve_failures_dir(cwd)

    written = 0
    for item in items:
        ftype = item.get("failure_type", "assumption")
        if ftype not in _FAILURE_TYPE_FILE:
            ftype = "assumption"

        target = failures_dir / _FAILURE_TYPE_FILE[ftype]
        content = item.get("content", "").strip()
        tags = item.get("domain_tags", [])
        if not content or len(content) < 10:
            continue

        # Dedup：與目標檔案既有條目比對（新骨架始末行 + 舊單行格式）
        if target.exists() and _failure_dedup_hit(
            target.read_text(encoding="utf-8-sig"), content
        ):
            continue

        # 組多區塊骨架（始末/根因/設計原理/運作邏輯/防再犯）
        now = datetime.now().strftime("%Y-%m-%d")
        entry_block = _build_failure_skeleton(content, tags, now)

        # 走 atom_io.write_raw funnel（保留原 marker fallback 行為，
        # 但統一經過 audit log + PreToolUse 強制門禁放行）
        if target.exists():
            text = target.read_text(encoding="utf-8-sig")
            inserted = False
            for marker in ("## 行動", "## 演化日誌"):
                idx = text.find(marker)
                if idx > 0:
                    text = text[:idx] + entry_block + "\n\n" + text[idx:]
                    inserted = True
                    break
            if not inserted:
                text += "\n" + entry_block + "\n"
            res = write_raw(target, text, source="hook:extract-worker", op="failure_append")
            if not res.ok:
                _atom_debug_log("failure_writeback", f"funnel reject: {res.error}", config)
                continue
        else:
            _create_failure_atom(target, ftype, entry_block)
        written += 1

    if written:
        _atom_debug_log(
            "failure_writeback",
            f"Wrote {written} failure entries to {failures_dir}",
            config,
        )


def _create_failure_atom(path: Path, ftype: str, first_block: str) -> None:
    """建立最小 failure atom 檔（專案層首次寫入用）。first_block 為多區塊骨架。

    走 atom_io.write_raw funnel（failures 子族不符 V4 build_atom_content
    規範 — 用 Type/Created 而非 Trigger/Last-used，故走 raw escape hatch）。
    """
    content = (
        f"# {_FAILURE_TITLES.get(ftype, ftype)}\n\n"
        f"- Scope: project\n"
        f"- Confidence: [臨]\n"
        f"- Type: procedural\n"
        f"- Created: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"## 知識\n\n{first_block}\n\n"
        f"## 行動\n\n- 同全域 failures 共通行動規則\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    write_raw(path, content, source="hook:extract-worker", op="failure_create")


# ─── Entry point ──────────────────────────────────────────────────────────────


def main():
    try:
        # New interface: read JSON from stdin
        raw_input = sys.stdin.read()
        ctx = json.loads(raw_input)
        result = run_extraction(ctx)

        # atom-debug: log extraction results (human-readable)
        _cfg = ctx.get("config", {})
        mode = ctx.get("mode", "session_end")
        items = result.get("extracted_items", [])
        tag = f"萃取:{mode}"

        # Build human-readable summary
        _KT_LABEL = {"factual": "事實", "procedural": "程序", "architectural": "架構",
                      "pitfall": "踩坑", "decision": "決策", "observation": "觀察"}
        if items:
            dest_label = {"per_turn": "→ knowledge_queue", "session_end": "→ knowledge_queue",
                          "failure": "→ failure atom 檔"}
            dest = dest_label.get(mode, "→ ?")
            summary_lines = [f"{len(items)} 筆萃取 {dest}"]
            for i, it in enumerate(items, 1):
                cls = it.get("classification", "?")
                kt = _KT_LABEL.get(it.get("knowledge_type", ""), it.get("knowledge_type", "?"))
                content = it.get("content", "")[:80]
                summary_lines.append(f"  {i}. {cls}{kt}: {content}")
            body = "\n".join(summary_lines)
        else:
            body = None
        _atom_debug_log(tag, body, _cfg)

        # Mode-specific writeback
        if mode == "failure":
            items = result.get("extracted_items", [])
            if items:
                _failure_writeback(ctx, items)
        elif mode == "per_turn":
            _per_turn_writeback(ctx, result)
        else:  # session_end (default) — flush queue + fresh extraction → [臨] atoms
            _session_end_writeback(ctx, result)

        sys.stdout.write(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(f"[extract-worker] error: {e}", file=sys.stderr)
        _atom_debug_error("萃取:extract-worker:main", e)
        sys.stdout.write(json.dumps(_empty_result()))


def _legacy_main():
    """Backward-compatible CLI args mode (for pre-S3A guardian)."""
    session_id = sys.argv[1]
    cwd = sys.argv[2]
    config = json.loads(sys.argv[3])

    # Read state to get knowledge_queue
    state_path = WORKFLOW_DIR / f"state-{session_id}.json"
    state = {}
    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    ctx = {
        "session_id": session_id,
        "cwd": cwd,
        "config": config,
        "knowledge_queue": state.get("knowledge_queue", []),
        "session_intent": "build",  # legacy mode defaults to build
    }
    result = run_extraction(ctx)

    # Legacy mode: write results back to state file (same as old behavior)
    if result.get("extracted_items"):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        state["pending_extraction"] = result["extracted_items"]
        state["last_updated"] = _now_iso()
        tmp = state_path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            tmp.replace(state_path)
        except OSError:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass


if __name__ == "__main__":
    try:
        if len(sys.argv) >= 4:
            _legacy_main()
        else:
            main()
    except Exception as e:
        _atom_debug_error("extract_worker:entry", e)
        pass  # Silent failure — never block Claude Code

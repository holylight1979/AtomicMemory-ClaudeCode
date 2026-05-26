"""
handlers/post_tool_use.py — PostToolUse hook handler

追蹤 modified_files / accessed_files / vcs_queries；
偵測測試失敗、_CHANGELOG 自動 roll、staging 命名、路徑強制、docdrift、hot cache mid-turn 注入。
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from wg_core import (
    _ensure_state, _now_iso, write_state, output_json, output_nothing,
)
from wg_episodic import _check_output_quality
from wg_extraction import _is_lease_valid  # noqa: F401
from wg_evasion import is_test_command, detect_test_failure
from wg_atoms import _trigger_incremental_index
from wg_extraction import is_plan_filename
from handlers._shared import (
    _is_ephemeral_path,
    WISDOM_AVAILABLE, wisdom_track_retry,
    DOCDRIFT_AVAILABLE, check_source_drift, resolve_doc_update, prune_committed_entries,
    read_hot_cache, mark_injected, format_injection_line,
)


_CHANGELOG_TABLE_DATA_RE = re.compile(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|")


def _maybe_auto_roll_changelog(file_path: str, config: Dict[str, Any]) -> None:
    """Detached roll when _CHANGELOG.md rows exceed threshold. Fail-open."""
    try:
        normalized = file_path.replace("\\", "/")
        if not normalized.endswith("/_CHANGELOG.md") and not normalized.endswith("_CHANGELOG.md"):
            return
        if normalized.endswith("_CHANGELOG_ARCHIVE.md"):
            return
        cfg = (config or {}).get("changelog_auto_roll", {}) or {}
        if not cfg.get("enabled", True):
            return
        threshold = int(cfg.get("threshold", 8))
        cl_path = Path(file_path)
        if not cl_path.exists():
            return
        rows = 0
        for line in cl_path.read_text(encoding="utf-8").splitlines():
            if _CHANGELOG_TABLE_DATA_RE.match(line):
                rows += 1
        if rows <= threshold:
            return
        tool_path = Path(__file__).resolve().parent.parent.parent / "tools" / "changelog-roll.py"
        if not tool_path.exists():
            return
        bg_kwargs: dict = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            bg_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            bg_kwargs["start_new_session"] = True
        subprocess.Popen(
            [sys.executable, str(tool_path),
             "--changelog", str(cl_path),
             f"--keep={threshold}", "--quiet"],
            **bg_kwargs,
        )
    except Exception:
        pass


def handle_post_tool_use(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    state = _ensure_state(session_id, input_data, config)
    if not state:
        output_nothing()
        return

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if tool_name in ("Edit", "Write") and file_path:
        _maybe_auto_roll_changelog(file_path, config)

    if (
        tool_name in ("Edit", "Write")
        and file_path
        and not _is_ephemeral_path(file_path)
    ):
        state.setdefault("modified_files", []).append({
            "path": file_path,
            "tool": tool_name,
            "at": _now_iso(),
        })
        state["sync_pending"] = True

        edit_counts = state.setdefault("edit_counts", {})
        edit_counts[file_path] = edit_counts.get(file_path, 0) + 1

        if WISDOM_AVAILABLE:
            try:
                wisdom_track_retry(state, file_path)
            except Exception as e:
                print(f"[v2.8] Wisdom retry track error: {e}", file=sys.stderr)

        try:
            qf = _check_output_quality(file_path, session_id, config)
            if qf:
                state.setdefault("quality_feedback", {}).setdefault(
                    "rewritten_files", []
                ).append(qf)
                print(
                    f"[v2.7] Quality feedback: {file_path} was also modified "
                    f"in session {qf['original_session']}",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"[v2.7] Quality check error: {e}", file=sys.stderr)

        write_state(session_id, state)

        normalized = file_path.replace("\\", "/")
        if "/memory/" in normalized and normalized.endswith(".md"):
            _trigger_incremental_index(config)

        if "/_staging/" in normalized and normalized.endswith(".md"):
            staging_fname = normalized.rsplit("/", 1)[-1]
            if staging_fname != "next-phase.md":
                state["_staging_advisory"] = (
                    f"⚠ `_staging/{staging_fname}` 非標準檔名。"
                    f"/continue 優先讀 `next-phase.md`。"
                    f"建議重新命名：mv → next-phase.md"
                )
                print(
                    f"[v2.16] Staging name gate: {staging_fname}", file=sys.stderr
                )

        _claude_projects_pat = "/.claude/projects/"
        if _claude_projects_pat in normalized and "/memory/" in normalized:
            _proj_root = state.get("atom_index", {}).get("project_root", "")
            if _proj_root:
                _rel_part = normalized.split("/memory/", 1)[-1]
                _exempt = (
                    _rel_part == "MEMORY.md"
                    or _rel_part.startswith("episodic/")
                    or _rel_part == "access.json"
                )
                if not _exempt:
                    _proj_root_norm = _proj_root.replace("\\", "/")
                    _correct_base = f"{_proj_root_norm}/.claude/memory/"
                    state["_path_enforcement_advisory"] = (
                        f"🚫 **路徑錯誤** — 寫入了舊個人層路徑 `~/.claude/projects/*/memory/`。\n"
                        f"V2.21 規則：專案記憶必須寫到 `{_correct_base}`。\n"
                        f"正確路徑：`{_correct_base}{_rel_part}`\n"
                        f"請立即搬移檔案並刪除錯誤路徑的副本。"
                    )
                    print(
                        f"[v2.22] Path enforcement BLOCKED: {normalized} → should be {_correct_base}{_rel_part}",
                        file=sys.stderr,
                    )

        if "/_AIDocs/" in normalized or "/_aidocs/" in normalized.lower():
            fname = normalized.rsplit("/", 1)[-1]
            if is_plan_filename(fname):
                state["_aidocs_advisory"] = (
                    f"⚠ {fname} 看起來是暫時性文件，"
                    f"建議放 memory/_staging/ 而非 _AIDocs/。"
                    f"判斷基準：實作完成後是否仍有長期參考價值？"
                )
                print(f"[v2.15] AIDocs gate triggered: {fname}", file=sys.stderr)

        if DOCDRIFT_AVAILABLE and config.get("docdrift", {}).get("enabled", True):
            try:
                if "/_aidocs/" in normalized.lower():
                    resolve_doc_update(file_path, state, config)
                else:
                    check_source_drift(file_path, state, config)
                write_state(session_id, state)
            except Exception as e:
                print(f"[v3.3] DocDrift error: {e}", file=sys.stderr)

    elif tool_name == "Read" and file_path:
        accessed = state.setdefault("accessed_files", [])
        if not any(a["path"] == file_path for a in accessed):
            accessed.append({"path": file_path, "at": _now_iso()})
            write_state(session_id, state)

    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        if re.search(r"\b(git\s+(log|blame|show|diff)|svn\s+(log|blame|diff))\b", command):
            vcs = state.setdefault("vcs_queries", [])
            vcs.append({"command": command[:200], "at": _now_iso()})
            write_state(session_id, state)

        if is_test_command(command):
            tr = input_data.get("tool_response", {}) or {}
            if isinstance(tr, dict):
                stdout = tr.get("stdout", "") or ""
                stderr = tr.get("stderr", "") or ""
                interrupted = bool(tr.get("interrupted", False))
            else:
                stdout, stderr, interrupted = str(tr), "", False
            failure = detect_test_failure(stdout, stderr, interrupted)
            if failure:
                ft = state.setdefault("failing_tests", [])
                ft.append({
                    "tool": "Bash",
                    "cmd": command[:200],
                    "summary": failure,
                    "at": _now_iso(),
                })
                write_state(session_id, state)
            elif state.get("failing_tests"):
                cmd_prefix = command[:80].strip()
                cmd_lower = command.lower()
                is_pytest_success = "pytest" in cmd_lower
                before = state["failing_tests"]
                after = [
                    f for f in before
                    if not f.get("cmd", "").startswith(cmd_prefix[:40])
                    and not (is_pytest_success and "pytest" in f.get("cmd", "").lower())
                ]
                if len(after) != len(before):
                    state["failing_tests"] = after
                    write_state(session_id, state)

    if DOCDRIFT_AVAILABLE and config.get("docdrift", {}).get("enabled", True):
        try:
            if prune_committed_entries(state, config) > 0:
                write_state(session_id, state)
        except Exception:
            pass

    advisories = []
    if state:
        for key, prefix in [
            ("_path_enforcement_advisory", "[Guardian:PathEnforce]"),
            ("_aidocs_advisory", "[Guardian:AIDocs]"),
            ("_staging_advisory", "[Guardian:StagingName]"),
            ("_docdrift_advisory", "[Guardian:DocDrift]"),
        ]:
            val = state.get(key)
            if val:
                advisories.append(f"{prefix} {val}")
                del state[key]

    if read_hot_cache:
        try:
            hot_data = read_hot_cache(session_id)
            if hot_data:
                advisories.append(format_injection_line(hot_data, context="mid-turn"))
                mark_injected(session_id)
        except Exception:
            pass

    if advisories:
        write_state(session_id, state)
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "\n".join(advisories),
            }
        })
    else:
        output_nothing()

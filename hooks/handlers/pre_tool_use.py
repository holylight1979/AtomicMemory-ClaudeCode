"""
handlers/pre_tool_use.py — PreToolUse hook handler

對 Write/Edit 進行 atom 格式/Confidence gate + memory 路徑防呆 + svn test block。
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from wg_core import (
    output_json, output_nothing,
    check_memory_path_block, check_svn_test_block,
    check_cross_realm_write,
    _atom_debug_log,
)
from wg_atoms import build_injection_blob

# Phase 1: sub-agent 注入 budget（緊湊，守 token 紅線；2-3 顆最高活化）
_SUBAGENT_INJECT_BUDGET = 700


_CONFIDENCE_FRONTMATTER_RE = re.compile(r"^- Confidence:\s*(\[[臨觀固]\])", re.MULTILINE)
_SOLID_INLINE_RE = re.compile(r"^- \[固\]", re.MULTILINE)
_OBSERVED_INLINE_RE = re.compile(r"^- \[觀\]", re.MULTILINE)


def _scan_atom_confidence(content: str) -> Dict[str, Any]:
    """Parse confidence signals from atom content."""
    fm = _CONFIDENCE_FRONTMATTER_RE.search(content)
    return {
        "frontmatter": fm.group(1) if fm else None,
        "solid_inline": bool(_SOLID_INLINE_RE.search(content)),
        "observed_inline": bool(_OBSERVED_INLINE_RE.search(content)),
    }


def _check_memory_atom_format(
    tool_name: str, tool_input: Dict[str, Any]
) -> Optional[str]:
    """Memory write must follow atom format AND new atoms must start at [臨]."""
    if tool_name != "Write":
        return None
    file_path_raw = tool_input.get("file_path", "")
    file_path = file_path_raw.replace("\\", "/")
    if "/.claude/memory/" not in file_path or not file_path.endswith(".md"):
        return None
    if "/_staging/" in file_path:
        return None
    if "/_pending_review/" in file_path:
        return None
    fname = file_path.rsplit("/", 1)[-1]
    if fname.startswith("_") or fname == "MEMORY.md" or fname.startswith("episodic-"):
        return None
    if fname == "role.md" and ("/personal/" in file_path or "/roles/" in file_path):
        return None
    full_content = tool_input.get("content", "")
    content_head = full_content[:300]
    required = [
        "- Scope:", "- Confidence:", "- Trigger:",
        "- Last-used:", "- Confirmations:", "- ReadHits:",
    ]
    hits = sum(1 for r in required if r in content_head)
    if hits < 3:
        return (
            f"[Guardian:AtomFormat] 偵測到寫入 {file_path}\n"
            f"但內容不符合原子格式（缺少 Scope/Confidence/Trigger 等 frontmatter，僅 {hits}/5 命中）。\n"
            "請改用 atom_write MCP（自動產生標準 frontmatter + 索引登記 + 去重檢查）：\n"
            "  mcp__workflow-guardian__atom_write(scope=\"shared\", project_cwd=\"...\", ...)\n"
            "如為臨時暫存，請寫入 _staging/ 子目錄（自由格式允許）。\n"
            "如為索引/變更日誌，請以 _ 開頭命名（如 _NOTES.md）。"
        )

    try:
        is_new = not Path(file_path_raw).exists()
    except OSError:
        is_new = True
    if is_new:
        sig = _scan_atom_confidence(full_content)
        fm = sig["frontmatter"]
        if fm and fm != "[臨]":
            return (
                f"[Guardian:AtomConfidence] 新 atom {fname} frontmatter Confidence={fm}，"
                "違反語意契約：新 atom 必須以 [臨] 起始（[觀]/[固] 反映跨 session 穩定度，"
                "首寫無法主張）。\n"
                "請改用 atom_write MCP（mode=create，confidence='[臨]'）。"
            )
        if sig["solid_inline"] or sig["observed_inline"]:
            tags = []
            if sig["solid_inline"]:
                tags.append("[固]")
            if sig["observed_inline"]:
                tags.append("[觀]")
            return (
                f"[Guardian:AtomConfidence] 新 atom {fname} 內文含 {'/'.join(tags)} "
                "標籤，違反語意契約：新 atom 的知識行也必須以 [臨] 起始，待跨 session 確認後再晉升。\n"
                "請改用 atom_write MCP（mode=create，knowledge 各行 prefix 為 '[臨]'）。"
            )
    return None


def _check_feedback_routing_advisory(
    tool_name: str, tool_input: Dict[str, Any]
) -> Optional[str]:
    """V5+: 偵測 memory/feedback-*.md Write/Edit → 回 advisory（不阻擋）。

    feedback-* atoms 已遷移至 _AIDocs/Failures/；走 atom_write MCP 會自動正確路由。
    """
    if tool_name not in ("Write", "Edit"):
        return None
    fp_raw = tool_input.get("file_path", "") or ""
    fp = fp_raw.replace("\\", "/")
    if "/.claude/memory/" not in fp or not fp.endswith(".md"):
        return None
    fname = fp.rsplit("/", 1)[-1]
    if not fname.startswith("feedback-"):
        return None
    return (
        "[Guardian:RoutingAdvice] 偵測 memory/feedback-* 寫入。\n"
        f"路徑：{fp_raw}\n"
        "feedback-* atoms 已遷移至 _AIDocs/Failures/。請改用：\n"
        "  mcp__workflow-guardian__atom_write(scope=\"global\", title=\"feedback-...\", ...)\n"
        "MCP 會自動路由到 _AIDocs/Failures/（含索引同步 + access.json）。\n"
        "詳見 _AIDocs/SPEC_ATOM_V5.md「Atom 存放擴展」段。"
    )


def handle_pre_tool_use(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # ─── Phase 1 (#1): Sub-agent 記憶注入 ────────────────────────────────────
    # sub-agent（Agent/Task）開全新 context、不觸發 UserPromptSubmit，吃不到 atom。
    # 唯一 parent→child 通道是工具 prompt 字串 → 經 PreToolUse updatedInput prepend
    # 緊湊記憶 blob。fail-open：任何錯誤都不擋 spawn。
    if tool_name in ("Agent", "Task"):
        try:
            orig_prompt = tool_input.get("prompt", "") or ""
            blob, injected = build_injection_blob(
                orig_prompt, budget=_SUBAGENT_INJECT_BUDGET,
            )
            if blob and injected:
                new_input = dict(tool_input)
                new_input["prompt"] = f"{blob}\n\n{orig_prompt}"
                _atom_debug_log(
                    "SubagentInject",
                    f"tool={tool_name} injected={injected} "
                    f"blob_tokens=~{len(blob) // 4} prompt_head={orig_prompt[:60]!r}",
                    config,
                )
                output_json({
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "updatedInput": new_input,
                    }
                })
                return
        except Exception as e:
            try:
                sys.stderr.write(f"[phase1] sub-agent inject error: {e}\n")
            except OSError:
                pass
        output_nothing()
        return

    # Advisory：feedback-* 寫入舊位址提示（不擋）
    advisory = _check_feedback_routing_advisory(tool_name, tool_input)
    if advisory:
        try:
            sys.stderr.write(advisory + "\n")
        except OSError:
            pass

    deny_reason = _check_memory_atom_format(tool_name, tool_input)
    if deny_reason:
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            }
        })
        return

    deny_reason = check_memory_path_block(tool_name, tool_input)
    if deny_reason:
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            }
        })
        return

    # Phase 3b（方案甲 2026-06-12）：外部專案 session 寫核心層 → deny
    deny_reason = check_cross_realm_write(
        tool_name, tool_input, input_data.get("cwd", "") or "", config,
    )
    if deny_reason:
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            }
        })
        return

    deny_reason = check_svn_test_block(tool_name, tool_input)
    if deny_reason:
        output_json({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            }
        })
        return

    output_nothing()

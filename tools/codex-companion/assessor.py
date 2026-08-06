"""assessor.py — Codex assessment runner.

Builds review prompts from accumulated events, invokes `codex exec`,
parses structured JSON output.

Sandbox: 不傳 -s 旗標，沿用 ~/.codex/config.toml 預設（通常 danger-full-access）。
Windows 上 -s read-only 會踩 CreateProcessWithLogonW 1385 spawn 失敗導致 stdout 為空。
寫入限制改靠 prompts.py 模板開頭的紅線約束。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

SERVICE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVICE_DIR))

import artifact_io
import prompts

# artifact 採樣預算：主審對象（plan_review 的計畫檔）給大預算；
# handoff 維持既有預算。原則見 artifact_io module docstring。
PLAN_SAMPLE_HEAD = 8000
PLAN_SAMPLE_TAIL = 2000
HANDOFF_SAMPLE_HEAD = 4500
HANDOFF_SAMPLE_TAIL = 1500

# 最終 prompt 軟預算：超額時以縮減 trace 重組一次（單次，不迭代；
# artifact 採樣段與 last_assistant_tail 永不砍）。
DEFAULT_MAX_PROMPT_CHARS = 16000
BUDGET_TRACE_MAX_ITEMS = 8
# acceptance_review 案卷總量（config acceptance_review.max_prompt_chars 同步）
ACCEPTANCE_MAX_PROMPT_CHARS = 22000

# Windows: detached 父進程（codex_companion hook spawn audit.py 帶 DETACHED_PROCESS）
# 沒 console 時呼叫 codex.cmd batch wrapper → Windows 會新開 cmd.exe 視窗。
# CREATE_NO_WINDOW (0x08000000) 防此踩坑。POSIX 不需要。
_CODEX_FLAGS = 0x08000000 if sys.platform == "win32" else 0


def _log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[assessor {ts}] {msg}", file=sys.stderr, flush=True)


def _summarize_tool_trace(
    trace: List[Dict[str, Any]],
    max_items: int = 30,
    dropped_earlier: int = 0,
    budget_reduced: bool = False,
) -> str:
    """Format tool trace into a compact string for prompt injection.

    集合截斷附計數標頭（showing last N of M）：codex 需要知道自己看的是
    節錄，否則會把「trace 裡沒有」誤判成「agent 沒做過」。
    dropped_earlier = state 端 trace 腰斬已丟棄的筆數。
    """
    if not trace:
        return "(empty)"

    recent = trace[-max_items:]
    total = len(trace) + max(0, int(dropped_earlier))
    lines = []
    if len(recent) < total:
        header = f"(showing last {len(recent)} of {total} tool events; earlier events not shown"
        if budget_reduced:
            header += "; 因 prompt 總量預算，trace 已縮減"
        lines.append(header + ")")
    for i, t in enumerate(recent, 1):
        tool = t.get("tool", t.get("type", "?"))
        inp = t.get("input", "")
        out = t.get("output_summary", "")
        path = t.get("path", "")

        # Truncate long fields
        if len(inp) > 200:
            inp = inp[:200] + "..."
        if len(out) > 150:
            out = out[:150] + "..."

        parts = [f"{i}. [{tool}]"]
        if path:
            parts.append(path)
        if inp:
            parts.append(f"input: {inp}")
        if out:
            parts.append(f"→ {out}")
        lines.append(" ".join(parts))

    return "\n".join(lines)


def _summarize_modified_files(trace: List[Dict[str, Any]]) -> str:
    """Extract unique modified file paths from trace."""
    paths = set()
    for t in trace:
        if t.get("tool") in ("Edit", "Write") and t.get("path"):
            paths.add(t["path"])
    if not paths:
        return "(none)"
    return "\n".join(f"- {p}" for p in sorted(paths))


def _extract_arch_files(trace: List[Dict[str, Any]]) -> str:
    """Extract structural files from trace.

    共用 heuristics._ARCH_FILE_RE 避免 service / assessor / heuristics
    三處 regex drift。
    """
    import heuristics as _heur
    paths = set()
    for t in trace:
        p = t.get("path", "")
        if p and _heur._ARCH_FILE_RE.search(p):
            paths.add(p)
    if not paths:
        return "(none)"
    return "\n".join(f"- {p}" for p in sorted(paths))


def _summarize_files_examined(
    tool_trace: List[Dict[str, Any]], max_items: int = 30, max_chars: int = 1500
) -> str:
    """從 tool_trace 萃取「代理人已接觸的檔案」摘要供 codex prompt 用。

    實際供給受 hook 監測範圍限制：PostToolUse matcher 只送 Edit/Write/Bash/
    plan/handoff 觸發事件進 trace，Read/Glob/Grep/Agent 不在其中——分支保留
    （data-driven，監測範圍放寬即自動生效），模板端已明示此限制避免
    「agent 未讀檔」誤報。Cap max_items 條 / max_chars 字。
    """
    if not tool_trace:
        return "(none)"

    read_tools = {"Read", "Glob", "Grep"}
    write_tools = {"Edit", "Write", "NotebookEdit"}

    lines: List[str] = []
    seen_paths: set = set()

    for t in tool_trace:
        tool = t.get("tool", "")
        path = (t.get("path") or "").strip()
        inp = (t.get("input") or "").strip()
        out = (t.get("output_summary") or "").strip()

        if tool in read_tools:
            label = path or inp
            if label and label not in seen_paths:
                lines.append(f"- [{tool}] {label[:160]}")
                seen_paths.add(label)
        elif tool in write_tools:
            if path and path not in seen_paths:
                lines.append(f"- [{tool}] {path[:160]}")
                seen_paths.add(path)
        elif tool == "Agent":
            desc = inp[:120] if inp else "(no desc)"
            out_snip = out[:240] if out else ""
            entry = f"- [Agent] {desc}"
            if out_snip:
                entry += f"\n    → result: {out_snip}"
            lines.append(entry)

        if len(lines) >= max_items:
            break

    if not lines:
        return "(none)"

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n…(truncated)"
    return text


def _extract_verification_evidence(trace: List[Dict[str, Any]]) -> str:
    """從 tool_trace 抽 verify cmd 事證給 codex prompt。

    撈取 Bash + 命中 heuristics._VERIFY_CMD_RE 的 input 行。
    若出現過 `[FAILED] ` prefix（hook 端 failure 偵測），保留以提示 codex。
    """
    try:
        import heuristics
        verify_re = heuristics._VERIFY_CMD_RE
    except Exception:
        return "(none found)"

    hits: List[str] = []
    for i, t in enumerate(trace, 1):
        if t.get("tool") != "Bash":
            continue
        cmd = t.get("input", "") or ""
        if not verify_re.search(cmd):
            continue
        out = t.get("output_summary", "") or ""
        outcome = "FAILED" if out.startswith("[FAILED]") else "ok"
        hits.append(f"#{i} [{outcome}] {cmd[:120]}")

    if not hits:
        return "(none found)"
    return "\n".join(hits[-5:])  # 最近 5 條足夠


def _run_codex(prompt_text: str, cwd: str, config: Dict[str, Any]) -> tuple[str, str]:
    """Run `codex exec` and return (stdout_text, stderr_text).

    stderr 回傳給上層做 sandbox 失敗識別。
    無論成功失敗都把 stderr（含 timeout/spawn 錯誤的合成訊息）一併送出。
    """
    codex_bin = config.get("codex_binary", "codex")
    model = config.get("model", "")
    timeout = config.get("assessment_timeout", 60)

    # Write prompt to temp file to avoid shell escaping issues
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(prompt_text)
        prompt_file = f.name

    # Write output to temp file
    output_file = prompt_file + ".out"

    try:
        cmd = [codex_bin, "exec"]
        if model:
            cmd += ["-m", model]
        cmd += [
            "--ephemeral",
            "--ignore-rules",
            "--skip-git-repo-check",
            "-o", output_file,
        ]

        # Read prompt from stdin (via file)
        _log(f"Running: {' '.join(cmd[:6])}... (timeout={timeout}s)")

        with open(prompt_file, "r", encoding="utf-8") as pf:
            result = subprocess.run(
                cmd,
                stdin=pf,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd if cwd and os.path.isdir(cwd) else None,
                env={**os.environ, "NO_COLOR": "1"},
                creationflags=_CODEX_FLAGS,
            )

        _log(f"codex exec exit code: {result.returncode}")
        stderr_text = (result.stderr or "")

        # Prefer -o output file
        if os.path.exists(output_file):
            text = Path(output_file).read_text(encoding="utf-8").strip()
            if text:
                return text, stderr_text

        # Fallback to stdout
        return result.stdout.strip(), stderr_text

    except subprocess.TimeoutExpired:
        _log(f"codex exec timed out after {timeout}s")
        return "", f"[assessor] timeout after {timeout}s"
    except FileNotFoundError:
        _log(f"codex binary not found: {codex_bin}")
        return "", f"[assessor] codex binary not found: {codex_bin}"
    except Exception as e:
        _log(f"codex exec error: {e}")
        return "", f"[assessor] exception: {e}"
    finally:
        # Cleanup temp files
        for f in (prompt_file, output_file):
            try:
                os.unlink(f)
            except OSError:
                pass


_SANDBOX_FAILURE_RE = re.compile(r"CreateProcessWithLogon|sandbox", re.IGNORECASE)


def _run_codex_with_retry(
    prompt_text: str, cwd: str, config: Dict[str, Any]
) -> tuple[str, str, int]:
    """空字串/非 JSON → 退 300-500ms 重試 1 次。

    回傳 (stdout, stderr_combined, attempts)。
    第一次 stdout 不空且能 JSON 解析 → 直接返回 attempts=1。
    否則 sleep 0.4s 再跑一次，stderr 串接讓上層做 sandbox 識別。
    """
    stdout1, stderr1 = _run_codex(prompt_text, cwd, config)

    if stdout1 and _try_parse_json(stdout1) is not None:
        return stdout1, stderr1, 1

    _log("First codex call returned empty/non-JSON; retry once in 400ms")
    time.sleep(0.4)
    stdout2, stderr2 = _run_codex(prompt_text, cwd, config)

    final_stdout = stdout2 or stdout1
    combined_stderr = "\n".join(s for s in (stderr1, stderr2) if s)
    return final_stdout, combined_stderr, 2


def _classify_failure(stderr: str) -> Dict[str, Any]:
    """依 stderr 內容把 codex 失敗分類成 assessment。

    sandbox 命中（CreateProcessWithLogon|sandbox）→ system 高嚴重度，
      防 R2-5 級 bug 再被吞掉。
    其他失敗 → warning + delivery=inject + notify_next_turn=True，
      下一輪 drain 端會加注短訊提醒。
    """
    stderr_excerpt = (stderr or "")[-300:]
    if _SANDBOX_FAILURE_RE.search(stderr or ""):
        return _apply_defaults({
            "status": "error",
            "severity": "high",
            "category": "system",
            "summary": "Codex sandbox 失敗，請檢查 -s 設定",
            "evidence": stderr_excerpt,
            "delivery": "inject",
            "confidence": "high",
            "applies_until": "next_prompt",
            "notify_next_turn": True,
        })
    return _apply_defaults({
        "status": "warning",
        "severity": "low",
        "category": "system",
        "summary": "退回 heuristics-only",
        "evidence": stderr_excerpt,
        "delivery": "inject",
        "confidence": "low",
        "applies_until": "next_prompt",
        "notify_next_turn": True,
    })


def _apply_defaults(d: Dict[str, Any]) -> Dict[str, Any]:
    """補 schema v2 預設值；舊 codex 回 recommended_action 也吃。

    模組級 helper：給 _classify_failure / _try_parse_json 共用。
    """
    d.setdefault("status", "ok")
    d.setdefault("severity", "low")
    d.setdefault("category", "unknown")
    d.setdefault("summary", "")
    d.setdefault("evidence", "")
    # delivery 預設策略：嚴重度 medium 以上才 inject，否則 ignore（保守）
    if "delivery" not in d:
        sev = str(d.get("severity", "low")).lower()
        d["delivery"] = "inject" if sev in ("medium", "high") else "ignore"
    d.setdefault("confidence", "medium")
    d.setdefault("applies_until", "next_prompt")
    # turn_index 由 service 補 _turn_index，這裡先補 0 占位
    d.setdefault("turn_index", 0)
    # 舊欄位 recommended_action 視為 corrective_prompt 的別名
    if "corrective_prompt" not in d and d.get("recommended_action"):
        d["corrective_prompt"] = d["recommended_action"]
    d.setdefault("corrective_prompt", "")
    return d


def _try_parse_json(raw: str) -> Optional[Dict[str, Any]]:
    """嘗試從 codex stdout 抽出 JSON dict。失敗回 None（讓 retry 路徑判斷）。

    抽 module-level 給 _run_codex_with_retry 用。
    """
    if not raw:
        return None
    text = raw.strip()

    # Remove markdown fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        start = 0
        end = len(lines)
        for i, line in enumerate(lines):
            if line.strip().startswith("```") and i == 0:
                start = i + 1
                continue
            if line.strip() == "```" and i > 0:
                end = i
                break
        text = "\n".join(lines[start:end]).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return _apply_defaults(parsed)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            # acceptance_review 回的是 verdict schema（無 status 欄）
            if isinstance(parsed, dict) and ("status" in parsed or "verdict" in parsed):
                return _apply_defaults(parsed)
        except json.JSONDecodeError:
            pass

    return None


def _parse_assessment(raw: str) -> Dict[str, Any]:
    """Parse Codex output into structured assessment dict.

    失敗分類由 _classify_failure 負責；本函式只負責成功路徑與
    legacy fallback（unknown 文字當 summary）。
    """
    parsed = _try_parse_json(raw)
    if parsed is not None:
        return parsed
    # Fallback: wrap raw text as summary
    return _apply_defaults({
        "status": "ok",
        "severity": "low",
        "category": "unknown",
        "summary": (raw or "")[:500],
        "delivery": "ignore",
        "confidence": "low",
    })


# ─── Public API ──────────────────────────────────────────────────────────────


def _resolve_artifact_body(
    extra_context: Dict[str, Any],
    head: int,
    tail: int,
    inline_key: str = "plan_inline",
    artifact_label: str = "artifact",
) -> str:
    """依統一原則取 artifact 正文：inline 全文優先，否則讀 artifact_path 實體。

    兩者皆不可得 → 回 in-band 說明（動作紀錄不得替代內容本體，
    codex 須知道自己沒有正文可依據，而非拿到冒充品）。
    """
    inline = (extra_context.get(inline_key) or "").strip()
    if inline:
        return artifact_io.sample_text(inline, head=head, tail=tail)

    artifact_path = (extra_context.get("artifact_path") or "").strip()
    if artifact_path:
        body = artifact_io.read_artifact_sampled(artifact_path, head=head, tail=tail)
        if body:
            return body
        return (
            f"({artifact_label} 讀取失敗：{artifact_path} — 本審計無正文可依據；"
            "請以 missing_evidence 回報此狀況，勿臆測內容)"
        )
    return (
        f"(未解析到{artifact_label} — 本審計無正文可依據；"
        "請以 missing_evidence 回報此狀況，勿把工具動作紀錄當作正文)"
    )


def build_prompt(
    assessment_type: str,
    tool_trace: List[Dict[str, Any]],
    cwd: str,
    extra_context: Dict[str, Any],
    trace_max_items: int = 30,
    budget_reduced: bool = False,
) -> str:
    """組出送 codex 的完整 prompt。純函式（不打 codex、不碰 state 檔），
    輸入完整性 verify 直接對此斷言。

    材料規則（唯一來源，caller 不各自組裝）：
    - artifact 正文（plan/handoff）經 _resolve_artifact_body 實體化
    - trace/files/verification 皆由 tool_trace 即時計算（避免 stale state）
    - extra_context 只收觸發事實：turn_index / last_assistant_tail / user_goal /
      artifact_path / plan_inline / trace_dropped
    """
    trace_dropped = int(extra_context.get("trace_dropped", 0) or 0)
    trace_str = _summarize_tool_trace(
        tool_trace, max_items=trace_max_items,
        dropped_earlier=trace_dropped, budget_reduced=budget_reduced,
    )

    turn_index = int(extra_context.get("turn_index", 0))
    user_goal = extra_context.get("user_goal", "") or ""
    last_assistant_tail = extra_context.get("last_assistant_tail", "") or ""
    if last_assistant_tail and len(last_assistant_tail) > 1500:
        last_assistant_tail = last_assistant_tail[:1500] + "…(截斷)"

    # Import heuristics for flag context
    flags_str = "None"
    heuristic_summary = "None"
    try:
        import heuristics
        # Build a pseudo guardian-compatible state for heuristics
        heur_state = {
            "tool_trace": tool_trace,
            "modified_files": [
                {"path": t.get("path", "")}
                for t in tool_trace
                if t.get("tool") in ("Edit", "Write") and t.get("path")
            ],
        }
        flags = heuristics.triggered_results(heur_state, stop_text=last_assistant_tail)
        if flags:
            heuristic_summary = heuristics.format_for_context(flags)
            flags_str = heuristic_summary
    except Exception:
        pass

    if assessment_type == "plan_review":
        return prompts.build_plan_review_prompt(
            user_goal=user_goal,
            plan_content=_resolve_artifact_body(
                extra_context, PLAN_SAMPLE_HEAD, PLAN_SAMPLE_TAIL,
                artifact_label="計畫 artifact",
            ),
            files_examined=_summarize_files_examined(tool_trace),
            heuristic_flags=flags_str,
            turn_index=turn_index,
        )
    if assessment_type == "acceptance_review":
        import acceptance
        spec_path = extra_context.get("spec_path", "") or ""
        _fm, spec_text = (
            acceptance.read_spec_with_done_fallback(spec_path)
            if spec_path else ({}, "")
        )
        diff_digest = extra_context.get("diff_digest", "") or ""
        return prompts.build_acceptance_review_prompt(
            user_goal=acceptance.sample_goal(user_goal),
            spec_path=spec_path,
            spec_content=acceptance.sample_spec(spec_text) if spec_text else "",
            diff_digest=diff_digest,
            verification_evidence=acceptance.collect_verification_evidence(tool_trace),
            tool_trace=trace_str,
            last_assistant_tail=last_assistant_tail,
            cwd=cwd,
            turn_index=turn_index,
        )
    if assessment_type == "architecture_review":
        return prompts.build_architecture_review_prompt(
            cwd=cwd,
            arch_files=_extract_arch_files(tool_trace),
            tool_trace=trace_str,
            turn_index=turn_index,
        )
    if assessment_type == "handoff_review":
        return prompts.build_handoff_review_prompt(
            handoff_content=_resolve_artifact_body(
                extra_context, HANDOFF_SAMPLE_HEAD, HANDOFF_SAMPLE_TAIL,
                inline_key="handoff_inline", artifact_label="handoff 文件",
            ),
            user_goal=user_goal,
            turn_index=turn_index,
        )
    # Default: turn_audit
    return prompts.build_turn_audit_prompt(
        cwd=cwd,
        tool_trace=trace_str,
        modified_files=_summarize_modified_files(tool_trace),
        heuristic_flags=flags_str,
        turn_index=turn_index,
        user_goal=user_goal,
        last_assistant_tail=last_assistant_tail,
        verification_evidence=_extract_verification_evidence(tool_trace),
        heuristic_summary=heuristic_summary,
        files_examined=_summarize_files_examined(tool_trace),
    )


def build_prompt_budgeted(
    assessment_type: str,
    tool_trace: List[Dict[str, Any]],
    cwd: str,
    extra_context: Dict[str, Any],
    config: Dict[str, Any],
) -> str:
    """總量軟預算：超額時以縮減 trace 重組一次（單次不迭代）。

    artifact 採樣段與 last_assistant_tail 自帶上限、永不砍；縮減有
    in-band 標記（budget_reduced → trace 計數標頭註明）。
    """
    prompt = build_prompt(assessment_type, tool_trace, cwd, extra_context)
    if assessment_type == "acceptance_review":
        # 案卷有專屬預算（含 diff/規格/測試輸出，與一般審計不同量級）
        max_chars = int(
            config.get("acceptance_review", {}).get("max_prompt_chars")
            or config.get("max_prompt_chars")
            or ACCEPTANCE_MAX_PROMPT_CHARS
        )
    else:
        max_chars = int(config.get("max_prompt_chars", DEFAULT_MAX_PROMPT_CHARS))
    if len(prompt) > max_chars:
        prompt = build_prompt(
            assessment_type, tool_trace, cwd, extra_context,
            trace_max_items=BUDGET_TRACE_MAX_ITEMS, budget_reduced=True,
        )
    return prompt


_VALID_VERDICTS = ("pass", "fail", "uncertain")


def map_acceptance_verdict(
    parsed: Dict[str, Any],
    binding: str = "bound",
    binding_reason: str = "",
) -> Dict[str, Any]:
    """把 acceptance verdict schema 映射成既有 assessment 欄位（沿用注入管道）。

    **紅線 INV-CASE-BINDING-OR-UNCERTAIN 的程式化執行點**：binding 不是
    `bound` 時，無論裁判回什麼，一律改寫成 uncertain 且 delivery=ignore；
    Phase 3 接 Stop 閘時也必須經過本函式，故不得 block 的保證在此落實。

    映射（影子期 delivery 僅決定 advisory 是否浮出，無 block 權）：
      pass      → status=ok,             delivery=ignore
      fail      → status=needs_followup, delivery=inject, category=completion_risk
      uncertain → status=warning,        delivery=ignore, category=missing_evidence
    """
    result = dict(parsed or {})
    verdict = str(result.get("verdict", "")).lower().strip()
    if verdict not in _VALID_VERDICTS:
        verdict = "uncertain"
        result.setdefault(
            "uncertain_reason", "裁判輸出缺少有效 verdict 欄位，依保守原則記為 uncertain"
        )

    if binding != "bound":
        verdict = "uncertain"
        result["uncertain_reason"] = binding_reason or result.get(
            "uncertain_reason", "任務與驗收規格檔無法唯一對應"
        )
        result["problems"] = []
        result["score"] = -1

    problems = result.get("problems")
    if not isinstance(problems, list):
        problems = []
    # 扣分必引證據：引不出 evidence 的 problem 不算數（本場 5 誤報的教訓）
    problems = [
        p for p in problems
        if isinstance(p, dict) and str(p.get("evidence", "")).strip()
    ]
    result["problems"] = problems
    if verdict == "fail" and not problems:
        # 判 fail 卻列不出帶證據的問題 → 降為 uncertain，不讓無證據的擋收尾
        verdict = "uncertain"
        result["uncertain_reason"] = result.get("uncertain_reason") or (
            "裁判判 fail 但未提出任何帶證據的具體問題，依「扣分必引證據」降為 uncertain"
        )

    result["verdict"] = verdict
    summary = str(result.get("summary", "")).strip()

    if verdict == "pass":
        result.update({
            "status": "ok", "severity": "low", "category": "completion_risk",
            "delivery": "ignore",
            "summary": summary or "驗收清單逐條均有對應證據",
            "corrective_prompt": "",
        })
    elif verdict == "fail":
        sev = str(result.get("severity", "medium")).lower()
        if sev not in ("low", "medium", "high"):
            sev = "medium"
        lines = [
            f"- {p.get('criterion', '(未指明條目)')}｜事證：{p.get('evidence', '')}"
            f"｜{p.get('explanation', '')}"
            for p in problems[:5]
        ]
        result.update({
            "status": "needs_followup", "severity": sev,
            "category": "completion_risk", "delivery": "inject",
            "summary": summary or f"驗收未過：{len(problems)} 項未達標",
            "evidence": "\n".join(lines)[:1200],
            "corrective_prompt": (
                "【影子裁判 advisory，不阻斷收尾】獨立裁判對照本任務驗收清單後認為"
                f"有 {len(problems)} 項未達標（見事證）。請自行判斷是否屬實：真的漏做就補，"
                "誤判請忽略——本輪不會擋你收尾。"
            ),
        })
    else:  # uncertain
        result.update({
            "status": "warning", "severity": "low",
            "category": "missing_evidence", "delivery": "ignore",
            "summary": summary or "案卷證據不足以判定驗收結果",
            "evidence": str(result.get("uncertain_reason", ""))[:600],
            "corrective_prompt": "",
            "score": -1,
        })

    result.setdefault("score", -1 if verdict == "uncertain" else 0)
    result.setdefault("confidence", "medium")
    result.setdefault("applies_until", "next_prompt")
    result.setdefault("turn_index", 0)
    result["_binding"] = binding
    return result


def run_assessment(
    assessment_type: str,
    session_id: str,
    tool_trace: List[Dict[str, Any]],
    cwd: str,
    extra_context: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Run a Codex assessment and return structured result.

    assessment_type: "plan_review" | "turn_audit" | "architecture_review"
                     | "handoff_review"
    prompt 材料組裝全在 build_prompt（規則唯一來源）；本函式只負責
    預算檢查 → 呼叫 codex → 解析。
    """
    turn_index = int(extra_context.get("turn_index", 0))
    prompt = build_prompt_budgeted(assessment_type, tool_trace, cwd, extra_context, config)

    _log(f"Prompt built for {assessment_type} (t{turn_index}): {len(prompt)} chars")

    # retry 1 次 + sandbox 失敗識別
    raw, stderr_combined, attempts = _run_codex_with_retry(prompt, cwd, config)
    parsed = _try_parse_json(raw) if raw else None

    if assessment_type == "acceptance_review":
        # 裁判失效（逾時/空回/非 JSON）→ uncertain 而非靜默通過
        # （INV-JUDGE-FAILURE-IS-DISCLOSE：揭露後放行，不假裝有審過）
        base = parsed if parsed is not None else {
            "verdict": "uncertain",
            "uncertain_reason": (
                "裁判未回傳有效判定（逾時或輸出無法解析）："
                + (stderr_combined or "")[-200:]
            ),
        }
        result = map_acceptance_verdict(
            base,
            binding=str(extra_context.get("binding", "bound")),
            binding_reason=str(extra_context.get("binding_reason", "")),
        )
        if parsed is None:
            result["notify_next_turn"] = True
    elif parsed is None:
        result = _classify_failure(stderr_combined)
    else:
        result = parsed

    # Tag with metadata
    result["_assessment_type"] = assessment_type
    result["_prompt_chars"] = len(prompt)
    result["_session_id"] = session_id
    result["_attempts"] = attempts

    return result

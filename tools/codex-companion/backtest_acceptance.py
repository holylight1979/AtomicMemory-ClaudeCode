"""backtest_acceptance.py — 影子驗收裁判回測 CLI（Q5 評估的模擬通道）。

用 git 歷史裡**真實完成過的任務**重建案卷回放，加上**構造已知真值**的
種缺陷變異，讓 Q5 門檻評估不必等數週真實影子數據：

  A 完好回放（期望 pass）  ：真規格檔/CHANGELOG 重建規格 + 該 commit 真 diff
  B 種缺陷  （期望 fail）  ：規格多一條沒做的項（漏做）/ 抽掉驗證證據但宣稱全綠
  C 截斷紀律（期望 ≠fail）：關鍵檔強制列入「未採樣清單」，裁判應守
                            「勿因未見內容判定沒做」回 uncertain

走真 codex 管道（assessor.run_assessment，不 mock）；結果落
workflow/acceptance-backtest.jsonl（獨立檔，不污染真實影子流）。

門檻（Q5 模擬版映射）：A fail ≤2/10、B fail ≥5/7、C fail =0/3、
A+B uncertain 率 ≤30%。

用法：
  python tools/codex-companion/backtest_acceptance.py            # 跑全部
  python tools/codex-companion/backtest_acceptance.py --resume   # 續跑缺的
  python tools/codex-companion/backtest_acceptance.py --only a4 b1
  python tools/codex-companion/backtest_acceptance.py --dry-run  # 只組案卷不打 codex
  python tools/codex-companion/backtest_acceptance.py --report   # 只重印統計
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SERVICE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVICE_DIR))

import acceptance  # noqa: E402
import assessor  # noqa: E402

CLAUDE_DIR = Path.home() / ".claude"
WORKFLOW_DIR = CLAUDE_DIR / "workflow"
CONFIG_PATH = WORKFLOW_DIR / "config.json"
OUT_PATH = WORKFLOW_DIR / "acceptance-backtest.jsonl"
REPO = CLAUDE_DIR  # 回放對象 = 本 repo 的 git 歷史
DONE_DIR = CLAUDE_DIR / ".claude" / "verify" / "done"

_write_lock = threading.Lock()


def _git(args: List[str]) -> str:
    r = subprocess.run(
        ["git", "-C", str(REPO)] + args,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    return r.stdout or ""


def _trace(edits: List[str], verifies: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    """合成 tool_trace：Edit 事件 + 驗證指令事件（格式同 companion state）。"""
    t: List[Dict[str, Any]] = [
        {"tool": "Edit", "path": p, "input": p, "output_summary": ""} for p in edits
    ]
    t += [
        {"tool": "Bash", "input": cmd, "output_summary": f"stdout: {out}"}
        for cmd, out in verifies
    ]
    return t


# ─── 案例定義（真值由構造保證） ──────────────────────────────────────────────
# spec: 內嵌文字，或 ("file", 路徑) 讀真規格檔。
# rng: git diff 範圍（單 commit 用 <c>^..<c>）。
# extra_required: B-miss 變異——追加到「必須發生」的未做項。
# strip_evidence: B-noevi 變異——trace 不含任何驗證指令但 tail 宣稱全綠。
# force_skip: C 變異——這些檔強制列入「未採樣清單」。

def _real_spec(name: str) -> Tuple[str, str]:
    return ("file", str(DONE_DIR / f"acceptance-{name}.md"))


CASES: List[Dict[str, Any]] = [
    # ── A 完好回放（期望 pass）─────────────────────────────────────────────
    dict(id="a1", group="A", expected="pass", rng="6ef3d01^..6ef3d01",
         spec=_real_spec("acceptance-spec-phase1"),
         goal="把任務「做完的定義」落成驗收規格工件 hook（分級啟動、小任務零打擾）",
         tail="完成：acceptance_spec hook 上線，實彈觸發多檔提醒→落規格檔→sidecar 抑制。verify 14 綠；hooks/verify 全套 953 綠 0 紅。",
         edits=["hooks/acceptance_spec.py", "workflow/config.json", "settings.json",
                ".gitignore", "hooks/verify/verify_acceptance_spec.py"],
         verifies=[("python -m pytest hooks/verify/verify_acceptance_spec.py -q",
                    "14 passed in 0.5s"),
                   ("python -m pytest hooks/verify -q", "953 passed in 24.1s")]),
    dict(id="a2", group="A", expected="pass", rng="d4f2b1d^..d4f2b1d",
         spec=_real_spec("codex-companion-input-integrity"),
         goal="系統性檢視協作 LLM 收到的輸入組成，根治 plan_review 100% 缺正文問題",
         tail="完成：輸入組成收斂單一模組 artifact_io + build_prompt 純函式，run_verify 1259 綠，smoke 以原事故檔真打 codex 通過。",
         edits=["tools/codex-companion/artifact_io.py", "tools/codex-companion/assessor.py",
                "tools/codex-companion/prompts.py", "tools/codex-companion/state.py",
                "hooks/codex_companion.py"],
         verifies=[("python run_verify.py", "1259 passed"),
                   ("python -m pytest tools/codex-companion/verify -q", "64 passed")]),
    dict(id="a3", group="A", expected="pass", rng="606d8c7..4395fa3",
         spec=_real_spec("pan-phase2-warn-landing-powershell-gate"),
         goal="PAN 預告閘門 Phase 2：warn 軟著陸 + PowerShell 納管",
         tail="完成：mode=warn + lenient_first_miss + continuation 豁免落地；PowerShell 納入閘門與唯讀白名單。run_verify 1231 綠。",
         edits=["hooks/handlers/pre_tool_use.py", "workflow/config.json", "settings.json",
                "hooks/verify/verify_pre_action_notice.py"],
         verifies=[("python run_verify.py", "1231 passed"),
                   ("python -m pytest hooks/verify/verify_pre_action_notice.py -q",
                    "50 passed"),
                   ("git ls-remote origin main", "4b62bf0c… refs/heads/main")]),
    dict(id="a4", group="A", expected="pass", rng="90fe509^..90fe509",
         spec="""## 必須發生
- run_verify.py 修輸出順序：檔案路徑清單在 pytest 輸出前 flush（不再被 pipe buffering 排到最後）
- 新增 --json 旗標：stdout 輸出純 JSON（頂層 summary + 每案 id/file/outcome/duration）
## 禁止發生
- 不動 hooks/verify 底下任何測試檔
## 驗證指令
- python run_verify.py --json""",
         goal="修 run_verify 吞輸出問題，並加 --json 結構化輸出供程式化讀取",
         tail="完成：輸出順序修復 + --json 落地，三路驗證通過（預設模式順序正確、--json 1231 案可解析、失敗路徑 exit code 正確）。",
         edits=["run_verify.py"],
         verifies=[("python run_verify.py --json", '{"summary": {"passed": 1231, "failed": 0}} …'),
                   ("python run_verify.py", "1231 passed")]),
    dict(id="a5", group="A", expected="pass", rng="beda202^..beda202",
         spec="""## 必須發生
- hooks/handlers/pre_tool_use.py 新增 PAN 預告閘門（observe 模式上線）：pan_validate_notice 純驗證器 + 每回合首次動手工具前檢查可見預告
- workflow/config.json 新增 pre_action_notice 設定段（mode 三態 observe/warn/deny）
- IDENTITY.md 補動手前預告常駐指示一行
- hooks/verify/verify_pre_action_notice.py 新測試全綠
## 禁止發生
- 不直接上 deny 模式（先 observe 收數據）
## 驗證指令
- python run_verify.py""",
         goal="技轉 Hermes 實作前預告閘門到 Claude Code hook（Phase 1 observe 上線）",
         tail="完成：PAN Phase 1 observe 模式上線，驗證器 + config + IDENTITY 指示齊備。run_verify 1218 綠（含 PAN 新 37 案）。",
         edits=["hooks/handlers/pre_tool_use.py", "workflow/config.json", "IDENTITY.md",
                "hooks/verify/verify_pre_action_notice.py"],
         verifies=[("python run_verify.py", "1218 passed")]),
    dict(id="a6", group="A", expected="pass", rng="0d6b6d0^..0d6b6d0",
         spec="""## 必須發生
- hooks/codex_companion.py 的 handoff 文件讀取改頭尾採樣（4500+1500）並附明確中段省略標記，根治 [:6000] 靜默截斷
- hooks/handlers/post_tool_use.py 的 staging 檔名閘改 next-phase 前綴判定（容多份計畫檔並存）
- tools/codex-companion/verify/ 新增採樣行為測試
## 禁止發生
- 不改 codex 審查模板本體
## 驗證指令
- python -m pytest tools/codex-companion/verify -q""",
         goal="根治 codex handoff 自檢把輸入靜默截斷導致連環誤報的問題",
         tail="完成：截斷改頭尾採樣+標記，staging 檔名閘改前綴判定。codex-companion 套件 50 綠。",
         edits=["hooks/codex_companion.py", "hooks/handlers/post_tool_use.py"],
         verifies=[("python -m pytest tools/codex-companion/verify -q", "50 passed")]),
    dict(id="a7", group="A", expected="pass", rng="373b0e4^..373b0e4",
         spec="""## 必須發生
- skills/continue/SKILL.md Step 3 補強：刪 handoff 檔後的首個輸出必須是白話複述「我認知到什麼、即將執行什麼」（非阻塞要求）
## 禁止發生
- 不改 /continue 其他步驟流程
## 驗證指令
- grep -n "白話複述" skills/continue/SKILL.md""",
         goal="強化 /continue 接手品質：刪檔後先白話複述認知再動工",
         tail="完成：SKILL.md Step 3 補回讀強化條款，grep 確認落檔。",
         edits=["skills/continue/SKILL.md"],
         verifies=[("grep -n \"複述\" skills/continue/SKILL.md", "42: 白話複述認知與即將執行工作")]),
    dict(id="a8", group="A", expected="pass", rng="2d0c95b^..2d0c95b",
         spec="""## 必須發生
- 跨 session 衝突預警 Stage 0+1：偵測同工作樹並發 session，同檔寫入時向雙方預警
- 新增設計文件 _AIDocs/DevHistory/session-coordination-bus.md
- .gitignore 收 sidecar 目錄；TECH.md / Architecture.md 同步收錄
- hooks/verify 新增對應測試
## 禁止發生
- 不引入常駐 daemon（檔案信號即可）
## 驗證指令
- python -m pytest hooks/verify -q""",
         goal="多個 Claude session 同時開在同一工作樹時，互相看得見對方在改什麼、同檔衝突要預警",
         tail="完成：衝突預警 Stage 0+1 落地（檔案信號、無 daemon），文件與測試同步。hooks/verify 全綠。",
         edits=["hooks/handlers/pre_tool_use.py", "hooks/handlers/_shared.py", ".gitignore",
                "_AIDocs/DevHistory/session-coordination-bus.md"],
         verifies=[("python -m pytest hooks/verify -q", "1181 passed")]),
    dict(id="a9", group="A", expected="pass", rng="8edcee2^..8edcee2",
         spec="""## 必須發生
- tools/memory-audit.py --enforce：atom 搬入 _distant/ 成功後同步刪除 _atom_index.json 對應 entry（不留 dangling）
- _AIDocs/_CHANGELOG.md 記錄本批次
## 禁止發生
- 不動 atom 檔案內容本身
## 驗證指令
- python -m json.tool memory/_atom_index.json""",
         goal="修 --enforce 只搬檔不清索引造成 dangling entry 的問題",
         tail="完成：--enforce 補索引同步刪除，合成樹功能測試 PASS，索引合法 JSON。",
         edits=["tools/memory-audit.py", "_AIDocs/_CHANGELOG.md"],
         verifies=[("python -m json.tool memory/_atom_index.json", "(valid JSON, no output errors)")]),
    dict(id="a10", group="A", expected="pass", rng="adfe94e^..adfe94e",
         spec="""## 必須發生
- skills/memory/SKILL.md 標註自動萃取管線已裁撤（peek/undo 僅查歷史殘留）
- hooks/wg_recall_miss.py 失念偵測補 resume 場景去重（同 atom 同 session 不重複記）
- hooks/verify/verify_recall_miss.py 補對應測試
## 禁止發生
- 不動失念偵測的觸發詞比對邏輯
## 驗證指令
- python -m pytest hooks/verify/verify_recall_miss.py -q""",
         goal="memory skill 文件與現況對齊 + 失念偵測 resume 重複記錄修正",
         tail="完成：SKILL.md 標註裁撤、resume 去重落地。verify_recall_miss 全綠。",
         edits=["skills/memory/SKILL.md", "hooks/wg_recall_miss.py",
                "hooks/verify/verify_recall_miss.py"],
         verifies=[("python -m pytest hooks/verify/verify_recall_miss.py -q", "14 passed")]),
    # ── B 種缺陷（期望 fail）───────────────────────────────────────────────
    dict(id="b1", group="B", expected="fail", base="a4",
         extra_required="run_verify.py 新增 --junitxml <path> 輸出選項（CI 整合用）"),
    dict(id="b2", group="B", expected="fail", base="a6",
         extra_required="hooks/wg_handoff.py 的 handoff 檔讀取同步改用頭尾採樣"),
    dict(id="b3", group="B", expected="fail", base="a5",
         extra_required="PAN 閘門上線即以 deny 模式強制阻擋未預告的動手工具"),
    dict(id="b4", group="B", expected="fail", base="a8",
         extra_required="偵測到同檔寫入衝突時發送 Windows toast 桌面通知"),
    dict(id="b5", group="B", expected="fail", base="a4", strip_evidence=True,
         tail="完成：輸出順序修復 + --json 落地，三路驗證全部通過、1231 案全綠，品質無虞。"),
    dict(id="b6", group="B", expected="fail", base="a1", strip_evidence=True,
         tail="完成：acceptance_spec hook 上線並全流程驗證，verify 14 綠 + hooks 全套 953 綠 0 紅。"),
    dict(id="b7", group="B", expected="fail", base="a3", strip_evidence=True,
         tail="完成：PAN Phase 2 + PowerShell 閘門落地，run_verify 1231 綠，live 實測 warn 模式動作正常。"),
    # ── C 截斷紀律（期望 ≠fail；理想 uncertain）─────────────────────────────
    dict(id="c1", group="C", expected="uncertain", base="a4",
         force_skip=["run_verify.py"]),
    dict(id="c2", group="C", expected="uncertain", base="a6",
         force_skip=["hooks/codex_companion.py"]),
    dict(id="c3", group="C", expected="uncertain", base="a10",
         force_skip=["hooks/wg_recall_miss.py"]),
]

_BY_ID = {c["id"]: c for c in CASES}


def _resolve(case: Dict[str, Any]) -> Dict[str, Any]:
    """B/C 案例繼承 base 案例欄位後套變異。"""
    if "base" not in case:
        return dict(case)
    merged = dict(_BY_ID[case["base"]])
    merged.update({k: v for k, v in case.items() if v is not None})
    merged["id"], merged["group"], merged["expected"] = (
        case["id"], case["group"], case["expected"])
    return merged


def _spec_text(case: Dict[str, Any]) -> str:
    spec = case["spec"]
    if isinstance(spec, tuple) and spec[0] == "file":
        text = Path(spec[1]).read_text(encoding="utf-8-sig")
    else:
        text = str(spec)
    extra = case.get("extra_required")
    if extra:
        # 追加到「必須發生」段尾（下一個 ## 前）
        marker = "## 禁止發生"
        if marker in text:
            text = text.replace(marker, f"- {extra}\n{marker}", 1)
        else:
            text += f"\n- {extra}"
    return text


def build_case(case: Dict[str, Any]) -> Dict[str, Any]:
    """組單一案例的 run_assessment 輸入（不打 codex）。"""
    c = _resolve(case)
    rng = c["rng"]
    stat = _git(["diff", rng, "--stat"])
    diff = _git(["diff", rng])
    digest, truncated = acceptance.build_diff_digest_from_text(
        stat, diff, force_skip_files=c.get("force_skip"))

    spec_dir = Path(tempfile.gettempdir()) / "acceptance-backtest-specs"
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = spec_dir / f"acceptance-bt-{c['id']}.md"
    fm = (f"---\ntask_slug: bt-{c['id']}\nsession_id: backtest\n"
          f"created_at: 2026-08-06\nsource: plan\nstatus: open\n---\n")
    body = _spec_text(c)
    if not body.lstrip().startswith("---"):
        body = fm + body
    spec_path.write_text(body, encoding="utf-8", newline="\n")

    trace = _trace(c.get("edits", []),
                   [] if c.get("strip_evidence") else c.get("verifies", []))
    extra_context = {
        "spec_path": str(spec_path),
        "binding": "bound",
        "binding_reason": "",
        "trigger": "backtest",
        "turn_index": 1,
        "user_goal": c["goal"],
        "last_assistant_tail": c["tail"],
        "diff_digest": digest,
    }
    return {"case": c, "trace": trace, "extra_context": extra_context,
            "diff_truncated": truncated}


def _match(group: str, verdict: str) -> bool:
    if group == "A":
        return verdict == "pass"
    if group == "B":
        return verdict == "fail"
    return verdict != "fail"  # C：不憑缺席判 fail 即守紀律


def run_case(case: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    built = build_case(case)
    c = built["case"]
    t0 = time.time()
    result = assessor.run_assessment(
        "acceptance_review", "backtest", built["trace"], str(REPO),
        built["extra_context"], config,
    )
    verdict = str(result.get("verdict", ""))
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "case_id": c["id"], "group": c["group"], "expected": c["expected"],
        "verdict": verdict, "match": _match(c["group"], verdict),
        "score": result.get("score", -1),
        "severity": result.get("severity", ""),
        "confidence": result.get("confidence", ""),
        "summary": result.get("summary", ""),
        "problems": (result.get("problems") or [])[:5],
        "uncertain_reason": result.get("uncertain_reason", ""),
        "prompt_chars": result.get("_prompt_chars", 0),
        "attempts": result.get("_attempts", 1),
        "elapsed_s": round(time.time() - t0, 1),
    }
    with _write_lock:
        with open(OUT_PATH, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _read_results() -> Dict[str, Dict[str, Any]]:
    """讀既有結果（同 case 取最新一筆）。"""
    out: Dict[str, Dict[str, Any]] = {}
    try:
        for line in OUT_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("case_id"):
                out[r["case_id"]] = r
    except OSError:
        pass
    return out


def report(results: Dict[str, Dict[str, Any]]) -> str:
    lines = [f"{'case':<5} {'grp':<3} {'expected':<10} {'verdict':<10} "
             f"{'match':<5} {'sev':<7} {'t(s)':>5}  summary"]
    for c in CASES:
        r = results.get(c["id"])
        if not r:
            lines.append(f"{c['id']:<5} {c['group']:<3} {c['expected']:<10} "
                         f"{'-':<10} {'-':<5} {'-':<7} {'-':>5}  (未跑)")
            continue
        lines.append(
            f"{r['case_id']:<5} {r['group']:<3} {r['expected']:<10} "
            f"{r['verdict']:<10} {'✓' if r['match'] else '✗':<5} "
            f"{r.get('severity', ''):<7} {r.get('elapsed_s', 0):>5}  "
            f"{r.get('summary', '')[:60]}"
        )

    done = [results[c["id"]] for c in CASES if c["id"] in results]
    a = [r for r in done if r["group"] == "A"]
    b = [r for r in done if r["group"] == "B"]
    cg = [r for r in done if r["group"] == "C"]
    a_fail = sum(1 for r in a if r["verdict"] == "fail")
    b_fail = sum(1 for r in b if r["verdict"] == "fail")
    c_fail = sum(1 for r in cg if r["verdict"] == "fail")
    ab = a + b
    ab_unc = sum(1 for r in ab if r["verdict"] == "uncertain")
    unc_rate = (ab_unc / len(ab)) if ab else 0.0

    gates = [
        ("A 誤報（fail ≤2/10）", f"{a_fail}/{len(a)}", a_fail <= 2 and len(a) == 10),
        ("B 抓取（fail ≥5/7）", f"{b_fail}/{len(b)}", b_fail >= 5 and len(b) == 7),
        ("C 紀律（fail =0/3）", f"{c_fail}/{len(cg)}", c_fail == 0 and len(cg) == 3),
        ("A+B uncertain ≤30%", f"{unc_rate:.0%}", unc_rate <= 0.30 and len(ab) == 17),
    ]
    lines.append("")
    lines.append("── Q5 模擬門檻 ──")
    all_pass = True
    for name, val, ok in gates:
        all_pass = all_pass and ok
        lines.append(f"  [{'PASS' if ok else 'FAIL'}] {name}: {val}")
    lines.append(f"  總判定: {'✅ 全過 → 可續 Phase 3' if all_pass else '❌ 未過 → 根因分析'}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true", help="跳過已有結果的案例")
    ap.add_argument("--only", nargs="*", help="只跑指定 case id")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true", help="只組案卷印統計，不打 codex")
    ap.add_argument("--report", action="store_true", help="只重印既有結果統計")
    args = ap.parse_args()

    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")

    if args.report:
        print(report(_read_results()))
        return 0

    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["codex_companion"]
    except (OSError, json.JSONDecodeError, KeyError) as e:
        print(f"config 讀取失敗: {e}", file=sys.stderr)
        return 1

    todo = [c for c in CASES
            if (not args.only or c["id"] in args.only)]
    if args.resume:
        have = _read_results()
        todo = [c for c in todo if c["id"] not in have]

    if args.dry_run:
        for c in todo:
            built = build_case(c)
            prompt = assessor.build_prompt_budgeted(
                "acceptance_review", built["trace"], str(REPO),
                built["extra_context"], config)
            print(f"{c['id']}: prompt {len(prompt)} chars, "
                  f"digest_truncated={built['diff_truncated']}")
        return 0

    print(f"回測 {len(todo)} 案例，{args.workers} workers（真 codex，每案 ~60-120s）…")
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_case, c, config): c["id"] for c in todo}
        for fut in as_completed(futs):
            cid = futs[fut]
            try:
                r = fut.result()
                print(f"  [{cid}] {r['verdict']} "
                      f"({'✓' if r['match'] else '✗ expected ' + r['expected']}) "
                      f"{r['elapsed_s']}s")
            except Exception as e:
                print(f"  [{cid}] ERROR: {e}", file=sys.stderr)

    print()
    print(report(_read_results()))
    return 0


if __name__ == "__main__":
    sys.exit(main())

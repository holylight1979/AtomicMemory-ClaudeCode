"""probe_move_dir.py — 規則 MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE 的真 hook 入口探針（hooks/workflow-guardian.py 吃造好的事件 JSON）。

做什麼：沿用 probe_release_rules.py 的沙箱，在假專案裡真的把 lib/pkg（含 .py）搬到 src/pkg，送 Bash 事件：
  M1 搬完直接收尾 → Stop 寫碼查核擋，訊息含規則名與兩張缺的收據名
  M2 跑 tools/move-dir-check.py scan（hits=0）與 sample --for（PASS）後再收尾 → 不再因這條擋
  M3 子代理搬、自己跑收據 → SubagentStop 先擋後過，主 session 收尾也認得
  M4 搬了又搬回原處 → 收尾不因這條擋
不是 pytest 案例（檔名不以 verify_／test_ 開頭）；pytest 案例在 verify_release_rules.py。

怎麼跑：python -X utf8 hooks/verify/probe_move_dir.py --tree <受測樹> [--keep]
尾行：MOVE_DIR_PROBE_CHECK PASS|FAIL（檢查點全對才 PASS）。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_release_rules import TEXT_DONE, Sandbox, Session, reason_of  # noqa: E402

RULE = "MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE"


def run(tree: Path, base: Path) -> list:
    sb = Sandbox(tree, base, "m1")
    proj = sb.project("proj")
    (proj / "lib" / "pkg").mkdir(parents=True)
    (proj / "lib" / "pkg" / "a.py").write_text("X = 1\n", encoding="utf-8")
    (proj / "src").mkdir()
    (proj / "src" / "README.txt").write_text("src\n", encoding="utf-8")
    s = Session(sb, proj)
    s.session_start()
    s.prompt("把 lib/pkg 搬到 src/pkg")
    s.read(proj / "src" / "README.txt")                  # OverviewHub：沒部位表的專案改 src 前要先讀過 src 的檔（另一道閘）
    shutil.move(str(proj / "lib" / "pkg"), str(proj / "src" / "pkg"))
    s.bash("mv lib/pkg src/pkg")
    first = reason_of(s.stop(TEXT_DONE))
    rows = [("M1 搬完直接收尾被這條擋", RULE in first, True),
            ("M1 訊息列兩張缺的收據", "MOVE_PATH_SCAN" in first and "MOVE_SAMPLE_CHECK" in first, True)]
    tool = tree / "tools" / "move-dir-check.py"
    for args in (["scan", "--old", "lib/pkg", "--new", "src/pkg"],
                 ["sample", "--for", "src/pkg", "--run", f'"{sys.executable}" -c "import sys"']):
        r = subprocess.run([sys.executable, "-X", "utf8", str(tool), *args], cwd=str(proj), capture_output=True, text=True,
                           encoding="utf-8")
        shown = " ".join(a if " " not in a else f"'{a}'" for a in args)
        s.bash(f'python "{tool.as_posix()}" {shown}', stdout=r.stdout, exit_code=r.returncode)
    second = reason_of(s.stop(TEXT_DONE))
    rows.append(("M2 兩張收據都有之後不再因這條擋", RULE in second, False))
    return rows + _subagent_rows(tree, base) + _move_back_rows(tree, base)


def _sandbox(tree: Path, base: Path, name: str) -> tuple:
    sb = Sandbox(tree, base, name)
    proj = sb.project("proj")
    (proj / "lib" / "pkg").mkdir(parents=True)
    (proj / "lib" / "pkg" / "a.py").write_text("X = 1\n", encoding="utf-8")
    (proj / "lib" / "README.txt").write_text("lib\n", encoding="utf-8")
    (proj / "src").mkdir()
    (proj / "src" / "README.txt").write_text("src\n", encoding="utf-8")
    s = Session(sb, proj)
    s.session_start()
    s.prompt("把 lib/pkg 搬到 src/pkg")
    s.read(proj / "src" / "README.txt")                  # OverviewHub：沒部位表的專案改 src、lib 前要先讀過同頂層的檔
    s.read(proj / "lib" / "README.txt")
    return sb, proj, s


def _agent_bash(s: Session, cmd: str, stdout: str, agent: str = "a1") -> None:
    s.hook({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_use_id": s._id(), "tool_input": {"command": cmd},
            "tool_response": {"stdout": stdout, "stderr": "", "interrupted": False}, "agent_id": agent,
            "agent_type": "general-purpose"}, f"PostToolUse(agent) `{cmd[:60]}`")


def _subagent_rows(tree: Path, base: Path) -> list:
    """M3：子代理搬目錄、自己跑 scan／sample（收據在子代理鍵下）：子代理收尾先被擋、跑完收據後過；主 session 收尾也過。"""
    sb, proj, s = _sandbox(tree, base, "m3")
    shutil.move(str(proj / "lib" / "pkg"), str(proj / "src" / "pkg"))
    _agent_bash(s, "mv lib/pkg src/pkg", "")
    agent_tp = sb.dir / "agent.jsonl"
    agent_tp.write_text("", encoding="utf-8")
    sub_stop = {"hook_event_name": "SubagentStop", "agent_id": "a1", "agent_type": "general-purpose",
                "agent_transcript_path": str(agent_tp), "stop_hook_active": False, "last_assistant_message": TEXT_DONE}
    rows = [("M3 子代理搬完直接收尾被這條擋", RULE in reason_of(s.hook(dict(sub_stop), "SubagentStop")), True)]
    tool = tree / "tools" / "move-dir-check.py"
    for args in (["scan", "--old", "lib/pkg", "--new", "src/pkg"],
                 ["sample", "--for", "src/pkg", "--run", f'"{sys.executable}" -c "import sys"']):
        r = subprocess.run([sys.executable, "-X", "utf8", str(tool), *args], cwd=str(proj), capture_output=True, text=True,
                           encoding="utf-8")
        shown = " ".join(a if " " not in a else f"'{a}'" for a in args)
        _agent_bash(s, f'python "{tool.as_posix()}" {shown}', r.stdout)
    rows.append(("M3 子代理跑完收據後收尾不再因這條擋", RULE in reason_of(s.hook(dict(sub_stop), "SubagentStop")), False))
    rows.append(("M3 主 session 收尾也認子代理的收據", RULE in reason_of(s.stop(TEXT_DONE)), False))
    return rows


def _move_back_rows(tree: Path, base: Path) -> list:
    """M4：搬了又搬回原處 → 收尾不因這條擋（中間位置不存在，不能要求它的收據）。"""
    sb, proj, s = _sandbox(tree, base, "m4")
    shutil.move(str(proj / "lib" / "pkg"), str(proj / "src" / "pkg"))
    s.bash("mv lib/pkg src/pkg")
    shutil.move(str(proj / "src" / "pkg"), str(proj / "lib" / "pkg"))
    s.bash("mv src/pkg lib/pkg")
    return [("M4 搬了又搬回原處收尾不因這條擋", RULE in reason_of(s.stop(TEXT_DONE)), False)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tree", required=True, help="受測樹（含 hooks/workflow-guardian.py 與 tools/move-dir-check.py）")
    ap.add_argument("--keep", action="store_true", help="留下沙箱目錄")
    a = ap.parse_args()
    base = Path(tempfile.mkdtemp(prefix="probe-move-"))
    try:
        rows = run(Path(a.tree).resolve(), base)
    finally:
        if not a.keep:
            shutil.rmtree(base, ignore_errors=True)
    ok = all(actual == want for _, actual, want in rows)
    for what, actual, want in rows:
        print(f"{'OK ' if actual == want else 'BAD'} {what}：實際 {actual}／預期 {want}")
    print(f"MOVE_DIR_PROBE_CHECK {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

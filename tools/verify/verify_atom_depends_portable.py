"""verify_atom_depends_portable.py：tools/atom-depends-portable.py 的四條對應規則與預覽輸出。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_atom_depends_portable.py
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))
TOOL = CLAUDE_DIR / "tools" / "atom-depends-portable.py"


def _load():
    spec = importlib.util.spec_from_file_location("atom_depends_portable", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ADP = _load()


def _world(tmp_path: Path):
    """本機：資料根 claude/、專案根 proj/（裡面有 Tools/CodeReview/src/cli.js、_workspace/modules.json、Client/x.cs）。"""
    claude = tmp_path / "claude"
    (claude / "tools").mkdir(parents=True)
    (claude / "tools" / "t.py").write_text("1", encoding="utf-8")
    proj = tmp_path / "proj"
    for rel in ("Tools/CodeReview/src/cli.js", "_workspace/modules.json", "Client/x.cs"):
        f = proj / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("1", encoding="utf-8")
    return claude, proj


def test_r1_under_claude_dir(tmp_path):
    claude, proj = _world(tmp_path)
    assert ADP.map_abs_path(str(claude / "tools" / "t.py"), claude, proj) == ("~/.claude/tools/t.py", "R1")


def test_r2_under_project_root_and_exists(tmp_path):
    claude, proj = _world(tmp_path)
    assert ADP.map_abs_path(str(proj / "Client" / "x.cs"), claude, proj) == ("Client/x.cs", "R2")


def test_r3_other_machine_root_takes_longest_existing_tail(tmp_path):
    """別台電腦的根（C:/Projects/TSLG/Develop/…）與舊配置多一層（<proj>/Develop/…）都剝到本機存在的最長尾段。"""
    claude, proj = _world(tmp_path)
    other = "C:/Projects/TSLG/Develop/Tools/CodeReview/src/cli.js" if sys.platform == "win32" \
        else "/Projects/TSLG/Develop/Tools/CodeReview/src/cli.js"
    assert ADP.map_abs_path(other, claude, proj) == ("Tools/CodeReview/src/cli.js", "R3")
    assert ADP.map_abs_path(str(proj / "Develop" / "_workspace" / "modules.json"), claude, proj) == ("_workspace/modules.json", "R3")


def test_r4_under_root_but_missing_becomes_relative_and_foreign_stays_unmapped(tmp_path):
    claude, proj = _world(tmp_path)
    assert ADP.map_abs_path(str(proj / "Client" / "gone.cs"), claude, proj) == ("Client/gone.cs", "R4")
    foreign = "C:/OlgCase/TSLG/Dev/Client/nowhere.py" if sys.platform == "win32" else "/OlgCase/TSLG/Dev/Client/nowhere.py"
    assert ADP.map_abs_path(foreign, claude, proj) == (None, "R4-unmapped")


def test_rewrite_line_keeps_relative_and_tilde_entries_and_reports_unmapped(tmp_path):
    """已是相對或 ~/ 的條目不動；無法對應的原樣保留並回報；非 path 型條目原樣。"""
    claude, proj = _world(tmp_path)
    foreign = "C:/OlgCase/x.py" if sys.platform == "win32" else "/OlgCase/x.py"
    line = f"- Depends: path:Client/x.cs, path:~/.claude/tools/t.py, path:{proj / 'Client' / 'x.cs'}, path:{foreign}, decision:abc"
    new, notes, unmapped = ADP.rewrite_line(line, claude, proj)
    assert new == f"- Depends: path:Client/x.cs, path:~/.claude/tools/t.py, path:Client/x.cs, path:{foreign}, decision:abc"
    assert len(notes) == 1 and notes[0].startswith("[R2]")
    assert unmapped == [foreign]
    assert ADP.rewrite_line("- Trigger: a, b", claude, proj) == ("- Trigger: a, b", [], [])


def test_cli_preview_lists_rules_and_unmapped_and_does_not_write(tmp_path):
    claude, proj = _world(tmp_path)
    mem = proj / ".claude" / "memory" / "shared"
    mem.mkdir(parents=True)
    foreign = "C:/OlgCase/x.py" if sys.platform == "win32" else "/OlgCase/x.py"
    card = mem / "c.md"
    body = f"# c\n\n- Depends: path:{proj / 'Client' / 'x.cs'}, path:{foreign}\n"
    card.write_text(body, encoding="utf-8")
    r = subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "--memory-dir", str(proj / ".claude" / "memory"),
                        "--claude-dir", str(claude)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert "[R2]" in r.stdout and "無法對應" in r.stdout and foreign in r.stdout
    assert r.stdout.rstrip().splitlines()[-1] == "ATOM_DEPENDS_PORTABLE DONE scanned=1 changed=1 unmapped=1 applied=0"
    assert card.read_text(encoding="utf-8") == body
    r2 = subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "--memory-dir", str(proj / ".claude" / "memory"),
                         "--claude-dir", str(claude), "--apply"], capture_output=True, text=True, encoding="utf-8")
    assert r2.returncode == 0 and "- Depends: path:Client/x.cs, path:" + foreign in card.read_text(encoding="utf-8")
